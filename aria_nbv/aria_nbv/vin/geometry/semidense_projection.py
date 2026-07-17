"""Semidense point projection helpers shared by VIN scorers.

The active :mod:`aria_nbv.vin.models.scene_myopic` scorer uses semidense ASE/EFM points as
actor-visible scene evidence. This module owns the stateless tensor operations
for that path:

- sample valid ``VinSnippetView.points_world`` rows,
- project world points into PyTorch3D candidate cameras,
- encode scalar projection statistics, and
- build screen-space grids consumed by model-owned CNN encoders.

Keeping those operations outside the scorer class makes the geometry contract
testable without constructing the full model while preserving the neural module
ownership boundary in :class:`aria_nbv.vin.models.scene_myopic.VinModelV3`.
"""

from __future__ import annotations

from typing import Any

import torch
from pytorch3d.renderer.cameras import (  # type: ignore[import-untyped]
    PerspectiveCameras,
)
from torch import Tensor

from .semidense_schema import (
    SEMIDENSE_GRID_CHANNELS,
    SEMIDENSE_GRID_FEATURES,
    SEMIDENSE_PROJ_DIM,
    SEMIDENSE_PROJ_FEATURES,
    semidense_proj_feature_index,
)


def sample_semidense_points(
    snippet: Any,
    *,
    device: torch.device,
    max_points: int,
) -> Tensor:
    """Sample valid semidense world points from a VIN snippet.

    Args:
        snippet: Object with the :class:`aria_nbv.data_handling.raw.views.VinSnippetView`
            point contract. It must expose ``points_world`` as
            ``Tensor["P C", float32]`` or ``Tensor["B P C", float32]`` and
            optional ``lengths``.
            XYZ is measured in metres, ``1/sigma_d`` in inverse metres, and
            optional ``n_obs`` in channel five is a dimensionless count.
        device: Target device for the returned tensor.
        max_points: Maximum sampled point count per batch item. Batched inputs
            are padded to this length with NaNs so candidate projection keeps a
            rectangular ``Tensor["B P_fr C", float32]`` layout.

    Returns:
        ``Tensor["P_fr C", float32]`` or ``Tensor["B P_max C", float32]`` on
        ``device``.

    Raises:
        RuntimeError: If the snippet has no valid points.
        ValueError: If the point tensor has an invalid shape, insufficient
            channels, mismatched lengths, or non-finite XYZ values.
    """
    max_points = int(max_points)
    points = snippet.points_world
    lengths = getattr(snippet, "lengths", None)
    if points.numel() == 0:
        raise RuntimeError("VinSnippetView.points_world is empty.")
    if points.shape[-1] < 4:
        raise ValueError(
            "VinSnippetView.points_world must have at least 4 channels (x,y,z,1/sigma_d); n_obs is optional.",
        )
    if points.ndim == 2:
        valid_len = None
        if lengths is not None and lengths.numel() > 0:
            valid_len = int(lengths.reshape(-1)[0].item())
            valid_len = min(valid_len, int(points.shape[0]))
        if valid_len is None:
            valid_len = int(points.shape[0])
        if valid_len <= 0:
            raise RuntimeError("VinSnippetView.points_world has zero valid points.")
        if not torch.isfinite(points[:valid_len, :3]).all():
            raise ValueError("VinSnippetView.points_world contains non-finite XYZ values.")
        if valid_len > max_points:
            idx = torch.randperm(valid_len, device=points.device)[:max_points]
            points = points[:valid_len][idx]
        else:
            points = points[:valid_len]
    elif points.ndim == 3:
        batch_size, num_points, dim = points.shape
        if lengths is None or lengths.numel() == 0:
            lengths = torch.full(
                (batch_size,),
                num_points,
                device=points.device,
                dtype=torch.long,
            )
        else:
            lengths = lengths.reshape(-1).to(device=points.device, dtype=torch.long)
            if lengths.numel() == 1 and batch_size > 1:
                lengths = lengths.expand(batch_size)
            if lengths.numel() != batch_size:
                raise ValueError(
                    "VinSnippetView.lengths must have shape (B,) or (1,) when points_world is batched.",
                )
        lengths = lengths.clamp(min=0, max=num_points)
        valid_mask = torch.arange(num_points, device=points.device).unsqueeze(0) < lengths.unsqueeze(1)
        if not valid_mask.any():
            raise RuntimeError("VinSnippetView.points_world has zero valid points.")
        if not torch.isfinite(points[..., :3])[valid_mask].all():
            raise ValueError("VinSnippetView.points_world contains non-finite XYZ values.")

        k = min(max_points, int(num_points))
        scores = torch.rand((batch_size, num_points), device=points.device)
        scores = scores.masked_fill(~valid_mask, float("-inf"))
        topk_scores, topk_idx = scores.topk(k, dim=1)
        selected = points.gather(1, topk_idx.unsqueeze(-1).expand(-1, -1, dim))

        points_out = torch.full(
            (batch_size, max_points, dim),
            float("nan"),
            dtype=points.dtype,
            device=points.device,
        )
        valid_topk = torch.isfinite(topk_scores)
        points_out[:, :k] = torch.where(
            valid_topk.unsqueeze(-1),
            selected,
            points_out[:, :k],
        )
        points = points_out
    else:
        raise ValueError(
            f"Expected VinSnippetView.points_world with ndim 2 or 3, got {points.ndim}.",
        )
    return points.to(device=device, dtype=torch.float32)


