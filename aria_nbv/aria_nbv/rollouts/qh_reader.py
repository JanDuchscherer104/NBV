"""Lazy storage reader for complete finite-candidate ``Q_H`` rollout chains.

Corpus admission indexes and validates every complete, non-empty persisted
chain. Worker processes reopen Zarr handles and read only bounded state rows
and contiguous candidate slices. Tensor conversion, VIN composition, padding,
and the public five-DTO interface belong to :mod:`aria_nbv.data_handling.qh`.
"""

from __future__ import annotations

import json
import os
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import zarr
from pydantic import Field, field_validator
from zarr.storage import LocalStore

from ..targets.protocol import ORACLE_GT_TARGET_SOURCE, TargetInputProtocol, validate_target_protocol_admission
from ..utils import Stage, TargetConfig
from .manifest import (
    ROLLOUT_MANIFEST_FILENAME,
    ROLLOUT_MANIFEST_VERSION,
    manifest_sha256,
    read_rollout_store_manifest,
)
from .zarr_store import (
    DEFAULT_RETURN_SEMANTICS,
    Q_H_REWARD_METRIC,
    Q_H_TD_SEMANTICS,
    ROLLOUT_ZARR_SCHEMA_VERSION,
)


@dataclass(frozen=True, slots=True)
class _QhSourceLineage:
    """Compact immutable source facts admitted during rollout preflight."""

    source_row_id: int
    source_sample_index: int
    source_sample_key: str
    source_shard_id: str
    source_shard_row: int
    scene_id: str
    snippet_id: str
    split: Stage
    source_cache_version: str
    source_offline_store_manifest_hash: str
    split_manifest_hash: str


@dataclass(frozen=True, slots=True)
class _StoredChain:
    """One decoded chain of storage facts before tensor/VIN composition."""

    root_pose_world: np.ndarray
    target_extents: np.ndarray
    target_pose_world_object: np.ndarray
    candidate_pose_relative_root: tuple[np.ndarray, ...]
    candidate_position_id: tuple[np.ndarray, ...]
    actor_action_mask: tuple[np.ndarray, ...]
    remaining_budget: np.ndarray
    candidate_row_id: tuple[np.ndarray, ...]
    q_train_mask: tuple[np.ndarray, ...]
    invalid_reason_bitset: tuple[np.ndarray, ...]
    one_step_target_rri: tuple[np.ndarray, ...]
    one_step_target_root_gain: tuple[np.ndarray, ...]
    selected_candidate_index: np.ndarray
    discount: np.ndarray
    terminal: np.ndarray
    lineage: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class _ChainIndexEntry:
    rollout_position: int
    rollout_row_id: int
    state_start: int
    state_stop: int
    step_row_ids: tuple[int, ...]


class QhRolloutReaderConfig(TargetConfig["QhRolloutReader"]):
    """Validate and construct a homogeneous V0 rollout-reader corpus."""

    store_dirs: tuple[Path, ...] = Field(min_length=1)
    """Completed production rollout stores in deterministic corpus order."""

    @field_validator("store_dirs", mode="before")
    @classmethod
    def _resolve_store_dirs(cls, value: Any) -> tuple[Path, ...]:
        paths = tuple(Path(path).expanduser().resolve() for path in value)
        if len(set(paths)) != len(paths):
            raise ValueError("Q_H rollout store paths must be unique.")
        return paths

    @property
    def target_type(self) -> type[QhRolloutReader]:
        """Runtime reader constructed by :meth:`setup_target`."""

        return QhRolloutReader


@dataclass(frozen=True, slots=True)
class _StoreMetadata:
    path: Path
    manifest_hash: str
    state_count: int
    chains: tuple[_ChainIndexEntry, ...]
    dictionaries: dict[str, tuple[str, ...]]
    compatibility: tuple[tuple[str, object], ...]
    source_lineage: tuple[_QhSourceLineage, ...]
    scene_ids: frozenset[str]


