"""Shared tensor preparation for VIN scorer forward passes.

The helpers in this module are intentionally stateless. Model classes own
their `torch.nn.Module` instances, while this sidecar owns the repeatable
pose-frame and voxel-position transformations used by the maintained v2 and v3
scorers.
"""

from __future__ import annotations

from typing import Any

from efm3d.aria.pose import PoseTW
from torch import Tensor

from .geometry.voxel import pos_grid_from_pts_world
from .types import GlobalContext, PoseFeatures


def encode_pose_features(
    *,
    pose_encoder: Any,
    pose_world_cam: PoseTW,
    pose_world_rig_ref: PoseTW,
) -> PoseFeatures:
    """Encode candidates after converting world-camera poses into the reference rig frame.

    Args:
        pose_encoder: Encoder object exposing `encode(PoseTW)`.
        pose_world_cam: Candidate camera poses as `PoseTW` with shape
            compatible with `Tensor["B Q ..."]`.
        pose_world_rig_ref: Reference rig pose for each batch item.

    Returns:
        `PoseFeatures` containing the pose embedding, raw pose vector, and
        candidate centers in reference-rig meters.
    """
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
    """Pool pose-conditioned scene context over the shared voxel field.

    The positional grid is expressed relative to the reference rig frame before
    `PoseConditionedGlobalPool` consumes it. The returned tensors preserve the
    field device and dtype so downstream scorer heads can concatenate features
    without implicit casts.
    """
    pos_grid = pos_grid_from_pts_world(
        pts_world.to(device=field.device, dtype=field.dtype),
        t_world_voxel=t_world_voxel,
        pose_world_rig_ref=pose_world_rig_ref,
        voxel_extent=voxel_extent,
        grid_shape=(field.shape[-3], field.shape[-2], field.shape[-1]),
    )
    global_feat = global_pooler.forward(field, pose_enc, pos_grid=pos_grid).to(dtype=field.dtype)
    return GlobalContext(pos_grid=pos_grid, global_feat=global_feat)


__all__ = ["compute_global_context", "encode_pose_features"]
