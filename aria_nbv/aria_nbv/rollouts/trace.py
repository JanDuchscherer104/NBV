"""Minimal rollout replay inputs shared by the Zarr writer.

`rollouts.zarr` stores facts derived from existing counterfactual rollout
results. This module intentionally does not define a second serializable trace
hierarchy; it only carries invalidity constants, lineage facts, and the compact
record that pairs a `CounterfactualRolloutResult` with source/target lineage.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import torch

from .counterfactuals import (
    CounterfactualRolloutResult,
    CounterfactualSelectionPolicy,
    CounterfactualTrajectory,
)

INVALID_REASON_CODES: dict[str, int] = {
    "VALID": 0,
    "POSE_NONFINITE": 1,
    "POSE_OUT_OF_EXTENT": 2,
    "CAMERA_OUT_OF_EXTENT": 3,
    "COLLISION_MESH": 4,
    "CLEARANCE_TOO_SMALL": 5,
    "PATH_SEGMENT_COLLISION": 6,
    "FRUSTUM_OUT_OF_BOUNDS": 7,
    "DEPTH_NO_HIT": 8,
    "DEPTH_TOO_SPARSE": 9,
    "BACKPROJECT_EMPTY": 10,
    "CANDIDATE_DUPLICATE": 11,
    "SAMPLER_RULE_REJECTED": 12,
    "TARGET_NOT_ACTOR_VISIBLE": 13,
    "TARGET_GT_UNMATCHED": 14,
    "TARGET_CROP_EMPTY": 15,
    "TARGET_SUPPORT_TOO_LOW": 16,
    "TARGET_VISIBILITY_TOO_LOW": 17,
    "SEMIDENSE_SUPPORT_TOO_LOW": 18,
    "EVL_EVIDENCE_MISSING": 19,
    "MESH_REFERENCE_MISSING": 20,
    "ORACLE_DISTANCE_FAILED": 21,
    "CANDIDATE_ORDER_GUARD_FAILED": 22,
    "RUNTIME_ERROR": 23,
}
"""Version-1 invalidity reason bit positions for rollout replay tables."""

INVALID_REASON_VERSION = "rollout-invalidity-v1"
"""Version label for `INVALID_REASON_CODES`."""

_RULE_REASON_BITS = {
    "FreeSpaceRule": INVALID_REASON_CODES["POSE_OUT_OF_EXTENT"],
    "MinDistanceToMeshRule": INVALID_REASON_CODES["CLEARANCE_TOO_SMALL"],
    "PathCollisionRule": INVALID_REASON_CODES["PATH_SEGMENT_COLLISION"],
}

_HARD_DIAGNOSTIC_REASON_BITS = {
    "path_collision_mask": INVALID_REASON_CODES["PATH_SEGMENT_COLLISION"],
}

_PRIMARY_INVALID_REASON_PRIORITY = (
    "POSE_NONFINITE",
    "PATH_SEGMENT_COLLISION",
    "CLEARANCE_TOO_SMALL",
    "POSE_OUT_OF_EXTENT",
    "CAMERA_OUT_OF_EXTENT",
    "FRUSTUM_OUT_OF_BOUNDS",
    "DEPTH_NO_HIT",
    "DEPTH_TOO_SPARSE",
    "BACKPROJECT_EMPTY",
    "TARGET_SUPPORT_TOO_LOW",
    "TARGET_VISIBILITY_TOO_LOW",
    "SAMPLER_RULE_REJECTED",
)


@dataclass(slots=True)
class RolloutLineage:
    """Deterministic provenance for one rollout root, target, and policy.

    These fields bridge the immutable VIN source row to the rollout replay
    tables. Source lineage identifies the original shard-local VIN row, target
    lineage describes the selected Oracle target task and GT evaluation match, and
    config hashes bind candidate generation, oracle scoring, and rollout policy
    choices without embedding heavy source artifacts.
    """

    rollout_id: str = ""
    """Stable rollout identifier; filled from `RolloutZarrRecord` per retained chain."""

    chain_id: int = 0
    """Zero-based retained trajectory index."""

    scene_id: str | None = None
    snippet_id: str | None = None
    mesh_version: str | None = None
    candidate_config_hash: str | None = None
    oracle_config_hash: str | None = None
    model_checkpoint_hash: str | None = None
    random_seed: int | None = None
    rollout_policy: str = "unknown"
    source_cache_version: str | None = None
    split: str | None = None
    source_offline_store_manifest_hash: str | None = None
    source_row_id: int | None = None
    source_sample_index: int | None = None
    source_sample_key: str | None = None
    split_manifest_hash: str | None = None
    source_shard_id: str | None = None
    source_shard_row: int | None = None
    rollout_config_hash: str | None = None
    branch_schedule_id: str | None = None
    target_row_id: int | None = None
    target_id: str | None = None
    target_protocol_version: str | None = None
    target_crop_policy: str | None = None
    reason_code_version: str = INVALID_REASON_VERSION
    selection_rng_state_hash: str | None = None
    target_selection_policy: str | None = None
    target_selection_rank: int | None = None
    target_selection_score: float | None = None
    target_selection_probability: float | None = None
    target_selection_temperature: float | None = None
    target_source: str | None = None
    target_source_index: int | None = None
    target_sem_id: int | None = None
    target_inst_id: int | None = None
    target_class_name: str | None = None
    target_confidence: float | None = None
    target_projected_area_pixels: float | None = None
    target_projected_area_fraction: float | None = None
    target_semidense_support_count: int | None = None
    target_evl_support_count: int | None = None
    target_effective_support_count: float | None = None
    target_visibility_score: float | None = None
    target_support_score: float | None = None
    target_deficit_score: float | None = None
    target_center_world: tuple[float, float, float] | None = None
    target_extents: tuple[float, float, float] | None = None
    target_pose_world_object: tuple[float, ...] | None = None
    target_relative_pose_reference_object: tuple[float, ...] | None = None
    target_invalid_reason_bitset: int | None = None
    target_primary_invalid_reason: int | None = None
    target_reason_code_version: str | None = None
    matched_gt_target_row_id: int | None = None
    matched_gt_target_id: str | None = None
    gt_match_iou: float | None = None
    gt_match_score: float | None = None
    gt_match_status: str | None = None


@dataclass(slots=True)
class RolloutZarrRecord:
    """One counterfactual rollout result plus source/target lineage.

    `CounterfactualRolloutResult` owns the generated trajectories and candidate
    shells. `RolloutLineage` owns where those trajectories came from. The Zarr
    writer flattens this pair into normalized source, target, rollout, step,
    and candidate tables.
    """

    result: CounterfactualRolloutResult
    lineage: RolloutLineage
    rollout_id_prefix: str

    def lineage_for_chain(self, chain_id: int) -> RolloutLineage:
        """Return lineage with rollout id and chain id for one retained trajectory."""

        return replace(
            self.lineage,
            rollout_id=f"{self.rollout_id_prefix}-{chain_id:06d}",
            chain_id=chain_id,
            rollout_policy=_policy_name(self.result.selection_policy),
        )


def _full_candidate_vector(
    values: torch.Tensor,
    candidate_valid: torch.Tensor,
    *,
    fill_value: float | int | None = None,
    require_full_shell: bool = False,
) -> torch.Tensor:
    valid_values = values.detach().cpu().reshape(-1)
    valid_mask = candidate_valid.detach().cpu().to(dtype=torch.bool).reshape(-1)
    if require_full_shell:
        if valid_values.numel() != valid_mask.numel():
            raise ValueError(f"Expected {valid_mask.numel()} full-shell values, got {valid_values.numel()}.")
        return valid_values
    valid_count = int(valid_mask.sum().item())
    if valid_values.numel() != valid_count:
        raise ValueError(f"Expected {valid_count} valid values, got {valid_values.numel()}.")
    if fill_value is None:
        fill_value = float("nan") if torch.is_floating_point(valid_values) else 0
    full = torch.full(valid_mask.shape, fill_value, dtype=valid_values.dtype, device=valid_values.device)
    full[valid_mask] = valid_values
    return full


def _full_shell_or_default(
    values: torch.Tensor | None,
    candidate_valid: torch.Tensor,
    *,
    fill_value: float | int,
) -> torch.Tensor:
    valid_mask = candidate_valid.detach().cpu().to(dtype=torch.bool).reshape(-1)
    if values is None:
        dtype = torch.float32 if isinstance(fill_value, float) else torch.int64
        return torch.full(valid_mask.shape, fill_value, dtype=dtype)
    return _full_candidate_vector(values, candidate_valid, fill_value=fill_value, require_full_shell=True)


def _candidate_invalid_reasons(candidates: Any) -> tuple[torch.Tensor, torch.Tensor]:
    valid_mask = candidates.mask_valid.detach().cpu().to(dtype=torch.bool).reshape(-1)
    bitset = torch.zeros(valid_mask.shape, dtype=torch.int64)
    bitset[valid_mask] = 1 << INVALID_REASON_CODES["VALID"]

    previous = torch.ones_like(valid_mask)
    for rule_name, cumulative_mask in candidates.masks.items():
        current = cumulative_mask.detach().cpu().to(dtype=torch.bool).reshape(-1)
        if current.shape != valid_mask.shape:
            continue
        failed_here = previous & (~current)
        reason_bit = _RULE_REASON_BITS.get(rule_name, INVALID_REASON_CODES["SAMPLER_RULE_REJECTED"])
        bitset[failed_here] = bitset[failed_here] | (1 << reason_bit)
        previous = current

    for diagnostic_name, reason_bit in _HARD_DIAGNOSTIC_REASON_BITS.items():
        diagnostic_mask = _full_shell_bool_extra(candidates.extras, diagnostic_name, valid_mask)
        if diagnostic_mask.shape == valid_mask.shape:
            bitset[diagnostic_mask] = bitset[diagnostic_mask] | (1 << reason_bit)

    shell = candidates.shell_poses.tensor().detach().cpu()
    nonfinite = ~torch.isfinite(shell.reshape(shell.shape[0], -1)).all(dim=1)
    bitset[nonfinite] = bitset[nonfinite] | (1 << INVALID_REASON_CODES["POSE_NONFINITE"])

    unresolved_invalid = (~valid_mask) & (bitset == 0)
    bitset[unresolved_invalid] = 1 << INVALID_REASON_CODES["SAMPLER_RULE_REJECTED"]
    primary = _primary_candidate_invalid_reason(bitset=bitset, valid_mask=valid_mask)
    return bitset.to(dtype=torch.int64), primary.to(dtype=torch.int64)


def _full_shell_bool_extra(extras: dict[str, Any], name: str, valid_mask: torch.Tensor) -> torch.Tensor:
    value = extras.get(name)
    if value is None:
        return torch.zeros_like(valid_mask)
    tensor = torch.as_tensor(value).detach().cpu().to(dtype=torch.bool).reshape(-1)
    if tensor.numel() == valid_mask.numel():
        return tensor
    if tensor.numel() != int(valid_mask.sum().item()):
        return torch.zeros_like(valid_mask)
    full = torch.zeros_like(valid_mask)
    full[valid_mask] = tensor
    return full


def _primary_candidate_invalid_reason(*, bitset: torch.Tensor, valid_mask: torch.Tensor) -> torch.Tensor:
    primary = torch.full(bitset.shape, INVALID_REASON_CODES["SAMPLER_RULE_REJECTED"], dtype=torch.int64)
    primary[valid_mask] = INVALID_REASON_CODES["VALID"]
    invalid = ~valid_mask
    unresolved = invalid.clone()
    for reason_name in _PRIMARY_INVALID_REASON_PRIORITY:
        reason_code = INVALID_REASON_CODES[reason_name]
        has_reason = unresolved & ((bitset & (1 << reason_code)) != 0)
        primary[has_reason] = reason_code
        unresolved &= ~has_reason
    return primary


def _termination_reason(result: CounterfactualRolloutResult, trajectory: CounterfactualTrajectory) -> str:
    if trajectory.terminated_early:
        return "terminated_early"
    if len(trajectory.steps) >= int(result.horizon):
        return "fixed_horizon"
    return "incomplete_rollout"


def _policy_name(policy: str | CounterfactualSelectionPolicy) -> str:
    return policy.value if isinstance(policy, CounterfactualSelectionPolicy) else str(policy)


__all__ = [
    "INVALID_REASON_CODES",
    "INVALID_REASON_VERSION",
    "RolloutLineage",
    "RolloutZarrRecord",
]
