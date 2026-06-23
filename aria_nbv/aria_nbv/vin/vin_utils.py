"""Shared VIN helper dataclasses and utility functions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch
from efm3d.aria.pose import PoseTW
from torch import Tensor

from ..data_handling import VinSnippetView
from .encoders import LearnableFourierFeaturesConfig
from .geometry.voxel import pos_grid_from_pts_world


@dataclass(slots=True)
class PreparedInputs:
    """Prepared inputs for VIN v3 forward pass."""

    pose_world_cam: PoseTW
    """``PoseTW["B N 12"]`` Candidate poses in world frame."""

    pose_world_rig_ref: PoseTW
    """``PoseTW["B 12"]`` Reference rig pose in world frame."""

    t_world_voxel: PoseTW
    """``PoseTW["B 12"]`` World←voxel pose for the EVL voxel grid."""

    batch_size: int
    """Batch size inferred from candidate poses."""

    num_candidates: int
    """Number of candidates per batch."""

    device: torch.device
    """Device for tensors in the forward pass."""

    snippet: VinSnippetView
    """VIN snippet view (padded semidense points) for semidense features."""


@dataclass(slots=True)
class PoseFeatures:
    """Pose-related features for VIN v3."""

    pose_enc: Tensor
    """``Tensor["B N E", float32]`` Pose encoder output."""

    pose_vec: Tensor
    """``Tensor["B N D", float32]`` Pose vector fed into the pose encoder."""

    candidate_center_rig_m: Tensor
    """``Tensor["B N 3", float32]`` Candidate centers in reference rig frame."""


@dataclass(slots=True)
class FieldBundle:
    """Scene field tensors for VIN v3."""

    field_in: Tensor
    """``Tensor["B C_in D H W", float32]`` Raw scene field."""

    field: Tensor
    """``Tensor["B C_out D H W", float32]`` Projected scene field."""

    aux: dict[str, Tensor]
    """Auxiliary channels (e.g. counts_norm, occ_pr)."""


@dataclass(slots=True)
class GlobalContext:
    """Global context features computed from the scene field."""

    pos_grid: Tensor
    """``Tensor["B 3 D H W", float32]`` Normalized position grid."""

    global_feat: Tensor
    """``Tensor["B N C", float32]`` Pose-conditioned global features."""


def largest_divisor_leq(n: int, max_divisor: int) -> int:
    """Return the largest divisor of ``n`` that is <= ``max_divisor``.

    This helper is used to choose a valid GroupNorm group count. GroupNorm
    requires ``num_groups`` to divide ``num_channels`` exactly. We therefore
    compute:

        g = max { d : d <= max_divisor and n % d == 0 }.

    Args:
        n: Channel dimension to be normalized.
        max_divisor: Upper bound for the group count.

    Returns:
        Largest valid group count (>=1).
    """
    g = min(max_divisor, n)
    while g > 1 and (n % g) != 0:
        g -= 1
    return max(1, g)


def validate_pos_grid_xyz_encoder(
    value: LearnableFourierFeaturesConfig,
) -> LearnableFourierFeaturesConfig:
    """Validate that a position-grid encoder consumes XYZ coordinates."""
    if value.input_dim != 3:
        raise ValueError("pos_grid_encoder_lff.input_dim must be 3 for XYZ coordinates.")
    return value


def encode_pose_features(
    *,
    pose_encoder: Any,
    pose_world_cam: PoseTW,
    pose_world_rig_ref: PoseTW,
) -> PoseFeatures:
    """Encode candidate poses expressed in the reference rig frame."""
    pose_rig_cam = pose_world_rig_ref.inverse()[:, None] @ pose_world_cam
    pose_out = pose_encoder.encode(pose_rig_cam)
    return PoseFeatures(
        pose_enc=pose_out.pose_enc,
        pose_vec=pose_out.pose_vec,
        candidate_center_rig_m=pose_out.center_m,
    )


def compute_global_context(
    *,
    global_pooler: Any,
    field: Tensor,
    pose_enc: Tensor,
    pts_world: Tensor,
    t_world_voxel: PoseTW,
    pose_world_rig_ref: PoseTW,
    voxel_extent: Tensor,
) -> GlobalContext:
    """Compute pose-conditioned global features from the shared scene field."""
    pos_grid = pos_grid_from_pts_world(
        pts_world.to(device=field.device, dtype=field.dtype),
        t_world_voxel=t_world_voxel,
        pose_world_rig_ref=pose_world_rig_ref,
        voxel_extent=voxel_extent,
        grid_shape=(field.shape[-3], field.shape[-2], field.shape[-1]),
    )
    global_feat = global_pooler.forward(field, pose_enc, pos_grid=pos_grid).to(dtype=field.dtype)
    return GlobalContext(pos_grid=pos_grid, global_feat=global_feat)