class QhRolloutReader:
    """Read a homogeneous corpus through a small, lazy state interface.

    Construction preflights manifests, schemas, tensor shapes, provenance, and
    cross-store compatibility. :meth:`read` then performs bounded row/slice
    access, while :meth:`__getstate__` prevents process-owned Zarr handles from
    crossing PyTorch DataLoader worker boundaries.
    """

    _COMPATIBILITY_ROOT_ATTRS: ClassVar[tuple[str, ...]] = (
        "schema_version",
        "reason_code_version",
        "target_protocol_version",
        "return_semantics",
        "discount_gamma",
        "source_offline_store_version",
        "split_manifest_hash",
        "source_split",
        "q_h_horizon",
    )

    def __init__(self, config: QhRolloutReaderConfig) -> None:
        self.config = config
        self._stores = tuple(_preflight_store(path) for path in config.store_dirs)
        _validate_homogeneous(self._stores)
        chain_prefix_ends: list[int] = []
        chain_total = 0
        for store in self._stores:
            chain_total += len(store.chains)
            chain_prefix_ends.append(chain_total)
        self._chain_prefix_ends = tuple(chain_prefix_ends)
        self._source_lineage = tuple(dict.fromkeys(source for store in self._stores for source in store.source_lineage))
        self._scene_ids = frozenset(scene for store in self._stores for scene in store.scene_ids)
        self._open_pid: int | None = None
        self._roots: dict[int, zarr.Group] = {}

    def __len__(self) -> int:
        """Return the number of complete non-empty persisted chains."""

        return self._chain_prefix_ends[-1]

    def __getitem__(self, index: int) -> _StoredChain:
        """Decode one validated chain through bounded Zarr slices."""
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(f"Q_H chain index {index} is outside corpus length {len(self)}.")
        store_index = bisect_right(self._chain_prefix_ends, index)
        previous_end = 0 if store_index == 0 else self._chain_prefix_ends[store_index - 1]
        store = self._stores[store_index]
        return _read_chain(self._root(store_index), store, store.chains[index - previous_end])

    @property
    def source_lineage(self) -> tuple[_QhSourceLineage, ...]:
        """Return compact source rows validated without reading state payloads."""

        return self._source_lineage

    @property
    def scene_ids(self) -> frozenset[str]:
        """Return scenes referenced by states using preflighted 1D joins."""

        return self._scene_ids

    @property
    def q_h_horizon(self) -> int:
        """Return the validated corpus-wide padded ``Q_H`` horizon.

        This is the maximum realized rollout horizon admitted during reader
        preflight, as required by the persisted ``q_h_horizon`` compatibility
        contract. Reading it does not open a Zarr store or materialize a state.
        """

        return int(dict(self._stores[0].compatibility)["q_h_horizon"])

    @property
    def provenance(self) -> dict[str, object]:
        """Return preflighted corpus identity without reopening Zarr stores.

        The result contains only store-level facts already decoded during
        construction. It is JSON serializable and never materializes a rollout
        state, candidate matrix, or actor observation.
        """

        return {
            "stores": [
                {
                    "path": str(store.path),
                    "manifest_sha256": store.manifest_hash,
                    "state_count": store.state_count,
                }
                for store in self._stores
            ],
            "compatibility": dict(self._stores[0].compatibility),
        }

    def __getstate__(self) -> dict[str, Any]:
        """Drop process-owned Zarr handles before worker pickling."""

        state = self.__dict__.copy()
        state["_open_pid"] = None
        state["_roots"] = {}
        return state

    def _root(self, store_index: int) -> zarr.Group:
        pid = os.getpid()
        if self._open_pid != pid:
            self._open_pid = pid
            self._roots = {}
        root = self._roots.get(store_index)
        if root is None:
            root = zarr.open_group(
                store=LocalStore(str(self._stores[store_index].path), read_only=True),
                mode="r",
            )
            self._roots[store_index] = root
        return root


_Q_H_VECTOR_NAMES = (
    "state_step_row_id",
    "source_row_id",
    "target_row_id",
    "selected_candidate_index",
    "td_selected_candidate_row_id",
    "td_reward",
    "td_reward_target_rri",
    "td_next_step_row_id",
    "td_terminal_mask",
    "td_discount",
)
_Q_H_MATRIX_NAMES = (
    "candidate_row_id",
    "valid_action_mask",
    "q_train_mask",
    "position_id",
    "one_step_target_rri",
    "one_step_target_root_gain",
    "invalid_reason_bitset",
)
_STEP_VECTOR_NAMES = (
    "step_row_id",
    "rollout_row_id",
    "step_index",
    "selected_candidate_row_id",
    "num_candidates",
)
_CANDIDATE_VECTOR_NAMES = (
    "candidate_row_id",
    "step_row_id",
    "actor_action_mask",
    "q_train_mask",
    "position_id",
    "invalid_reason_bitset",
    "target_rri",
    "target_root_gain",
)
_ROLLOUT_VECTOR_NAMES = (
    "rollout_row_id",
    "rollout_id",
    "chain_id",
    "source_row_id",
    "target_row_id",
    "horizon",
    "root_time_ns",
    "root_trajectory_index",
    "root_frame_index",
    "policy_id",
    "branch_factor",
    "beam_width",
    "temperature",
    "random_seed",
    "termination_reason",
)
_TARGET_VECTOR_NAMES = (
    "target_row_id",
    "target_source_id",
    "target_sem_id",
    "target_inst_id",
)
_SOURCE_VECTOR_NAMES = (
    "source_row_id",
    "sample_index",
    "sample_key_id",
    "scene_id",
    "snippet_id",
    "split_id",
    "source_cache_version_id",
    "source_offline_store_manifest_hash_id",
    "split_manifest_hash_id",
    "source_shard_id",
    "source_shard_row",
)
_LINEAGE_VECTOR_NAMES = (
    "rollout_row_id",
    "candidate_config_id",
    "oracle_config_id",
    "rollout_config_id",
    "model_checkpoint_id",
    "mesh_version_id",
    "branch_schedule_id",
    "target_protocol_version_id",
    "target_crop_policy_id",
    "reason_code_version_id",
    "selection_rng_state_hash_id",
)


