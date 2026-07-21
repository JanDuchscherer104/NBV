"""Derived scene-state/target/candidate views over normalized rollout rows.

This module does not own persistence.  It groups factual decision rows only
when callers provide the same exact reconstruction-state fingerprint, and it
deduplicates target-independent candidate acquisition by exact float32 pose
bits.
"""

from __future__ import annotations

import hashlib
import math
import struct
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

import torch
from efm3d.aria.pose import PoseTW
from torch import Tensor

from ..rollouts.read_model import rollout_at, rollout_steps, target_rows

if TYPE_CHECKING:
    from ..rollouts.zarr_store import RolloutZarrStoreReader

EntityId = int | str
Pose = tuple[float, ...]
PoseKey = tuple[int, ...]
_ACTOR_TARGET_SOURCES = frozenset({"detected_obbs_actor", "evl_obbs_actor"})


@dataclass(frozen=True, slots=True)
class ActorTargetQuery:
    """Actor-visible target geometry supplied independently of Oracle labels."""

    target_row_id: int
    pose_world_object: Sequence[float]
    extents_m: Sequence[float]
    objective: float = 0.0

    def __post_init__(self) -> None:
        exact_pose_key(self.pose_world_object)
        extents = tuple(float(value) for value in self.extents_m)
        if len(extents) != 3 or not all(math.isfinite(value) and value > 0.0 for value in extents):
            raise ValueError("actor target extents must contain three finite positive values")
        if not math.isfinite(self.objective):
            raise ValueError("actor target objective must be finite")


@dataclass(frozen=True, slots=True)
class NormalizedDecisionRow:
    """One factual ``[scene-state, target, candidate]`` decision row."""

    scene_id: str
    source_row_id: int
    state_fingerprint: str
    target_id: EntityId
    candidate_id: int
    candidate_pose_world: Sequence[float]
    target_utility: float
    actor_action_mask: bool
    oracle_label_mask: bool


@dataclass(frozen=True, slots=True)
class AcquisitionKey:
    """Exact key for one target-independent candidate render/fusion."""

    scene_id: str
    state_fingerprint: str
    candidate_pose_key: PoseKey


@dataclass(frozen=True, slots=True)
class GroupedDecisionView:
    """One exact scene-state with target rows over a deduplicated pose union."""

    scene_id: str
    state_fingerprint: str
    source_row_ids: tuple[int, ...]
    target_ids: tuple[EntityId, ...]
    candidate_poses_world: tuple[Pose, ...]
    candidate_ids: tuple[tuple[int | None, ...], ...]
    target_utilities: tuple[tuple[float, ...], ...]
    actor_action_mask: tuple[tuple[bool, ...], ...]
    utility_mask: tuple[tuple[bool, ...], ...]
    acquisition_keys: tuple[AcquisitionKey, ...]

    @property
    def candidate_set_key(self) -> tuple[PoseKey, ...]:
        """Return an order-independent exact candidate-pose set key."""

        return tuple(sorted(key.candidate_pose_key for key in self.acquisition_keys))

    @property
    def later_rollout_share_key(self) -> tuple[str, str, tuple[PoseKey, ...]]:
        """Require identical scene, reconstruction state, and candidate set."""

        return self.scene_id, self.state_fingerprint, self.candidate_set_key