def project_points_to_candidate_cameras(
    points_world: Tensor | None,
    p3d_cameras: PerspectiveCameras,
    *,
    batch_size: int,
    num_candidates: int,
    device: torch.device,
) -> dict[str, Tensor]:
    """Project world points into a batch of candidate cameras.

    This is the shared projection path for semidense points and pooled voxel
    centers. It enforces the PyTorch3D camera batch contract used by
    :class:`aria_nbv.vin.models.scene_myopic.VinModelV3`: the camera batch is either
    ``Nq`` when ``B == 1`` or ``B * Nq`` for true batched inputs.

    Args:
        points_world: ``Tensor["P C", float32]`` or
            ``Tensor["B P C", float32]`` in the world frame; XYZ is measured
            in metres.
            ``C`` must include XYZ; additional channels are propagated as
            ``inv_dist_std`` and optional ``obs_count`` when present.
        p3d_cameras: PyTorch3D candidate camera batch with ``image_size``.
        batch_size: Batch size ``B``.
        num_candidates: Candidate count ``N_q`` per batch item.
        device: Target device for projection tensors.

    Returns:
        Dictionary with screen coordinates ``x``/``y``, camera depth ``z``,
        ``finite`` and ``valid`` masks, optional reliability channels,
        ``image_size``, and scalar ``num_cams``.
    """
    if points_world is None or points_world.numel() == 0:
        raise RuntimeError("Semidense projection requires non-empty points_world.")

    cameras = p3d_cameras.to(device)
    image_size = getattr(cameras, "image_size", None)
    if image_size is None or image_size.numel() == 0:
        raise RuntimeError("p3d_cameras.image_size is required for semidense projection.")

    num_cams = int(cameras.R.shape[0])
    if num_cams == 0:
        raise RuntimeError("p3d_cameras has zero cameras.")

    image_size = image_size.to(device=device, dtype=torch.float32)
    if image_size.shape[0] == 1 and num_cams > 1:
        image_size = image_size.expand(num_cams, -1)
    if image_size.shape[0] != num_cams:
        raise ValueError(
            f"p3d_cameras.image_size batch mismatch: image_size {tuple(image_size.shape)} vs num_cams={num_cams}.",
        )

    pts_world = points_world.to(device=device, dtype=torch.float32)
    xyz = pts_world[..., :3]
    extra = pts_world[..., 3:] if pts_world.shape[-1] > 3 else None
    inv_dist_std = None
    obs_count = None
    if extra is not None:
        if extra.shape[-1] >= 1:
            inv_dist_std = extra[..., 0]
        if extra.shape[-1] >= 2:
            obs_count = extra[..., 1]
    if xyz.ndim == 2:
        xyz = xyz.unsqueeze(0)
        if inv_dist_std is not None:
            inv_dist_std = inv_dist_std.unsqueeze(0)
        if obs_count is not None:
            obs_count = obs_count.unsqueeze(0)
    if xyz.shape[0] == 1 and batch_size > 1:
        xyz = xyz.expand(batch_size, -1, -1)
        if inv_dist_std is not None:
            inv_dist_std = inv_dist_std.expand(batch_size, -1)
        if obs_count is not None:
            obs_count = obs_count.expand(batch_size, -1)
    if xyz.shape[0] != batch_size:
        raise ValueError("Semidense points batch size must match candidates.")

    if batch_size == 1 and num_cams == num_candidates:
        points_cam = xyz.expand(num_candidates, -1, -1)
        inv_cam = inv_dist_std.expand(num_candidates, -1) if inv_dist_std is not None else None
        obs_cam = obs_count.expand(num_candidates, -1) if obs_count is not None else None
    elif num_cams == batch_size * num_candidates:
        points_cam = xyz[:, None].expand(batch_size, num_candidates, -1, -1).reshape(num_cams, -1, 3)
        if inv_dist_std is not None:
            inv_cam = inv_dist_std[:, None].expand(batch_size, num_candidates, -1).reshape(num_cams, -1)
        else:
            inv_cam = None
        if obs_count is not None:
            obs_cam = obs_count[:, None].expand(batch_size, num_candidates, -1).reshape(num_cams, -1)
        else:
            obs_cam = None
    else:
        raise ValueError(
            "p3d_cameras batch size must be N (when B=1) or B*N; "
            f"got {num_cams} for B={batch_size}, N={num_candidates}.",
        )

    pts_screen = cameras.transform_points_screen(points_cam, image_size=image_size)
    pts_view = cameras.get_world_to_view_transform().transform_points(points_cam)
    x, y = pts_screen[..., 0], pts_screen[..., 1]
    z = pts_view[..., 2]
    h = image_size[:, 0].unsqueeze(1)
    w = image_size[:, 1].unsqueeze(1)
    finite = torch.isfinite(pts_screen).all(dim=-1) & torch.isfinite(pts_view).all(dim=-1)
    valid = finite & (z > 0.0) & (x >= 0.0) & (y >= 0.0) & (x <= (w - 1.0)) & (y <= (h - 1.0))

    return {
        "x": x,
        "y": y,
        "z": z,
        "finite": finite,
        "valid": valid,
        "inv_dist_std": inv_cam if inv_cam is not None else torch.empty(0, device=device),
        "obs_count": obs_cam if obs_cam is not None else torch.empty(0, device=device),
        "image_size": image_size,
        "num_cams": torch.tensor(num_cams, device=device),
    }