def _preflight_store(path: Path) -> _StoreMetadata:
    if not path.is_dir():
        raise ValueError(f"Q_H rollout store does not exist: {path}.")
    root = zarr.open_group(store=LocalStore(str(path), read_only=True), mode="r")
    _validate_manifest(root, path)
    _validate_root_contract(root, path)
    target_source = _admitted_target_source(root)
    protocol = validate_target_protocol_admission(
        root.attrs.get("target_protocol_version", ""),
        target_source=target_source,
    )
    if protocol is not TargetInputProtocol.V0_GT_INPUT:
        raise ValueError("Q_H rollout reader materializes only canonical v0_gt_input corpora.")

    q_h = root["q_h"]
    if q_h.attrs.get("td_semantics") != Q_H_TD_SEMANTICS:
        raise ValueError(f"Q_H store {path} must use {Q_H_TD_SEMANTICS!r} TD semantics.")
    if q_h.attrs.get("reward_metric") != Q_H_REWARD_METRIC:
        raise ValueError(f"Q_H store {path} must use {Q_H_REWARD_METRIC!r} rewards.")
    if q_h.attrs.get("return_semantics") != root.attrs.get("return_semantics"):
        raise ValueError(f"Q_H store {path} has inconsistent root and q_h return semantics.")
    if float(q_h.attrs.get("discount_gamma", float("nan"))) != float(root.attrs["discount_gamma"]):
        raise ValueError(f"Q_H store {path} has inconsistent root and q_h discounts.")

    state_count = int(root["q_h/state_step_row_id"].shape[0])
    if state_count < 1:
        raise ValueError(f"Q_H rollout store contains no states: {path}.")
    _validate_shapes(
        root,
        state_count=state_count,
        candidate_count=int(root["candidates/candidate_row_id"].shape[0]),
        rollout_count=int(root["rollouts/rollout_row_id"].shape[0]),
        target_count=int(root["targets/target_row_id"].shape[0]),
        source_count=int(root["sources/source_row_id"].shape[0]),
        max_candidates=int(q_h.attrs.get("max_candidates", -1)),
    )

    dictionaries = {
        name: _decode_dictionary(root, name)
        for name in (
            "config",
            "rollout",
            "scene",
            "snippet",
            "source_key",
            "source_shard",
            "split",
            "target_source",
            "policy",
            "termination_reason",
        )
    }
    source_lineage = _read_source_lineage(root, path, dictionaries)
    _validate_lineage_provenance(root, path, dictionaries)
    chains = _build_chain_index(root, path)
    state_scene_ids = frozenset(source.scene_id for source in source_lineage)
    compatibility = tuple((name, root.attrs.get(name)) for name in QhRolloutReader._COMPATIBILITY_ROOT_ATTRS) + (
        ("td_semantics", q_h.attrs.get("td_semantics")),
        ("reward_metric", q_h.attrs.get("reward_metric")),
        ("candidate_config_hashes", _config_hashes(root, dictionaries, "lineage/candidate_config_id")),
        ("oracle_config_hashes", _config_hashes(root, dictionaries, "lineage/oracle_config_id")),
        ("rollout_config_hashes", _config_hashes(root, dictionaries, "lineage/rollout_config_id")),
    )
    return _StoreMetadata(
        path=path,
        manifest_hash=str(root.attrs["manifest_sha256"]),
        state_count=state_count,
        chains=chains,
        dictionaries=dictionaries,
        compatibility=compatibility,
        source_lineage=source_lineage,
        scene_ids=state_scene_ids,
    )


def _read_source_lineage(
    root: zarr.Group,
    path: Path,
    dictionaries: dict[str, tuple[str, ...]],
) -> tuple[_QhSourceLineage, ...]:
    """Decode bounded source-table vectors and validate their split provenance."""

    sources = root["sources"]
    source_ids = np.asarray(sources["source_row_id"], dtype=np.int64).reshape(-1)
    if source_ids.size == 0 or np.any(source_ids[1:] <= source_ids[:-1]):
        raise ValueError(f"Q_H store {path} requires sorted unique immutable source ids.")
    rows = tuple(
        _QhSourceLineage(
            source_row_id=int(source_id),
            source_sample_index=int(sources["sample_index"][row]),
            source_sample_key=_decode_id(root, dictionaries, "source_key", "sources/sample_key_id", row),
            source_shard_id=_decode_id(root, dictionaries, "source_shard", "sources/source_shard_id", row),
            source_shard_row=int(sources["source_shard_row"][row]),
            scene_id=_decode_id(root, dictionaries, "scene", "sources/scene_id", row),
            snippet_id=_decode_id(root, dictionaries, "snippet", "sources/snippet_id", row),
            split=Stage.from_str(_decode_id(root, dictionaries, "split", "sources/split_id", row)),
            source_cache_version=_decode_id(
                root,
                dictionaries,
                "config",
                "sources/source_cache_version_id",
                row,
            ),
            source_offline_store_manifest_hash=_decode_id(
                root,
                dictionaries,
                "config",
                "sources/source_offline_store_manifest_hash_id",
                row,
            ),
            split_manifest_hash=_decode_id(
                root,
                dictionaries,
                "config",
                "sources/split_manifest_hash_id",
                row,
            ),
        )
        for row, source_id in enumerate(source_ids)
    )
    expected_split_hash = str(root.attrs["split_manifest_hash"])
    mismatched = [row.source_row_id for row in rows if row.split_manifest_hash != expected_split_hash]
    if mismatched:
        raise ValueError(f"Q_H store {path} source rows {mismatched} do not match root split_manifest_hash.")
    return rows


