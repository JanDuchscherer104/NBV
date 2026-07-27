"""Lazy storage-only reader for finite-candidate ``Q_H`` rollout chains.

Corpus admission indexes and validates every complete, non-empty persisted
rollout chain. Worker processes reopen Zarr handles and read only bounded state
rows and contiguous candidate slices. The legacy state-at-a-time surface stays
temporarily available for the transition data plane; the chain facts consumed
by its replacement remain private until :mod:`aria_nbv.data_handling.qh` owns
the public tensor DTOs.
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
class QhStateLocator:
    """Store-local address of one validated ``Q_H`` state row."""

    store_index: int
    """Zero-based index into :attr:`QhRolloutReaderConfig.store_dirs`."""

    state_row: int
    """Zero-based row on the selected store's dense ``q_h`` state axis."""


@dataclass(frozen=True, slots=True)
class QhActorState:
    """Actor-safe rollout facts for one finite-candidate state.

    ``remaining_budget`` is the fixed acquisition budget ``horizon -
    step_index``. History contains only previously selected pose, position/action
    id, and candidate id rows; persisted depth and Oracle diagnostics are absent.
    """

    candidate_row_id: np.ndarray
    """``ndarray["N_q", int64]`` stable candidate-table ids for the compact shell."""

    candidate_pose_world_cam: np.ndarray
    """``ndarray["N_q 12", float32]`` world-from-camera poses."""

    candidate_pose_relative_root: np.ndarray
    """``ndarray["N_q 12", float32]`` root-reference-from-camera poses."""

    candidate_position_id: np.ndarray
    """``ndarray["N_q", int32]`` actor-visible finite-position family ids."""

    actor_action_mask: np.ndarray
    """``ndarray["N_q", bool]`` hard action-admission mask for selection."""

    root_pose_world: np.ndarray
    """``ndarray["12", float32]`` persisted world-from-rollout-root pose."""

    target_row_id: int
    """Dense row id of the persisted V0 target descriptor."""

    target_center_world: np.ndarray
    """``ndarray["3", float32]`` target OBB center in world frame, metres."""

    target_extents: np.ndarray
    """``ndarray["3", float32]`` target OBB full extents, metres."""

    target_pose_world_object: np.ndarray
    """``ndarray["12", float32]`` world-from-object target pose."""

    target_relative_pose_reference_object: np.ndarray
    """``ndarray["12", float32]`` rollout-reference-from-object target pose."""

    target_sem_id: int
    """Target semantic-category id from the admitted Oracle GT descriptor."""

    target_inst_id: int
    """Target instance id from the admitted Oracle GT descriptor."""

    history_candidate_row_id: np.ndarray
    """``ndarray["H_t", int64]`` stable ids selected before this state."""

    history_pose_world_cam: np.ndarray
    """``ndarray["H_t 12", float32]`` prior selected world-from-camera poses."""

    history_pose_relative_root: np.ndarray
    """``ndarray["H_t 12", float32]`` prior root-reference-from-camera poses."""

    history_position_id: np.ndarray
    """``ndarray["H_t", int32]`` prior selected finite-position family ids."""

    remaining_budget: int
    """Acquisitions remaining including the current step, ``horizon - step_index``."""


@dataclass(frozen=True, slots=True)
class QhSupervision:
    """One-step Oracle labels and hard training masks aligned to candidates."""

    q_train_mask: np.ndarray
    """``ndarray["N_q", bool]`` candidates with actor validity and finite Oracle labels."""

    invalid_reason_bitset: np.ndarray
    """``ndarray["N_q", uint32]`` persisted hard-invalid reason flags."""

    one_step_target_rri: np.ndarray
    """``ndarray["N_q", float32]`` one-step target RRI; invalid entries may be NaN."""

    one_step_target_root_gain: np.ndarray
    """``ndarray["N_q", float32]`` root-gain rewards; invalid entries may be NaN."""


@dataclass(frozen=True, slots=True)
class QhTransition:
    """Factual selected transition and its optional next-state address."""

    selected_candidate_index: int
    """Index of the factual selected action on the current compact candidate axis."""

    selected_candidate_row_id: int
    """Stable candidate-table id at :attr:`selected_candidate_index`."""

    reward: float
    """Selected one-step target-root-gain reward used by fitted ``Q_H``."""

    reward_target_rri: float
    """Selected one-step target RRI retained as an audit diagnostic."""

    discount: float
    """Persisted TD discount: corpus gamma for successors and ``0.0`` at terminal rows."""

    terminal: bool
    """Whether the selected transition ends the persisted rollout chain."""

    next_state: QhStateLocator | None
    """Exact next state in the same store and chain, absent iff :attr:`terminal`."""