def encode_projection_summary(
    proj_data: dict[str, Tensor] | None,
    *,
    batch_size: int,
    num_candidates: int,
    device: torch.device,
    dtype: torch.dtype,
    grid_size: int,
    obs_count_max: int,
    inv_dist_std_min: float,
    inv_dist_std_p95: float,
) -> Tensor:
    """Summarize semidense projection coverage, visibility, and depth.

    Args:
        proj_data: Output from :func:`project_points_to_candidate_cameras`.
        batch_size: Batch size ``B``.
        num_candidates: Candidate count ``N_q`` per batch item.
        device: Target device for features.
        dtype: Output dtype.
        grid_size: Screen-space bin count per side for coverage.
        obs_count_max: Saturation point for the ``log1p(n_obs)`` reliability
            factor.
        inv_dist_std_min: Lower bound for inverse depth-uncertainty scaling.
        inv_dist_std_p95: Upper reference percentile for inverse
            depth-uncertainty scaling.

    Returns:
        ``Tensor["B N_q F_proj", float32]`` with
        ``F_proj == SEMIDENSE_PROJ_DIM``, ordered by
        `SEMIDENSE_PROJ_FEATURES`.
    """
    proj_feat = torch.zeros(
        (batch_size, num_candidates, SEMIDENSE_PROJ_DIM),
        device=device,
        dtype=dtype,
    )
    if proj_data is None:
        raise RuntimeError("Semidense projection data is missing.")

    x = proj_data["x"]
    y = proj_data["y"]
    z = proj_data["z"]
    finite = proj_data.get("finite")
    if finite is None:
        finite = torch.isfinite(torch.stack([x, y, z], dim=-1)).all(dim=-1)
    valid = proj_data["valid"]
    image_size = proj_data["image_size"]
    inv_dist_std = proj_data.get("inv_dist_std")
    obs_count = proj_data.get("obs_count")
    if inv_dist_std is not None and inv_dist_std.numel() == 0:
        inv_dist_std = None
    if obs_count is not None and obs_count.numel() == 0:
        obs_count = None
    num_cams = int(proj_data["num_cams"].item())
    h = image_size[:, 0].unsqueeze(1).clamp_min(1.0)
    w = image_size[:, 1].unsqueeze(1).clamp_min(1.0)

    grid_size = int(grid_size)
    num_bins = grid_size * grid_size
    x_safe = torch.where(valid, x, torch.zeros_like(x))
    y_safe = torch.where(valid, y, torch.zeros_like(y))
    z_safe = torch.where(valid, z, torch.zeros_like(z))
    x_safe = torch.nan_to_num(x_safe, nan=0.0, posinf=0.0, neginf=0.0)
    y_safe = torch.nan_to_num(y_safe, nan=0.0, posinf=0.0, neginf=0.0)
    z_safe = torch.nan_to_num(z_safe, nan=0.0, posinf=0.0, neginf=0.0)
    x_bin = torch.clamp((x_safe / w) * grid_size, 0.0, float(grid_size - 1)).to(dtype=torch.long)
    y_bin = torch.clamp((y_safe / h) * grid_size, 0.0, float(grid_size - 1)).to(dtype=torch.long)
    bin_idx = y_bin * grid_size + x_bin

    counts = torch.zeros((num_cams, num_bins), device=device, dtype=torch.float32)
    bin_idx = torch.where(valid, bin_idx, torch.zeros_like(bin_idx))
    valid_f = valid.to(dtype=counts.dtype)
    counts.scatter_add_(1, bin_idx, valid_f)
    coverage = (counts > 0).to(dtype=counts.dtype).mean(dim=1)
    empty_frac = 1.0 - coverage

    finite_f = finite.to(dtype=counts.dtype)
    eps = 1e-6
    if obs_count is not None:
        obs = obs_count.to(device=device, dtype=counts.dtype).clamp_min(0.0)
        obs = torch.nan_to_num(obs, nan=0.0, posinf=0.0, neginf=0.0)
        obs_log = torch.log1p(obs)
        obs_log = torch.where(finite, obs_log, torch.zeros_like(obs_log))
        denom = torch.log1p(torch.tensor(float(obs_count_max), device=device, dtype=counts.dtype)).clamp_min(eps)
        a = (obs_log / denom).clamp(0.0, 1.0)
    else:
        a = torch.ones_like(valid_f)

    if inv_dist_std is not None:
        inv = inv_dist_std.to(device=device, dtype=counts.dtype).clamp_min(0.0)
        inv = torch.nan_to_num(inv, nan=0.0, posinf=0.0, neginf=0.0)
        inv_min = float(inv_dist_std_min)
        inv_p95 = max(float(inv_dist_std_p95), inv_min + eps)
        denom = torch.tensor(inv_p95 - inv_min, device=device, dtype=counts.dtype).clamp_min(eps)
        b = ((inv - inv_min) / denom).clamp(0.0, 1.0)
    else:
        b = torch.ones_like(valid_f)
    w_rel = (a * b).clamp(0.0, 1.0)

    weight_valid = w_rel * valid_f
    weight_finite = w_rel * finite_f
    weight_sum = weight_valid.sum(dim=1).clamp_min(eps)
    finite_sum = weight_finite.sum(dim=1).clamp_min(eps)
    semidense_candidate_vis_frac = weight_valid.sum(dim=1) / finite_sum

    depth_mean = (z_safe * weight_valid).sum(dim=1) / weight_sum
    depth_var = ((z_safe - depth_mean.unsqueeze(1)) ** 2 * weight_valid).sum(dim=1) / weight_sum
    depth_std = torch.sqrt(depth_var.clamp_min(0.0))

    feats = torch.stack(
        [coverage, empty_frac, semidense_candidate_vis_frac, depth_mean, depth_std],
        dim=-1,
    )
    if batch_size == 1 and num_cams == num_candidates:
        proj_feat = feats.view(1, num_candidates, -1)
    else:
        proj_feat = feats.view(batch_size, num_candidates, -1)
    return proj_feat.to(device=device, dtype=dtype)