def _validate_lineage_provenance(
    root: zarr.Group,
    path: Path,
    dictionaries: dict[str, tuple[str, ...]],
) -> None:
    """Require per-rollout protocol and reason versions to match root truth."""

    config = dictionaries["config"]
    for array_path, root_attr in (
        ("lineage/target_protocol_version_id", "target_protocol_version"),
        ("lineage/reason_code_version_id", "reason_code_version"),
    ):
        values = {
            _decoded(config, int(value_id), array_path)
            for value_id in np.asarray(root[array_path], dtype=np.int64).reshape(-1)
        }
        expected = str(root.attrs[root_attr])
        if values != {expected}:
            raise ValueError(
                f"Q_H store {path} {array_path} values {sorted(values)} do not match root {root_attr}={expected!r}."
            )


def _config_hashes(
    root: zarr.Group,
    dictionaries: dict[str, tuple[str, ...]],
    array_path: str,
) -> tuple[str, ...]:
    """Return the bounded set of persisted lineage-config hashes."""

    ids = np.asarray(root[array_path], dtype=np.int64).reshape(-1)
    return tuple(sorted({_decoded(dictionaries["config"], int(value_id), array_path) for value_id in ids}))


def _validate_manifest(root: zarr.Group, path: Path) -> None:
    if root.attrs.get("manifest_path") != ROLLOUT_MANIFEST_FILENAME:
        raise ValueError(f"Q_H store {path} has an invalid manifest path.")
    try:
        manifest = read_rollout_store_manifest(path)
    except (OSError, ValueError) as error:
        raise ValueError(f"Q_H store {path} has no readable production manifest: {error}.") from error
    if manifest.get("manifest_version") != ROLLOUT_MANIFEST_VERSION:
        raise ValueError(f"Q_H store {path} has an unsupported manifest version.")
    if manifest.get("schema_version") != ROLLOUT_ZARR_SCHEMA_VERSION:
        raise ValueError(f"Q_H store {path} manifest has an unsupported schema version.")
    expected_hash = root.attrs.get("manifest_sha256")
    if not isinstance(expected_hash, str) or manifest_sha256(manifest) != expected_hash:
        raise ValueError(f"Q_H store {path} manifest hash does not match root metadata.")


def _validate_root_contract(root: zarr.Group, path: Path) -> None:
    if root.attrs.get("schema_version") != ROLLOUT_ZARR_SCHEMA_VERSION:
        raise ValueError(f"Q_H store {path} has an unsupported schema version.")
    if root.attrs.get("return_semantics") != DEFAULT_RETURN_SEMANTICS:
        raise ValueError(f"Q_H store {path} must use {DEFAULT_RETURN_SEMANTICS!r} return semantics.")
    for name in ("reason_code_version", "source_offline_store_version", "split_manifest_hash"):
        value = root.attrs.get(name)
        if not isinstance(value, str) or not value or value.startswith("unknown-"):
            raise ValueError(f"Q_H store {path} is missing required provenance attr {name!r}.")


def _validate_shapes(
    root: zarr.Group,
    *,
    state_count: int,
    candidate_count: int,
    rollout_count: int,
    target_count: int,
    source_count: int,
    max_candidates: int,
) -> None:
    if max_candidates < 1:
        raise ValueError("Q_H max_candidates must be positive.")
    vector_shapes = {
        **{f"q_h/{name}": (state_count,) for name in _Q_H_VECTOR_NAMES},
        **{f"steps/{name}": (state_count,) for name in _STEP_VECTOR_NAMES},
        **{f"rollouts/{name}": (rollout_count,) for name in _ROLLOUT_VECTOR_NAMES},
        **{f"targets/{name}": (target_count,) for name in _TARGET_VECTOR_NAMES},
        **{f"sources/{name}": (source_count,) for name in _SOURCE_VECTOR_NAMES},
        **{f"lineage/{name}": (rollout_count,) for name in _LINEAGE_VECTOR_NAMES},
    }
    for path, shape in vector_shapes.items():
        _require_shape(root, path, shape)
    for name in _Q_H_MATRIX_NAMES:
        _require_shape(root, f"q_h/{name}", (state_count, max_candidates))
    for name in _CANDIDATE_VECTOR_NAMES:
        _require_shape(root, f"candidates/{name}", (candidate_count,))
    for name in ("pose_world_cam", "pose_relative_root"):
        _require_shape(root, f"candidates/{name}", (candidate_count, 12))
    _require_shape(root, "rollouts/root_pose_world", (rollout_count, 12))
    for name, width in (
        ("target_center_world", 3),
        ("target_extents", 3),
        ("target_pose_world_object", 12),
        ("target_relative_pose_reference_object", 12),
    ):
        _require_shape(root, f"targets/{name}", (target_count, width))
    if int(root["q_h"].attrs.get("state_count", -1)) != state_count:
        raise ValueError("Q_H state_count attr does not match the persisted state axis.")
    if int(root.attrs.get("q_h_state_count", -1)) != state_count:
        raise ValueError("Q_H root state count does not match the persisted state axis.")
    q_h_horizon = int(root["q_h"].attrs.get("horizon", -1))
    realized_max = max((int(root["rollouts/horizon"][row]) for row in range(rollout_count)), default=-1)
    if q_h_horizon < 1 or realized_max != q_h_horizon or q_h_horizon != int(root.attrs.get("q_h_horizon", -1)):
        raise ValueError("Q_H rollout horizons must lie in [1, q_h_horizon] and realize the padded maximum.")
    if any(not 1 <= int(root["rollouts/horizon"][row]) <= q_h_horizon for row in range(rollout_count)):
        raise ValueError("Q_H rollout horizons must lie in [1, q_h_horizon] and realize the padded maximum.")


