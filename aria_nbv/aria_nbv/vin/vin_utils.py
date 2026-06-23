"""Shared VIN helper dataclasses and utility functions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import torch
from efm3d.aria.pose import PoseTW
from efm3d.utils.voxel_sampling import pc_to_vox, sample_voxels
from torch import Tensor
from torch.nn import functional as functional

from ..data_handling import VinSnippetView
from .pose_encoding import LearnableFourierFeaturesConfig


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


def sample_voxel_field(
    field: Tensor,
    *,
    points_world: Tensor,
    t_world_voxel: PoseTW,
    voxel_extent: Tensor,
) -> tuple[Tensor, Tensor]:
    """Sample a voxel-aligned field at world points.

    We map world-space points into EVL's voxel frame using the provided
    ``voxel/T_world_voxel`` pose:

        T_voxel_world = (T_world_voxel)^{-1}
        p_voxel = T_voxel_world * p_world.

    The voxel frame is **metric** (meters). We convert metric coordinates to
    voxel indices via the extent bounds:

        i_x = (x - x_min) / dx,  dx = (x_max - x_min) / W,
        i_y = (y - y_min) / dy,  dy = (y_max - y_min) / H,
        i_z = (z - z_min) / dz,  dz = (z_max - z_min) / D.

    ``pc_to_vox`` returns both these indices and an *extent* validity mask.
    ``sample_voxels`` then performs trilinear interpolation in grid coordinates
    (``grid_sample`` under the hood) and returns a *grid* validity mask.

    Args:
        field: ``Tensor["B C D H W"]`` voxel-aligned feature field.
        points_world: ``Tensor["B N K 3"]`` world points (K points per candidate).
        t_world_voxel: ``PoseTW["B 12"]`` world<-voxel transform.
        voxel_extent: ``Tensor["B 6"]`` voxel grid extent in voxel frame
            ``[x_min,x_max,y_min,y_max,z_min,z_max]``.

    Returns:
        Tuple of:
            - tokens: ``Tensor["B N K C", float32]`` sampled features.
            - valid: ``Tensor["B N K", bool]`` mask of in-bounds samples
              (extent AND grid validity).
    """
    if field.ndim != 5:
        raise ValueError(f"Expected field shape (B,C,D,H,W), got {tuple(field.shape)}.")
    if points_world.ndim != 4:
        raise ValueError(
            f"Expected points_world shape (B,N,K,3), got {tuple(points_world.shape)}.",
        )
    if int(points_world.shape[-1]) != 3:
        raise ValueError(
            f"Expected points_world[..., 3], got {tuple(points_world.shape)}.",
        )

    batch_size, field_channels, grid_d, grid_h, grid_w = field.shape
    _, num_candidates, num_points, _ = points_world.shape

    t_world_voxel_b = t_world_voxel
    if t_world_voxel_b.ndim == 1:
        t_world_voxel_b = PoseTW(t_world_voxel_b._data.unsqueeze(0))
    if int(t_world_voxel_b.shape[0]) != int(batch_size):
        if int(t_world_voxel_b.shape[0]) == 1:
            t_world_voxel_b = PoseTW(t_world_voxel_b._data.expand(batch_size, 12))
        else:
            raise ValueError(
                "t_world_voxel must have batch size 1 or match field batch size.",
            )

    vox_extent = voxel_extent.to(device=field.device, dtype=torch.float32)
    if vox_extent.ndim == 1:
        vox_extent = vox_extent.view(1, 6).expand(batch_size, 6)
    if vox_extent.shape != (batch_size, 6):
        raise ValueError(
            f"Expected voxel_extent shape (B,6), got {tuple(vox_extent.shape)}.",
        )

    world_points_flat = points_world.to(device=field.device, dtype=field.dtype).reshape(
        batch_size,
        num_candidates * num_points,
        3,
    )

    # NOTE: EVL's voxel field is defined in the *voxel frame* (metres), but our candidates/frustum points are in WORLD.
    # EVL provides `voxel/T_world_voxel` (world←voxel). We invert it to get voxel←world and map points into voxel coords.
    # NOTE: If you ever swap EVL conventions or change voxel-grid anchoring, re-verify this transform (sanity check:
    # voxelized points should be stable under small candidate translations).
    t_voxel_world = t_world_voxel_b.inverse()  # voxel<-world
    voxel_points_m = t_voxel_world * world_points_flat  # B (N*K) 3 in voxel frame (metres)

    pts_vox_id, valid_extent = pc_to_vox(
        voxel_points_m.to(dtype=torch.float32),
        vW=int(grid_w),
        vH=int(grid_h),
        vD=int(grid_d),
        voxel_extent=vox_extent,
    )
    # sample_voxels does not support NaNs; replace invalid coords with 0 and rely on validity masks below.
    pts_vox_id = torch.nan_to_num(pts_vox_id, nan=0.0, posinf=0.0, neginf=0.0)

    samp, valid_grid = sample_voxels(
        field,
        pts_vox_id,
        differentiable=False,
    )  # B C (N*K), B (N*K)
    valid = (valid_extent & valid_grid).reshape(batch_size, num_candidates, num_points)
    tokens = samp.transpose(1, 2).reshape(
        batch_size,
        num_candidates,
        num_points,
        field_channels,
    )
    return tokens, valid


def candidate_valid_from_token(
    token_valid: Tensor,
    *,
    min_valid_frac: float,
) -> Tensor:
    """Convert per-token validity into a per-candidate mask."""
    if token_valid.ndim < 1:
        raise ValueError(f"Expected token_valid with ndim>=1, got {tuple(token_valid.shape)}.")
    valid_frac = token_valid.float().mean(dim=-1)
    return valid_frac >= min_valid_frac


def build_scene_field(
    out: Any,
    *,
    use_channels: list[str],
    occ_input_threshold: float,
    counts_norm_mode: Literal["log1p", "linear"],
    occ_pr_is_logits: bool,
) -> Tensor:
    """Build a compact voxel-aligned scene field from EVL head/evidence tensors."""

    def _require(name: str) -> Tensor:
        value = getattr(out, name)
        if not isinstance(value, torch.Tensor):
            raise KeyError(
                f"Missing backbone output '{name}'. Ensure EvlBackboneConfig.features_mode includes 'heads'.",
            )
        return value

    parts: dict[str, Tensor] = {}

    if "occ_pr" in use_channels or "new_surface_prior" in use_channels:
        occ_pr = _require("occ_pr").to(dtype=torch.float32)
        if occ_pr_is_logits:
            occ_pr = torch.sigmoid(occ_pr)
        parts["occ_pr"] = occ_pr

    if "occ_input" in use_channels or "free_input" in use_channels:
        parts["occ_input"] = _require("occ_input").to(dtype=torch.float32)

    if "cent_pr" in use_channels:
        parts["cent_pr"] = _require("cent_pr").to(dtype=torch.float32)

    if "free_input" in use_channels:
        if isinstance(out.free_input, torch.Tensor):
            parts["free_input"] = out.free_input.to(dtype=torch.float32)
        else:
            counts = _require("counts")
            observed = (counts > 0).to(dtype=torch.float32).unsqueeze(1)
            occ_evidence = (parts["occ_input"] > occ_input_threshold).to(dtype=torch.float32)
            parts["free_input"] = observed * (1.0 - occ_evidence)

    if (
        "counts_norm" in use_channels
        or "observed" in use_channels
        or "unknown" in use_channels
        or "new_surface_prior" in use_channels
        or "free_input" in use_channels
    ):
        counts = _require("counts")
        observed = (counts > 0).to(dtype=torch.float32).unsqueeze(1)
        parts["observed"] = observed
        parts["unknown"] = 1.0 - observed

        max_counts = counts.amax(dim=(-3, -2, -1), keepdim=True).clamp_min(1.0)
        if counts_norm_mode == "log1p":
            parts["counts_norm"] = torch.log1p(counts).unsqueeze(1) / torch.log1p(max_counts).unsqueeze(1)
        else:
            parts["counts_norm"] = (counts / max_counts).unsqueeze(1)

    if "new_surface_prior" in use_channels:
        parts["new_surface_prior"] = parts["unknown"] * parts["occ_pr"]

    missing = [name for name in use_channels if name not in parts]
    if missing:
        raise KeyError(f"Unsupported scene-field channel(s): {missing}.")
    return torch.cat([parts[name] for name in use_channels], dim=1)


def infer_padded_grid_shape(
    num_pts: int,
    target_shape: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Infer a symmetrically padded grid shape from a flattened voxel count."""
    d_t, h_t, w_t = target_shape
    if num_pts == d_t * h_t * w_t:
        return target_shape
    for pad in range(1, 4):
        d_p, h_p, w_p = d_t + 2 * pad, h_t + 2 * pad, w_t + 2 * pad
        if num_pts == d_p * h_p * w_p:
            return (d_p, h_p, w_p)
    raise ValueError(
        "pts_world size mismatch: "
        f"got {num_pts} points; expected {d_t * h_t * w_t} "
        f"for grid_shape {target_shape} or a symmetric padding variant.",
    )


