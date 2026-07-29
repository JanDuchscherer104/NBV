"""Typed, presentation-free projections over persisted rollout stores."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal, cast

import numpy as np
from numpy.typing import NDArray

from ..pose_generation import CandidatePositionMode, candidate_position_id
from .trace import INVALID_REASON_CODES
from .zarr_store import RolloutZarrStoreReader

_INVALID_REASON_NAMES = {int(code): name for name, code in INVALID_REASON_CODES.items()}
_POSITION_NAMES = {candidate_position_id(mode): mode.value for mode in CandidatePositionMode}


@dataclass(frozen=True, slots=True)
class StoredRollout:
    """One persisted rollout row with decoded context and ordered step links."""

    row_position: int
    rollout_row_id: int
    chain_id: int
    source_row_id: int
    target_row_id: int
    scene: str
    snippet: str
    split: str
    policy: str
    horizon: int
    branch_factor: int
    beam_width: int
    temperature: float
    root_pose_world: NDArray[np.float32]
    final_cumulative_target_rri: float
    final_cumulative_scene_rri: float
    step_row_positions: NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class StoredStep:
    """One step row with shell-ordered candidate columns shared by readers."""

    row_position: int
    step_row_id: int
    rollout_row_id: int
    step_index: int
    selected_candidate_row_id: int
    selected_local_index: int
    num_candidates: int
    num_valid_candidates: int
    cumulative_target_rri: float
    cumulative_scene_rri: float
    cumulative_target_root_gain: float
    cumulative_scene_root_gain: float
    candidate_row_positions: NDArray[np.int64]
    candidate_row_ids: NDArray[np.int64]
    shell_indices: NDArray[np.int32]
    compact_valid_indices: NDArray[np.int32]
    actor_action_mask: NDArray[np.bool_]
    oracle_label_mask: NDArray[np.bool_]
    selected_mask: NDArray[np.bool_]
    pose_world_cam: NDArray[np.float32]
    target_rri: NDArray[np.float32]
    target_root_gain: NDArray[np.float32]
    scene_rri: NDArray[np.float32]
    selection_probabilities: NDArray[np.float32]
    mixture_ids: NDArray[np.int32]
    mixture_names: NDArray[np.str_]
    sampler_probabilities: NDArray[np.float32]
    position_ids: NDArray[np.int32]
    position_names: NDArray[np.str_]
    invalid_reason_bitsets: NDArray[np.uint32]
    primary_invalid_reason_ids: NDArray[np.uint16]
    primary_invalid_reason_names: NDArray[np.str_]
    mesh_distance_m: NDArray[np.float32]
    path_min_clearance_m: NDArray[np.float32]
    motion_step_length_m: NDArray[np.float32]
    target_distance_m: NDArray[np.float32]


@dataclass(frozen=True, slots=True)
class StoredTarget:
    """One persisted target row with decoded audit fields and factual geometry."""

    row_position: int
    target_row_id: int
    target_id: str
    source: str
    source_index: int
    class_name: str
    sem_id: int
    inst_id: int
    confidence: float
    selection_rank: int
    selection_score: float
    selection_probability: float
    target_valid: bool
    primary_invalid_reason_id: int
    gt_label_valid: bool
    matched_gt_target_row_id: int
    matched_gt_target_id: str
    gt_match_status: str
    gt_match_iou: float
    gt_match_score: float
    projected_area_pixels: float
    projected_area_fraction: float
    semidense_support_count: float
    evl_support_count: float
    effective_support_count: float
    visibility_score: float
    support_score: float
    deficit_score: float
    center_world: NDArray[np.float32]
    extents: NDArray[np.float32]
    pose_world_object: NDArray[np.float32]


@dataclass(frozen=True, slots=True)
class StoredSelectedDepth:
    """One selected-depth lookup outcome without display-specific processing."""

    available: bool
    warning: str | None
    step_row_id: int
    candidate_row_id: int | None
    depth_m: NDArray[np.float32] | None
    valid_mask: NDArray[np.bool_] | None
    focal_px: NDArray[np.float32] | None
    principal_point_px: NDArray[np.float32] | None
    image_size_hw: tuple[int, int] | None


@dataclass(frozen=True, slots=True)
class StoredEvaluationLineage:
    """Exact persisted identities required to reopen an endpoint audit unit.

    The source, rollout, target, and resolved-config identities are decoded
    from their canonical Zarr tables. Empty dictionary values, placeholder
    indices, and missing temporal anchors are rejected by
    :func:`endpoint_evaluation_unit` rather than passed to an evaluator.
    """

    source_row_id: int
    """Stable row identity in the rollout store's ``sources/`` table."""
    source_sample_index: int
    """Sample index used to reopen the immutable source dataset."""
    source_sample_key: str
    """Canonical source sample identity."""
    source_shard_id: str
    """Immutable VIN shard identity containing the source sample."""
    source_shard_row: int
    """Zero-based source row within :attr:`source_shard_id`."""
    source_offline_store_manifest_hash: str
    """Content identity of the immutable source-store manifest."""
    split_manifest_hash: str
    """Content identity of the split manifest admitting the source row."""
    split: str
    """Dataset split associated with the source row and rollout."""
    scene_id: str
    """Scene identity used as the independent statistical cluster."""
    snippet_id: str
    """Source snippet identity within :attr:`scene_id`."""
    rollout_row_id: int
    """Stable row identity in the rollout store's ``rollouts/`` table."""
    rollout_id: str
    """Persisted logical rollout identity."""
    chain_id: int
    """Retained trajectory-chain index within the logical rollout."""
    root_time_ns: int
    """Root capture timestamp in nanoseconds."""
    root_trajectory_index: int
    """Source trajectory index anchoring root reconstruction evidence."""
    root_frame_index: int
    """Source frame index anchoring root camera evidence."""
    candidate_config_hash: str
    """Resolved candidate-generation configuration identity."""
    oracle_config_hash: str
    """Resolved oracle-evaluation configuration identity."""
    rollout_config_hash: str
    """Resolved rollout configuration identity."""
    target_row_id: int
    """Stable target row referenced by the rollout."""
    target_id: str
    """Exact target-task identity reopened by endpoint evaluation."""
    target_protocol_version: str
    """Target-admission protocol frozen for the stored rollout."""
    target_crop_policy: str
    """Target crop rule used by persisted oracle evaluation."""


