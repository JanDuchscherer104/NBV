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
from torch import Tensor, nn

from ..data_handling._raw import (
    EfmSnippetView,
    VinSnippetView,
    is_efm_snippet_view_instance,
    is_vin_snippet_view_instance,
)
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


def apply_vin_scorer_film(
    global_feat: Tensor,
    cond_feat: Tensor,
    *,
    film: nn.Module,
    norm: nn.GroupNorm | None,
) -> Tensor:
    """Apply FiLM modulation to per-candidate global scene features.

    Concrete scorer models own the trainable FiLM projection and optional
    normalization modules. This stateless helper only applies the shared
    ``global * (1 + gamma) + beta`` formula and preserves candidate-axis
    broadcasting when ``cond_feat`` has shape ``Tensor["B 1 F"]``.

    Args:
        global_feat: ``Tensor["B Nq F_g"]`` global features to modulate.
        cond_feat: ``Tensor["B Nq F_c"]`` or ``Tensor["B 1 F_c"]`` conditioning
            features consumed by ``film``.
        film: Module that maps ``cond_feat`` to ``2 * F_g`` FiLM parameters.
        norm: Optional GroupNorm over ``F_g`` channels.

    Returns:
        ``Tensor["B Nq F_g"]`` after FiLM and optional normalization.
    """
    film_out = film(cond_feat.to(dtype=global_feat.dtype))
    gamma, beta = film_out.chunk(2, dim=-1)
    modulated = global_feat * (1.0 + gamma) + beta
    if norm is not None:
        modulated = norm(modulated.transpose(1, 2)).transpose(1, 2)
    return modulated


def encode_trajectory_context(
    *,
    traj_encoder: Any | None,
    snippet: EfmSnippetView | VinSnippetView | None,
    pose_world_rig_ref: PoseTW,
    batch_size: int,
    device: torch.device,
    dtype: torch.dtype,
) -> tuple[Tensor | None, Tensor | None, Tensor | None]:
    """Encode snippet rig trajectory poses in the reference rig frame.

    Maintained VIN scorers use this helper to share the deterministic trajectory
    preparation step while keeping attention modules and scorer-head ownership
    inside each model. The snippet trajectory is interpreted as world-from-rig
    poses ``T_w_rig_t`` and converted to reference-rig coordinates via
    ``T_r_ref_rig_t = (T_w_r_ref)^-1 @ T_w_rig_t`` before the configured
    `aria_nbv.vin.encoders.trajectory.TrajectoryEncoder` consumes it.

    Args:
        traj_encoder: Optional trajectory encoder. When ``None``, the helper
            returns ``(None, None, None)``.
        snippet: VIN or EFM snippet view carrying ``t_world_rig``. Missing
            trajectories produce a zero pooled feature and no per-frame tensors,
            preserving the existing V2/V3 fallback.
        pose_world_rig_ref: ``PoseTW["B 12"]`` reference rig poses ``T_w_r``.
        batch_size: Batch size ``B`` used for broadcast validation.
        device: Target device for trajectory tensors and outputs.
        dtype: Output dtype.

    Returns:
        Tuple ``(traj_feat, traj_pose_vec, traj_pose_enc)`` where
        ``traj_feat`` is ``Tensor["B F_traj"]`` when an encoder is configured,
        and the per-frame tensors are ``None`` when no trajectory poses are
        available.
    """
    if traj_encoder is None:
        return None, None, None

    traj_world_rig: PoseTW | None = None
    if snippet is not None and is_vin_snippet_view_instance(snippet):
        traj_world_rig = snippet.t_world_rig
    elif snippet is not None and is_efm_snippet_view_instance(snippet):
        try:
            traj_world_rig = snippet.trajectory.t_world_rig
        except Exception:
            traj_world_rig = None
    elif snippet is not None:
        try:
            traj_world_rig = snippet.trajectory.t_world_rig
        except Exception:
            traj_world_rig = None

    if traj_world_rig is None or traj_world_rig.numel() == 0:
        traj_feat = torch.zeros(
            (batch_size, traj_encoder.out_dim),
            device=device,
            dtype=dtype,
        )
        return traj_feat, None, None

    traj_world_rig = traj_world_rig.to(device=device, dtype=torch.float32)
    if traj_world_rig.ndim == 2:
        traj_world_rig = PoseTW(traj_world_rig._data.unsqueeze(0))
    elif traj_world_rig.ndim != 3:
        raise ValueError(
            f"Expected trajectory poses with ndim 2 or 3, got {traj_world_rig.ndim}.",
        )
    if traj_world_rig.shape[0] == 1 and batch_size > 1:
        traj_world_rig = PoseTW(traj_world_rig._data.expand(batch_size, -1, -1))
    elif traj_world_rig.shape[0] != batch_size:
        raise ValueError(
            "Trajectory batch size must match candidates or be broadcastable.",
        )

    t_rig_world = pose_world_rig_ref.inverse()
    traj_rig_ref = t_rig_world[:, None] @ traj_world_rig
    traj_out = traj_encoder.encode_poses(traj_rig_ref)
    traj_feat = traj_out.pooled
    if traj_feat is None:
        traj_feat = traj_out.per_frame.pose_enc.mean(dim=1)
    traj_feat = traj_feat.to(device=device, dtype=dtype)
    traj_pose_vec = traj_out.per_frame.pose_vec.to(device=device, dtype=dtype)
    traj_pose_enc = traj_out.per_frame.pose_enc.to(device=device, dtype=dtype)
    return traj_feat, traj_pose_vec, traj_pose_enc


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
    "apply_vin_scorer_film",
    "build_vin_scorer_scene_field",
    "compute_global_context",
    "encode_pose_features",
    "encode_trajectory_context",
]
