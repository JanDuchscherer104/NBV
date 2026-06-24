"""Stateless helper functions for VIN scorer implementations."""

from __future__ import annotations

from typing import Any

from efm3d.aria.pose import PoseTW
from torch import Tensor

from .encoders import LearnableFourierFeaturesConfig
from .geometry.voxel import pos_grid_from_pts_world
from .types import GlobalContext, PoseFeatures


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