@dataclass(frozen=True, slots=True)
class StoredSelectedPoseChain:
    """Root and selected camera poses forming one factual rollout path.

    Attributes:
        root_pose_world: ``ndarray[float32, (12,)]`` world-from-camera root
            pose in the EFM3D ``PoseTW`` 3x4 layout; translation is metres.
        selected_poses_world_cam: ``ndarray[float32, (H_a, 12)]`` selected
            world-from-camera poses in increasing factual-step order, where
            ``H_a`` is the achieved number of acquisitions.
    """

    root_pose_world: NDArray[np.float32]
    """``ndarray[float32, (12,)]`` root world-from-camera pose."""
    selected_poses_world_cam: NDArray[np.float32]
    """``ndarray[float32, (H_a, 12)]`` ordered selected poses."""
    step_row_ids: tuple[int, ...]
    """Factual step row IDs in zero-based rollout-depth order."""
    selected_candidate_row_ids: tuple[int, ...]
    """Selected candidate row ID corresponding to each factual step."""


@dataclass(frozen=True, slots=True)
class StoredRootActionSetIdentity:
    """Content identity of the persisted pre-treatment root action table.

    The digest covers only the shell-ordered step-zero candidate contract and
    the fixed acquisition budget. Physical row IDs, policy selections, scores,
    reconstruction outcomes, and every downstream action table are excluded so
    the value can safely gate exact pre-treatment matching across policies.
    """

    rollout_row_id: int
    """Stable rollout row used to locate the table; excluded from the digest."""
    step_row_id: int
    """Stable root-step row used to locate candidates; excluded from the digest."""
    budget: int
    """Fixed acquisition budget included in the digest."""
    candidate_count: int
    """Number of shell rows included in the digest."""
    sha256: str
    """Lowercase SHA-256 over canonical little-endian field bytes."""

    def __post_init__(self) -> None:
        if self.budget < 1 or self.candidate_count < 1:
            raise ValueError("Root action-set identities require positive budget and candidate count.")
        if len(self.sha256) != 64 or any(char not in "0123456789abcdef" for char in self.sha256):
            raise ValueError("Root action-set identity requires a full lowercase SHA-256.")


@dataclass(frozen=True, slots=True)
class StoredEndpointComparator:
    r"""Persisted return kept outside independent evaluator inputs.

    Theory:
        The stored comparator is the undiscounted telescoping return over
        selected target root gains. Its canonical normalization is

        $$
        G_H=\frac{\Delta_0-\Delta_H}{\max(\Delta_0,10^{-12})}.
        $$

        Independent endpoint evaluation must recompute this expression from
        reopened errors; this DTO supplies only the persisted comparison value.
        A valid root-only early termination has the empty-sum comparator zero,
        even though the legacy aggregate array represents that empty sum as
        ``NaN``.
    """

    gain: float
    """Persisted final cumulative target-root gain, dimensionless."""
    gamma: float = 1.0
    """Undiscounted comparator factor required for telescoping equivalence."""
    epsilon: float = 1e-12
    """Clamp-min denominator guard used by canonical target-root gain."""

    def __post_init__(self) -> None:
        if self.gamma != 1.0 or self.epsilon != 1e-12:
            raise ValueError("Stored endpoint comparator semantics are frozen at gamma=1 and epsilon=1e-12.")


@dataclass(frozen=True, slots=True)
class StoredEndpointEvaluationUnit:
    """Fail-closed persisted input unit for independent endpoint evaluation.

    Evaluators consume :attr:`lineage` and :attr:`pose_chain` to reopen source
    assets and reconstruct the selected factual path. :attr:`comparator` is a
    separate typed object so persisted outcomes cannot be mistaken for
    evaluator inputs or used to synthesize terminal reconstruction evidence.
    """

    lineage: StoredEvaluationLineage
    """Immutable source, rollout, target, temporal, and config identities."""
    pose_chain: StoredSelectedPoseChain
    """Root and factual selected poses in acquisition order."""
    budget: int
    """Predeclared maximum acquisition horizon."""
    achieved_steps: int
    """Number of selected factual acquisitions in :attr:`pose_chain`."""
    termination_reason: Literal["fixed_horizon", "terminated_early"]
    """Complete persisted termination state; incomplete rollouts are rejected."""
    comparator: StoredEndpointComparator
    """Persisted return isolated from independent evaluator inputs."""


def decode_invalid_reason(reason: int | np.integer[Any]) -> str:
    """Return the frozen invalid-reason name for one numeric code."""
    return _INVALID_REASON_NAMES.get(int(reason), f"reason_{int(reason)}")


def decode_position_id(position_id: int | np.integer[Any]) -> str:
    """Return the frozen candidate-position name for one numeric id."""

    value = int(position_id)
    return _POSITION_NAMES.get(value, "unknown" if value < 0 else f"position_{value}")


def rollout_at(reader: RolloutZarrStoreReader, row_position: int) -> StoredRollout:
    """Resolve one rollout by physical row position."""

    return _rollout_at(reader, row_position, require_steps=True)


