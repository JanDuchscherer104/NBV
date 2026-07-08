"""Pose and candidate-frame adapters for VIN diagnostic figures.

The functions in this module normalize VIN diagnostic pose inputs to
:class:`efm3d.aria.pose.PoseTW`, broadcast reference and candidate pose batches,
and derive candidate-center or validity arrays used by Plotly views. Voxel and
backbone evidence extraction lives in
:mod:`aria_nbv.vin.diagnostics._voxel_evidence_adapter`.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import torch
from efm3d.aria.pose import PoseTW

from ...utils.frames import rotate_yaw_cw90


def _pose_first_batch(pose: PoseTW) -> PoseTW:
    """Return the first pose batch while preserving a single-pose batch axis."""
    if pose.ndim == 1:
        return PoseTW(pose._data.unsqueeze(0))
    if pose.ndim == 2 and pose.shape[0] > 1:
        return PoseTW(pose._data[:1])
    return pose


def _as_pose_tw(pose: PoseTW | torch.Tensor) -> PoseTW:
    """Convert a PoseTW or ``(..., 12)/(3, 4)`` tensor into :class:`PoseTW`."""
    if isinstance(pose, PoseTW):
        return pose
    if torch.is_tensor(pose):
        data = pose
        if data.shape[-1] == 12:
            data = data.view(*data.shape[:-1], 3, 4)
        return PoseTW.from_matrix3x4(data)
    raise TypeError(f"Unsupported pose type: {type(pose)!s}")


def _as_pose_batch(pose: PoseTW | torch.Tensor) -> PoseTW:
    """Convert a pose-like object to a batched :class:`PoseTW` container."""
    pose_tw = _as_pose_tw(pose)
    if pose_tw.ndim == 1:
        return PoseTW(pose_tw._data.unsqueeze(0))
    if pose_tw.ndim == 2 and pose_tw.shape[-1] == 12:
        return PoseTW(pose_tw._data.unsqueeze(0))
    return pose_tw


def _broadcast_pose_batch(pose: PoseTW, *, batch_size: int, name: str) -> PoseTW:
    """Broadcast a singleton pose batch to match candidate batch size."""
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
    """Compute candidate camera centers in the reference rig frame."""
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
    """Read the best available per-candidate validity fraction from diagnostics."""
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
    """Rotate points with the display-only CW90 yaw convention used in plots."""
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


__all__ = [
    "_as_pose_batch",
    "_as_pose_tw",
    "_broadcast_pose_batch",
    "_candidate_valid_fraction",
    "_centers_rig_from_poses",
    "_pose_first_batch",
    "_rotate_points_yaw_cw90",
]