def build_projection_grid(
    proj_data: dict[str, Tensor] | None,
    *,
    device: torch.device,
    dtype: torch.dtype,
    grid_size: int,
) -> Tensor:
    """Build per-camera semidense projection grids for CNN encoders.

    Args:
        proj_data: Output from :func:`project_points_to_candidate_cameras`.
        device: Target device for the grid.
        dtype: Output dtype consumed by the caller-owned CNN.
        grid_size: Screen-space bin count per side.

    Returns:
        ``Tensor["B*N_q C_grid G G", float32]`` containing occupancy, mean
        camera-frame depth in metres, and depth standard-deviation grids, with
        ``C_grid == SEMIDENSE_GRID_CHANNELS``.
    """
    if proj_data is None:
        raise RuntimeError("Semidense projection data is missing.")

    x = proj_data["x"]
    y = proj_data["y"]
    z = proj_data["z"]
    valid = proj_data["valid"]
    image_size = proj_data["image_size"]
    num_cams = int(proj_data["num_cams"].item())

    grid_size = int(grid_size)
    num_bins = grid_size * grid_size
    h = image_size[:, 0].unsqueeze(1).clamp_min(1.0)
    w = image_size[:, 1].unsqueeze(1).clamp_min(1.0)

    x_safe = torch.where(valid, x, torch.zeros_like(x))
    y_safe = torch.where(valid, y, torch.zeros_like(y))
    z_safe = torch.where(valid, z, torch.zeros_like(z))
    x_safe = torch.nan_to_num(x_safe, nan=0.0, posinf=0.0, neginf=0.0)
    y_safe = torch.nan_to_num(y_safe, nan=0.0, posinf=0.0, neginf=0.0)
    z_safe = torch.nan_to_num(z_safe, nan=0.0, posinf=0.0, neginf=0.0)

    x_bin = torch.clamp((x_safe / w) * grid_size, 0.0, float(grid_size - 1)).to(dtype=torch.long)
    y_bin = torch.clamp((y_safe / h) * grid_size, 0.0, float(grid_size - 1)).to(dtype=torch.long)
    bin_idx = y_bin * grid_size + x_bin

    counts = torch.zeros((num_cams, num_bins), device=device, dtype=torch.float32)
    sum_z = torch.zeros_like(counts)
    sum_z2 = torch.zeros_like(counts)
    bin_idx = torch.where(valid, bin_idx, torch.zeros_like(bin_idx))
    valid_f = valid.to(dtype=counts.dtype)

    counts.scatter_add_(1, bin_idx, valid_f)
    sum_z.scatter_add_(1, bin_idx, z_safe * valid_f)
    sum_z2.scatter_add_(1, bin_idx, (z_safe**2) * valid_f)

    denom = counts.clamp_min(1.0)
    depth_mean = sum_z / denom
    depth_var = (sum_z2 / denom) - depth_mean**2
    depth_std = torch.sqrt(depth_var.clamp_min(0.0))

    empty_mask = counts <= 0.0
    depth_mean = torch.where(empty_mask, torch.zeros_like(depth_mean), depth_mean)
    depth_std = torch.where(empty_mask, torch.zeros_like(depth_std), depth_std)

    occupancy = (counts > 0.0).to(dtype=counts.dtype)
    occ_grid = occupancy.view(num_cams, grid_size, grid_size)
    mean_grid = depth_mean.view(num_cams, grid_size, grid_size)
    std_grid = depth_std.view(num_cams, grid_size, grid_size)
    return torch.stack([occ_grid, mean_grid, std_grid], dim=1).to(device=device, dtype=dtype)


__all__ = [
    "SEMIDENSE_GRID_CHANNELS",
    "SEMIDENSE_GRID_FEATURES",
    "SEMIDENSE_PROJ_DIM",
    "SEMIDENSE_PROJ_FEATURES",
    "build_projection_grid",
    "encode_projection_summary",
    "project_points_to_candidate_cameras",
    "sample_semidense_points",
    "semidense_proj_feature_index",
]