def _rollout_at(
    reader: RolloutZarrStoreReader,
    row_position: int,
    *,
    require_steps: bool,
) -> StoredRollout:
    """Decode one rollout while optionally admitting a root-only trajectory."""

    rollouts: Any = reader.root["rollouts"]
    steps: Any = reader.root["steps"]
    rollout_ids = np.asarray(rollouts["rollout_row_id"], dtype=np.int64).reshape(-1)
    position = int(row_position)
    if position < 0 or position >= rollout_ids.shape[0]:
        raise IndexError(f"rollout row position {position} is outside [0, {rollout_ids.shape[0]}).")

    rollout_row_id = int(rollout_ids[position])
    step_rollout_ids = np.asarray(steps["rollout_row_id"], dtype=np.int64).reshape(-1)
    step_indices = np.asarray(steps["step_index"], dtype=np.int64).reshape(-1)
    step_positions = np.flatnonzero(step_rollout_ids == rollout_row_id).astype(np.int64)
    if require_steps and step_positions.size == 0:
        raise ValueError(f"Rollout row {rollout_row_id} has no step rows.")
    step_positions = step_positions[np.argsort(step_indices[step_positions], kind="stable")]

    scene_names = _string_dictionary(reader, "scene")
    snippet_names = _string_dictionary(reader, "snippet")
    split_names = _string_dictionary(reader, "split")
    policy_names = _string_dictionary(reader, "policy")

    def decoded(values: list[str], index: Any) -> str:
        value = int(index)
        return values[value] if 0 <= value < len(values) else ""

    return StoredRollout(
        row_position=position,
        rollout_row_id=rollout_row_id,
        chain_id=int(rollouts["chain_id"][position]),
        source_row_id=int(rollouts["source_row_id"][position]),
        target_row_id=int(rollouts["target_row_id"][position]),
        scene=decoded(scene_names, rollouts["scene_id"][position]),
        snippet=decoded(snippet_names, rollouts["snippet_id"][position]),
        split=decoded(split_names, rollouts["split_id"][position]),
        policy=decoded(policy_names, rollouts["policy_id"][position]),
        horizon=int(rollouts["horizon"][position]),
        branch_factor=int(rollouts["branch_factor"][position]),
        beam_width=int(rollouts["beam_width"][position]),
        temperature=float(rollouts["temperature"][position]),
        root_pose_world=np.asarray(rollouts["root_pose_world"][position], dtype=np.float32).reshape(12),
        final_cumulative_target_rri=float(rollouts["final_cumulative_target_rri"][position]),
        final_cumulative_scene_rri=float(rollouts["final_cumulative_scene_rri"][position]),
        step_row_positions=step_positions,
    )


def rollout_by_id(reader: RolloutZarrStoreReader, rollout_row_id: int) -> StoredRollout:
    """Resolve one rollout by its stable row id."""

    rollout_ids = np.asarray(reader.array("rollouts/rollout_row_id"), dtype=np.int64).reshape(-1)
    matches = np.flatnonzero(rollout_ids == int(rollout_row_id))
    if matches.size != 1:
        raise KeyError(f"rollout_row_id {rollout_row_id} is not present in rollouts/rollout_row_id.")
    return rollout_at(reader, int(matches[0]))


def rollout_steps(reader: RolloutZarrStoreReader, rollout: StoredRollout) -> tuple[StoredStep, ...]:
    """Read shell-ordered shared candidate columns for one rollout."""

    candidates: Any = reader.root["candidates"]
    diagnostics: Any = reader.root["candidate_diagnostics"]
    step_table: Any = reader.root["steps"]
    candidate_step_ids = np.asarray(candidates["step_row_id"], dtype=np.int64).reshape(-1)
    candidate_ids = np.asarray(candidates["candidate_row_id"], dtype=np.int64).reshape(-1)
    shell_indices = np.asarray(candidates["shell_index"], dtype=np.int32).reshape(-1)
    component_names: dict[int, str] = {}
    try:
        writer_config = reader.manifest().get("manifest", {}).get("generation", {}).get("writer_config")
        candidate_mixture = writer_config.get("candidate_mixture") if isinstance(writer_config, dict) else None
        components = candidate_mixture.get("components") if isinstance(candidate_mixture, dict) else None
        if isinstance(components, list):
            for index, component in enumerate(components):
                if isinstance(component, dict):
                    name = component.get("name") or component.get("family") or component.get("position_mode")
                    if name is not None:
                        component_names[index] = str(name)
    except (KeyError, TypeError, ValueError):
        component_names = {}

    steps: list[StoredStep] = []
    for step_position in rollout.step_row_positions.tolist():
        step_row_id = int(step_table["step_row_id"][step_position])
        row_positions = np.flatnonzero(candidate_step_ids == step_row_id).astype(np.int64)
        order = np.argsort(shell_indices[row_positions], kind="stable")
        row_positions = row_positions[order]

        def take(group: Any, name: str, dtype: Any, positions: np.ndarray = row_positions) -> np.ndarray:
            return np.asarray(group[name][positions], dtype=dtype)

        selected_mask = take(candidates, "selected_mask", np.bool_)
        selected_matches = np.flatnonzero(selected_mask)
        selected_local_index = int(selected_matches[0]) if selected_matches.size else -1
        mixture_ids = take(candidates, "mixture_id", np.int32)
        position_ids = take(diagnostics, "position_id", np.int32)
        reason_ids = take(candidates, "primary_invalid_reason", np.uint16)
        steps.append(
            StoredStep(
                row_position=int(step_position),
                step_row_id=step_row_id,
                rollout_row_id=rollout.rollout_row_id,
                step_index=int(step_table["step_index"][step_position]),
                selected_candidate_row_id=int(step_table["selected_candidate_row_id"][step_position]),
                selected_local_index=selected_local_index,
                num_candidates=int(step_table["num_candidates"][step_position]),
                num_valid_candidates=int(step_table["num_valid_candidates"][step_position]),
                cumulative_target_rri=float(step_table["cumulative_target_rri"][step_position]),
                cumulative_scene_rri=float(step_table["cumulative_scene_rri"][step_position]),
                cumulative_target_root_gain=float(step_table["cumulative_target_root_gain"][step_position]),
                cumulative_scene_root_gain=float(step_table["cumulative_scene_root_gain"][step_position]),
                candidate_row_positions=row_positions,
                candidate_row_ids=candidate_ids[row_positions],
                shell_indices=shell_indices[row_positions],
                compact_valid_indices=take(candidates, "compact_valid_index", np.int32),
                actor_action_mask=take(candidates, "actor_action_mask", np.bool_),
                oracle_label_mask=take(candidates, "oracle_label_mask", np.bool_),
                selected_mask=selected_mask,
                pose_world_cam=take(candidates, "pose_world_cam", np.float32).reshape(-1, 12),
                target_rri=take(candidates, "target_rri", np.float32),
                target_root_gain=take(candidates, "target_root_gain", np.float32),
                scene_rri=take(candidates, "scene_rri", np.float32),
                selection_probabilities=take(candidates, "selection_probabilities", np.float32),
                mixture_ids=mixture_ids,
                mixture_names=np.asarray(
                    [
                        component_names.get(
                            int(value),
                            "unknown" if int(value) < 0 else f"component_{int(value)}",
                        )
                        for value in mixture_ids
                    ],
                    dtype=np.str_,
                ),
                sampler_probabilities=take(candidates, "sampler_probability", np.float32),
                position_ids=position_ids,
                position_names=np.asarray([decode_position_id(value) for value in position_ids], dtype=np.str_),
                invalid_reason_bitsets=take(candidates, "invalid_reason_bitset", np.uint32),
                primary_invalid_reason_ids=reason_ids,
                primary_invalid_reason_names=np.asarray(
                    [decode_invalid_reason(value) for value in reason_ids], dtype=np.str_
                ),
                mesh_distance_m=take(diagnostics, "mesh_distance_m", np.float32),
                path_min_clearance_m=take(diagnostics, "path_min_clearance_m", np.float32),
                motion_step_length_m=take(diagnostics, "motion_step_length_m", np.float32),
                target_distance_m=take(diagnostics, "target_distance_m", np.float32),
            )
        )
    return tuple(steps)