def _build_chain_index(root: zarr.Group, path: Path) -> tuple[_ChainIndexEntry, ...]:
    """Validate chains with scalar state scans and bounded padded-row reads."""

    rollout_count = int(root["rollouts/rollout_row_id"].shape[0])
    state_count = int(root["steps/step_row_id"].shape[0])
    if rollout_count == 0:
        raise ValueError(f"Q_H rollout store contains no rollout chains: {path}.")
    steps = root["steps"]
    q_h = root["q_h"]
    entries: list[_ChainIndexEntry] = []
    seen_rollout_ids: set[int] = set()
    state_position = 0
    for rollout_position in range(rollout_count):
        rollout_row_id = int(root["rollouts/rollout_row_id"][rollout_position])
        if rollout_row_id in seen_rollout_ids:
            raise ValueError(f"Q_H store {path} has duplicate rollouts/rollout_row_id values.")
        seen_rollout_ids.add(rollout_row_id)
        horizon = int(root["rollouts/horizon"][rollout_position])
        source_row_id = int(root["rollouts/source_row_id"][rollout_position])
        target_row_id = int(root["rollouts/target_row_id"][rollout_position])
        start = state_position
        step_row_ids: list[int] = []
        for step_index in range(horizon):
            if state_position >= state_count:
                raise ValueError(f"Q_H rollout_row_id={rollout_row_id} is empty or incomplete.")
            step_row_id = int(steps["step_row_id"][state_position])
            step_row_ids.append(step_row_id)
            if int(q_h["state_step_row_id"][state_position]) != step_row_id:
                raise ValueError(f"Q_H store {path} q_h states do not align one-to-one with step rows.")
            if int(steps["rollout_row_id"][state_position]) != rollout_row_id:
                raise ValueError(f"Q_H rollout_row_id={rollout_row_id} crosses or leaves unowned state rows.")
            if int(steps["step_index"][state_position]) != step_index:
                raise ValueError(f"Q_H rollout_row_id={rollout_row_id} requires contiguous step indices 0..S-1.")
            width = int(steps["num_candidates"][state_position])
            if width < 1:
                raise ValueError(f"Q_H rollout_row_id={rollout_row_id} contains an empty candidate state.")
            if (
                int(q_h["source_row_id"][state_position]) != source_row_id
                or int(q_h["target_row_id"][state_position]) != target_row_id
            ):
                raise ValueError(f"Q_H rollout_row_id={rollout_row_id} has mismatched source/target lineage.")
            expected_terminal = step_index == horizon - 1
            if bool(q_h["td_terminal_mask"][state_position]) != expected_terminal:
                raise ValueError(f"Q_H rollout_row_id={rollout_row_id} has broken or crossing successor linkage.")
            if step_index > 0 and int(q_h["td_next_step_row_id"][state_position - 1]) != step_row_id:
                raise ValueError(f"Q_H rollout_row_id={rollout_row_id} has broken or crossing successor linkage.")
            if expected_terminal and int(q_h["td_next_step_row_id"][state_position]) != -1:
                raise ValueError(f"Q_H rollout_row_id={rollout_row_id} has broken or crossing successor linkage.")
            _validate_indexed_candidate_slice(root, row=state_position, width=width, step_row_id=step_row_id)
            state_position += 1
        entries.append(_ChainIndexEntry(rollout_position, rollout_row_id, start, state_position, tuple(step_row_ids)))
    if state_position != state_count:
        raise ValueError(f"Q_H store {path} contains state rows not owned by exactly one rollout chain.")
    return tuple(entries)


def _validate_indexed_candidate_slice(root: zarr.Group, *, row: int, width: int, step_row_id: int) -> None:
    q_rows = _read_padded_qh_row(root, row)
    candidate_ids = q_rows["candidate_row_id"][:width].astype(np.int64, copy=False)
    candidates = _candidate_slice(root, candidate_ids, row, step_row_id)
    _validate_materialized_qh_row(q_rows, candidates, width=width, row=row)
    selected = int(root["q_h/selected_candidate_index"][row])
    if selected < 0 or selected >= width or not bool(q_rows["valid_action_mask"][selected]):
        raise ValueError(f"Q_H selected candidate linkage is invalid at state row {row}.")
    selected_id = int(candidate_ids[selected])
    if selected_id != int(root["q_h/td_selected_candidate_row_id"][row]) or selected_id != int(
        root["steps/selected_candidate_row_id"][row]
    ):
        raise ValueError(f"Q_H selected candidate row id is inconsistent at state row {row}.")
    if not np.isclose(float(root["q_h/td_reward"][row]), float(q_rows["one_step_target_root_gain"][selected])):
        raise ValueError(f"Q_H selected reward is inconsistent at state row {row}.")
    if not np.isclose(float(root["q_h/td_reward_target_rri"][row]), float(q_rows["one_step_target_rri"][selected])):
        raise ValueError(f"Q_H selected target RRI is inconsistent at state row {row}.")


