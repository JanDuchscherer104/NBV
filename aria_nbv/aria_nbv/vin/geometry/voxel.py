"""Voxel-field geometry helpers for VIN scorers.

This module owns stateless operations on EVL voxel fields: sampling fields at
world points, deriving compact scene-field channels, converting flattened voxel
centers into normalized grids, and pooling voxel center points. Model classes
remain responsible for neural projections and scorer heads.
"""

from __future__ import annotations

from typing import Any, Literal

import torch
from efm3d.aria.pose import PoseTW
from efm3d.utils.voxel_sampling import pc_to_vox, sample_voxels
from torch import Tensor
from torch.nn import functional as functional


def sample_voxel_field(
    field: Tensor,
    *,
    points_world: Tensor,
    t_world_voxel: PoseTW,
    voxel_extent: Tensor,
) -> tuple[Tensor, Tensor]:
    """Sample a voxel-aligned field at world points.

    World-space query points are transformed into EVL's metric voxel frame with
    ``T_voxel_world = T_world_voxel.inverse()`` and then converted to voxel-grid
    indices with ``voxel_extent``.

    Args:
        field: ``Tensor["B C D H W"]`` voxel-aligned feature field.
        points_world: ``Tensor["B N K 3"]`` world points where ``N`` is the
            candidate count and ``K`` is the query count per candidate.
        t_world_voxel: ``PoseTW["B 12"]`` world-from-voxel transform.
        voxel_extent: ``Tensor["B 6"]`` voxel-frame bounds ordered as
            ``[x_min, x_max, y_min, y_max, z_min, z_max]``.

    Returns:
        Tuple ``(tokens, valid)``:

        - ``tokens``: ``Tensor["B N K C"]`` sampled field values.
        - ``valid``: ``Tensor["B N K", bool]`` extent and grid validity mask.
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

    t_voxel_world = t_world_voxel_b.inverse()
    voxel_points_m = t_voxel_world * world_points_flat

    pts_vox_id, valid_extent = pc_to_vox(
        voxel_points_m.to(dtype=torch.float32),
        vW=int(grid_w),
        vH=int(grid_h),
        vD=int(grid_d),
        voxel_extent=vox_extent,
    )
    pts_vox_id = torch.nan_to_num(pts_vox_id, nan=0.0, posinf=0.0, neginf=0.0)

    sampled, valid_grid = sample_voxels(
        field,
        pts_vox_id,
        differentiable=False,
    )
    valid = (valid_extent & valid_grid).reshape(batch_size, num_candidates, num_points)
    tokens = sampled.transpose(1, 2).reshape(
        batch_size,
        num_candidates,
        num_points,
        field_channels,
    )
    return tokens, valid


def sample_candidate_voxel_coverage(
    counts_norm: Tensor,
    *,
    candidate_centers_world: Tensor,
    pose_finite: Tensor,
    t_world_voxel: PoseTW,
    voxel_extent: Tensor,
) -> Tensor:
    """Sample normalized voxel observation coverage at candidate camera centers.

    Args:
        counts_norm: ``Tensor["B 1 D H W", float32]`` normalized observation-count
            field from the VIN scene-field bundle.
        candidate_centers_world: ``Tensor["B N 3", float32]`` candidate camera
            centers in the world frame.
        pose_finite: ``Tensor["B N", bool]`` mask for finite candidate pose
            encodings. Non-finite poses are forced to zero coverage.
        t_world_voxel: ``PoseTW["B 12"]`` world-from-voxel transform for the EVL grid.
        voxel_extent: ``Tensor["B 6"]`` or ``Tensor["6"]`` voxel-frame grid bounds.

    Returns:
        ``Tensor["B N", float32]`` per-candidate coverage in ``[0, 1]``.

    Notes:
        This helper keeps candidate-center voxel sampling out of scorer forward
        methods. It is intentionally stateless and differentiability-neutral:
        `sample_voxel_field` uses nearest-neighbor EVL sampling, and this helper
        only folds in hard geometric validity plus pose finiteness.
    """
    if counts_norm.ndim != 5 or int(counts_norm.shape[1]) != 1:
        raise ValueError(f"Expected counts_norm shape (B,1,D,H,W), got {tuple(counts_norm.shape)}.")
    if candidate_centers_world.ndim != 3 or int(candidate_centers_world.shape[-1]) != 3:
        raise ValueError(
            f"Expected candidate_centers_world shape (B,N,3), got {tuple(candidate_centers_world.shape)}.",
        )
    if pose_finite.shape != candidate_centers_world.shape[:2]:
        raise ValueError(
            "Expected pose_finite shape to match candidate_centers_world[:2], "
            f"got {tuple(pose_finite.shape)} and {tuple(candidate_centers_world.shape[:2])}.",
        )

    center_tokens, center_valid = sample_voxel_field(
        counts_norm,
        points_world=candidate_centers_world.unsqueeze(2),
        t_world_voxel=t_world_voxel,
        voxel_extent=voxel_extent,
    )
    counts_norm_center = center_tokens[..., 0, 0]
    center_valid = center_valid.squeeze(-1)
    coverage = counts_norm_center * center_valid.to(dtype=counts_norm_center.dtype)
    coverage = coverage * pose_finite.to(device=coverage.device, dtype=coverage.dtype)
    return coverage.clamp(0.0, 1.0)


def candidate_valid_from_token(
    token_valid: Tensor,
    *,
    min_valid_frac: float,
) -> Tensor:
    """Convert per-token validity into a per-candidate validity mask."""
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
    """Build a compact voxel-aligned scene field from EVL evidence tensors.

    Args:
        out: Backbone output object exposing EVL head/evidence tensors.
        use_channels: Ordered channel names to concatenate.
        occ_input_threshold: Threshold for deriving free-space evidence when
            ``free_input`` is absent.
        counts_norm_mode: Observation-count normalization mode.
        occ_pr_is_logits: Whether ``occ_pr`` must be passed through sigmoid.

    Returns:
        ``Tensor["B C D H W"]`` with channels ordered by ``use_channels``.
    """

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
    """Infer a symmetrically padded voxel-grid shape from a flattened count."""
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
    """Center-crop a voxel grid with trailing XYZ/channel values."""
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
    """Convert voxel centers to a normalized position grid in reference-rig frame.

    If ``pts_world`` corresponds to a padded grid (for example before a valid
    Conv3d shrink), the grid is center-cropped to ``grid_shape`` before
    normalization.
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


def pool_voxel_points(
    pts_world: Tensor,
    *,
    grid_shape: tuple[int, int, int],
    pool_grid: int,
) -> Tensor:
    """Downsample voxel center points to a pooled token grid.

    Args:
        pts_world: Voxel centers as ``Tensor["B D H W 3"]`` or flattened
            ``Tensor["B V 3"]``.
        grid_shape: Target ``(D, H, W)`` grid shape before pooling.
        pool_grid: Output side length ``G``.

    Returns:
        ``Tensor["B G*G*G 3"]`` pooled world-frame voxel centers.
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


__all__ = [
    "build_scene_field",
    "candidate_valid_from_token",
    "center_crop_grid",
    "infer_padded_grid_shape",
    "pool_voxel_points",
    "pos_grid_from_pts_world",
    "sample_voxel_field",
]