def target_rows(reader: RolloutZarrStoreReader) -> tuple[StoredTarget, ...]:
    """Read all persisted target rows with decoded factual fields."""

    if "targets" not in reader.root:
        return ()
    targets: Any = reader.root["targets"]
    target_row_ids = np.asarray(targets["target_row_id"], dtype=np.int64).reshape(-1)
    target_names = _string_dictionary(reader, "target")
    source_names = _string_dictionary(reader, "target_source")
    class_names = _string_dictionary(reader, "class_name")
    status_names = _string_dictionary(reader, "target_match_status")

    def decoded(values: list[str], index: Any) -> str:
        value = int(index)
        return values[value] if 0 <= value < len(values) else ""

    def optional(name: str, index: int, default: float = float("nan")) -> float:
        try:
            values = np.asarray(targets[name]).reshape(-1)
        except KeyError:
            return default
        return float(values[index]) if index < values.shape[0] else default

    rows: list[StoredTarget] = []
    for index, target_row_id in enumerate(target_row_ids.tolist()):
        rows.append(
            StoredTarget(
                row_position=index,
                target_row_id=int(target_row_id),
                target_id=decoded(target_names, targets["target_id"][index]),
                source=decoded(source_names, targets["target_source_id"][index]),
                source_index=int(targets["target_source_index"][index]),
                class_name=decoded(class_names, targets["target_class_name_id"][index]),
                sem_id=int(targets["target_sem_id"][index]),
                inst_id=int(targets["target_inst_id"][index]),
                confidence=float(targets["target_confidence"][index]),
                selection_rank=int(targets["target_selection_rank"][index]),
                selection_score=float(targets["target_selection_score"][index]),
                selection_probability=float(targets["target_selection_probability"][index]),
                target_valid=bool(targets["target_valid_mask"][index]),
                primary_invalid_reason_id=int(targets["target_primary_invalid_reason"][index]),
                gt_label_valid=bool(targets["gt_label_valid_mask"][index]),
                matched_gt_target_row_id=int(targets["matched_gt_target_row_id"][index]),
                matched_gt_target_id=decoded(target_names, targets["matched_gt_target_id"][index]),
                gt_match_status=decoded(status_names, targets["gt_match_status_id"][index]),
                gt_match_iou=float(targets["gt_match_iou"][index]),
                gt_match_score=float(targets["gt_match_score"][index]),
                projected_area_pixels=optional("target_projected_area_pixels", index),
                projected_area_fraction=optional("target_projected_area_fraction", index),
                semidense_support_count=optional("target_semidense_support_count", index),
                evl_support_count=optional("target_evl_support_count", index),
                effective_support_count=optional("target_effective_support_count", index),
                visibility_score=optional("target_visibility_score", index),
                support_score=optional("target_support_score", index),
                deficit_score=optional("target_deficit_score", index),
                center_world=np.asarray(targets["target_center_world"][index], dtype=np.float32).reshape(3),
                extents=np.asarray(targets["target_extents"][index], dtype=np.float32).reshape(3),
                pose_world_object=np.asarray(targets["target_pose_world_object"][index], dtype=np.float32).reshape(12),
            )
        )
    return tuple(rows)


def target_by_id(reader: RolloutZarrStoreReader, target_row_id: int) -> StoredTarget | None:
    """Return one target by stable row id, or None when absent."""

    return next((row for row in target_rows(reader) if row.target_row_id == int(target_row_id)), None)