def _validate_homogeneous(stores: tuple[_StoreMetadata, ...]) -> None:
    expected = stores[0].compatibility
    for store in stores[1:]:
        if store.compatibility == expected:
            continue
        expected_map = dict(expected)
        actual_map = dict(store.compatibility)
        mismatches = [name for name in expected_map if expected_map[name] != actual_map.get(name)]
        raise ValueError(f"Q_H rollout stores are heterogeneous at {store.path}: incompatible {', '.join(mismatches)}.")


def _admitted_target_source(root: zarr.Group) -> str:
    dictionary = _decode_dictionary(root, "target_source")
    if set(dictionary) != {ORACLE_GT_TARGET_SOURCE}:
        raise ValueError(
            "v0_gt_input requires the target-source dictionary to contain only the canonical Oracle GT source; "
            f"found {sorted(dictionary)}."
        )
    return ORACLE_GT_TARGET_SOURCE


def _require_shape(root: zarr.Group, path: str, expected: tuple[int, ...]) -> None:
    actual = tuple(root[path].shape)
    if actual != expected:
        raise ValueError(f"Q_H field {path} has shape {actual}, expected {expected}.")


def _array_equal(left: np.ndarray, right: np.ndarray) -> bool:
    if np.issubdtype(left.dtype, np.floating) or np.issubdtype(right.dtype, np.floating):
        return bool(np.allclose(left, right, equal_nan=True))
    return bool(np.array_equal(left, right))


def _read_chain(root: zarr.Group, store: _StoreMetadata, entry: _ChainIndexEntry) -> _StoredChain:
    """Decode one preflighted root-to-leaf chain without a terminal empty state."""

    rows = range(entry.state_start, entry.state_stop)
    steps = root["steps"]
    q_h = root["q_h"]
    candidate_rows = tuple(
        _read_chain_candidate_row(
            root,
            row=row,
            width=int(steps["num_candidates"][row]),
            step_row_id=step_row_id,
        )
        for row, step_row_id in zip(rows, entry.step_row_ids, strict=True)
    )
    selected_index = np.asarray(q_h["selected_candidate_index"][entry.state_start : entry.state_stop], dtype=np.int64)

    rollout = root["rollouts"]
    rollout_position = entry.rollout_position
    source_row_id = int(rollout["source_row_id"][rollout_position])
    target_row_id = int(rollout["target_row_id"][rollout_position])
    source_row = _find_sorted_row(root["sources/source_row_id"], source_row_id, "sources/source_row_id")
    target_row = _find_sorted_row(root["targets/target_row_id"], target_row_id, "targets/target_row_id")
    sources = root["sources"]
    target = root["targets"]
    dictionaries = store.dictionaries
    target_source = _decode_id(root, dictionaries, "target_source", "targets/target_source_id", target_row)
    root_pose_world = np.asarray(rollout["root_pose_world"][rollout_position], dtype=np.float32)
    target_extents = np.asarray(target["target_extents"][target_row], dtype=np.float32)
    target_pose = np.asarray(target["target_pose_world_object"][target_row], dtype=np.float32)
    if root_pose_world.shape != (12,) or not np.isfinite(root_pose_world).all():
        raise ValueError(f"Q_H rollout_row_id={entry.rollout_row_id} has an invalid rollout root pose.")
    if (
        target_extents.shape != (3,)
        or target_pose.shape != (12,)
        or not (np.isfinite(target_extents).all() and np.isfinite(target_pose).all())
    ):
        raise ValueError(f"Q_H rollout_row_id={entry.rollout_row_id} has an incomplete canonical V0 descriptor.")

    horizon = int(rollout["horizon"][rollout_position])
    discounts = np.asarray(q_h["td_discount"][entry.state_start : entry.state_stop], dtype=np.float32)
    terminals = np.asarray(q_h["td_terminal_mask"][entry.state_start : entry.state_stop], dtype=np.bool_)
    expected_discounts = np.full(horizon, float(root.attrs["discount_gamma"]), dtype=np.float32)
    expected_discounts[-1] = 0.0
    if not np.allclose(discounts, expected_discounts):
        raise ValueError(f"Q_H rollout_row_id={entry.rollout_row_id} has inconsistent transition discounts.")

    return _StoredChain(
        root_pose_world=_readonly(root_pose_world),
        target_extents=_readonly(target_extents),
        target_pose_world_object=_readonly(target_pose),
        candidate_pose_relative_root=tuple(facts["candidate_pose_relative_root"] for facts in candidate_rows),
        candidate_position_id=tuple(facts["candidate_position_id"] for facts in candidate_rows),
        actor_action_mask=tuple(facts["actor_action_mask"] for facts in candidate_rows),
        remaining_budget=_readonly(np.arange(horizon, 0, -1, dtype=np.int64)),
        candidate_row_id=tuple(facts["candidate_row_id"] for facts in candidate_rows),
        q_train_mask=tuple(facts["q_train_mask"] for facts in candidate_rows),
        invalid_reason_bitset=tuple(facts["invalid_reason_bitset"] for facts in candidate_rows),
        one_step_target_rri=tuple(facts["one_step_target_rri"] for facts in candidate_rows),
        one_step_target_root_gain=tuple(facts["one_step_target_root_gain"] for facts in candidate_rows),
        selected_candidate_index=_readonly(selected_index),
        discount=_readonly(discounts),
        terminal=_readonly(terminals),
        lineage=(
            source_row_id,
            int(sources["sample_index"][source_row]),
            _decode_id(root, dictionaries, "source_key", "sources/sample_key_id", source_row),
            _decode_id(root, dictionaries, "source_shard", "sources/source_shard_id", source_row),
            int(sources["source_shard_row"][source_row]),
            _decode_id(root, dictionaries, "scene", "sources/scene_id", source_row),
            _decode_id(root, dictionaries, "snippet", "sources/snippet_id", source_row),
            Stage.from_str(_decode_id(root, dictionaries, "split", "sources/split_id", source_row)),
            _decode_id(root, dictionaries, "config", "sources/source_cache_version_id", source_row),
            _decode_id(root, dictionaries, "config", "sources/source_offline_store_manifest_hash_id", source_row),
            _decode_id(root, dictionaries, "config", "sources/split_manifest_hash_id", source_row),
            _decode_optional_id(root, dictionaries, "config", "lineage/mesh_version_id", rollout_position),
            target_row_id,
            int(target["target_sem_id"][target_row]),
            int(target["target_inst_id"][target_row]),
            str(root.attrs["target_protocol_version"]),
            target_source,
            _decode_optional_id(root, dictionaries, "config", "lineage/target_crop_policy_id", rollout_position),
            str(root.attrs["schema_version"]),
            str(root.attrs["reason_code_version"]),
            str(root.attrs["return_semantics"]),
            str(q_h.attrs["td_semantics"]),
            str(q_h.attrs["reward_metric"]),
            float(root.attrs["discount_gamma"]),
            horizon,
            entry.rollout_row_id,
            _decode_id(root, dictionaries, "rollout", "rollouts/rollout_id", rollout_position),
            int(rollout["chain_id"][rollout_position]),
            int(rollout["root_time_ns"][rollout_position]),
            int(rollout["root_trajectory_index"][rollout_position]),
            int(rollout["root_frame_index"][rollout_position]),
            _decode_id(root, dictionaries, "policy", "rollouts/policy_id", rollout_position),
            int(rollout["branch_factor"][rollout_position]),
            int(rollout["beam_width"][rollout_position]),
            float(rollout["temperature"][rollout_position]),
            int(rollout["random_seed"][rollout_position]),
            _decode_id(root, dictionaries, "termination_reason", "rollouts/termination_reason", rollout_position),
            _decode_id(root, dictionaries, "config", "lineage/candidate_config_id", rollout_position),
            _decode_id(root, dictionaries, "config", "lineage/oracle_config_id", rollout_position),
            _decode_id(root, dictionaries, "config", "lineage/rollout_config_id", rollout_position),
            _decode_optional_id(root, dictionaries, "config", "lineage/model_checkpoint_id", rollout_position),
            _decode_optional_id(root, dictionaries, "config", "lineage/branch_schedule_id", rollout_position),
            _decode_optional_id(root, dictionaries, "config", "lineage/selection_rng_state_hash_id", rollout_position),
        ),
    )


