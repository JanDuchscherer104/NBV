r"""Utilities to back-project rendered depth maps into world-frame point clouds.

This module centralises depth unprojection for candidate renders to avoid frame
confusion between the PyTorch3D renderer (which outputs metric ``z`` depth in
the physical camera frame) and downstream visualisations or fusion steps.

All functions assume:
    * ``depth`` is metric depth along the camera +Z axis (same convention as
      `pytorch3d.renderer.MeshRasterizer` with ``in_ndc=False``).
    * ``pose_world_cam`` is a `efm3d.aria.pose.PoseTW` storing
      **world ← camera** extrinsics (LUF camera frame).
    * ``camera`` is the matching `efm3d.aria.camera.CameraTW` carrying
      intrinsics (and, if batched, per-candidate extrinsics that align with the
      provided depths/poses).

The returned points live in the same VIO/world frame as the ASE mesh and
semidense history. Conceptually a valid depth pixel $d(u,v)$ maps to
$\mathbf{p}_w = T_{w \leftarrow c}\,\pi^{-1}(u,v,d)$; crop and RRI code then
decide whether the point contributes to scene-level or target-level scoring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import torch
from pytorch3d.renderer.cameras import PerspectiveCameras  # type: ignore[import-untyped]

from .pytorch3d_depth_renderer import camera_tw_to_pytorch3d

if TYPE_CHECKING:
    from efm3d.aria.camera import CameraTW
    from efm3d.aria.pose import PoseTW


def backproject_depths_camera_tw_batch(
    depths: torch.Tensor,
    mask_valid: torch.Tensor,
    camera: CameraTW,
    pose_world_camera: PoseTW,
    *,
    stride: int = 1,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Back-project stored camera-z depth through the canonical PyTorch3D adapter."""

    cameras = camera_tw_to_pytorch3d(
        camera,
        pose_world_camera,
        device=depths.device,
        dtype=depths.dtype,
    )
    return backproject_depths_p3d_batch(depths, mask_valid, cameras, stride=stride)


def backproject_depths_p3d_batch(
    depths: torch.Tensor,
    mask_valid: torch.Tensor,
    cameras: PerspectiveCameras,
    *,
    stride: int = 1,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Back-project a batch of PyTorch3D depth maps to world-frame points.

    Args:
        depths: ``Tensor["B", "H", "W"]`` metric z-depth maps in metres.
        mask_valid: ``Tensor["B", "H", "W"]`` boolean masks for usable pixels.
        cameras: One `pytorch3d.renderer.PerspectiveCameras` entry per
            depth map, carrying world-from-camera extrinsics.
        stride: Pixel subsampling stride.

    Returns:
        Pair ``(padded, lengths)`` where ``padded`` is
        ``Tensor["B", "Pmax", 3]`` in world coordinates and ``lengths`` is
        ``Tensor["B"]`` with the valid count per candidate.
    """
    if depths.ndim != 3:
        raise ValueError(f"Expected depths of shape (B,H,W), got {tuple(depths.shape)}")
    if mask_valid.shape != depths.shape:
        raise ValueError(f"mask_valid shape {tuple(mask_valid.shape)} must match depths {tuple(depths.shape)}")
    if stride < 1:
        raise ValueError(f"stride must be >=1, got {stride}")

    bsz, height, width = depths.shape
    yy = torch.arange(0, height, stride, device=depths.device)
    xx = torch.arange(0, width, stride, device=depths.device)
    gy, gx = torch.meshgrid(yy, xx, indexing="ij")
    num_pixels = gy.numel()

    depth_sub = depths[:, gy, gx].reshape(bsz, num_pixels)
    mask = torch.isfinite(depth_sub) & mask_valid[:, gy, gx].reshape(bsz, num_pixels)
    depth_filtered = torch.where(mask, depth_sub, torch.zeros_like(depth_sub))

    gx_flat = gx.reshape(-1).to(depths.dtype) + 0.5
    gy_flat = gy.reshape(-1).to(depths.dtype) + 0.5
    scale = float(min(height, width))
    x_ndc = -(gx_flat - (width * 0.5)) * (2.0 / scale)
    y_ndc = -(gy_flat - (height * 0.5)) * (2.0 / scale)

    xy_depth = torch.stack(
        [
            x_ndc.unsqueeze(0).expand(bsz, -1),
            y_ndc.unsqueeze(0).expand(bsz, -1),
            depth_filtered.to(depths.dtype),
        ],
        dim=-1,
    )
    pts_world = cameras.unproject_points(xy_depth, world_coordinates=True, from_ndc=True)

    lengths = mask.sum(dim=1)
    max_len = int(lengths.max().item()) if lengths.numel() > 0 else 0
    if max_len == 0:
        return torch.empty(bsz, 0, 3, device=depths.device, dtype=depths.dtype), lengths

    padded = torch.full((bsz, max_len, 3), torch.nan, device=depths.device, dtype=depths.dtype)
    cumsum = mask.cumsum(dim=1) - 1
    batch_idx, flat_idx = torch.nonzero(mask, as_tuple=True)
    padded[batch_idx, cumsum[batch_idx, flat_idx]] = pts_world[batch_idx, flat_idx]

    return padded, lengths


__all__ = ["backproject_depths_camera_tw_batch", "backproject_depths_p3d_batch"]