def root_action_set_identity(
    reader: RolloutZarrStoreReader,
    rollout: int | StoredEndpointEvaluationUnit,
) -> StoredRootActionSetIdentity:
    """Hash the exact persisted step-zero candidate contract for one rollout.

    Args:
        reader: Validated read-only rollout store reader.
        rollout: Stable rollout row ID or an already decoded endpoint unit.

    Returns:
        Frozen root-table identity over budget, shell order, both persisted pose
        representations, generation provenance, sampler mass, admission masks,
        compact indexing, and invalid-reason fields.

    Notes:
        Outcome and policy-decision fields are intentionally absent. In
        particular, selected masks, policy probabilities, logits, RRI, gains,
        row IDs, and downstream candidate tables cannot change this digest.
    """

    rollout_row_id = (
        rollout.lineage.rollout_row_id if isinstance(rollout, StoredEndpointEvaluationUnit) else int(rollout)
    )
    positions = np.flatnonzero(
        np.asarray(reader.array("rollouts/rollout_row_id"), dtype=np.int64).reshape(-1) == rollout_row_id
    )
    if positions.size != 1:
        raise KeyError(f"rollout_row_id {rollout_row_id} is not present exactly once.")
    rollout_position = int(positions[0])
    budget = int(reader.array("rollouts/horizon")[rollout_position])
    if budget < 1:
        raise ValueError(f"Rollout {rollout_row_id} has invalid horizon budget {budget}.")
    if isinstance(rollout, StoredEndpointEvaluationUnit) and rollout.budget != budget:
        raise ValueError("Endpoint-unit budget disagrees with the persisted rollout budget.")

    try:
        steps: Any = reader.root["steps"]
        candidates: Any = reader.root["candidates"]
    except KeyError as exc:
        raise ValueError("Root action-set identity requires persisted steps and candidates tables.") from exc
    step_rollout_ids = np.asarray(steps["rollout_row_id"], dtype=np.int64).reshape(-1)
    step_indices = np.asarray(steps["step_index"], dtype=np.int64).reshape(-1)
    root_step_positions = np.flatnonzero((step_rollout_ids == rollout_row_id) & (step_indices == 0))
    if root_step_positions.size != 1:
        raise ValueError(f"Rollout {rollout_row_id} must have exactly one persisted step-zero action table.")
    root_step_position = int(root_step_positions[0])
    step_row_id = int(steps["step_row_id"][root_step_position])
    candidate_step_ids = np.asarray(candidates["step_row_id"], dtype=np.int64).reshape(-1)
    row_positions = np.flatnonzero(candidate_step_ids == step_row_id)
    if row_positions.size == 0:
        raise ValueError(f"Rollout {rollout_row_id} root action table has no candidate rows.")

    shell_indices = np.asarray(candidates["shell_index"][row_positions], dtype=np.int32).reshape(-1)
    if np.unique(shell_indices).size != shell_indices.size:
        raise ValueError("Root action table contains duplicate shell indices.")
    order = np.argsort(shell_indices, kind="stable")
    row_positions = row_positions[order]
    shell_indices = shell_indices[order]
    expected_shell = np.arange(shell_indices.size, dtype=np.int32)
    if not np.array_equal(shell_indices, expected_shell):
        raise ValueError("Root action table shell indices must be contiguous from zero in shell order.")

    def take(name: str, dtype: Any, *, shape: tuple[int, ...] | None = None) -> np.ndarray:
        try:
            values = np.asarray(candidates[name][row_positions], dtype=dtype)
        except KeyError as exc:
            raise ValueError(f"Root action-set identity requires candidates/{name}.") from exc
        if shape is not None:
            try:
                values = values.reshape(shape)
            except ValueError as exc:
                raise ValueError(f"Root action-set field candidates/{name} has an invalid shape.") from exc
        return values

    count = int(shell_indices.size)
    pose_world = take("pose_world_cam", "<f4", shape=(count, 12))
    pose_relative = take("pose_relative_root", "<f4", shape=(count, 12))
    sampler_probability = take("sampler_probability", "<f4", shape=(count,))
    if not np.isfinite(pose_world).all() or not np.isfinite(pose_relative).all():
        raise ValueError("Root action table poses must be finite.")
    if not np.isfinite(sampler_probability).all():
        raise ValueError("Root action table sampler probabilities must be finite.")

    fields = (
        ("budget", np.asarray([budget], dtype="<i8")),
        ("shell_index", shell_indices.astype("<i4", copy=False)),
        ("pose_world_cam", pose_world),
        ("pose_relative_root", pose_relative),
        ("strategy_id", take("strategy_id", "<i4", shape=(count,))),
        ("position_id", take("position_id", "<i4", shape=(count,))),
        ("mixture_id", take("mixture_id", "<i4", shape=(count,))),
        ("sampler_probability", sampler_probability),
        ("actor_action_mask", take("actor_action_mask", "u1", shape=(count,))),
        ("oracle_label_mask", take("oracle_label_mask", "u1", shape=(count,))),
        ("q_train_mask", take("q_train_mask", "u1", shape=(count,))),
        ("compact_valid_index", take("compact_valid_index", "<i4", shape=(count,))),
        ("invalid_reason_bitset", take("invalid_reason_bitset", "<u4", shape=(count,))),
        ("primary_invalid_reason", take("primary_invalid_reason", "<u2", shape=(count,))),
    )
    digest = hashlib.sha256(b"aria-nbv-root-action-set-v1\0")
    for name, values in fields:
        encoded_name = name.encode("ascii")
        digest.update(np.asarray([len(encoded_name)], dtype="<u2").tobytes())
        digest.update(encoded_name)
        digest.update(np.asarray(values.shape, dtype="<i8").tobytes())
        digest.update(np.ascontiguousarray(values).tobytes(order="C"))
    return StoredRootActionSetIdentity(
        rollout_row_id=rollout_row_id,
        step_row_id=step_row_id,
        budget=budget,
        candidate_count=count,
        sha256=digest.hexdigest(),
    )


def selected_pose_chain_sha256(pose_chain: StoredSelectedPoseChain) -> str:
    """Hash a factual pose chain using canonical little-endian bytes.

    Pose values and their shapes are followed by factual step and selected-row
    IDs. The digest validates audit-to-store joins; it is deliberately not an
    exact policy-pairing key because selected paths are treatment outcomes.
    """

    digest = hashlib.sha256()
    for array in (pose_chain.root_pose_world, pose_chain.selected_poses_world_cam):
        canonical = np.asarray(array).astype("<f4", copy=False)
        digest.update(np.asarray(canonical.shape, dtype="<i8").tobytes())
        digest.update(canonical.tobytes(order="C"))
    for values in (pose_chain.step_row_ids, pose_chain.selected_candidate_row_ids):
        canonical_ids = np.asarray(values, dtype="<i8")
        digest.update(np.asarray(canonical_ids.shape, dtype="<i8").tobytes())
        digest.update(canonical_ids.tobytes())
    return digest.hexdigest()