@dataclass(frozen=True, slots=True)
class GroupedRolloutTrainingBatch:
    """One persisted scene-state packed as target/candidate training tensors."""

    scene_id: str
    snippet_id: str
    split: str
    source_row_id: int
    state_fingerprint: str
    step_index: int
    target_row_ids: tuple[int, ...]
    targets_world_query: Tensor
    target_features: Tensor
    candidates_world_camera: Tensor
    target_utilities: Tensor
    pair_valid: Tensor

    def __post_init__(self) -> None:
        targets = len(self.target_row_ids)
        if self.targets_world_query.shape != (1, targets, 3, 4):
            raise ValueError("targets_world_query must have shape [1,T,3,4]")
        if self.target_features.shape != (1, targets, 4):
            raise ValueError("target_features must have shape [1,T,4]")
        if self.candidates_world_camera.ndim != 4 or self.candidates_world_camera.shape[:1] != (1,):
            raise ValueError("candidates_world_camera must have shape [1,C,3,4]")
        if self.candidates_world_camera.shape[-2:] != (3, 4):
            raise ValueError("candidates_world_camera must have shape [1,C,3,4]")
        pair_shape = (1, targets, self.candidates_world_camera.shape[1])
        if self.target_utilities.shape != pair_shape or self.pair_valid.shape != pair_shape:
            raise ValueError("target_utilities and pair_valid must have shape [1,T,C]")
        if self.pair_valid.dtype is not torch.bool:
            raise TypeError("pair_valid must be bool")

    def to(self, device: torch.device | str) -> Self:
        """Move only tensor payloads while preserving exact persisted identities."""

        return type(self)(
            scene_id=self.scene_id,
            snippet_id=self.snippet_id,
            split=self.split,
            source_row_id=self.source_row_id,
            state_fingerprint=self.state_fingerprint,
            step_index=self.step_index,
            target_row_ids=self.target_row_ids,
            targets_world_query=self.targets_world_query.to(device),
            target_features=self.target_features.to(device),
            candidates_world_camera=self.candidates_world_camera.to(device),
            target_utilities=self.target_utilities.to(device),
            pair_valid=self.pair_valid.to(device),
        )

    def ordinal_labels(self, boundaries: Tensor) -> Tensor:
        """Bin finite utilities for CORAL while leaving invalid pairs masked."""

        if boundaries.ndim != 1 or boundaries.numel() == 0:
            raise ValueError("boundaries must be a non-empty one-dimensional tensor")
        if torch.any(boundaries[1:] <= boundaries[:-1]).item():
            raise ValueError("boundaries must be strictly increasing")
        values = torch.nan_to_num(self.target_utilities, nan=0.0)
        return torch.bucketize(values, boundaries.to(values))


def exact_pose_key(pose_world_cam: Sequence[float]) -> PoseKey:
    """Encode one 12-value PoseTW row as stable, exact float32 bits."""

    values = tuple(float(value) for value in pose_world_cam)
    if len(values) != 12 or not all(math.isfinite(value) for value in values):
        raise ValueError("candidate_pose_world must contain 12 finite values.")
    try:
        return struct.unpack("!12I", struct.pack("!12f", *values))
    except (OverflowError, struct.error) as error:
        raise ValueError("candidate_pose_world values must be representable as float32.") from error


def acquisition_key(scene_id: str, state_fingerprint: str, pose_world_cam: Sequence[float]) -> AcquisitionKey:
    """Build the exact ``(scene, state fingerprint, candidate pose)`` key."""

    if not scene_id or not state_fingerprint:
        raise ValueError("scene_id and state_fingerprint must be non-empty.")
    return AcquisitionKey(scene_id, state_fingerprint, exact_pose_key(pose_world_cam))


def group_decision_rows(rows: Iterable[NormalizedDecisionRow]) -> tuple[GroupedDecisionView, ...]:
    """Group normalized rows by exact scene-state and deduplicate pose acquisition."""

    grouped: dict[tuple[str, str], list[NormalizedDecisionRow]] = {}
    for row in rows:
        if not row.state_fingerprint:
            raise ValueError("state_fingerprint must be non-empty.")
        grouped.setdefault((row.scene_id, row.state_fingerprint), []).append(row)
    return tuple(
        _group_state(scene_id, fingerprint, state_rows)
        for (scene_id, fingerprint), state_rows in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1]))
    )


def can_share_later_rollout(left: GroupedDecisionView, right: GroupedDecisionView) -> bool:
    """Return whether later-step acquisition is exactly reusable."""

    return left.later_rollout_share_key == right.later_rollout_share_key


