"""Historical VIN v2 semidense projection helpers.

VIN v2 predates the stricter `aria_nbv.vin.geometry.semidense_projection`
contract used by v3. These helpers preserve v2's permissive missing-data
behavior and legacy PyTorch3D screen-depth projection semantics while keeping
that implementation out of the model class.
"""

from __future__ import annotations

from typing import Any

import torch
from pytorch3d.renderer.cameras import PerspectiveCameras  # type: ignore[import-untyped]
from torch import Tensor

from ..geometry.semidense_schema import SEMIDENSE_PROJ_DIM


def sample_semidense_points_v2(
    snippet: Any | None,
    *,
    max_points: int,
    device: torch.device,
    include_obs_count: bool,
) -> Tensor | None:
    """Sample semidense world points with VIN v2's optional-data policy.

    Parameters
    ----------
    snippet:
        EFM snippet view, VIN snippet view, or ``None``. VIN v2 returns ``None``
        when no usable semidense points are available instead of failing fast.
    max_points:
        Maximum sampled point count.
    device:
        Target device for the returned float32 tensor.
    include_obs_count:
        Whether EFM point collapse should append observation-count evidence.

    Returns
    -------
    Tensor | None
        ``Tensor["P C"]`` or ``Tensor["B P C"]`` containing XYZ and optional
        reliability channels, or ``None`` when v2 would skip semidense evidence.
    """
    if snippet is None:
        return None
    points = getattr(snippet, "points_world", None)
    if isinstance(points, Tensor):
        if points.numel() == 0:
            return None
        if points.ndim == 2:
            finite = torch.isfinite(points[:, :3]).all(dim=-1)
            valid_idx = torch.nonzero(finite, as_tuple=False).reshape(-1)
            if valid_idx.numel() == 0:
                return None
            if points.shape[0] > max_points and valid_idx.numel() > max_points:
                perm = torch.randperm(valid_idx.numel(), device=valid_idx.device)[:max_points]
                valid_idx = valid_idx[perm]
            points = points[valid_idx[:max_points]]
        elif points.ndim == 3:
            finite = torch.isfinite(points[..., :3]).all(dim=-1)
            if not bool(finite.any().item()):
                return None
            batch_size, _, dim = points.shape
            points_out = torch.full(
                (batch_size, max_points, dim),
                float("nan"),
                dtype=points.dtype,
                device=points.device,
            )
            for b in range(batch_size):
                valid_idx = torch.nonzero(finite[b], as_tuple=False).reshape(-1)
                if valid_idx.numel() == 0:
                    continue
                k = min(int(valid_idx.numel()), int(max_points))
                if valid_idx.numel() > k:
                    perm = torch.randperm(valid_idx.numel(), device=valid_idx.device)[:k]
                    valid_idx = valid_idx[perm]
                points_out[b, :k] = points[b, valid_idx[:k]]
            points = points_out
        else:
            raise ValueError(
                f"Expected VinSnippetView.points_world with ndim 2 or 3, got {points.ndim}.",
            )
        return points.to(device=device, dtype=torch.float32)

    semidense = getattr(snippet, "semidense", None)
    if semidense is None:
        return None
    pts_world = semidense.collapse_points(
        max_points=max_points,
        include_inv_dist_std=True,
        include_obs_count=include_obs_count,
    )
    if pts_world.numel() == 0:
        return None
    return pts_world.to(device=device, dtype=torch.float32)


def project_semidense_points_v2(
    points_world: Tensor | None,
    p3d_cameras: PerspectiveCameras,
    *,
    batch_size: int,
    num_candidates: int,
    device: torch.device,
) -> dict[str, Tensor] | None:
    """Project v2 semidense points into candidates using legacy semantics.

    Unlike the v3 geometry helper, this returns ``None`` for missing optional
    camera metadata and uses ``transform_points_screen(points)[..., 2]`` as the
    depth value because that is the historical v2 feature contract.
    """
    if points_world is None or points_world.numel() == 0:
        return None

    cameras = p3d_cameras.to(device)
    image_size = getattr(cameras, "image_size", None)
    if image_size is None or image_size.numel() == 0:
        return None

    num_cams = int(cameras.R.shape[0])
    if num_cams == 0:
        return None

    image_size = image_size.to(device=device, dtype=torch.float32)
    if image_size.shape[0] == 1 and num_cams > 1:
        image_size = image_size.expand(num_cams, -1)
    if image_size.shape[0] != num_cams:
        return None

    pts_world = points_world.to(device=device, dtype=torch.float32)
    xyz = pts_world[..., :3]
    extra = pts_world[..., 3:] if pts_world.shape[-1] > 3 else None
    inv_dist_std = extra[..., 0] if extra is not None else None
    obs_count = extra[..., 1] if extra is not None and extra.shape[-1] > 1 else None
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

    pts_screen = cameras.transform_points_screen(points_cam)
    x, y, z = pts_screen.unbind(dim=-1)
    h = image_size[:, 0].unsqueeze(1)
    w = image_size[:, 1].unsqueeze(1)
    finite = torch.isfinite(pts_screen).all(dim=-1)
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


def encode_semidense_projection_features_v2(
    proj_data: dict[str, Tensor] | None,
    *,
    batch_size: int,
    num_candidates: int,
    device: torch.device,
    dtype: torch.dtype,
    grid_size: int,
) -> Tensor:
    """Summarize v2 semidense projection coverage and legacy depth stats.

    The visibility fraction is raw valid/finite support. Depth weighting uses
    only inverse distance standard deviation when available; observation counts
    are intentionally ignored to preserve VIN v2 outputs.
    """
    proj_feat = torch.zeros(
        (batch_size, num_candidates, SEMIDENSE_PROJ_DIM),
        device=device,
        dtype=dtype,
    )
    if proj_data is None:
        return proj_feat

    x = proj_data["x"]
    y = proj_data["y"]
    z = proj_data["z"]
    finite = proj_data.get("finite")
    if finite is None:
        finite = torch.isfinite(torch.stack([x, y, z], dim=-1)).all(dim=-1)
    valid = proj_data["valid"]
    image_size = proj_data["image_size"]
    inv_dist_std = proj_data.get("inv_dist_std")
    if inv_dist_std is not None and inv_dist_std.numel() == 0:
        inv_dist_std = None
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

    valid_count = valid_f.sum(dim=1)
    denom = torch.clamp(valid_count, min=1.0)
    total_points = finite.to(dtype=counts.dtype).sum(dim=1).clamp_min(1.0)
    semidense_candidate_vis_frac = valid_count / total_points

    if inv_dist_std is not None:
        inv_dist_std = inv_dist_std.to(device=device, dtype=counts.dtype).clamp_min(0.0)
        inv_dist_std = torch.nan_to_num(
            inv_dist_std,
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )
        weight_valid = inv_dist_std * valid_f
        weight_sum = weight_valid.sum(dim=1).clamp_min(1e-6)
        depth_mean = (z_safe * weight_valid).sum(dim=1) / weight_sum
        depth_var = ((z_safe - depth_mean.unsqueeze(1)) ** 2 * weight_valid).sum(dim=1) / weight_sum
    else:
        depth_mean = (z_safe * valid_f).sum(dim=1) / denom
        depth_var = ((z_safe - depth_mean.unsqueeze(1)) ** 2 * valid_f).sum(dim=1) / denom
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


__all__ = [
    "encode_semidense_projection_features_v2",
    "project_semidense_points_v2",
    "sample_semidense_points_v2",
]