def persisted_pre_treatment_context_sha256(
    lineage: StoredEvaluationLineage,
    target: StoredTarget,
    root_action_identity: StoredRootActionSetIdentity,
) -> str:
    """Hash persisted non-treatment context available at the read-model seam.

    The versioned digest binds source, split, sample/shard, scene/snippet,
    target protocol and persisted target identity, root temporal anchors,
    persisted config identities, fixed budget, reason/label state, and the root
    action-table hash. Policy schedules, branch/beam parameters, selected pose
    chains, candidate outcomes, and reconstruction scores are excluded.

    Notes:
        This helper can bind only identities persisted in the current rollout
        schema. Independently reopened mesh/content identities remain separate
        in the scientific audit's raw-asset context. A model checkpoint is
        bound through normalized config/treatment identity unless a future
        persisted lineage field supplies an exact checkpoint hash.
    """

    if root_action_identity.rollout_row_id != lineage.rollout_row_id:
        raise ValueError("Root action-set identity belongs to a different rollout lineage.")
    if target.target_row_id != lineage.target_row_id or target.target_id != lineage.target_id:
        raise ValueError("Stored target identity differs from the rollout lineage.")
    payload = {
        "version": "aria-nbv-persisted-pre-treatment-context-v1",
        "source": {
            "row_id": lineage.source_row_id,
            "sample_index": lineage.source_sample_index,
            "sample_key": lineage.source_sample_key,
            "shard_id": lineage.source_shard_id,
            "shard_row": lineage.source_shard_row,
            "offline_store_manifest_hash": lineage.source_offline_store_manifest_hash,
            "split_manifest_hash": lineage.split_manifest_hash,
            "split": lineage.split,
            "scene_id": lineage.scene_id,
            "snippet_id": lineage.snippet_id,
        },
        "target": {
            "row_id": target.target_row_id,
            "target_id": target.target_id,
            "source": target.source,
            "source_index": target.source_index,
            "class_name": target.class_name,
            "sem_id": target.sem_id,
            "inst_id": target.inst_id,
            "confidence": float(target.confidence),
            "protocol_version": lineage.target_protocol_version,
            "crop_policy": lineage.target_crop_policy,
            "target_valid": target.target_valid,
            "primary_invalid_reason_id": target.primary_invalid_reason_id,
            "gt_label_valid": target.gt_label_valid,
            "matched_gt_target_row_id": target.matched_gt_target_row_id,
            "matched_gt_target_id": target.matched_gt_target_id,
            "gt_match_status": target.gt_match_status,
            "center_world_f32le": _canonical_float32_hex(target.center_world, shape=(3,)),
            "extents_f32le": _canonical_float32_hex(target.extents, shape=(3,)),
            "pose_world_object_f32le": _canonical_float32_hex(target.pose_world_object, shape=(12,)),
        },
        "root": {
            "time_ns": lineage.root_time_ns,
            "trajectory_index": lineage.root_trajectory_index,
            "frame_index": lineage.root_frame_index,
            "budget": root_action_identity.budget,
            "action_set_sha256": root_action_identity.sha256,
        },
        "configs": {
            "candidate": lineage.candidate_config_hash,
            "oracle": lineage.oracle_config_hash,
            "rollout": lineage.rollout_config_hash,
        },
    }
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _canonical_float32_hex(value: NDArray[np.float32], *, shape: tuple[int, ...]) -> str:
    array = np.asarray(value, dtype="<f4").reshape(shape)
    if not np.isfinite(array).all():
        raise ValueError("Persisted pre-treatment geometry must be finite.")
    return np.ascontiguousarray(array).tobytes(order="C").hex()


def endpoint_evaluation_unit(
    reader: RolloutZarrStoreReader,
    rollout_row_id: int,
) -> StoredEndpointEvaluationUnit:
    r"""Decode one strict independent endpoint-evaluation unit.

    The projection admits only a complete factual path whose source assets can
    be reopened unambiguously. Every factual step must have exactly one
    selected actor-valid, oracle-labelled candidate, and selected poses must be
    finite world-from-camera ``PoseTW`` rows.

    Args:
        reader: Validated read-only rollout store reader.
        rollout_row_id: Stable rollout-table row identity.

    Returns:
        A typed evaluation unit with evaluator inputs and a separately typed
        persisted comparator.

    Theory:
        The comparator records the stored cumulative target-root return. An
        independent evaluator must instead reopen the source row and evaluate
        the ordered path $[T^w_{c,0},\ldots,T^w_{c,H_a}]$; no endpoint error is
        inferred from the stored return.
    """

    rollout_positions = np.flatnonzero(
        np.asarray(reader.array("rollouts/rollout_row_id"), dtype=np.int64).reshape(-1) == int(rollout_row_id)
    )
    if rollout_positions.size != 1:
        raise KeyError(f"rollout_row_id {rollout_row_id} is not present exactly once.")
    rollout_position = int(rollout_positions[0])
    rollout = _rollout_at(reader, rollout_position, require_steps=False)
    steps = rollout_steps(reader, rollout) if rollout.step_row_positions.size else ()
    _validate_factual_steps(steps, rollout_row_id=rollout.rollout_row_id)

    rollouts: Any = reader.root["rollouts"]
    termination_reason = _required_decoded(
        reader,
        "termination_reason",
        rollouts["termination_reason"][rollout_position],
        label="termination_reason",
    )
    if termination_reason not in {"fixed_horizon", "terminated_early"}:
        raise ValueError(
            f"Rollout {rollout.rollout_row_id} has incomplete or unknown termination {termination_reason!r}."
        )
    achieved_steps = len(steps)
    budget = int(rollout.horizon)
    if budget < 1:
        raise ValueError(f"Rollout {rollout.rollout_row_id} has invalid horizon budget {budget}.")
    if termination_reason == "fixed_horizon" and achieved_steps != budget:
        raise ValueError(
            f"fixed_horizon rollout {rollout.rollout_row_id} achieved {achieved_steps} steps for budget {budget}."
        )
    if termination_reason == "terminated_early" and achieved_steps >= budget:
        raise ValueError(
            f"terminated_early rollout {rollout.rollout_row_id} must be shorter than budget {budget}, "
            f"got {achieved_steps}."
        )

    root_pose = _readonly_pose(rollout.root_pose_world, label="root_pose_world")
    selected_poses = np.empty((achieved_steps, 12), dtype=np.float32)
    step_row_ids: list[int] = []
    selected_candidate_row_ids: list[int] = []
    for row_index, step in enumerate(steps):
        selected_index = step.selected_local_index
        selected_poses[row_index] = step.pose_world_cam[selected_index]
        step_row_ids.append(step.step_row_id)
        selected_candidate_row_ids.append(step.selected_candidate_row_id)
    selected_poses = _readonly_pose_matrix(selected_poses, label="selected_poses_world_cam")

    lineage = _evaluation_lineage(reader, rollout=rollout, rollout_position=rollout_position)
    comparator_gain = float(rollouts["final_cumulative_target_root_gain"][rollout_position])
    if achieved_steps == 0 and termination_reason == "terminated_early" and np.isnan(comparator_gain):
        comparator_gain = 0.0
    if not np.isfinite(comparator_gain):
        raise ValueError(f"Rollout {rollout.rollout_row_id} has a non-finite endpoint comparator.")
    return StoredEndpointEvaluationUnit(
        lineage=lineage,
        pose_chain=StoredSelectedPoseChain(
            root_pose_world=root_pose,
            selected_poses_world_cam=selected_poses,
            step_row_ids=tuple(step_row_ids),
            selected_candidate_row_ids=tuple(selected_candidate_row_ids),
        ),
        budget=budget,
        achieved_steps=achieved_steps,
        termination_reason=cast(Literal["fixed_horizon", "terminated_early"], termination_reason),
        comparator=StoredEndpointComparator(gain=comparator_gain),
    )