@dataclass(frozen=True, slots=True)
class QhLineage:
    """Observation, target, rollout, and configuration provenance.

    The immutable VIN source row is the observation provenance. The rollout
    store does not reinterpret that lineage as an actor observation payload.
    """

    source_row_id: int
    """Dense rollout-store row id of the immutable VIN source reference."""

    source_sample_index: int
    """Global immutable VIN ``sample_index.jsonl`` index used for the actor join."""

    source_sample_key: str
    """Stable compact ASE/ATEK sample key."""

    source_shard_id: str
    """Immutable VIN shard containing :attr:`source_shard_row`."""

    source_shard_row: int
    """Zero-based row within :attr:`source_shard_id`."""

    scene_id: str
    """ASE scene id used for scene-disjoint split validation."""

    snippet_id: str
    """ATEK snippet id of the source observation."""

    split: Stage
    """Immutable VIN source split recorded for the observation row."""

    source_cache_version: str
    """Strict immutable VIN store-format version."""

    source_offline_store_manifest_hash: str
    """Hash binding the rollout row to the complete immutable VIN manifest."""

    split_manifest_hash: str
    """Hash binding source admission to the rollout corpus split manifest."""

    target_protocol_version: str
    """Persisted actor-visible target-input protocol version."""

    target_source: str
    """Canonical target descriptor source admitted by that protocol."""

    schema_version: str
    """Rollout Zarr schema version used to decode the state."""

    reason_code_version: str
    """Version of the invalid-reason bitset vocabulary."""

    return_semantics: str
    """Corpus-level definition of persisted finite-horizon returns."""

    td_semantics: str
    """Definition of the selected-transition Bellman tuple."""

    reward_metric: str
    """Name of the scalar reward carried by :attr:`QhTransition.reward`."""

    discount_gamma: float
    """Corpus discount gamma applied to non-terminal transitions."""

    horizon: int
    """Maximum acquisition-step count for this rollout chain."""

    rollout_row_id: int
    """Dense row id of the owning rollout."""

    rollout_id: str
    """Stable persisted rollout identifier."""

    chain_id: int
    """Persisted chain identifier within the rollout source/target task."""

    step_index: int
    """Zero-based state index within the rollout chain."""

    candidate_config_hash: str
    """Hash of the candidate-generation config used by the rollout."""

    oracle_config_hash: str
    """Hash of the privileged Oracle scoring config used to label the rollout."""

    rollout_config_hash: str
    """Hash of the rollout-policy and persistence config."""


@dataclass(frozen=True, slots=True)
class QhRolloutState:
    """Storage-side current state returned by :class:`QhRolloutReader`."""

    locator: QhStateLocator
    """Store-local address from which this state was read."""

    actor: QhActorState
    """Actor-visible candidate, target, and selected-history facts."""

    supervision: QhSupervision
    """Candidate-aligned Oracle labels and hard training admission."""

    transition: QhTransition
    """Factual selected Bellman transition."""

    lineage: QhLineage
    """Observation, target, rollout, and configuration provenance."""


@dataclass(frozen=True, slots=True)
class QhSourceLineage:
    """Compact immutable source facts admitted during rollout preflight."""

    source_row_id: int
    """Dense rollout-store source-table row id."""

    source_sample_index: int
    """Global immutable VIN sample index used by :class:`QhRolloutReader`."""

    source_sample_key: str
    """Stable compact ASE/ATEK sample key."""

    source_shard_id: str
    """Immutable VIN shard containing the source observation."""

    source_shard_row: int
    """Zero-based row within :attr:`source_shard_id`."""

    scene_id: str
    """ASE scene id used for split-disjointness checks."""

    snippet_id: str
    """ATEK snippet id of the source observation."""

    split: Stage
    """Immutable VIN source split."""

    source_cache_version: str
    """Strict immutable VIN store-format version."""

    source_offline_store_manifest_hash: str
    """Hash of the complete immutable VIN source manifest."""

    split_manifest_hash: str
    """Hash of the admitted rollout split manifest."""


@dataclass(frozen=True, slots=True)
class _QhChainStateFacts:
    root_pose_world: np.ndarray
    target_extents: np.ndarray
    target_pose_world_object: np.ndarray
    candidate_pose_relative_root: tuple[np.ndarray, ...]
    candidate_position_id: tuple[np.ndarray, ...]
    actor_action_mask: tuple[np.ndarray, ...]
    remaining_budget: np.ndarray


@dataclass(frozen=True, slots=True)
class _QhChainSupervisionFacts:
    candidate_row_id: tuple[np.ndarray, ...]
    q_train_mask: tuple[np.ndarray, ...]
    invalid_reason_bitset: tuple[np.ndarray, ...]
    one_step_target_rri: tuple[np.ndarray, ...]
    one_step_target_root_gain: tuple[np.ndarray, ...]
    selected_candidate_index: np.ndarray


@dataclass(frozen=True, slots=True)
class _QhChainTransitionFacts:
    discount: np.ndarray
    terminal: np.ndarray


@dataclass(frozen=True, slots=True)
class _QhChainLineage:
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
    mesh_version: str
    target_row_id: int
    target_sem_id: int
    target_inst_id: int
    target_protocol_version: str
    target_source: str
    target_crop_policy: str
    schema_version: str
    reason_code_version: str
    return_semantics: str
    td_semantics: str
    reward_metric: str
    discount_gamma: float
    horizon: int
    rollout_row_id: int
    rollout_id: str
    chain_id: int
    root_time_ns: int
    root_trajectory_index: int
    root_frame_index: int
    policy: str
    branch_factor: int
    beam_width: int
    temperature: float
    random_seed: int
    termination_reason: str
    candidate_config_hash: str
    oracle_config_hash: str
    rollout_config_hash: str
    model_checkpoint_hash: str
    branch_schedule_id: str
    selection_rng_state_hash: str


