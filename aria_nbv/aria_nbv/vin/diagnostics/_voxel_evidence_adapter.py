"""Voxel and backbone evidence adapters for VIN diagnostic figures.

This module converts VIN voxel-grid diagnostics into world-frame point arrays
for Plotly visualizations. Pose normalization is delegated to
:mod:`aria_nbv.vin.diagnostics._pose_candidate_adapter`; generic Plotly trace
builders live in :mod:`aria_nbv.vin.diagnostics._plot_primitives`.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import torch
from efm3d.aria.pose import PoseTW

from ._pose_candidate_adapter import _pose_first_batch


def _voxel_corners(extent: np.ndarray) -> np.ndarray:
    """Return the eight voxel-grid box corners from ``[xmin, xmax, ...]`` extent."""
    x_min, x_max, y_min, y_max, z_min, z_max = extent.tolist()
    return np.array(
        [
            [x_min, y_min, z_min],
            [x_max, y_min, z_min],
            [x_max, y_max, z_min],
            [x_min, y_max, z_min],
            [x_min, y_min, z_max],
            [x_max, y_min, z_max],
            [x_max, y_max, z_max],
            [x_min, y_max, z_max],
        ],
        dtype=float,
    )


def _voxel_indices_to_world(
    indices: np.ndarray,
    *,
    pose: PoseTW,
    extent: np.ndarray,
    shape: tuple[int, int, int],
) -> np.ndarray:
    """Map ``(z, y, x)`` voxel indices to world-frame voxel-center points."""
    d, h, w = shape
    x_min, x_max, y_min, y_max, z_min, z_max = extent.tolist()

    dx = (x_max - x_min) / w
    dy = (y_max - y_min) / h
    dz = (z_max - z_min) / d

    z_idx, y_idx, x_idx = indices[:, 0], indices[:, 1], indices[:, 2]
    x = x_min + (x_idx + 0.5) * dx
    y = y_min + (y_idx + 0.5) * dy
    z = z_min + (z_idx + 0.5) * dz
    points_vox = torch.tensor(
        np.stack([x, y, z], axis=-1),
        dtype=torch.float32,
        device=pose.t.device,
    )
    points_world = pose.transform(points_vox)
    return points_world.detach().cpu().numpy()


def _voxel_indices_to_world_from_cache(
    indices: np.ndarray,
    *,
    pose: PoseTW,
    extent: np.ndarray,
    shape: tuple[int, int, int],
    pts_world: torch.Tensor | None,
) -> np.ndarray:
    """Convert voxel indices to world points using cached centers when available."""
    if torch.is_tensor(pts_world):
        pts = pts_world.detach().cpu()
        if pts.ndim == 3:
            pts = pts[0]
        if pts.ndim == 2 and pts.shape[-1] == 3:
            d, h, w = shape
            if pts.numel() == d * h * w * 3:
                pts_grid = pts.reshape(d, h, w, 3)
                sel = pts_grid[indices[:, 0], indices[:, 1], indices[:, 2]]
                return sel.numpy()
    return _voxel_indices_to_world(
        indices,
        pose=pose,
        extent=extent,
        shape=shape,
    )


def _collect_backbone_evidence_points(
    debug: Any,
    *,
    fields: list[str],
    occ_threshold: float,
    max_points: int,
) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """Collect sampled world-frame evidence points from selected backbone fields."""
    if not fields:
        return []

    out = debug.backbone_out
    voxel_fields = {
        "occ_pr": out.occ_pr,
        "occ_input": out.occ_input,
        "counts": out.counts,
    }
    selected = [name for name in fields if voxel_fields.get(name) is not None]
    if not selected:
        return []

    pose = _pose_first_batch(out.t_world_voxel)
    extent = out.voxel_extent.detach().cpu().numpy()
    if extent.ndim == 2:
        extent = extent[0]

    samples: list[tuple[str, np.ndarray, np.ndarray]] = []
    pts_world = out.pts_world
    pts_world_np: np.ndarray | None = None
    if isinstance(pts_world, torch.Tensor):
        pts_world = pts_world.detach().cpu()
        if pts_world.ndim == 3:
            pts_world = pts_world[0]
        if pts_world.ndim == 2 and pts_world.shape[1] == 3:
            pts_world_np = pts_world.numpy()

    for name in selected:
        tensor = voxel_fields[name]
        if tensor is None:
            continue
        field = tensor.detach().cpu()
        if field.ndim == 5:
            field = field[0, 0]
        elif field.ndim == 4:
            field = field[0]
        if name == "occ_pr":
            finite = field[torch.isfinite(field)]
            if finite.numel() > 0:
                min_val = float(finite.min().item())
                max_val = float(finite.max().item())
                if min_val < 0.0 or max_val > 1.0:
                    field = torch.sigmoid(field)
        d, h, w = field.shape

        if name == "counts":
            flat = field.reshape(-1)
            if flat.numel() == 0:
                continue
            topk = min(int(max_points), flat.numel())
            _, idx = torch.topk(flat, k=topk)
            indices = np.stack(np.unravel_index(idx.numpy(), field.shape), axis=-1)
            values = flat[idx].numpy()
        else:
            mask = field > float(occ_threshold)
            indices = np.stack(np.nonzero(mask.numpy()), axis=-1)
            values = field[mask].numpy()
            if indices.size == 0:
                flat = field.reshape(-1)
                if flat.numel() == 0:
                    continue
                topk = min(int(max_points), flat.numel())
                _, idx = torch.topk(flat, k=topk)
                indices = np.stack(
                    np.unravel_index(idx.numpy(), field.shape),
                    axis=-1,
                )
                values = flat[idx].numpy()
            if indices.shape[0] > max_points:
                sel = np.random.choice(indices.shape[0], size=max_points, replace=False)
                indices = indices[sel]
                values = values[sel]

        if indices.size == 0:
            continue

        points_world = None
        if pts_world_np is not None:
            flat_idx = indices[:, 0] * (h * w) + indices[:, 1] * w + indices[:, 2]
            flat_idx = np.clip(flat_idx, 0, pts_world_np.shape[0] - 1)
            points_world = pts_world_np[flat_idx]
        if points_world is None:
            points_world = _voxel_indices_to_world(
                indices,
                pose=pose,
                extent=extent,
                shape=(d, h, w),
            )
        values_np = np.asarray(values)
        finite = np.isfinite(points_world).all(axis=1)
        if values_np.shape[0] == points_world.shape[0]:
            values_np = values_np[finite]
        points_world = points_world[finite]
        if points_world.size == 0:
            continue
        samples.append((name, points_world, values_np))

    return samples


__all__ = [
    "_collect_backbone_evidence_points",
    "_voxel_corners",
    "_voxel_indices_to_world",
    "_voxel_indices_to_world_from_cache",
]