def selected_depth_for_step(reader: RolloutZarrStoreReader, step: StoredStep) -> StoredSelectedDepth:
    """Read and validate one selected-depth row without presentation policy."""

    def unavailable(message: str, candidate_row_id: int | None = None) -> StoredSelectedDepth:
        return StoredSelectedDepth(
            available=False,
            warning=message,
            step_row_id=step.step_row_id,
            candidate_row_id=candidate_row_id,
            depth_m=None,
            valid_mask=None,
            focal_px=None,
            principal_point_px=None,
            image_size_hw=None,
        )

    if not bool(reader.root.attrs.get("selected_depth_enabled", False)):
        return unavailable("selected_depth unavailable: store metadata has selected_depth_enabled=false.")
    try:
        group: Any = reader.root["selected_depth"]
        step_ids = np.asarray(group["step_row_id"], dtype=np.int64).reshape(-1)
        candidate_ids = np.asarray(group["candidate_row_id"], dtype=np.int64).reshape(-1)
    except KeyError as exc:
        return unavailable(f"selected_depth unavailable: missing array {exc}.")

    matches = np.flatnonzero(step_ids == step.step_row_id)
    if matches.size != 1:
        return unavailable(
            f"selected_depth unavailable: expected one row for step_row_id={step.step_row_id}, found {matches.size}."
        )
    row = int(matches[0])
    candidate_row_id = int(candidate_ids[row])
    if candidate_row_id != step.selected_candidate_row_id:
        return unavailable(
            "selected_depth candidate mismatch: "
            f"depth candidate_row_id={candidate_row_id}, "
            f"step selected_candidate_row_id={step.selected_candidate_row_id}.",
            candidate_row_id,
        )
    try:
        depth = np.asarray(group["depth_m"][row], dtype=np.float32)
        valid_mask = np.asarray(group["valid_mask"][row], dtype=np.bool_)
        focal = np.asarray(group["focal_px"][row], dtype=np.float32).reshape(-1)
        principal = np.asarray(group["principal_point_px"][row], dtype=np.float32).reshape(-1)
        image_size = np.asarray(group["image_size_hw"][row], dtype=np.int32).reshape(-1)
    except KeyError as exc:
        return unavailable(f"selected_depth unavailable: missing dense array {exc}.", candidate_row_id)
    if depth.ndim != 2 or valid_mask.shape != depth.shape:
        return unavailable(
            f"selected_depth shape mismatch: depth_m={tuple(depth.shape)} valid_mask={tuple(valid_mask.shape)}.",
            candidate_row_id,
        )
    if focal.shape[0] != 2 or principal.shape[0] != 2 or image_size.shape[0] != 2:
        return unavailable("selected_depth camera metadata must have two values per row.", candidate_row_id)
    height, width = int(image_size[0]), int(image_size[1])
    if (height, width) != tuple(depth.shape):
        return unavailable(
            f"selected_depth image_size_hw={(height, width)} does not match depth shape {tuple(depth.shape)}.",
            candidate_row_id,
        )
    depth = depth.copy()
    depth[~(valid_mask & np.isfinite(depth))] = np.nan
    return StoredSelectedDepth(
        available=True,
        warning=None,
        step_row_id=step.step_row_id,
        candidate_row_id=candidate_row_id,
        depth_m=depth,
        valid_mask=valid_mask.copy(),
        focal_px=focal.copy(),
        principal_point_px=principal.copy(),
        image_size_hw=(height, width),
    )


