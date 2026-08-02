"""Typed, presentation-free projections over persisted rollout stores.

This module is the shared read-side owner for persisted rollout, step, target,
and selected-depth meaning.  Consumers such as the Rerun inspector may choose
their own entities, colours, transforms, and plots, but obtain the ordered
full-shell rows, action masks, selected transitions, and decoded dictionaries
from these projections.  It performs no store mutation or display policy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

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


def decode_invalid_reason(reason: int | np.integer[Any]) -> str:
    """Return the frozen invalid-reason name for one numeric code."""
    return _INVALID_REASON_NAMES.get(int(reason), f"reason_{int(reason)}")


def decode_position_id(position_id: int | np.integer[Any]) -> str:
    """Return the frozen candidate-position name for one numeric id."""

    value = int(position_id)
    return _POSITION_NAMES.get(value, "unknown" if value < 0 else f"position_{value}")


def rollout_at(reader: RolloutZarrStoreReader, row_position: int) -> StoredRollout:
    """Resolve one rollout by physical row position."""

    rollouts = reader.root["rollouts"]
    steps = reader.root["steps"]
    rollout_ids = np.asarray(rollouts["rollout_row_id"], dtype=np.int64).reshape(-1)
    position = int(row_position)
    if position < 0 or position >= rollout_ids.shape[0]:
        raise IndexError(f"rollout row position {position} is outside [0, {rollout_ids.shape[0]}).")

    rollout_row_id = int(rollout_ids[position])
    step_rollout_ids = np.asarray(steps["rollout_row_id"], dtype=np.int64).reshape(-1)
    step_indices = np.asarray(steps["step_index"], dtype=np.int64).reshape(-1)
    step_positions = np.flatnonzero(step_rollout_ids == rollout_row_id).astype(np.int64)
    if step_positions.size == 0:
        raise ValueError(f"Rollout row {rollout_row_id} has no step rows.")
    step_positions = step_positions[np.argsort(step_indices[step_positions], kind="stable")]

    scene_names = _string_dictionary(reader, "scene")
    snippet_names = _string_dictionary(reader, "snippet")
    split_names = _string_dictionary(reader, "split")
    policy_names = _string_dictionary(reader, "policy")

    def decoded(values: list[str], index: object) -> str:
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

    candidates = reader.root["candidates"]
    diagnostics = reader.root["candidate_diagnostics"]
    step_table = reader.root["steps"]
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
    targets = reader.root["targets"]
    target_row_ids = np.asarray(targets["target_row_id"], dtype=np.int64).reshape(-1)
    target_names = _string_dictionary(reader, "target")
    source_names = _string_dictionary(reader, "target_source")
    class_names = _string_dictionary(reader, "class_name")
    status_names = _string_dictionary(reader, "target_match_status")

    def decoded(values: list[str], index: object) -> str:
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
        group = reader.root["selected_depth"]
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


def _string_dictionary(reader: RolloutZarrStoreReader, name: str) -> list[str]:
    try:
        encoded = np.asarray(reader.array(f"dictionaries/{name}"), dtype=np.uint8).reshape(-1).tobytes()
        values = json.loads(encoded.decode("utf-8"))
    except (KeyError, json.JSONDecodeError, UnicodeDecodeError):
        return []
    return [str(value) for value in values] if isinstance(values, list) else []


__all__ = (
    "StoredRollout StoredSelectedDepth StoredStep StoredTarget decode_invalid_reason decode_position_id "
    "rollout_at rollout_by_id rollout_steps selected_depth_for_step target_by_id target_rows"
).split()