def grouped_rollout_training_batches(
    reader: RolloutZarrStoreReader,
    *,
    actor_targets: Mapping[int, ActorTargetQuery] | None = None,
    max_candidates_per_state: int | None = None,
) -> tuple[GroupedRolloutTrainingBatch, ...]:
    """Derive multi-target batches from canonical rollout rows without schema duplication."""

    if max_candidates_per_state is not None and max_candidates_per_state < 1:
        raise ValueError("max_candidates_per_state must be a positive integer.")

    persisted_targets = {target.target_row_id: target for target in target_rows(reader)}
    actor_queries = dict(actor_targets or {})
    for target_row_id, target in persisted_targets.items():
        if target_row_id in actor_queries:
            continue
        if target.source not in _ACTOR_TARGET_SOURCES:
            raise ValueError(
                f"target row {target_row_id} comes from non-actor source {target.source!r}; "
                "an explicit ActorTargetQuery is required",
            )
        actor_queries[target_row_id] = ActorTargetQuery(
            target_row_id=target_row_id,
            pose_world_object=tuple(float(value) for value in target.pose_world_object),
            extents_m=tuple(float(value) for value in target.extents),
            objective=target.deficit_score if math.isfinite(target.deficit_score) else 0.0,
        )
    normalized: dict[tuple[str, str, int, PoseKey], NormalizedDecisionRow] = {}
    state_context: dict[tuple[str, str], tuple[str, str, int, int]] = {}
    rollout_count = int(reader.array("rollouts/rollout_row_id").shape[0])
    for position in range(rollout_count):
        rollout = rollout_at(reader, position)
        if rollout.target_row_id not in persisted_targets:
            raise ValueError(f"rollout references missing target row {rollout.target_row_id}")
        selected_history: list[PoseKey] = []
        for step in rollout_steps(reader, rollout):
            root_pose = tuple(float(value) for value in rollout.root_pose_world)
            fingerprint = _state_fingerprint(rollout.scene, rollout.source_row_id, root_pose, selected_history)
            context_key = (rollout.scene, fingerprint)
            context = (rollout.snippet, rollout.split, rollout.source_row_id, step.step_index)
            previous = state_context.setdefault(context_key, context)
            if previous != context:
                raise ValueError("one reconstruction fingerprint resolved to conflicting persisted context")
            for index, pose in enumerate(step.pose_world_cam):
                key = (rollout.scene, fingerprint, rollout.target_row_id, exact_pose_key(pose))
                row = NormalizedDecisionRow(
                    scene_id=rollout.scene,
                    source_row_id=rollout.source_row_id,
                    state_fingerprint=fingerprint,
                    target_id=rollout.target_row_id,
                    candidate_id=int(step.candidate_row_ids[index]),
                    candidate_pose_world=pose,
                    target_utility=float(step.target_root_gain[index]),
                    actor_action_mask=bool(step.actor_action_mask[index]),
                    oracle_label_mask=bool(step.q_train_mask[index]),
                )
                existing = normalized.get(key)
                if existing is not None and not _same_decision(existing, row):
                    raise ValueError("duplicate persisted decision rows disagree for one exact state/target/pose")
                normalized.setdefault(key, row)
            if step.selected_local_index >= 0:
                selected_history.append(exact_pose_key(step.pose_world_cam[step.selected_local_index]))

    return tuple(
        _pack_training_batch(
            view,
            actor_queries,
            state_context[(view.scene_id, view.state_fingerprint)],
            max_candidates_per_state=max_candidates_per_state,
        )
        for view in group_decision_rows(normalized.values())
    )


def _state_fingerprint(
    scene_id: str,
    source_row_id: int,
    root_pose_world: Sequence[float],
    selected_history: Sequence[PoseKey],
) -> str:
    """Hash the exact source/root/selected-action prefix that defines reconstruction state."""

    digest = hashlib.sha256()
    digest.update(scene_id.encode("utf-8"))
    digest.update(struct.pack("!q", source_row_id))
    digest.update(struct.pack("!12I", *exact_pose_key(root_pose_world)))
    for pose_key in selected_history:
        digest.update(struct.pack("!12I", *pose_key))
    return digest.hexdigest()


def _same_decision(left: NormalizedDecisionRow, right: NormalizedDecisionRow) -> bool:
    return (
        left.actor_action_mask == right.actor_action_mask
        and left.oracle_label_mask == right.oracle_label_mask
        and (
            left.target_utility == right.target_utility
            or (math.isnan(left.target_utility) and math.isnan(right.target_utility))
        )
    )