def center_crop_grid(
    grid: Tensor,
    target_shape: tuple[int, int, int],
) -> Tensor:
    """Center-crop a voxel grid or raise when the crop is impossible."""
    d0, h0, w0 = int(grid.shape[1]), int(grid.shape[2]), int(grid.shape[3])
    d_t, h_t, w_t = target_shape
    if (d0, h0, w0) == target_shape:
        return grid
    if d0 < d_t or h0 < h_t or w0 < w_t:
        raise ValueError(f"pts_world grid {d0, h0, w0} smaller than target {target_shape}.")
    if (d0 - d_t) % 2 != 0 or (h0 - h_t) % 2 != 0 or (w0 - w_t) % 2 != 0:
        raise ValueError(f"pts_world grid {d0, h0, w0} cannot be center-cropped to {target_shape}.")
    d_start = (d0 - d_t) // 2
    h_start = (h0 - h_t) // 2
    w_start = (w0 - w_t) // 2
    return grid[
        :,
        d_start : d_start + d_t,
        h_start : h_start + h_t,
        w_start : w_start + w_t,
        :,
    ]


def pos_grid_from_pts_world(
    pts_world: Tensor,
    *,
    t_world_voxel: PoseTW,
    pose_world_rig_ref: PoseTW,
    voxel_extent: Tensor,
    grid_shape: tuple[int, int, int],
) -> Tensor:
    """Convert voxel center points to a per-axis normalized position grid in the reference rig frame.

    If the provided points correspond to a larger grid (e.g. before a valid-kernel
    Conv3d shrink), the grid is center-cropped to ``grid_shape``.
    """

    if pts_world.ndim == 3:
        batch_size, num_pts, _ = pts_world.shape
        pts_shape = infer_padded_grid_shape(int(num_pts), grid_shape)
        pts_grid = pts_world.view(
            batch_size,
            pts_shape[0],
            pts_shape[1],
            pts_shape[2],
            3,
        )
        pts_grid = center_crop_grid(pts_grid, grid_shape)
    elif pts_world.ndim == 5:
        pts_grid = center_crop_grid(pts_world, grid_shape)
    else:
        raise ValueError(
            f"Expected pts_world with ndim 3 or 5, got {pts_world.ndim}.",
        )

    pts_flat = pts_grid.reshape(pts_grid.shape[0], -1, 3)

    t_rig_world = pose_world_rig_ref.inverse()
    pts_rig = t_rig_world * pts_flat

    extent = voxel_extent.to(device=pts_rig.device, dtype=pts_rig.dtype)
    if extent.ndim == 1:
        extent = extent.view(1, 6).expand(pts_rig.shape[0], 6)
    mins = extent[:, [0, 2, 4]]
    maxs = extent[:, [1, 3, 5]]
    center_vox = 0.5 * (mins + maxs)
    span = (maxs - mins).clamp_min(1e-6)
    scale = 0.5 * span

    center_vox = center_vox[:, None, :]
    center_world = (t_world_voxel * center_vox).squeeze(1)
    center_rig = (t_rig_world * center_world[:, None, :]).squeeze(1)
    pts_norm = (pts_rig - center_rig[:, None, :]) / scale[:, None, :]

    pts_norm = pts_norm.view(
        pts_grid.shape[0],
        grid_shape[0],
        grid_shape[1],
        grid_shape[2],
        3,
    )
    return pts_norm.permute(0, 4, 1, 2, 3).contiguous()


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


def pool_voxel_points(
    pts_world: Tensor,
    *,
    grid_shape: tuple[int, int, int],
    pool_grid: int,
) -> Tensor:
    """Downsample voxel center points to match a pooled token grid."""
    if pts_world.ndim == 3:
        batch_size, num_pts, _ = pts_world.shape
        pts_shape = infer_padded_grid_shape(int(num_pts), grid_shape)
        pts_grid = pts_world.view(
            batch_size,
            pts_shape[0],
            pts_shape[1],
            pts_shape[2],
            3,
        )
        pts_grid = center_crop_grid(pts_grid, grid_shape)
    elif pts_world.ndim == 5 and pts_world.shape[-1] == 3:
        pts_grid = center_crop_grid(pts_world, grid_shape)
    else:
        raise ValueError(
            f"Expected pts_world shape (B,D,H,W,3) or (B,N,3), got {tuple(pts_world.shape)}.",
        )
    grid = int(pool_grid)
    pts_grid = pts_grid.to(dtype=torch.float32).permute(0, 4, 1, 2, 3)
    pts_pool = functional.adaptive_avg_pool3d(
        pts_grid,
        output_size=(grid, grid, grid),
    )
    return pts_pool.flatten(2).transpose(1, 2)