def _read_chain_candidate_row(
    root: zarr.Group,
    *,
    row: int,
    width: int,
    step_row_id: int,
) -> dict[str, np.ndarray]:
    q_rows = _read_padded_qh_row(root, row)
    candidate_ids = q_rows["candidate_row_id"][:width].astype(np.int64, copy=False)
    candidates = _candidate_slice(root, candidate_ids, row, step_row_id)
    return {
        "candidate_row_id": _readonly(candidate_ids),
        "candidate_pose_relative_root": _readonly(candidates["pose_relative_root"].astype(np.float32, copy=False)),
        "candidate_position_id": _readonly(q_rows["position_id"][:width].astype(np.int32, copy=False)),
        "actor_action_mask": _readonly(q_rows["valid_action_mask"][:width].astype(np.bool_, copy=False)),
        "q_train_mask": _readonly(q_rows["q_train_mask"][:width].astype(np.bool_, copy=False)),
        "invalid_reason_bitset": _readonly(q_rows["invalid_reason_bitset"][:width].astype(np.uint32, copy=False)),
        "one_step_target_rri": _readonly(q_rows["one_step_target_rri"][:width].astype(np.float32, copy=False)),
        "one_step_target_root_gain": _readonly(
            q_rows["one_step_target_root_gain"][:width].astype(np.float32, copy=False)
        ),
    }


def _candidate_slice(
    root: zarr.Group,
    candidate_ids: np.ndarray,
    state_row: int,
    step_row_id: int,
) -> dict[str, np.ndarray]:
    _contiguous_candidate_bounds(candidate_ids, state_row)
    group = root["candidates"]
    start = _find_sorted_row(group["candidate_row_id"], int(candidate_ids[0]), "candidates/candidate_row_id")
    stop = start + int(candidate_ids.size)
    values = {
        name: np.asarray(group[name][start:stop])
        for name in (
            "candidate_row_id",
            "step_row_id",
            "pose_world_cam",
            "pose_relative_root",
            "actor_action_mask",
            "q_train_mask",
            "position_id",
            "invalid_reason_bitset",
            "target_rri",
            "target_root_gain",
        )
    }
    if not np.array_equal(values["candidate_row_id"], candidate_ids):
        raise ValueError(f"Q_H candidate row-position join changed at state row {state_row}.")
    if np.any(values["step_row_id"] != step_row_id):
        raise ValueError(f"Q_H candidate rows cross state ownership at state row {state_row}.")
    return values