def _pack_training_batch(
    view: GroupedDecisionView,
    actor_targets: Mapping[int, ActorTargetQuery],
    context: tuple[str, str, int, int],
    *,
    max_candidates_per_state: int | None = None,
) -> GroupedRolloutTrainingBatch:
    target_queries: list[ActorTargetQuery] = []
    for target_id in view.target_ids:
        if not isinstance(target_id, int):
            raise TypeError("persisted rollout target ids must be integer row ids")
        target = actor_targets.get(target_id)
        if target is None:
            raise ValueError(f"missing actor-visible query for target row {target_id}")
        target_queries.append(target)
    source_rows = set(view.source_row_ids)
    if len(source_rows) != 1:
        raise ValueError("one exact reconstruction state must reference one source row")
    if max_candidates_per_state is not None and len(view.candidate_poses_world) > max_candidates_per_state:
        raise ValueError(
            "candidate set exceeds max_candidates_per_state. "
            f"count={len(view.candidate_poses_world)} limit={max_candidates_per_state}"
        )

    target_pose_values = torch.tensor(
        [tuple(target.pose_world_object) for target in target_queries], dtype=torch.float32
    )
    candidate_pose_values = torch.tensor(view.candidate_poses_world, dtype=torch.float32)
    targets_world_query = PoseTW(target_pose_values).matrix3x4.unsqueeze(0)
    candidates_world_camera = PoseTW(candidate_pose_values).matrix3x4.unsqueeze(0)
    extents = torch.tensor([tuple(target.extents_m) for target in target_queries], dtype=torch.float32)
    deficits = torch.tensor(
        [target.objective for target in target_queries],
        dtype=torch.float32,
    ).unsqueeze(1)
    features = torch.cat((torch.log1p(extents.clamp_min(0.0)), deficits), dim=1).unsqueeze(0)
    utilities = torch.tensor(view.target_utilities, dtype=torch.float32).unsqueeze(0)
    pair_valid = torch.tensor(view.utility_mask, dtype=torch.bool).unsqueeze(0)
    snippet_id, split, source_row_id, step_index = context
    return GroupedRolloutTrainingBatch(
        scene_id=view.scene_id,
        snippet_id=snippet_id,
        split=split,
        source_row_id=source_row_id,
        state_fingerprint=view.state_fingerprint,
        step_index=step_index,
        target_row_ids=tuple(int(target_id) for target_id in view.target_ids),
        targets_world_query=targets_world_query,
        target_features=features,
        candidates_world_camera=candidates_world_camera,
        target_utilities=utilities,
        pair_valid=pair_valid,
    )


def _group_state(
    scene_id: str,
    state_fingerprint: str,
    rows: Sequence[NormalizedDecisionRow],
) -> GroupedDecisionView:
    target_ids = tuple(
        sorted(
            {row.target_id for row in rows},
            key=lambda target_id: (str(type(target_id)), str(target_id)),
        )
    )
    source_row_ids = tuple(sorted({row.source_row_id for row in rows}))
    keyed_rows = tuple((row, exact_pose_key(row.candidate_pose_world)) for row in rows)
    poses_by_key: dict[PoseKey, Pose] = {}
    for _, key in keyed_rows:
        poses_by_key.setdefault(key, struct.unpack("!12f", struct.pack("!12I", *key)))

    pose_keys = tuple(sorted(poses_by_key))
    target_index = {target_id: index for index, target_id in enumerate(target_ids)}
    pose_index = {key: index for index, key in enumerate(pose_keys)}
    width = len(pose_keys)
    candidate_ids: list[list[int | None]] = [[None] * width for _ in target_ids]
    utilities = [[math.nan] * width for _ in target_ids]
    action_mask = [[False] * width for _ in target_ids]
    utility_mask = [[False] * width for _ in target_ids]

    for row, key in sorted(
        keyed_rows,
        key=lambda item: (str(item[0].target_id), item[1]),
    ):
        target = target_index[row.target_id]
        candidate = pose_index[key]
        if candidate_ids[target][candidate] is not None:
            raise ValueError(f"Duplicate decision row for target {row.target_id!r} and candidate pose.")
        candidate_ids[target][candidate] = int(row.candidate_id)
        action_mask[target][candidate] = bool(row.actor_action_mask)
        supervised = bool(row.actor_action_mask and row.oracle_label_mask and math.isfinite(row.target_utility))
        utility_mask[target][candidate] = supervised
        if supervised:
            utilities[target][candidate] = float(row.target_utility)

    return GroupedDecisionView(
        scene_id=scene_id,
        state_fingerprint=state_fingerprint,
        source_row_ids=source_row_ids,
        target_ids=target_ids,
        candidate_poses_world=tuple(poses_by_key.values()),
        candidate_ids=tuple(tuple(values) for values in candidate_ids),
        target_utilities=tuple(tuple(values) for values in utilities),
        actor_action_mask=tuple(tuple(values) for values in action_mask),
        utility_mask=tuple(tuple(values) for values in utility_mask),
        acquisition_keys=tuple(AcquisitionKey(scene_id, state_fingerprint, key) for key in pose_keys),
    )


__all__ = [
    "AcquisitionKey",
    "ActorTargetQuery",
    "GroupedDecisionView",
    "GroupedRolloutTrainingBatch",
    "NormalizedDecisionRow",
    "acquisition_key",
    "can_share_later_rollout",
    "exact_pose_key",
    "group_decision_rows",
    "grouped_rollout_training_batches",
]
