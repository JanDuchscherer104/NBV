"""Bounded reader for validated finite-candidate ``Q_H`` rollout chains.

Persisted integrity belongs to :mod:`zarr_store`; tensor and actor-store
composition belongs to :mod:`aria_nbv.data_handling.qh_data`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import numpy as np
import zarr
from zarr.storage import LocalStore

from ..targets.protocol import (
    ORACLE_GT_TARGET_SOURCE,
    ActorVisibleTargetSource,
    TargetInputProtocol,
    TargetLabelEvidence,
    target_label_is_trainable,
    validate_target_protocol_admission,
)
from ..utils import Stage
from .shard_manifest import build_rollout_split_manifest_hash
from .zarr_store import DEFAULT_RETURN_SEMANTICS, RolloutZarrStoreReader


@dataclass(frozen=True, slots=True)
class _QhSourceRef:
    source_sample_index: int
    source_sample_key: str
    source_shard_id: str
    source_shard_row: int
    scene_id: str
    snippet_id: str
    split: Stage
    actor_store_version: str
    source_manifest_hash: str
    split_manifest_hash: str
    campaign_split: Stage | None = None


@dataclass(frozen=True, slots=True)
class _StoredChain:
    root_pose_world: np.ndarray
    target_extents: np.ndarray
    target_pose_world_object: np.ndarray
    candidate_pose_relative_root: tuple[np.ndarray, ...]
    action_mask: tuple[np.ndarray, ...]
    horizon_remaining: np.ndarray
    label_mask: tuple[np.ndarray, ...]
    candidate_reward: tuple[np.ndarray, ...]
    selected_index: np.ndarray
    discount: np.ndarray
    terminal: np.ndarray
    store_index: int
    rollout_row_id: int
    target_row_id: int
    source_ref: _QhSourceRef


@dataclass(frozen=True, slots=True)
class QhDataContract:
    """Horizon- and provenance-independent reader/data compatibility."""

    schema_version: str
    target_protocol: str
    reward_metric: str
    return_semantics: str
    td_semantics: str
    discount_gamma: float
    reason_code_version: str
    actor_store_version: str


@dataclass(frozen=True, slots=True)
class _StoreFacts:
    path: Path
    manifest_hash: str
    state_count: int
    contract: QhDataContract
    max_horizon: int
    chains: tuple[_ChainRef, ...]
    source_refs: tuple[_QhSourceRef, ...]


@dataclass(frozen=True, slots=True)
class _ChainRef:
    store_index: int
    rollout_position: int
    rollout_row_id: int
    state_start: int
    state_stop: int
    target_position: int
    target_row_id: int
    source_sample_index: int


class QhRolloutReader:
    """Read compatible validated stores through bounded chain slices."""

    def __init__(
        self,
        store_dirs: tuple[str | Path, ...],
        *,
        campaign_split: Stage | str | None = None,
    ) -> None:
        """Open compatible stores, optionally selecting one learning split.

        ``campaign_split`` selects the persisted campaign/learning assignment.
        Legacy stores without that field fall back to their physical source
        split for filtering; the physical split remains available on every
        admitted source reference for immutable VIN lineage validation.
        """
        campaign_split = _normalize_campaign_split(campaign_split)
        paths = tuple(Path(path).expanduser().resolve() for path in store_dirs)
        if not paths:
            raise ValueError("Q_H rollout reader requires at least one store.")
        if len(set(paths)) != len(paths):
            raise ValueError("Q_H rollout store paths must be unique.")

        self.store_dirs = paths
        self.campaign_split = campaign_split
        self._stores = tuple(_preflight_store(path, store_index) for store_index, path in enumerate(paths))
        _validate_homogeneous(self._stores)
        source_ref_lookup = _merge_source_refs(self._stores)
        self._chains = tuple(
            chain
            for store in self._stores
            for chain in store.chains
            if _matches_campaign_split(source_ref_lookup[chain.source_sample_index], campaign_split)
        )
        admitted_sample_indices = {chain.source_sample_index for chain in self._chains}
        self._source_ref_lookup = {
            sample_index: source_ref
            for sample_index, source_ref in source_ref_lookup.items()
            if sample_index in admitted_sample_indices
        }
        self._source_refs = tuple(self._source_ref_lookup.values())
        self._scenes = frozenset(source.scene_id for source in self._source_refs)
        self._open_pid: int | None = None
        self._roots: dict[int, zarr.Group] = {}

    def __len__(self) -> int:
        """Return the number of complete persisted chains."""
        return len(self._chains)

    def __getitem__(self, index: int) -> _StoredChain:
        """Decode one validated chain through bounded Zarr slices."""
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(f"Q_H chain index {index} is outside corpus length {len(self)}.")
        chain = self._chains[index]
        return _read_chain(
            self._root(chain.store_index),
            chain,
            self._source_ref_lookup[chain.source_sample_index],
        )

    @property
    def source_refs(self) -> tuple[_QhSourceRef, ...]:
        """Return unique private source identities admitted during preflight."""
        return self._source_refs

    @property
    def scenes(self) -> frozenset[str]:
        """Return scenes referenced by the admitted source identities."""
        return self._scenes

    @property
    def max_horizon(self) -> int:
        """Return the largest realized chain length among admitted chains."""
        return max((chain.state_stop - chain.state_start for chain in self._chains), default=0)

    @property
    def contract(self) -> QhDataContract:
        """Return the common horizon-independent learning contract."""
        return self._stores[0].contract

    @property
    def provenance(self) -> dict[str, object]:
        """Return preflighted corpus identity without reopening stores."""
        return {
            "stores": [
                {
                    "path": str(store.path),
                    "manifest_sha256": store.manifest_hash,
                    "state_count": sum(
                        chain.state_stop - chain.state_start
                        for chain in self._chains
                        if chain.store_index == store_index
                    ),
                }
                for store_index, store in enumerate(self._stores)
            ],
            "contract": self.contract,
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


def _preflight_store(path: Path, store_index: int) -> _StoreFacts:
    if not path.is_dir():
        raise ValueError(f"Q_H rollout store does not exist: {path}.")

    reader = RolloutZarrStoreReader(path)
    validation = reader.validate()
    if not validation.ok:
        details = "; ".join(validation.errors[:5])
        raise ValueError(
            f"Q_H rollout store {path} failed canonical validation with {len(validation.errors)} error(s): {details}"
        )

    root = reader.root
    _validate_reader_admission(root)
    source_refs_by_row = _read_source_refs(root, path)
    chains = _read_chain_refs(root, path, store_index, source_refs_by_row)
    contract = _read_contract(root)
    return _StoreFacts(
        path=path,
        manifest_hash=str(root.attrs["manifest_sha256"]),
        state_count=validation.num_steps,
        contract=contract,
        max_horizon=max(chain.state_stop - chain.state_start for chain in chains),
        chains=chains,
        source_refs=tuple(source_refs_by_row.values()),
    )


def _normalize_campaign_split(value: Stage | str | None) -> Stage | None:
    """Normalize a configured campaign split, treating ``all`` as unfiltered."""

    return None if value is None or value == "all" else Stage.from_str(value)


def _matches_campaign_split(source_ref: _QhSourceRef, campaign_split: Stage | None) -> bool:
    """Return whether a source belongs to the requested campaign split."""

    return campaign_split is None or (source_ref.campaign_split or source_ref.split) == campaign_split


def _validate_reader_admission(root: zarr.Group) -> None:
    target_source = _decode_dictionary(root, "target_source")
    protocol = TargetInputProtocol(root.attrs.get("target_protocol_version", ""))
    if protocol is TargetInputProtocol.V0_GT_INPUT:
        if set(target_source) != {ORACLE_GT_TARGET_SOURCE}:
            raise ValueError(
                "v0_gt_input requires the target-source dictionary to contain only the canonical Oracle GT source; "
                f"found {sorted(target_source)}."
            )
        validate_target_protocol_admission(protocol, target_source=ORACLE_GT_TARGET_SOURCE)
    else:
        if (
            len(target_source) != 1
            or not target_source[0]
            or target_source[0] == ORACLE_GT_TARGET_SOURCE
            or target_source[0] not in {source.value for source in ActorVisibleTargetSource}
        ):
            raise ValueError(
                f"v1_observed requires exactly one non-Oracle actor-visible target source; found {target_source!r}."
            )
        # The fixed store schema persists the self-consistent actor-visible
        # source, while writer/config admission owns the stronger descriptor
        # provenance check before this artifact can exist.
    _validate_target_labels(root, protocol, target_source)
    if root.attrs.get("return_semantics") != DEFAULT_RETURN_SEMANTICS:
        raise ValueError(f"Q_H rollout reader requires {DEFAULT_RETURN_SEMANTICS!r} return semantics.")


def _validate_target_labels(
    root: zarr.Group,
    protocol: TargetInputProtocol,
    target_sources: tuple[str, ...],
) -> None:
    """Reject stores whose persisted target mask disagrees with typed evidence."""

    target = root["targets"]
    target_ids = _decode_dictionary(root, "target")
    match_statuses = _decode_dictionary(root, "target_match_status")
    descriptor_sources = _decode_dictionary(root, "descriptor_source")
    descriptor_provenances = _decode_dictionary(root, "descriptor_provenance")
    descriptor_hashes = _decode_dictionary(root, "descriptor_hash")
    explicit_target_hashes = _decode_dictionary(root, "explicit_target_hash")
    source_ids = np.asarray(target["target_source_id"], dtype=np.int64).reshape(-1)
    target_rows = np.asarray(target["target_row_id"]).reshape(-1)
    target_valid = np.asarray(target["target_valid_mask"], dtype=np.bool_).reshape(-1)
    target_reason = np.asarray(target["target_invalid_reason_bitset"], dtype=np.uint32).reshape(-1)
    if source_ids.shape != target_rows.shape:
        raise ValueError("targets/target_source_id must have one value per target row.")
    for row, encoded_id in enumerate(np.asarray(target["matched_gt_target_id"]).reshape(-1)):
        source_id = int(source_ids[row])
        if source_id < 0 or source_id >= len(target_sources):
            raise ValueError(f"targets/target_source_id row {row} is outside the target-source dictionary.")
        target_source = target_sources[source_id]
        if protocol is TargetInputProtocol.V0_GT_INPUT and target_source != ORACLE_GT_TARGET_SOURCE:
            raise ValueError(f"targets/target_source_id row {row} is not the canonical Oracle GT source.")
        if protocol is TargetInputProtocol.V1_OBSERVED and target_source not in {
            source.value for source in ActorVisibleTargetSource
        }:
            raise ValueError(f"targets/target_source_id row {row} is not an actor-visible target source.")
        match_id = ""
        if 0 <= int(encoded_id) < len(target_ids):
            match_id = target_ids[int(encoded_id)]
        status_id = int(np.asarray(target["gt_match_status_id"]).reshape(-1)[row])
        status = match_statuses[status_id] if 0 <= status_id < len(match_statuses) else ""
        expected = target_label_is_trainable(
            TargetLabelEvidence(
                protocol=protocol,
                target_source=target_source,
                gt_match_status=status,
                matched_gt_target_row_id=int(np.asarray(target["matched_gt_target_row_id"]).reshape(-1)[row]),
                matched_gt_target_id=match_id,
                gt_match_iou=float(np.asarray(target["gt_match_iou"]).reshape(-1)[row]),
                descriptor_source=descriptor_sources[int(np.asarray(target["descriptor_source_id"]).reshape(-1)[row])],
                descriptor_provenance=descriptor_provenances[
                    int(np.asarray(target["descriptor_provenance_id"]).reshape(-1)[row])
                ],
                descriptor_hash=descriptor_hashes[int(np.asarray(target["descriptor_hash_id"]).reshape(-1)[row])],
                explicit_target_hash=explicit_target_hashes[
                    int(np.asarray(target["explicit_target_hash_id"]).reshape(-1)[row])
                ],
                target_valid=bool(target_valid[row] and target_reason[row] == 1),
            )
        )
        actual = bool(np.asarray(target["gt_label_valid_mask"]).reshape(-1)[row])
        if actual != expected:
            raise ValueError(f"targets/gt_label_valid_mask row {row} disagrees with canonical target evidence.")


def _read_contract(root: zarr.Group) -> QhDataContract:
    q_h = root["q_h"]
    return QhDataContract(
        schema_version=str(root.attrs["schema_version"]),
        target_protocol=str(root.attrs["target_protocol_version"]),
        reward_metric=str(q_h.attrs["reward_metric"]),
        return_semantics=str(root.attrs["return_semantics"]),
        td_semantics=str(q_h.attrs["td_semantics"]),
        discount_gamma=float(root.attrs["discount_gamma"]),
        reason_code_version=str(root.attrs["reason_code_version"]),
        actor_store_version=str(root.attrs["source_offline_store_version"]),
    )


def _read_source_refs(root: zarr.Group, path: Path) -> dict[int, _QhSourceRef]:
    dictionaries = {
        name: _decode_dictionary(root, name)
        for name in ("config", "scene", "snippet", "source_key", "source_shard", "split")
    }
    sources = root["sources"]
    if not isinstance(sources, zarr.Group):
        raise ValueError(f"Q_H store {path} sources node must be a group.")

    def decode(dictionary_name: str, array_name: str, row: int) -> str:
        value_id = int(sources[array_name][row])
        dictionary = dictionaries[dictionary_name]
        if value_id < 0 or value_id >= len(dictionary):
            raise ValueError(f"Q_H sources/{array_name} dictionary id {value_id} is out of range.")
        return dictionary[value_id]

    source_ids = np.asarray(sources["source_row_id"], dtype=np.int64).reshape(-1)
    source_array_names = tuple(sources.array_keys())
    has_campaign_split = "campaign_split_id" in source_array_names

    def decode_campaign_split(row: int) -> Stage | None:
        if not has_campaign_split:
            return None
        value = decode("split", "campaign_split_id", row)
        if value == "unknown":
            return None
        # Campaign plans use the canonical dataset spelling ``validation``;
        # Stage's public value remains ``val`` at the reader boundary.
        return Stage.VAL if value == "validation" else Stage.from_str(value)

    refs = {
        int(source_id): _QhSourceRef(
            source_sample_index=int(sources["sample_index"][row]),
            source_sample_key=decode("source_key", "sample_key_id", row),
            source_shard_id=decode("source_shard", "source_shard_id", row),
            source_shard_row=int(sources["source_shard_row"][row]),
            scene_id=decode("scene", "scene_id", row),
            snippet_id=decode("snippet", "snippet_id", row),
            split=Stage.from_str(decode("split", "split_id", row)),
            campaign_split=decode_campaign_split(row),
            actor_store_version=decode("config", "source_cache_version_id", row),
            source_manifest_hash=decode("config", "source_offline_store_manifest_hash_id", row),
            split_manifest_hash=decode("config", "split_manifest_hash_id", row),
        )
        for row, source_id in enumerate(source_ids)
    }
    expected_hash = str(root.attrs["split_manifest_hash"])
    mismatched = [source_id for source_id, source in refs.items() if source.split_manifest_hash != expected_hash]
    if mismatched:
        raise ValueError(f"Q_H store {path} source rows {mismatched} do not match root split_manifest_hash.")
    ordered = [refs[int(source_id)] for source_id in source_ids]
    if not any(source.campaign_split is not None for source in ordered):
        return refs
    actual_hash = build_rollout_split_manifest_hash(
        source_manifest_hash=ordered[0].source_manifest_hash if ordered else "",
        split=_hash_physical_split_value(ordered[0].split) if ordered else "",
        records=[
            {
                "order": order,
                "sample_index": source.source_sample_index,
                "sample_key": source.source_sample_key,
                "scene_id": source.scene_id,
                "snippet_id": source.snippet_id,
                "split": _hash_physical_split_value(source.split),
                "source_shard_id": source.source_shard_id,
                "source_shard_row": source.source_shard_row,
                **(
                    {"campaign_split": _hash_campaign_split_value(source.campaign_split)}
                    if source.campaign_split
                    else {}
                ),
            }
            for order, source in enumerate(ordered)
        ],
    )
    if actual_hash != expected_hash:
        raise ValueError(f"Q_H store {path} source rows do not reproduce root split_manifest_hash.")
    return refs


def _hash_physical_split_value(value: Stage | None) -> str:
    """Return the physical VIN split spelling used by source manifests."""

    return "" if value is None else value.value


def _hash_campaign_split_value(value: Stage | None) -> str:
    """Return the campaign split spelling used by campaign manifests."""

    if value is Stage.VAL:
        return "validation"
    return "" if value is None else value.value


def _read_chain_refs(
    root: zarr.Group,
    path: Path,
    store_index: int,
    source_refs_by_row: dict[int, _QhSourceRef],
) -> tuple[_ChainRef, ...]:
    rollout = root["rollouts"]
    horizons = np.asarray(rollout["horizon"], dtype=np.int64).reshape(-1)
    if horizons.size == 0:
        raise ValueError(f"Q_H rollout store contains no rollout chains: {path}.")
    candidate_widths = np.asarray(root["steps/num_candidates"], dtype=np.int64).reshape(-1)
    if np.any(candidate_widths < 1):
        raise ValueError(f"Q_H store {path} contains an empty candidate state.")
    rollout_ids = np.asarray(rollout["rollout_row_id"], dtype=np.int64).reshape(-1)
    step_rollout_ids = np.asarray(root["steps/rollout_row_id"], dtype=np.int64).reshape(-1)
    step_indices = np.asarray(root["steps/step_index"], dtype=np.int64).reshape(-1)
    source_ids = np.asarray(rollout["source_row_id"], dtype=np.int64).reshape(-1)
    target_ids = np.asarray(rollout["target_row_id"], dtype=np.int64).reshape(-1)
    target_positions = {
        int(target_id): position
        for position, target_id in enumerate(np.asarray(root["targets/target_row_id"], dtype=np.int64).reshape(-1))
    }
    chains: list[_ChainRef] = []
    state_start = 0
    for position, (horizon, rollout_id, source_id, target_id) in enumerate(
        zip(horizons, rollout_ids, source_ids, target_ids, strict=True)
    ):
        if state_start >= step_rollout_ids.size or int(step_rollout_ids[state_start]) != int(rollout_id):
            raise ValueError(
                f"Q_H store {path} rollout_row_id={int(rollout_id)} does not own one ordered factual step run."
            )
        state_stop = state_start
        while state_stop < step_rollout_ids.size and int(step_rollout_ids[state_stop]) == int(rollout_id):
            state_stop += 1
        factual_indices = step_indices[state_start:state_stop]
        expected_indices = np.arange(state_stop - state_start, dtype=np.int64)
        if not np.array_equal(factual_indices, expected_indices):
            raise ValueError(
                f"Q_H store {path} rollout_row_id={int(rollout_id)} has non-contiguous factual step_index values."
            )
        if state_stop - state_start > int(horizon):
            raise ValueError(
                f"Q_H store {path} rollout_row_id={int(rollout_id)} has more factual steps than its configured horizon."
            )
        source_ref = source_refs_by_row[int(source_id)]
        chains.append(
            _ChainRef(
                store_index=store_index,
                rollout_position=position,
                rollout_row_id=int(rollout_id),
                state_start=state_start,
                state_stop=state_stop,
                target_position=target_positions[int(target_id)],
                target_row_id=int(target_id),
                source_sample_index=source_ref.source_sample_index,
            )
        )
        state_start = state_stop
    if state_start != step_rollout_ids.size:
        raise ValueError(f"Q_H store {path} contains orphaned factual steps after the rollout table.")
    return tuple(chains)


def _merge_source_refs(stores: tuple[_StoreFacts, ...]) -> dict[int, _QhSourceRef]:
    lookup: dict[int, _QhSourceRef] = {}
    for source_ref in (source for store in stores for source in store.source_refs):
        existing = lookup.setdefault(source_ref.source_sample_index, source_ref)
        if existing != source_ref:
            raise ValueError(
                "Q_H rollout stores contain conflicting source identity for "
                f"sample_index={source_ref.source_sample_index}."
            )
    return lookup


def _validate_homogeneous(stores: tuple[_StoreFacts, ...]) -> None:
    expected = stores[0].contract
    for store in stores[1:]:
        if store.contract == expected:
            continue
        mismatches = [
            field.name
            for field in fields(QhDataContract)
            if getattr(expected, field.name) != getattr(store.contract, field.name)
        ]
        raise ValueError(f"Q_H rollout stores are heterogeneous at {store.path}: incompatible {', '.join(mismatches)}.")


def _read_chain(root: zarr.Group, chain: _ChainRef, source_ref: _QhSourceRef) -> _StoredChain:
    rows = slice(chain.state_start, chain.state_stop)
    q_h = root["q_h"]
    step_indices = np.asarray(root["steps/step_index"][rows], dtype=np.int64)
    configured_horizon = int(root["rollouts/horizon"][chain.rollout_position])
    candidate_ids = np.asarray(q_h["candidate_row_id"][rows], dtype=np.int64)
    widths = np.count_nonzero(candidate_ids >= 0, axis=1)
    root_pose = np.asarray(root["rollouts/root_pose_world"][chain.rollout_position], dtype=np.float32)
    candidate_poses = tuple(
        _read_candidate_poses(root, ids[:width]) for ids, width in zip(candidate_ids, widths, strict=True)
    )
    target = root["targets"]
    target_extents = np.asarray(target["target_extents"][chain.target_position], dtype=np.float32)
    target_pose = np.asarray(target["target_pose_world_object"][chain.target_position], dtype=np.float32)
    if not (np.isfinite(target_extents).all() and np.isfinite(target_pose).all()):
        raise ValueError(f"Q_H rollout_row_id={chain.rollout_row_id} has an incomplete canonical V0 descriptor.")

    return _StoredChain(
        root_pose_world=_readonly(root_pose),
        target_extents=_readonly(target_extents),
        target_pose_world_object=_readonly(target_pose),
        candidate_pose_relative_root=candidate_poses,
        action_mask=_trim_rows(q_h["valid_action_mask"][rows], widths, np.bool_),
        horizon_remaining=_readonly(configured_horizon - step_indices),
        label_mask=_trim_rows(q_h["q_train_mask"][rows], widths, np.bool_),
        candidate_reward=_trim_rows(q_h["one_step_target_root_gain"][rows], widths, np.float32),
        selected_index=_readonly(np.asarray(q_h["selected_candidate_index"][rows], dtype=np.int64)),
        discount=_readonly(np.asarray(q_h["td_discount"][rows], dtype=np.float32)),
        terminal=_readonly(np.asarray(q_h["td_terminal_mask"][rows], dtype=np.bool_)),
        store_index=chain.store_index,
        rollout_row_id=chain.rollout_row_id,
        target_row_id=chain.target_row_id,
        source_ref=source_ref,
    )


def _read_candidate_poses(
    root: zarr.Group,
    candidate_ids: np.ndarray,
) -> np.ndarray:
    candidates = root["candidates"]
    start = _find_sorted_row(candidates["candidate_row_id"], int(candidate_ids[0]))
    rows = slice(start, start + len(candidate_ids))
    relative = np.asarray(candidates["pose_relative_root"][rows], dtype=np.float32)
    return _readonly(relative)


def _trim_rows(values: Any, widths: np.ndarray, dtype: np.dtype[Any]) -> tuple[np.ndarray, ...]:
    array = np.asarray(values, dtype=dtype)
    return tuple(_readonly(row[:width]) for row, width in zip(array, widths, strict=True))


def _decode_dictionary(root: zarr.Group, name: str) -> tuple[str, ...]:
    encoded = np.asarray(root[f"dictionaries/{name}"], dtype=np.uint8)
    values = json.loads(encoded.tobytes().decode("utf-8"))
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError(f"Q_H dictionary {name!r} is malformed.")
    return tuple(values)


def _find_sorted_row(array: zarr.Array, value: int) -> int:
    low = 0
    high = int(array.shape[0])
    while low < high:
        middle = (low + high) // 2
        if int(array[middle]) < value:
            low = middle + 1
        else:
            high = middle
    if low >= int(array.shape[0]) or int(array[low]) != value:
        raise ValueError(f"Q_H candidate id {value} is missing from candidates/candidate_row_id.")
    return low


def _readonly(values: Any) -> np.ndarray:
    array = np.asarray(values)
    array.setflags(write=False)
    return array


__all__ = ["QhDataContract", "QhRolloutReader"]