def _read_padded_qh_row(root: zarr.Group, row: int) -> dict[str, np.ndarray]:
    max_candidates = int(root["q_h"].attrs["max_candidates"])
    return {name: np.asarray(root[f"q_h/{name}"][row, :max_candidates]) for name in _Q_H_MATRIX_NAMES}


def _validate_materialized_qh_row(
    q_rows: dict[str, np.ndarray],
    candidates: dict[str, np.ndarray],
    *,
    width: int,
    row: int,
) -> None:
    for q_name, candidate_name in (
        ("valid_action_mask", "actor_action_mask"),
        ("q_train_mask", "q_train_mask"),
        ("position_id", "position_id"),
        ("invalid_reason_bitset", "invalid_reason_bitset"),
        ("one_step_target_rri", "target_rri"),
        ("one_step_target_root_gain", "target_root_gain"),
    ):
        if not _array_equal(q_rows[q_name][:width], candidates[candidate_name]):
            raise ValueError(f"Q_H q_h/{q_name} does not match candidates/{candidate_name} at state row {row}.")

    valid_mask = q_rows["valid_action_mask"].astype(np.bool_, copy=False)
    train_mask = q_rows["q_train_mask"].astype(np.bool_, copy=False)
    target_rri = q_rows["one_step_target_rri"].astype(np.float32, copy=False)
    root_gain = q_rows["one_step_target_root_gain"].astype(np.float32, copy=False)
    position_id = q_rows["position_id"].astype(np.int32, copy=False)
    candidate_id = q_rows["candidate_row_id"].astype(np.int64, copy=False)
    reason = q_rows["invalid_reason_bitset"].astype(np.uint32, copy=False)
    if (
        np.any(candidate_id[width:] != -1)
        or valid_mask[width:].any()
        or train_mask[width:].any()
        or np.any(position_id[width:] != -1)
    ):
        raise ValueError(f"Q_H padded candidate slots have non-sentinel actor fields at state row {row}.")
    if np.any(reason[width:] != 0):
        raise ValueError(f"Q_H padded candidate slots have non-zero invalid reasons at state row {row}.")
    if not np.isnan(target_rri[width:]).all() or not np.isnan(root_gain[width:]).all():
        raise ValueError(f"Q_H padded candidate slots have finite supervision at state row {row}.")
    if np.any(train_mask & ~valid_mask) or np.any(train_mask & (~np.isfinite(root_gain) | ~np.isfinite(target_rri))):
        raise ValueError(f"Q_H q_train_mask admits an invalid or unlabeled candidate at state row {row}.")


def _contiguous_candidate_bounds(candidate_ids: np.ndarray, state_row: int) -> tuple[int, int]:
    if candidate_ids.size == 0:
        raise ValueError(f"Q_H state row {state_row} has no materialized candidates.")
    start = int(candidate_ids[0])
    stop = int(candidate_ids[-1]) + 1
    if not np.array_equal(candidate_ids, np.arange(start, stop, dtype=np.int64)):
        raise ValueError(f"Q_H candidate ids are not a contiguous full-shell slice at state row {state_row}.")
    return start, stop


def _decode_dictionary(root: zarr.Group, name: str) -> tuple[str, ...]:
    encoded = np.asarray(root[f"dictionaries/{name}"], dtype=np.uint8)
    values = json.loads(encoded.tobytes().decode("utf-8"))
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError(f"Q_H dictionary {name!r} is malformed.")
    return tuple(values)


def _decode_id(
    root: zarr.Group,
    dictionaries: dict[str, tuple[str, ...]],
    dictionary_name: str,
    array_path: str,
    row: int,
) -> str:
    value_id = int(root[array_path][row])
    return _decoded(dictionaries[dictionary_name], value_id, array_path)


def _decode_optional_id(
    root: zarr.Group,
    dictionaries: dict[str, tuple[str, ...]],
    dictionary_name: str,
    array_path: str,
    row: int,
) -> str:
    value_id = int(root[array_path][row])
    if value_id == -1:
        return ""
    return _decoded(dictionaries[dictionary_name], value_id, array_path)


def _find_sorted_row(array: zarr.Array, value: int, label: str) -> int:
    low = 0
    high = int(array.shape[0])
    while low < high:
        middle = (low + high) // 2
        candidate = int(array[middle])
        if candidate < value:
            low = middle + 1
        else:
            high = middle
    if low >= int(array.shape[0]) or int(array[low]) != value:
        raise ValueError(f"Q_H immutable id {value} is missing from {label}.")
    return low


def _decoded(dictionary: tuple[str, ...], value_id: int, label: str) -> str:
    if value_id < 0 or value_id >= len(dictionary):
        raise ValueError(f"Q_H {label} dictionary id {value_id} is out of range.")
    return dictionary[value_id]


def _readonly(values: Any) -> np.ndarray:
    array = np.asarray(values)
    array.setflags(write=False)
    return array


__all__ = [
    "QhRolloutReader",
    "QhRolloutReaderConfig",
]
