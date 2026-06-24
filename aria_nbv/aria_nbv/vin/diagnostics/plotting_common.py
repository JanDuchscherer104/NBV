"""VIN-specific plotting adapters shared by diagnostics.

The helpers in this module translate VIN pose, voxel, and backbone diagnostic
state into arrays consumed by Plotly figures. Generic Plotly primitives live in
:mod:`aria_nbv.vin.diagnostics._plot_primitives`.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import torch
from efm3d.aria.pose import PoseTW

from ...utils.frames import rotate_yaw_cw90


def _voxel_corners(extent: np.ndarray) -> np.ndarray:
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


def _pose_first_batch(pose: PoseTW) -> PoseTW:
    if pose.ndim == 1:
        return PoseTW(pose._data.unsqueeze(0))
    if pose.ndim == 2 and pose.shape[0] > 1:
        return PoseTW(pose._data[:1])
    return pose


def _as_pose_tw(pose: PoseTW | torch.Tensor) -> PoseTW:
    if isinstance(pose, PoseTW):
        return pose
    if torch.is_tensor(pose):
        data = pose
        if data.shape[-1] == 12:
            data = data.view(*data.shape[:-1], 3, 4)
        return PoseTW.from_matrix3x4(data)
    raise TypeError(f"Unsupported pose type: {type(pose)!s}")


def _as_pose_batch(pose: PoseTW | torch.Tensor) -> PoseTW:
    pose_tw = _as_pose_tw(pose)
    if pose_tw.ndim == 1:
        return PoseTW(pose_tw._data.unsqueeze(0))
    if pose_tw.ndim == 2 and pose_tw.shape[-1] == 12:
        return PoseTW(pose_tw._data.unsqueeze(0))
    return pose_tw


def _broadcast_pose_batch(pose: PoseTW, *, batch_size: int, name: str) -> PoseTW:
    if pose.ndim != 2:
        raise ValueError(f"{name} must have shape (B, 12), got ndim={pose.ndim}.")
    if pose.shape[0] == 1 and batch_size > 1:
        return PoseTW(pose._data.expand(batch_size, 12))
    if pose.shape[0] != batch_size:
        raise ValueError(f"{name} must have batch size 1 or match candidates.")
    return pose


def _centers_rig_from_poses(
    reference_pose_world_rig: PoseTW,
    candidate_poses_world_cam: PoseTW,
) -> torch.Tensor:
    pose_world_cam = _as_pose_batch(candidate_poses_world_cam)
    pose_world_rig = _as_pose_batch(reference_pose_world_rig)
    pose_world_rig = _broadcast_pose_batch(
        pose_world_rig,
        batch_size=int(pose_world_cam.shape[0]),
        name="reference_pose_world_rig",
    )
    pose_rig_cam = pose_world_rig.inverse()[:, None] @ pose_world_cam
    return pose_rig_cam.t


def _candidate_valid_fraction(debug: Any) -> torch.Tensor:
    token_valid = getattr(debug, "token_valid", None)
    if isinstance(token_valid, torch.Tensor):
        return token_valid.float().mean(dim=-1)

    voxel_valid_frac = getattr(debug, "voxel_valid_frac", None)
    if isinstance(voxel_valid_frac, torch.Tensor):
        return voxel_valid_frac.float()

    candidate_valid = getattr(debug, "candidate_valid", None)
    if isinstance(candidate_valid, torch.Tensor):
        return candidate_valid.float()

    centers = debug.candidate_center_rig_m
    return torch.ones(centers.shape[:-1], dtype=torch.float32, device=centers.device)


def _rotate_points_yaw_cw90(
    points: np.ndarray | torch.Tensor,
    *,
    pose_world_frame: PoseTW | None = None,
    undo: bool = False,
) -> np.ndarray | torch.Tensor:
    if isinstance(points, np.ndarray):
        if points.size == 0:
            return points
        pts = torch.as_tensor(points, dtype=torch.float32)
        to_numpy = True
    else:
        pts = points
        to_numpy = False
    if pts.numel() == 0:
        return points

    angle = -np.pi / 2 if undo else np.pi / 2
    c, s = float(np.cos(angle)), float(np.sin(angle))
    r_roll = torch.tensor(
        [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]],
        device=pts.device,
        dtype=pts.dtype,
    )
    if pose_world_frame is None:
        rot = PoseTW.from_Rt(
            r_roll,
            torch.zeros(3, device=pts.device, dtype=pts.dtype),
        )
        rotated = rot.transform(pts)
    else:
        pose_rot = rotate_yaw_cw90(pose_world_frame, undo=undo)
        pts_frame = pose_world_frame.inverse().transform(pts)
        rotated = pose_rot.transform(pts_frame)
    return rotated.detach().cpu().numpy() if to_numpy else rotated


def _voxel_indices_to_world(
    indices: np.ndarray,
    *,
    pose: PoseTW,
    extent: np.ndarray,
    shape: tuple[int, int, int],
) -> np.ndarray:
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


def _collect_backbone_evidence_points(
    debug: Any,
    *,
    fields: list[str],
    occ_threshold: float,
    max_points: int,
) -> list[tuple[str, np.ndarray, np.ndarray]]:
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
    "_as_pose_batch",
    "_as_pose_tw",
    "_broadcast_pose_batch",
    "_candidate_valid_fraction",
    "_centers_rig_from_poses",
    "_collect_backbone_evidence_points",
    "_pose_first_batch",
    "_rotate_points_yaw_cw90",
    "_voxel_corners",
    "_voxel_indices_to_world",
]