@dataclass(frozen=True, slots=True)
class _QhRolloutChainFacts:
    state: _QhChainStateFacts
    supervision: _QhChainSupervisionFacts
    transition: _QhChainTransitionFacts
    lineage: _QhChainLineage


@dataclass(frozen=True, slots=True)
class _ChainIndexEntry:
    rollout_position: int
    rollout_row_id: int
    state_start: int
    state_stop: int


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
    source_lineage: tuple[QhSourceLineage, ...]
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
        prefix_ends: list[int] = []
        total = 0
        for store in self._stores:
            total += store.state_count
            prefix_ends.append(total)
        self._prefix_ends = tuple(prefix_ends)
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
        """Return the legacy transition-state count until G004 switches consumers."""

        return self._prefix_ends[-1]

    @property
    def chain_count(self) -> int:
        """Return the number of complete non-empty persisted rollout chains."""

        return self._chain_prefix_ends[-1]

    def read_chain(self, index: int) -> _QhRolloutChainFacts:
        """Decode one validated chain through bounded state and candidate slices."""

        if index < 0:
            index += self.chain_count
        if index < 0 or index >= self.chain_count:
            raise IndexError(f"Q_H chain index {index} is outside corpus length {self.chain_count}.")
        store_index = bisect_right(self._chain_prefix_ends, index)
        previous_end = 0 if store_index == 0 else self._chain_prefix_ends[store_index - 1]
        store = self._stores[store_index]
        return _read_chain(self._root(store_index), store, store.chains[index - previous_end])

    def __getitem__(self, index: int) -> QhRolloutState:
        """Return one state using bounded Zarr reads and direct dense-id joins."""

        locator = self.locator(index)
        return self.read(locator)

    @property
    def source_lineage(self) -> tuple[QhSourceLineage, ...]:
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

    def locator(self, index: int) -> QhStateLocator:
        """Translate one global corpus index with prefix-length bisection."""

        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(f"Q_H state index {index} is outside corpus length {len(self)}.")
        store_index = bisect_right(self._prefix_ends, index)
        previous_end = 0 if store_index == 0 else self._prefix_ends[store_index - 1]
        return QhStateLocator(store_index=store_index, state_row=index - previous_end)

    def read(self, locator: QhStateLocator) -> QhRolloutState:
        """Read one previously validated store-local state locator."""

        if locator.store_index < 0 or locator.store_index >= len(self._stores):
            raise IndexError(f"Unknown Q_H store index {locator.store_index}.")
        store = self._stores[locator.store_index]
        if locator.state_row < 0 or locator.state_row >= store.state_count:
            raise IndexError(f"Q_H state row {locator.state_row} is outside store length {store.state_count}.")
        root = self._root(locator.store_index)
        return _read_state(root, store, locator)

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
) -> tuple[QhSourceLineage, ...]:
    """Decode bounded source-table vectors and validate their split provenance."""

    sources = root["sources"]
    source_ids = np.asarray(sources["source_row_id"], dtype=np.int64).reshape(-1)
    if source_ids.size == 0 or np.any(source_ids[1:] <= source_ids[:-1]):
        raise ValueError(f"Q_H store {path} requires sorted unique immutable source ids.")
    rows = tuple(
        QhSourceLineage(
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
    horizons = np.asarray(root["rollouts/horizon"], dtype=np.int64)
    q_h_horizon = int(root["q_h"].attrs.get("horizon", -1))
    if (
        horizons.size == 0
        or q_h_horizon < 1
        or np.any(horizons < 1)
        or np.any(horizons > q_h_horizon)
        or int(horizons.max()) != q_h_horizon
        or q_h_horizon != int(root.attrs.get("q_h_horizon", -1))
    ):
        raise ValueError("Q_H rollout horizons must lie in [1, q_h_horizon] and realize the padded maximum.")


def _build_chain_index(root: zarr.Group, path: Path) -> tuple[_ChainIndexEntry, ...]:
    """Validate complete persisted chains without materializing padded matrices."""

    rollout_ids = np.asarray(root["rollouts/rollout_row_id"], dtype=np.int64).reshape(-1)
    if rollout_ids.size == 0:
        raise ValueError(f"Q_H rollout store contains no rollout chains: {path}.")
    if np.unique(rollout_ids).size != rollout_ids.size:
        raise ValueError(f"Q_H store {path} has duplicate rollouts/rollout_row_id values.")

    steps = root["steps"]
    step_ids = np.asarray(steps["step_row_id"], dtype=np.int64).reshape(-1)
    step_rollouts = np.asarray(steps["rollout_row_id"], dtype=np.int64).reshape(-1)
    step_indices = np.asarray(steps["step_index"], dtype=np.int64).reshape(-1)
    step_widths = np.asarray(steps["num_candidates"], dtype=np.int64).reshape(-1)
    q_h = root["q_h"]
    state_step_ids = np.asarray(q_h["state_step_row_id"], dtype=np.int64).reshape(-1)
    state_sources = np.asarray(q_h["source_row_id"], dtype=np.int64).reshape(-1)
    state_targets = np.asarray(q_h["target_row_id"], dtype=np.int64).reshape(-1)
    next_rows = np.asarray(q_h["td_next_step_row_id"], dtype=np.int64).reshape(-1)
    terminal = np.asarray(q_h["td_terminal_mask"], dtype=np.bool_).reshape(-1)
    rollout_sources = np.asarray(root["rollouts/source_row_id"], dtype=np.int64).reshape(-1)
    rollout_targets = np.asarray(root["rollouts/target_row_id"], dtype=np.int64).reshape(-1)
    horizons = np.asarray(root["rollouts/horizon"], dtype=np.int64).reshape(-1)

    if not np.array_equal(step_ids, state_step_ids):
        raise ValueError(f"Q_H store {path} q_h states do not align one-to-one with step rows.")
    entries: list[_ChainIndexEntry] = []
    previous_stop = 0
    for rollout_position, rollout_row_id in enumerate(rollout_ids.tolist()):
        positions = np.flatnonzero(step_rollouts == rollout_row_id)
        if positions.size == 0:
            raise ValueError(f"Q_H rollout_row_id={rollout_row_id} is empty.")
        start = int(positions[0])
        stop = int(positions[-1]) + 1
        if not np.array_equal(positions, np.arange(start, stop, dtype=np.int64)):
            raise ValueError(f"Q_H rollout_row_id={rollout_row_id} is not a contiguous state slice.")
        if start != previous_stop:
            raise ValueError(f"Q_H rollout_row_id={rollout_row_id} crosses or leaves unowned state rows.")
        expected_indices = np.arange(stop - start, dtype=np.int64)
        if not np.array_equal(step_indices[start:stop], expected_indices):
            raise ValueError(f"Q_H rollout_row_id={rollout_row_id} requires contiguous step indices 0..S-1.")
        if stop - start != int(horizons[rollout_position]):
            raise ValueError(f"Q_H rollout_row_id={rollout_row_id} has a missing or extra candidate-bearing state.")
        if np.any(step_widths[start:stop] < 1):
            raise ValueError(f"Q_H rollout_row_id={rollout_row_id} contains an empty candidate state.")
        if np.any(state_sources[start:stop] != rollout_sources[rollout_position]) or np.any(
            state_targets[start:stop] != rollout_targets[rollout_position]
        ):
            raise ValueError(f"Q_H rollout_row_id={rollout_row_id} has mismatched source/target lineage.")
        expected_next = np.arange(start + 1, stop + 1, dtype=np.int64)
        expected_next[-1] = -1
        expected_terminal = np.zeros(stop - start, dtype=np.bool_)
        expected_terminal[-1] = True
        if not np.array_equal(next_rows[start:stop], expected_next) or not np.array_equal(
            terminal[start:stop], expected_terminal
        ):
            raise ValueError(f"Q_H rollout_row_id={rollout_row_id} has broken or crossing successor linkage.")
        for row, width in zip(range(start, stop), step_widths[start:stop].tolist(), strict=True):
            _validate_indexed_candidate_slice(root, row=row, width=int(width))
        entries.append(_ChainIndexEntry(rollout_position, int(rollout_row_id), start, stop))
        previous_stop = stop
    if previous_stop != step_ids.size:
        raise ValueError(f"Q_H store {path} contains state rows not owned by exactly one rollout chain.")
    return tuple(entries)


def _validate_indexed_candidate_slice(root: zarr.Group, *, row: int, width: int) -> None:
    candidate_ids = np.asarray(root["q_h/candidate_row_id"][row, :width], dtype=np.int64)
    start, stop = _contiguous_candidate_bounds(candidate_ids, row)
    candidates = root["candidates"]
    if not np.array_equal(np.asarray(candidates["candidate_row_id"][start:stop]), candidate_ids):
        raise ValueError(f"Q_H candidate row-position join changed at state row {row}.")
    if np.any(np.asarray(candidates["step_row_id"][start:stop], dtype=np.int64) != row):
        raise ValueError(f"Q_H candidate rows cross state ownership at state row {row}.")


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


def _read_chain(root: zarr.Group, store: _StoreMetadata, entry: _ChainIndexEntry) -> _QhRolloutChainFacts:
    """Decode one preflighted root-to-leaf chain without a terminal empty state."""

    rows = range(entry.state_start, entry.state_stop)
    steps = root["steps"]
    q_h = root["q_h"]
    widths = np.asarray(steps["num_candidates"][entry.state_start : entry.state_stop], dtype=np.int64)
    candidate_rows = tuple(
        _read_chain_candidate_row(root, row=row, width=int(width))
        for row, width in zip(rows, widths.tolist(), strict=True)
    )
    selected_index = np.asarray(q_h["selected_candidate_index"][entry.state_start : entry.state_stop], dtype=np.int64)
    for offset, (selected, facts) in enumerate(zip(selected_index.tolist(), candidate_rows, strict=True)):
        row = entry.state_start + offset
        if selected < 0 or selected >= facts["candidate_row_id"].size:
            raise ValueError(f"Q_H selected candidate linkage is invalid at state row {row}.")
        selected_row_id = int(facts["candidate_row_id"][selected])
        if selected_row_id != int(q_h["td_selected_candidate_row_id"][row]) or selected_row_id != int(
            steps["selected_candidate_row_id"][row]
        ):
            raise ValueError(f"Q_H selected candidate row id is inconsistent at state row {row}.")
        if not bool(facts["actor_action_mask"][selected]):
            raise ValueError(f"Q_H selected candidate is actor-invalid at state row {row}.")
        if not np.isclose(float(q_h["td_reward"][row]), float(facts["one_step_target_root_gain"][selected])):
            raise ValueError(f"Q_H selected reward is inconsistent at state row {row}.")
        if not np.isclose(float(q_h["td_reward_target_rri"][row]), float(facts["one_step_target_rri"][selected])):
            raise ValueError(f"Q_H selected target RRI is inconsistent at state row {row}.")

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

    return _QhRolloutChainFacts(
        state=_QhChainStateFacts(
            root_pose_world=_readonly(root_pose_world),
            target_extents=_readonly(target_extents),
            target_pose_world_object=_readonly(target_pose),
            candidate_pose_relative_root=tuple(facts["candidate_pose_relative_root"] for facts in candidate_rows),
            candidate_position_id=tuple(facts["candidate_position_id"] for facts in candidate_rows),
            actor_action_mask=tuple(facts["actor_action_mask"] for facts in candidate_rows),
            remaining_budget=_readonly(np.arange(horizon, 0, -1, dtype=np.int64)),
        ),
        supervision=_QhChainSupervisionFacts(
            candidate_row_id=tuple(facts["candidate_row_id"] for facts in candidate_rows),
            q_train_mask=tuple(facts["q_train_mask"] for facts in candidate_rows),
            invalid_reason_bitset=tuple(facts["invalid_reason_bitset"] for facts in candidate_rows),
            one_step_target_rri=tuple(facts["one_step_target_rri"] for facts in candidate_rows),
            one_step_target_root_gain=tuple(facts["one_step_target_root_gain"] for facts in candidate_rows),
            selected_candidate_index=_readonly(selected_index),
        ),
        transition=_QhChainTransitionFacts(
            discount=_readonly(discounts),
            terminal=_readonly(terminals),
        ),
        lineage=_QhChainLineage(
            source_row_id=source_row_id,
            source_sample_index=int(sources["sample_index"][source_row]),
            source_sample_key=_decode_id(root, dictionaries, "source_key", "sources/sample_key_id", source_row),
            source_shard_id=_decode_id(root, dictionaries, "source_shard", "sources/source_shard_id", source_row),
            source_shard_row=int(sources["source_shard_row"][source_row]),
            scene_id=_decode_id(root, dictionaries, "scene", "sources/scene_id", source_row),
            snippet_id=_decode_id(root, dictionaries, "snippet", "sources/snippet_id", source_row),
            split=Stage.from_str(_decode_id(root, dictionaries, "split", "sources/split_id", source_row)),
            source_cache_version=_decode_id(
                root, dictionaries, "config", "sources/source_cache_version_id", source_row
            ),
            source_offline_store_manifest_hash=_decode_id(
                root, dictionaries, "config", "sources/source_offline_store_manifest_hash_id", source_row
            ),
            split_manifest_hash=_decode_id(root, dictionaries, "config", "sources/split_manifest_hash_id", source_row),
            mesh_version=_decode_optional_id(root, dictionaries, "config", "lineage/mesh_version_id", rollout_position),
            target_row_id=target_row_id,
            target_sem_id=int(target["target_sem_id"][target_row]),
            target_inst_id=int(target["target_inst_id"][target_row]),
            target_protocol_version=str(root.attrs["target_protocol_version"]),
            target_source=target_source,
            target_crop_policy=_decode_optional_id(
                root, dictionaries, "config", "lineage/target_crop_policy_id", rollout_position
            ),
            schema_version=str(root.attrs["schema_version"]),
            reason_code_version=str(root.attrs["reason_code_version"]),
            return_semantics=str(root.attrs["return_semantics"]),
            td_semantics=str(q_h.attrs["td_semantics"]),
            reward_metric=str(q_h.attrs["reward_metric"]),
            discount_gamma=float(root.attrs["discount_gamma"]),
            horizon=horizon,
            rollout_row_id=entry.rollout_row_id,
            rollout_id=_decode_id(root, dictionaries, "rollout", "rollouts/rollout_id", rollout_position),
            chain_id=int(rollout["chain_id"][rollout_position]),
            root_time_ns=int(rollout["root_time_ns"][rollout_position]),
            root_trajectory_index=int(rollout["root_trajectory_index"][rollout_position]),
            root_frame_index=int(rollout["root_frame_index"][rollout_position]),
            policy=_decode_id(root, dictionaries, "policy", "rollouts/policy_id", rollout_position),
            branch_factor=int(rollout["branch_factor"][rollout_position]),
            beam_width=int(rollout["beam_width"][rollout_position]),
            temperature=float(rollout["temperature"][rollout_position]),
            random_seed=int(rollout["random_seed"][rollout_position]),
            termination_reason=_decode_id(
                root, dictionaries, "termination_reason", "rollouts/termination_reason", rollout_position
            ),
            candidate_config_hash=_decode_id(
                root, dictionaries, "config", "lineage/candidate_config_id", rollout_position
            ),
            oracle_config_hash=_decode_id(root, dictionaries, "config", "lineage/oracle_config_id", rollout_position),
            rollout_config_hash=_decode_id(root, dictionaries, "config", "lineage/rollout_config_id", rollout_position),
            model_checkpoint_hash=_decode_optional_id(
                root, dictionaries, "config", "lineage/model_checkpoint_id", rollout_position
            ),
            branch_schedule_id=_decode_optional_id(
                root, dictionaries, "config", "lineage/branch_schedule_id", rollout_position
            ),
            selection_rng_state_hash=_decode_optional_id(
                root, dictionaries, "config", "lineage/selection_rng_state_hash_id", rollout_position
            ),
        ),
    )


def _read_chain_candidate_row(root: zarr.Group, *, row: int, width: int) -> dict[str, np.ndarray]:
    q_h = root["q_h"]
    q_rows = {name: np.asarray(q_h[name][row, :width]) for name in _Q_H_MATRIX_NAMES}
    candidate_ids = q_rows["candidate_row_id"].astype(np.int64, copy=False)
    candidates = _candidate_slice(root, candidate_ids, row)
    _validate_materialized_qh_row(q_rows, candidates, width=width, row=row)
    return {
        "candidate_row_id": _readonly(candidate_ids),
        "candidate_pose_relative_root": _readonly(candidates["pose_relative_root"].astype(np.float32, copy=False)),
        "candidate_position_id": _readonly(q_rows["position_id"].astype(np.int32, copy=False)),
        "actor_action_mask": _readonly(q_rows["valid_action_mask"].astype(np.bool_, copy=False)),
        "q_train_mask": _readonly(q_rows["q_train_mask"].astype(np.bool_, copy=False)),
        "invalid_reason_bitset": _readonly(q_rows["invalid_reason_bitset"].astype(np.uint32, copy=False)),
        "one_step_target_rri": _readonly(q_rows["one_step_target_rri"].astype(np.float32, copy=False)),
        "one_step_target_root_gain": _readonly(q_rows["one_step_target_root_gain"].astype(np.float32, copy=False)),
    }


def _read_state(root: zarr.Group, store: _StoreMetadata, locator: QhStateLocator) -> QhRolloutState:
    row = locator.state_row
    q_h = root["q_h"]
    step = root["steps"]
    q_rows = {name: np.asarray(q_h[name][row]) for name in _Q_H_MATRIX_NAMES}
    q_candidate_ids = q_rows["candidate_row_id"].astype(np.int64, copy=False)
    width = int(np.count_nonzero(q_candidate_ids >= 0))
    candidate_ids = q_candidate_ids[:width]
    if width < 1 or np.any(q_candidate_ids[width:] != -1):
        raise ValueError(f"Q_H state row {row} must have a non-empty candidate shell with trailing -1 padding.")
    if width != int(step["num_candidates"][row]):
        raise ValueError(f"Q_H candidate width does not match steps/num_candidates at state row {row}.")
    candidates = _candidate_slice(root, candidate_ids, row)
    _validate_materialized_qh_row(q_rows, candidates, width=width, row=row)

    step_row_id = int(q_h["state_step_row_id"][row])
    if step_row_id != row or int(step["step_row_id"][row]) != row:
        raise ValueError(f"Q_H state row {row} no longer matches its dense step row id.")
    rollout_row_id = int(step["rollout_row_id"][row])
    step_index = int(step["step_index"][row])
    rollout = root["rollouts"]
    if rollout_row_id < 0 or rollout_row_id >= int(rollout["rollout_row_id"].shape[0]):
        raise ValueError(f"Q_H state row {row} references unknown rollout row {rollout_row_id}.")
    if int(rollout["rollout_row_id"][rollout_row_id]) != rollout_row_id:
        raise ValueError(f"Q_H rollout row id is not dense at state row {row}.")
    horizon = int(rollout["horizon"][rollout_row_id])
    if step_index < 0 or step_index >= horizon:
        raise ValueError(f"Q_H step_index={step_index} is outside horizon={horizon} at state row {row}.")
    root_pose_world = np.asarray(rollout["root_pose_world"][rollout_row_id], dtype=np.float32)
    if root_pose_world.shape != (12,) or not np.isfinite(root_pose_world).all():
        raise ValueError(f"Q_H state row {row} has an invalid persisted rollout root pose.")

    target_row_id = int(q_h["target_row_id"][row])
    source_row_id = int(q_h["source_row_id"][row])
    target = root["targets"]
    sources = root["sources"]
    if target_row_id < 0 or target_row_id >= int(target["target_row_id"].shape[0]):
        raise ValueError(f"Q_H state row {row} references unknown target row {target_row_id}.")
    if int(target["target_row_id"][target_row_id]) != target_row_id:
        raise ValueError(f"Q_H target row id is not dense at state row {row}.")
    if (
        int(rollout["source_row_id"][rollout_row_id]) != source_row_id
        or int(rollout["target_row_id"][rollout_row_id]) != target_row_id
    ):
        raise ValueError(f"Q_H state row {row} does not match its rollout source/target lineage.")
    source_row = _find_sorted_row(sources["source_row_id"], source_row_id, "sources/source_row_id")
    history = _selected_history(root, row=row, rollout_row_id=rollout_row_id, step_index=step_index)

    selected_index = int(q_h["selected_candidate_index"][row])
    selected_candidate_id = int(q_h["td_selected_candidate_row_id"][row])
    if selected_index < 0 or selected_index >= width or int(candidate_ids[selected_index]) != selected_candidate_id:
        raise ValueError(f"Q_H selected candidate linkage is invalid at state row {row}.")
    if selected_candidate_id != int(step["selected_candidate_row_id"][row]) or not bool(
        q_rows["valid_action_mask"][selected_index]
    ):
        raise ValueError(f"Q_H selected candidate is not the actor-valid step selection at state row {row}.")
    if not np.isclose(
        float(q_h["td_reward"][row]),
        float(q_rows["one_step_target_root_gain"][selected_index]),
        equal_nan=False,
    ):
        raise ValueError(f"Q_H TD reward does not match the selected target-root-gain at state row {row}.")
    if not np.isclose(
        float(q_h["td_reward_target_rri"][row]),
        float(q_rows["one_step_target_rri"][selected_index]),
        equal_nan=False,
    ):
        raise ValueError(f"Q_H TD diagnostic RRI does not match the selected label at state row {row}.")
    terminal = bool(q_h["td_terminal_mask"][row])
    next_step_row = int(q_h["td_next_step_row_id"][row])
    discount = float(q_h["td_discount"][row])
    next_state = None if terminal else QhStateLocator(locator.store_index, next_step_row)
    if terminal != (next_step_row < 0):
        raise ValueError(f"Q_H terminal/next linkage is inconsistent at state row {row}.")
    if terminal and discount != 0.0:
        raise ValueError(f"Q_H terminal transition has non-zero discount at state row {row}.")
    if not terminal and not np.isclose(discount, float(root.attrs["discount_gamma"])):
        raise ValueError(f"Q_H non-terminal discount does not match corpus metadata at state row {row}.")
    if next_state is not None:
        _validate_next_state(root, row=row, next_row=next_step_row, rollout_row_id=rollout_row_id)

    dictionaries = store.dictionaries
    target_source = _decoded(
        dictionaries["target_source"],
        int(target["target_source_id"][target_row_id]),
        "target source",
    )
    if target_source != ORACLE_GT_TARGET_SOURCE:
        raise ValueError(f"Q_H state row {row} does not use the canonical Oracle GT target source.")
    target_values = {
        "target_center_world": np.asarray(target["target_center_world"][target_row_id]),
        "target_extents": np.asarray(target["target_extents"][target_row_id]),
        "target_pose_world_object": np.asarray(target["target_pose_world_object"][target_row_id]),
        "target_relative_pose_reference_object": np.asarray(
            target["target_relative_pose_reference_object"][target_row_id]
        ),
    }
    for name, values in target_values.items():
        if not np.isfinite(values).all():
            raise ValueError(f"Q_H state row {row} has an incomplete canonical V0 descriptor field targets/{name}.")
    actor = QhActorState(
        candidate_row_id=_readonly(candidate_ids),
        candidate_pose_world_cam=_readonly(candidates["pose_world_cam"]),
        candidate_pose_relative_root=_readonly(candidates["pose_relative_root"]),
        candidate_position_id=_readonly(candidates["position_id"]),
        actor_action_mask=_readonly(candidates["actor_action_mask"]),
        root_pose_world=_readonly(root_pose_world),
        target_row_id=target_row_id,
        target_center_world=_readonly(target_values["target_center_world"]),
        target_extents=_readonly(target_values["target_extents"]),
        target_pose_world_object=_readonly(target_values["target_pose_world_object"]),
        target_relative_pose_reference_object=_readonly(target_values["target_relative_pose_reference_object"]),
        target_sem_id=int(target["target_sem_id"][target_row_id]),
        target_inst_id=int(target["target_inst_id"][target_row_id]),
        history_candidate_row_id=_readonly(history["candidate_row_id"]),
        history_pose_world_cam=_readonly(history["pose_world_cam"]),
        history_pose_relative_root=_readonly(history["pose_relative_root"]),
        history_position_id=_readonly(history["position_id"]),
        remaining_budget=horizon - step_index,
    )
    supervision = QhSupervision(
        q_train_mask=_readonly(q_rows["q_train_mask"].astype(np.bool_, copy=False)[:width]),
        invalid_reason_bitset=_readonly(q_rows["invalid_reason_bitset"].astype(np.uint32, copy=False)[:width]),
        one_step_target_rri=_readonly(q_rows["one_step_target_rri"].astype(np.float32, copy=False)[:width]),
        one_step_target_root_gain=_readonly(q_rows["one_step_target_root_gain"].astype(np.float32, copy=False)[:width]),
    )
    transition = QhTransition(
        selected_candidate_index=selected_index,
        selected_candidate_row_id=selected_candidate_id,
        reward=float(q_h["td_reward"][row]),
        reward_target_rri=float(q_h["td_reward_target_rri"][row]),
        discount=discount,
        terminal=terminal,
        next_state=next_state,
    )
    lineage = QhLineage(
        source_row_id=source_row_id,
        source_sample_index=int(sources["sample_index"][source_row]),
        source_sample_key=_decode_id(root, dictionaries, "source_key", "sources/sample_key_id", source_row),
        source_shard_id=_decode_id(root, dictionaries, "source_shard", "sources/source_shard_id", source_row),
        source_shard_row=int(sources["source_shard_row"][source_row]),
        scene_id=_decode_id(root, dictionaries, "scene", "sources/scene_id", source_row),
        snippet_id=_decode_id(root, dictionaries, "snippet", "sources/snippet_id", source_row),
        split=Stage.from_str(_decode_id(root, dictionaries, "split", "sources/split_id", source_row)),
        source_cache_version=_decode_id(root, dictionaries, "config", "sources/source_cache_version_id", source_row),
        source_offline_store_manifest_hash=_decode_id(
            root,
            dictionaries,
            "config",
            "sources/source_offline_store_manifest_hash_id",
            source_row,
        ),
        split_manifest_hash=_decode_id(root, dictionaries, "config", "sources/split_manifest_hash_id", source_row),
        target_protocol_version=str(root.attrs["target_protocol_version"]),
        target_source=target_source,
        schema_version=str(root.attrs["schema_version"]),
        reason_code_version=str(root.attrs["reason_code_version"]),
        return_semantics=str(root.attrs["return_semantics"]),
        td_semantics=str(q_h.attrs["td_semantics"]),
        reward_metric=str(q_h.attrs["reward_metric"]),
        discount_gamma=float(root.attrs["discount_gamma"]),
        horizon=horizon,
        rollout_row_id=rollout_row_id,
        rollout_id=_decode_id(root, dictionaries, "rollout", "rollouts/rollout_id", rollout_row_id),
        chain_id=int(rollout["chain_id"][rollout_row_id]),
        step_index=step_index,
        candidate_config_hash=_decode_id(root, dictionaries, "config", "lineage/candidate_config_id", rollout_row_id),
        oracle_config_hash=_decode_id(root, dictionaries, "config", "lineage/oracle_config_id", rollout_row_id),
        rollout_config_hash=_decode_id(root, dictionaries, "config", "lineage/rollout_config_id", rollout_row_id),
    )
    return QhRolloutState(locator, actor, supervision, transition, lineage)


def _candidate_slice(root: zarr.Group, candidate_ids: np.ndarray, state_row: int) -> dict[str, np.ndarray]:
    start, stop = _contiguous_candidate_bounds(candidate_ids, state_row)
    group = root["candidates"]
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
    if np.any(values["step_row_id"] != state_row):
        raise ValueError(f"Q_H candidate rows cross state ownership at state row {state_row}.")
    return values


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
    if valid_mask[width:].any() or train_mask[width:].any() or np.any(position_id[width:] != -1):
        raise ValueError(f"Q_H padded candidate slots have non-sentinel actor fields at state row {row}.")
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


def _selected_history(
    root: zarr.Group,
    *,
    row: int,
    rollout_row_id: int,
    step_index: int,
) -> dict[str, np.ndarray]:
    if step_index == 0:
        return {
            "candidate_row_id": np.empty((0,), dtype=np.int64),
            "pose_world_cam": np.empty((0, 12), dtype=np.float32),
            "pose_relative_root": np.empty((0, 12), dtype=np.float32),
            "position_id": np.empty((0,), dtype=np.int32),
        }
    start = row - step_index
    if start < 0:
        raise ValueError(f"Q_H history underflows the state axis at row {row}.")
    step = root["steps"]
    history_rollouts = np.asarray(step["rollout_row_id"][start:row], dtype=np.int64)
    history_indices = np.asarray(step["step_index"][start:row], dtype=np.int64)
    if np.any(history_rollouts != rollout_row_id) or not np.array_equal(
        history_indices, np.arange(step_index, dtype=np.int64)
    ):
        raise ValueError(f"Q_H actor history is not a contiguous rollout prefix at row {row}.")
    candidate_ids = np.asarray(step["selected_candidate_row_id"][start:row], dtype=np.int64)
    candidate_group = root["candidates"]
    return {
        "candidate_row_id": candidate_ids,
        "pose_world_cam": np.asarray(candidate_group["pose_world_cam"].oindex[candidate_ids]),
        "pose_relative_root": np.asarray(candidate_group["pose_relative_root"].oindex[candidate_ids]),
        "position_id": np.asarray(candidate_group["position_id"].oindex[candidate_ids]),
    }


def _validate_next_state(root: zarr.Group, *, row: int, next_row: int, rollout_row_id: int) -> None:
    state_count = int(root["q_h/state_step_row_id"].shape[0])
    if next_row != row + 1 or next_row >= state_count:
        raise ValueError(f"Q_H next-state linkage is not the adjacent rollout state at row {row}.")
    if int(root["steps/rollout_row_id"][next_row]) != rollout_row_id:
        raise ValueError(f"Q_H next-state linkage crosses rollout ownership at row {row}.")
    if int(root["steps/step_index"][next_row]) != int(root["steps/step_index"][row]) + 1:
        raise ValueError(f"Q_H next-state linkage skips the next rollout step at row {row}.")


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
    "QhActorState",
    "QhLineage",
    "QhRolloutReader",
    "QhRolloutReaderConfig",
    "QhRolloutState",
    "QhStateLocator",
    "QhSupervision",
    "QhTransition",
]
