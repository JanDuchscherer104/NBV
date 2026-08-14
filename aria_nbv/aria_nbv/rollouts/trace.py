"""Minimal rollout replay inputs shared by the Zarr writer.

`rollouts.zarr` stores facts derived from existing counterfactual rollout
results. This module owns frozen invalidity codecs and composed lineage facts;
generation-pipeline aggregates remain outside replay and storage. It does not
define a second serializable trace hierarchy.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

import torch

from .replay.policy import CounterfactualSelectionPolicy
from .replay.state import CounterfactualRolloutResult, CounterfactualTrajectory

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
class SourceLineage:
    """Immutable VIN source identity for one generated rollout root."""

    scene_id: str | None = None
    """Source scene identifier copied from the immutable VIN index."""

    snippet_id: str | None = None
    """Source snippet identifier copied from the immutable VIN index."""

    mesh_version: str | None = None
    """Fingerprint/version of the oracle mesh used for rendering and labels."""

    source_cache_version: str | None = None
    """Schema/version label of the immutable VIN offline source cache."""

    split: str | None = None
    """VIN source split associated with this rollout root."""

    source_offline_store_manifest_hash: str | None = None
    """Hash of the complete VIN source-store manifest."""

    source_row_id: int | None = None
    """Dense source-table row id assigned by the rollout store writer."""

    source_sample_index: int | None = None
    """Stable VIN dataset sample index used to reopen the source row."""

    source_sample_key: str | None = None
    """Canonical VIN sample key used to detect source-index drift."""

    split_manifest_hash: str | None = None
    """Hash binding the split name and ordered source-row ownership records."""

    source_shard_id: str | None = None
    """Identifier of the immutable VIN storage shard containing the source."""

    source_shard_row: int | None = None
    """Zero-based row within ``source_shard_id``."""


@dataclass(slots=True)
class TargetLineage:
    """Actor descriptor and privileged Oracle target lineage."""

    target_row_id: int | None = None
    """Dense target-table row id assigned by the rollout store writer."""

    target_id: str | None = None
    """Stable target-task identifier from selection or oracle task sampling."""

    target_protocol_version: str | None = None
    """Versioned contract governing target evidence and label boundaries."""

    target_crop_policy: str | None = None
    """Versioned oracle geometry-crop policy used for target RRI labels."""

    target_selection_policy: str | None = None
    """Policy that admitted this target task before rollout generation."""

    target_selection_rank: int | None = None
    """Zero-based target rank within the source sample's selected set."""

    target_selection_score: float | None = None
    """Target-interest score under the recorded selection protocol."""

    target_selection_probability: float | None = None
    """Sampling probability assigned to the selected target task."""

    target_selection_temperature: float | None = None
    """Temperature used by stochastic target selection, when applicable."""

    target_source: str | None = None
    """Target source protocol, distinguishing observed and oracle task inputs."""

    target_source_index: int | None = None
    """Row index in the source OBB/task table before target filtering."""

    target_sem_id: int | None = None
    """Semantic class id carried by the chosen target task."""

    target_inst_id: int | None = None
    """Instance id carried by the chosen target task."""

    target_class_name: str | None = None
    """Human-readable semantic class label for audit and inspection."""

    target_confidence: float | None = None
    """Source OBB confidence; actor-visible only for observed-target protocols."""

    target_projected_area_pixels: float | None = None
    """Largest clipped target projection area, in square pixels."""

    target_projected_area_fraction: float | None = None
    """Projected area divided by the target selector's image normalizer."""

    target_semidense_support_count: int | None = None
    """Semidense world points inside the selected target volume."""

    target_evl_support_count: int | None = None
    """Positive EVL evidence points inside the selected target volume."""

    target_effective_support_count: float | None = None
    """Weighted support count used by the target-selection protocol."""

    target_visibility_score: float | None = None
    """Projected-visibility factor used when selecting observed targets."""

    target_support_score: float | None = None
    """Support-sufficiency factor used by target ranking."""

    target_deficit_score: float | None = None
    """Unsaturated-support factor favoring targets with improvement headroom."""

    target_center_world: tuple[float, float, float] | None = None
    """Target OBB center ``(x, y, z)`` in world metres."""

    target_extents: tuple[float, float, float] | None = None
    """Full target OBB side lengths in object axes, in metres."""

    target_pose_world_object: tuple[float, ...] | None = None
    """Flattened 12-value physical transform from target object to world."""

    target_relative_pose_reference_object: tuple[float, ...] | None = None
    """Flattened 12-value transform from target object to snippet reference."""

    target_invalid_reason_bitset: int | None = None
    """Versioned bitset of target-level invalidity facts; never encoded as score."""

    target_primary_invalid_reason: int | None = None
    """Prioritized target invalidity code for compact inspection."""

    target_reason_code_version: str | None = None
    """Version of target-selection invalidity bit positions."""

    matched_gt_target_row_id: int | None = None
    """Oracle-only GT target row matched after target selection."""

    matched_gt_target_id: str | None = None
    """Oracle-only stable identifier of the matched GT target."""

    gt_match_iou: float | None = None
    """Oracle-only oriented-box IoU used for target-label auditing."""

    gt_match_score: float | None = None
    """Oracle-only composite score used to choose the GT match."""

    gt_match_status: str | None = None
    """Oracle-only match outcome controlling target-label admissibility."""