def _evaluation_lineage(
    reader: RolloutZarrStoreReader,
    *,
    rollout: StoredRollout,
    rollout_position: int,
) -> StoredEvaluationLineage:
    sources: Any = reader.root["sources"]
    source_positions = np.flatnonzero(
        np.asarray(sources["source_row_id"], dtype=np.int64).reshape(-1) == rollout.source_row_id
    )
    if source_positions.size != 1:
        raise ValueError(
            f"Rollout {rollout.rollout_row_id} requires exactly one source row {rollout.source_row_id}, "
            f"found {source_positions.size}."
        )
    source_position = int(source_positions[0])

    lineage_table: Any = reader.root["lineage"]
    lineage_positions = np.flatnonzero(
        np.asarray(lineage_table["rollout_row_id"], dtype=np.int64).reshape(-1) == rollout.rollout_row_id
    )
    if lineage_positions.size != 1:
        raise ValueError(
            f"Rollout {rollout.rollout_row_id} requires exactly one aligned lineage row, "
            f"found {lineage_positions.size}."
        )
    lineage_position = int(lineage_positions[0])

    rollouts: Any = reader.root["rollouts"]
    rollout_id = _required_decoded(reader, "rollout", rollouts["rollout_id"][rollout_position], label="rollout_id")
    source_sample_index = int(sources["sample_index"][source_position])
    source_shard_row = int(sources["source_shard_row"][source_position])
    root_time_ns = int(rollouts["root_time_ns"][rollout_position])
    root_trajectory_index = int(rollouts["root_trajectory_index"][rollout_position])
    root_frame_index = int(rollouts["root_frame_index"][rollout_position])
    for label, value in (
        ("source_row_id", rollout.source_row_id),
        ("source_sample_index", source_sample_index),
        ("source_shard_row", source_shard_row),
        ("root_time_ns", root_time_ns),
        ("root_trajectory_index", root_trajectory_index),
        ("root_frame_index", root_frame_index),
        ("target_row_id", rollout.target_row_id),
    ):
        if value < 0:
            raise ValueError(f"Rollout {rollout.rollout_row_id} has missing or placeholder {label}={value}.")

    source_scene = _required_decoded(reader, "scene", sources["scene_id"][source_position], label="scene_id")
    source_snippet = _required_decoded(reader, "snippet", sources["snippet_id"][source_position], label="snippet_id")
    source_split = _required_decoded(reader, "split", sources["split_id"][source_position], label="split")
    if (source_scene, source_snippet, source_split) != (rollout.scene, rollout.snippet, rollout.split):
        raise ValueError(f"Rollout {rollout.rollout_row_id} disagrees with its source scene/snippet/split lineage.")

    target = target_by_id(reader, rollout.target_row_id)
    if target is None:
        raise ValueError(f"Rollout {rollout.rollout_row_id} references missing target row {rollout.target_row_id}.")
    target_id = _required_identity(target.target_id, label="target_id")

    return StoredEvaluationLineage(
        source_row_id=rollout.source_row_id,
        source_sample_index=source_sample_index,
        source_sample_key=_required_decoded(
            reader, "source_key", sources["sample_key_id"][source_position], label="source_sample_key"
        ),
        source_shard_id=_required_decoded(
            reader, "source_shard", sources["source_shard_id"][source_position], label="source_shard_id"
        ),
        source_shard_row=source_shard_row,
        source_offline_store_manifest_hash=_required_decoded(
            reader,
            "config",
            sources["source_offline_store_manifest_hash_id"][source_position],
            label="source_offline_store_manifest_hash",
        ),
        split_manifest_hash=_required_decoded(
            reader,
            "config",
            sources["split_manifest_hash_id"][source_position],
            label="split_manifest_hash",
        ),
        split=source_split,
        scene_id=source_scene,
        snippet_id=source_snippet,
        rollout_row_id=rollout.rollout_row_id,
        rollout_id=rollout_id,
        chain_id=rollout.chain_id,
        root_time_ns=root_time_ns,
        root_trajectory_index=root_trajectory_index,
        root_frame_index=root_frame_index,
        candidate_config_hash=_required_decoded(
            reader,
            "config",
            lineage_table["candidate_config_id"][lineage_position],
            label="candidate_config_hash",
        ),
        oracle_config_hash=_required_decoded(
            reader,
            "config",
            lineage_table["oracle_config_id"][lineage_position],
            label="oracle_config_hash",
        ),
        rollout_config_hash=_required_decoded(
            reader,
            "config",
            lineage_table["rollout_config_id"][lineage_position],
            label="rollout_config_hash",
        ),
        target_row_id=rollout.target_row_id,
        target_id=target_id,
        target_protocol_version=_required_decoded(
            reader,
            "config",
            lineage_table["target_protocol_version_id"][lineage_position],
            label="target_protocol_version",
        ),
        target_crop_policy=_required_decoded(
            reader,
            "config",
            lineage_table["target_crop_policy_id"][lineage_position],
            label="target_crop_policy",
        ),
    )


def _validate_factual_steps(steps: tuple[StoredStep, ...], *, rollout_row_id: int) -> None:
    indices = tuple(step.step_index for step in steps)
    if indices != tuple(range(len(steps))):
        raise ValueError(f"Rollout {rollout_row_id} has noncontiguous factual step indices {indices}.")
    for step in steps:
        if step.step_row_id < 0:
            raise ValueError(f"Rollout {rollout_row_id} has placeholder step_row_id={step.step_row_id}.")
        selected = np.flatnonzero(step.selected_mask)
        if selected.size != 1:
            raise ValueError(
                f"Step {step.step_row_id} requires exactly one selected candidate row, found {selected.size}."
            )
        selected_index = int(selected[0])
        selected_row_id = int(step.candidate_row_ids[selected_index])
        if selected_row_id < 0 or step.selected_candidate_row_id < 0:
            raise ValueError(f"Step {step.step_row_id} has a placeholder selected candidate row ID.")
        if selected_row_id != step.selected_candidate_row_id:
            raise ValueError(
                f"Step {step.step_row_id} selected candidate ID disagreement: "
                f"step={step.selected_candidate_row_id}, candidate={selected_row_id}."
            )
        if not bool(step.actor_action_mask[selected_index]):
            raise ValueError(f"Step {step.step_row_id} selected candidate is not actor-valid.")
        if not bool(step.oracle_label_mask[selected_index]):
            raise ValueError(f"Step {step.step_row_id} selected candidate is not oracle-labelled.")
        if not np.isfinite(step.pose_world_cam[selected_index]).all():
            raise ValueError(f"Step {step.step_row_id} selected pose_world_cam contains non-finite values.")


def _readonly_pose(value: NDArray[np.float32], *, label: str) -> NDArray[np.float32]:
    pose = np.asarray(value, dtype=np.float32).reshape(12).copy()
    if not np.isfinite(pose).all():
        raise ValueError(f"{label} contains non-finite values.")
    pose.setflags(write=False)
    return pose


def _readonly_pose_matrix(value: NDArray[np.float32], *, label: str) -> NDArray[np.float32]:
    poses = np.asarray(value, dtype=np.float32).reshape(-1, 12).copy()
    if not np.isfinite(poses).all():
        raise ValueError(f"{label} contains non-finite values.")
    poses.setflags(write=False)
    return poses


def _required_decoded(
    reader: RolloutZarrStoreReader,
    dictionary: str,
    index: Any,
    *,
    label: str,
) -> str:
    values = _string_dictionary(reader, dictionary)
    position = int(index)
    value = values[position] if 0 <= position < len(values) else ""
    return _required_identity(value, label=label)


def _required_identity(value: str, *, label: str) -> str:
    normalized = value.strip()
    if not normalized or normalized.lower() in {"unknown", "none", "null", "placeholder"}:
        raise ValueError(f"Missing or placeholder {label} identity.")
    return normalized


def _string_dictionary(reader: RolloutZarrStoreReader, name: str) -> list[str]:
    try:
        encoded = np.asarray(reader.array(f"dictionaries/{name}"), dtype=np.uint8).reshape(-1).tobytes()
        values = json.loads(encoded.decode("utf-8"))
    except (KeyError, json.JSONDecodeError, UnicodeDecodeError):
        return []
    return [str(value) for value in values] if isinstance(values, list) else []


__all__ = (
    "StoredEndpointComparator StoredEndpointEvaluationUnit StoredEvaluationLineage StoredRollout "
    "StoredSelectedDepth StoredSelectedPoseChain StoredStep StoredTarget decode_invalid_reason "
    "decode_position_id endpoint_evaluation_unit rollout_at rollout_by_id rollout_steps "
    "selected_depth_for_step target_by_id target_rows"
).split()
