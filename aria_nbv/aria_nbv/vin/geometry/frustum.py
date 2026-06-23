"""Frustum point sampling helpers for VIN geometry diagnostics.

The legacy experimental VIN variants and plotting diagnostics sample fixed
metric-depth grids inside PyTorch3D cameras. This module owns that camera-space
math so model classes only describe when frustum samples are needed.
"""

from __future__ import annotations

import torch
from efm3d.aria.pose import PoseTW
from pytorch3d.renderer.cameras import (  # type: ignore[import-untyped]
    PerspectiveCameras,
)
from torch import Tensor


def build_frustum_points_world_p3d(
    cameras: PerspectiveCameras,
    *,
    grid_size: int,
    depths_m: list[float],
) -> Tensor:
    """Unproject a square image grid at fixed depths into world points.

    Args:
        cameras: PyTorch3D camera batch with pixel ``image_size`` and
            ``principal_point`` parameters.
        grid_size: Number of image samples per side.
        depths_m: Positive metric depths to sample along each image ray.

    Returns:
        ``Tensor["Nc G*G*D 3"]`` of world-frame points, where ``Nc`` is the
        camera count and ``D`` is ``len(depths_m)``.
    """
    num_cams = int(cameras.R.shape[0])
    device = cameras.R.device

    image_size = cameras.image_size.to(device=device, dtype=torch.float32)
    principal_point = cameras.principal_point.to(device=device, dtype=torch.float32)
    if image_size.shape[0] == 1 and num_cams > 1:
        image_size = image_size.expand(num_cams, -1)
    if principal_point.shape[0] == 1 and num_cams > 1:
        principal_point = principal_point.expand(num_cams, -1)

    h = image_size[:, 0]
    w = image_size[:, 1]
    scale = torch.minimum(h, w)
    half = 0.95 * 0.5 * scale
    half_x = torch.minimum(
        half,
        torch.minimum(principal_point[:, 0] - 0.5, (w - 0.5) - principal_point[:, 0]),
    )
    half_y = torch.minimum(
        half,
        torch.minimum(principal_point[:, 1] - 0.5, (h - 0.5) - principal_point[:, 1]),
    )
    half_x = torch.clamp(half_x, min=0.0)
    half_y = torch.clamp(half_y, min=0.0)

    u_min = principal_point[:, 0] - half_x
    u_max = principal_point[:, 0] + half_x
    v_min = principal_point[:, 1] - half_y
    v_max = principal_point[:, 1] + half_y

    t = torch.linspace(0.0, 1.0, steps=grid_size, device=device, dtype=torch.float32)
    us = u_min[:, None] + (u_max - u_min)[:, None] * t[None, :]
    vs = v_min[:, None] + (v_max - v_min)[:, None] * t[None, :]

    uu = us[:, None, :].expand(num_cams, grid_size, grid_size)
    vv = vs[:, :, None].expand(num_cams, grid_size, grid_size)

    u = uu.reshape(num_cams, -1)
    v = vv.reshape(num_cams, -1)

    x_ndc = -(u - w[:, None] * 0.5) * (2.0 / scale[:, None])
    y_ndc = -(v - h[:, None] * 0.5) * (2.0 / scale[:, None])

    depths = torch.tensor(depths_m, device=device, dtype=torch.float32)
    num_depths = int(depths.shape[0])
    num_rays = int(x_ndc.shape[1])

    x_ndc = x_ndc[:, None, :].expand(num_cams, num_depths, num_rays)
    y_ndc = y_ndc[:, None, :].expand(num_cams, num_depths, num_rays)
    z = depths.view(1, num_depths, 1).expand(num_cams, num_depths, num_rays)

    xy_depth = torch.stack([x_ndc, y_ndc, z], dim=-1).reshape(num_cams, -1, 3)
    return cameras.unproject_points(xy_depth, world_coordinates=True, from_ndc=True)


def frustum_points_world_from_cameras(
    poses_world_cam: PoseTW,
    *,
    p3d_cameras: PerspectiveCameras,
    grid_size: int,
    depths_m: list[float],
) -> Tensor:
    """Generate per-candidate frustum sample points in world coordinates.

    Args:
        poses_world_cam: Candidate poses shaped as ``PoseTW["B N 12"]``. The
            tensor supplies the desired ``B`` and ``N`` layout; projection uses
            the aligned ``p3d_cameras`` batch.
        p3d_cameras: PyTorch3D cameras aligned with candidates. The camera
            batch must be ``N`` when ``B == 1`` or ``B * N`` otherwise.
        grid_size: Number of image samples per side.
        depths_m: Positive metric depths sampled along each image ray.

    Returns:
        ``Tensor["B N K 3"]`` world-frame frustum points.
    """
    if poses_world_cam.ndim != 3:
        raise ValueError(
            "poses_world_cam must have shape (B,N,12). Use ensure_candidate_batch before calling this helper.",
        )
    batch_size = int(poses_world_cam.t.shape[0])
    num_candidates = int(poses_world_cam.t.shape[1])

    cameras = p3d_cameras.to(device=poses_world_cam.t.device)
    pts_world_flat = build_frustum_points_world_p3d(
        cameras,
        grid_size=grid_size,
        depths_m=depths_m,
    )
    num_cams = int(pts_world_flat.shape[0])
    if batch_size == 1 and num_cams == num_candidates:
        return pts_world_flat.view(1, num_candidates, -1, 3)
    if num_cams == (batch_size * num_candidates):
        return pts_world_flat.view(batch_size, num_candidates, -1, 3)
    raise ValueError(
        f"p3d_cameras batch size must be N (when B=1) or B*N; got {num_cams} for B={batch_size}, N={num_candidates}.",
    )


__all__ = ["build_frustum_points_world_p3d", "frustum_points_world_from_cameras"]