@dataclass(slots=True)
class PolicyLineage:
    """Candidate, Oracle, and replay-policy configuration lineage."""

    candidate_config_hash: str | None = None
    """Stable hash of candidate-shell generation and hard-validity controls."""

    oracle_config_hash: str | None = None
    """Stable hash of Oracle rendering, crop, fusion, and RRI controls."""

    model_checkpoint_hash: str | None = None
    """Optional learned-policy checkpoint hash; absent for built-in policies."""

    random_seed: int | None = None
    """Recipe/root seed from which deterministic node seeds were derived."""

    rollout_policy: str = "unknown"
    """Action-selection policy used for this retained rollout chain."""

    rollout_config_hash: str | None = None
    """Stable hash of horizon, branching, policy, and diversity controls."""

    branch_schedule_id: str | None = None
    """Human-stable recipe or schedule identifier for branch provenance."""

    reason_code_version: str = INVALID_REASON_VERSION
    """Version of rollout candidate invalidity bit positions."""

    selection_rng_state_hash: str | None = None
    """Hash of target-selection RNG state for deterministic replay audits."""


@dataclass(slots=True)
class RolloutLineage:
    """Composed source, target, and policy lineage flattened only by the writer."""

    source: SourceLineage = field(default_factory=SourceLineage)
    """Immutable VIN source identity for the rollout root."""

    target: TargetLineage = field(default_factory=TargetLineage)
    """Actor descriptor and privileged Oracle target lineage."""

    policy: PolicyLineage = field(default_factory=PolicyLineage)
    """Candidate, Oracle, and replay-policy configuration lineage."""

    rollout_id: str = ""
    """Stable identifier assigned to one retained rollout chain."""

    chain_id: int = 0
    """Zero-based retained trajectory index within the rollout root."""

    def for_chain(self, chain_id: int, *, rollout_id: str, rollout_policy: str) -> "RolloutLineage":
        """Return persisted lineage identifiers for one retained chain."""

        return replace(
            self,
            rollout_id=rollout_id,
            chain_id=int(chain_id),
            policy=replace(self.policy, rollout_policy=rollout_policy),
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


def termination_reason(result: CounterfactualRolloutResult, trajectory: CounterfactualTrajectory) -> str:
    """Classify why a replay chain stopped without inventing a partial label.

    Early termination takes precedence over horizon completion.  A trajectory
    shorter than ``result.horizon`` without the explicit early-stop marker is
    reported as ``incomplete_rollout`` so persisted stores can distinguish a
    valid terminal transition from missing generation output.
    """

    if trajectory.terminated_early:
        return "terminated_early"
    if len(trajectory.steps) >= int(result.horizon):
        return "fixed_horizon"
    return "incomplete_rollout"


def policy_name(policy: str | CounterfactualSelectionPolicy) -> str:
    """Return the stable persisted policy label for enum or string inputs."""

    return policy.value if isinstance(policy, CounterfactualSelectionPolicy) else str(policy)


# Preserve the original private imports used by persisted-store code.
_termination_reason = termination_reason
_policy_name = policy_name


__all__ = [
    "INVALID_REASON_CODES",
    "INVALID_REASON_VERSION",
    "PolicyLineage",
    "RolloutLineage",
    "SourceLineage",
    "TargetLineage",
    "termination_reason",
    "policy_name",
]
