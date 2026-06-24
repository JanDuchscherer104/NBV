"""Shared tensor preparation for VIN scorer forward passes.

The helpers in this module are intentionally stateless. Model classes own
their `torch.nn.Module` instances, while this sidecar owns the repeatable
pose-frame and voxel-position transformations used by the maintained v2 and v3
scorers.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import torch
from efm3d.aria.pose import PoseTW
from torch import Tensor

from .geometry.voxel import pos_grid_from_pts_world
from .types import EvlBackboneOutput, GlobalContext, PoseFeatures


def build_vin_scorer_scene_field(
    backbone_out: EvlBackboneOutput,
    *,
    scene_field_channels: Sequence[str],
    model_name: str,
) -> tuple[Tensor, dict[str, Tensor]]:
    """Build the soft-coverage scene field used by maintained VIN scorers.

    This helper preserves the V2/V3 scorer contract where ``unknown`` is
    defined as ``1 - counts_norm`` rather than the geometry helper's binary
    ``1 - observed`` contract. The returned ``field_in`` is still unprojected;
    concrete models own the trainable ``field_proj`` module and wrap the result
    in :class:`aria_nbv.vin.types.FieldBundle`.

    Args:
        backbone_out: EVL backbone outputs with occupancy, centerness,
            observation count, and optional free-space tensors.
        scene_field_channels: Ordered channel names to concatenate.
        model_name: Name included in validation errors, e.g. ``"VinModelV3"``.

    Returns:
        Tuple of ``(field_in, field_aux)`` where ``field_in`` has shape
        ``Tensor["B C D H W"]`` and ``field_aux`` maps every derived channel to
        its single-channel tensor.
    """
    occ_pr = backbone_out.occ_pr.to(dtype=torch.float32)  # type: ignore[union-attr]
    cent_pr = backbone_out.cent_pr.to(dtype=torch.float32)  # type: ignore[union-attr]
    occ_input = backbone_out.occ_input.to(dtype=torch.float32)  # type: ignore[union-attr]
    counts = backbone_out.counts.to(dtype=torch.float32)  # type: ignore[union-attr]

    max_counts = counts.amax(dim=(-3, -2, -1), keepdim=True).clamp_min(1.0)
    counts_norm = torch.log1p(counts) / torch.log1p(max_counts)
    counts_norm = counts_norm.unsqueeze(1).clamp(0.0, 1.0)
    observed = (counts > 0).to(dtype=counts_norm.dtype).unsqueeze(1)
    unknown = (1.0 - counts_norm).clamp(0.0, 1.0)
    if isinstance(backbone_out.free_input, torch.Tensor):
        free_input = backbone_out.free_input.to(dtype=torch.float32)
    else:
        free_input = observed * (1.0 - occ_input)
    new_surface_prior = unknown * occ_pr

    field_aux = {
        "occ_pr": occ_pr,
        "cent_pr": cent_pr,
        "occ_input": occ_input,
        "counts_norm": counts_norm,
        "observed": observed,
        "unknown": unknown,
        "free_input": free_input,
        "new_surface_prior": new_surface_prior,
    }
    missing = [name for name in scene_field_channels if name not in field_aux]
    if missing:
        raise ValueError(
            f"{model_name}.scene_field_channels contains unknown entries: {missing}. Available: {sorted(field_aux)}.",
        )
    field_in = torch.cat([field_aux[name] for name in scene_field_channels], dim=1)
    field_in = field_in.to(device=backbone_out.voxel_extent.device)
    return field_in, field_aux


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


__all__ = [
    "build_vin_scorer_scene_field",
    "compute_global_context",
    "encode_pose_features",
]
