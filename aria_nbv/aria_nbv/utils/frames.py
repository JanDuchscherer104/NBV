"""Construct frame-safe Aria/EFM camera axes and coordinate transforms.

This module provides world-up broadcasting, pose-aware look-at axes,
rig-to-camera composition, and the CW90 display-yaw transform for `PoseTW` and
`CameraTW`. It owns LUF/Z-up frame conversion only; sampling policy, camera
calibration, and image data remain with callers. Look-at construction aligns
camera up with world up to avoid arbitrary roll while preserving the LUF
convention (X-left, Y-up, Z-forward).
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F  # noqa: N812
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW
from efm3d.utils.gravity import (
    GRAVITY_DIRECTION_VIO,  # [0, 0, -1]
)


def world_up_tensor(
    device: torch.device | None = None,
    dtype: torch.dtype | None = None,
) -> torch.Tensor:
    """Return world up vector as tensor.

    In the EFM3D VIO convention gravity points to ``[0, 0, -1]``; world-up is
    therefore ``+Z``. This helper keeps that logic in one place.
    """

    return torch.tensor(-GRAVITY_DIRECTION_VIO, device=device, dtype=dtype)


def _broadcast_poses_for_view(
    from_pose: PoseTW,
    to_pose: PoseTW,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Ensure pose tensors have matching batch dimensions.

    Args:
        from_pose: Origin pose(s).
        to_pose: Target pose(s).

    Returns:
        Tuple of tensors shaped ``(B, 3, 4)`` for aligned broadcasting.
    """

    t_from = from_pose.matrix3x4.view(-1, 3, 4)
    t_to = to_pose.matrix3x4.view(-1, 3, 4)

    if t_from.shape[0] == 1 and t_to.shape[0] > 1:
        t_from = t_from.expand(t_to.shape[0], -1, -1)
    if t_to.shape[0] == 1 and t_from.shape[0] > 1:
        t_to = t_to.expand(t_from.shape[0], -1, -1)

    if t_from.shape[0] != t_to.shape[0]:
        raise ValueError(f"Batch sizes must match for view construction: {t_from.shape} vs {t_to.shape}")

    return t_from, t_to


def view_axes_from_poses(
    from_pose: PoseTW,
    to_pose: PoseTW,
    *,
    look_away: bool = True,
    eps: float = 1e-6,
) -> PoseTW:
    """Construct roll-free camera poses looking along the segment ``from→to``.

    The resulting pose(s) satisfy the Aria LUF convention (x=left, y=up,
    z=forward) with zero roll by aligning the up-axis to ``world_up_tensor``.

    Args:
        from_pose: Pose of the reference point (typically the last pose).
        to_pose: Pose whose translations define the camera centers.
        look_away: If True, cameras look away from ``from_pose`` towards
            ``to_pose``; otherwise they look back.
        eps: Numerical stability guard.

    Returns:
        PoseTW with the same translations as ``to_pose`` and rotations derived
        from the line of sight and world-up.
    """

    t_from, t_to = _broadcast_poses_for_view(from_pose, to_pose)
    device = t_to.device
    world_up = world_up_tensor(device=device, dtype=t_to.dtype)

    p_from = t_from[..., :3, 3]
    p_to = t_to[..., :3, 3]

    disp = p_to - p_from
    if not look_away:
        disp = -disp

    z_cam = disp / disp.norm(dim=-1, keepdim=True).clamp_min(eps)

    wup_exp = world_up.view(1, 3).expand_as(z_cam)
    x_cam = torch.cross(wup_exp, z_cam, dim=-1)
    x_norm = x_cam.norm(dim=-1, keepdim=True)

    degenerate = x_norm.squeeze(-1) < eps
    if degenerate.any():  # fallback to a horizontal axis orthogonal to up
        tmp = torch.tensor([1.0, 0.0, 0.0], device=device, dtype=t_to.dtype)
        tmp = tmp - (tmp @ world_up) * world_up
        tmp = tmp / tmp.norm().clamp_min(eps)
        x_cam[degenerate] = tmp
        x_norm = x_cam.norm(dim=-1, keepdim=True)

    x_cam = x_cam / x_norm
    y_cam = torch.cross(z_cam, x_cam, dim=-1)

    r_wc = torch.stack([x_cam, y_cam, z_cam], dim=-1)

    out = torch.empty_like(t_to)
    out[..., :3, :3] = r_wc
    out[..., :3, 3] = p_to
    return PoseTW.from_matrix3x4(out)


def _view_axes_from_positions(
    cam_pos: torch.Tensor,
    look_at: torch.Tensor,
    world_up: torch.Tensor | None = None,
    eps: float = 1e-6,
) -> torch.Tensor:
    """Return camera axes (batch) for the Aria LUF camera frame.

    This is the tensor-level implementation. Use
    `view_axes_from_poses` when you already operate on ``PoseTW``
    instances.
    """

    world_up = world_up if world_up is not None else world_up_tensor(device=cam_pos.device, dtype=cam_pos.dtype)

    # Forward (camera z-axis) from camera to target.
    fwd = F.normalize(look_at - cam_pos, dim=-1)

    # Horizontal x-axis via world_up × forward ensures zero roll.
    while world_up.ndim < fwd.ndim:
        world_up = world_up.unsqueeze(0)

    left = torch.cross(world_up, fwd, dim=-1)
    left_norm = left.norm(dim=-1, keepdim=True)
    degenerate = left_norm.squeeze(-1) < eps

    if degenerate.any():
        alt = torch.tensor([1.0, 0.0, 0.0], device=cam_pos.device, dtype=cam_pos.dtype)
        while alt.ndim < fwd.ndim:
            alt = alt.unsqueeze(0)
        alt = alt - (alt * world_up).sum(dim=-1, keepdim=True) * world_up
        left[degenerate] = alt[degenerate]
        left_norm = left.norm(dim=-1, keepdim=True)

    left = left / left_norm.clamp_min(eps)
    up = torch.cross(fwd, left, dim=-1)
    up = F.normalize(up + eps, dim=-1)

    return torch.stack([left, up, fwd], dim=-1)


def view_axes_from_points(
    from_pose: PoseTW | torch.Tensor,
    look_at: PoseTW | torch.Tensor,
    world_up: torch.Tensor | None = None,
    eps: float = 1e-6,
) -> torch.Tensor:
    """PoseTW-aware look-at helper for LUF cameras.

    Args:
        from_pose: Camera pose (or center tensor) in world coordinates.
        look_at: Target point (or pose whose translation is the target).
        world_up: Optional world up vector; defaults to ``+Z``.
        eps: Numerical stability term.

    Returns:
        Rotation matrices ``R_world_cam`` with shape ``(..., 3, 3)`` following
        the LUF convention (columns = left, up, forward).
    """

    cam_origin = from_pose.t if isinstance(from_pose, PoseTW) else from_pose
    target = look_at.t if isinstance(look_at, PoseTW) else look_at

    return _view_axes_from_positions(cam_pos=cam_origin, look_at=target, world_up=world_up, eps=eps)


def world_from_camera(t_world_rig: PoseTW, cam: CameraTW, frame_idx: int) -> PoseTW:
    """Compute T_world_cam from rig pose and CameraTW extrinsics."""
    return t_world_rig @ cam.T_camera_rig[frame_idx].inverse()


def rotate_yaw_cw90(pose_world_cam: PoseTW, undo: bool = False) -> PoseTW:
    """Rotate a pose by 90° clockwise about its **local +Z axis**.

    Important:
        Despite the historical name, this is a *local-frame* rotation (right-multiplication)
        about the pose's +Z axis. In the Aria LUF convention (+Z = forward), this is a
        **roll/twist** that swaps the local +X/+Y axes.

    Why this exists:
        - Project Aria tooling/visualisations sometimes apply a fixed 90° twist for display.
        - In our candidate generation pipeline we also apply this to the **reference pose**
          as a rig-basis correction so that sampling assumptions (LUF: x=left, y=up, z=fwd)
          match the incoming `t_world_rig` basis (otherwise azimuth/elevation look swapped).

    Caution:
        Apply this conversion **at most once** in any given path; applying it again in
        plotting will look like an azimuth/elevation swap once roll jitter is enabled.
    """
    if undo:
        c, s = np.cos(-np.pi / 2), np.sin(-np.pi / 2)
    else:
        c, s = np.cos(np.pi / 2), np.sin(np.pi / 2)
    r_roll = torch.tensor(
        [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]],
        device=pose_world_cam.R.device,
        dtype=pose_world_cam.R.dtype,
    )
    return PoseTW.from_Rt(pose_world_cam.R @ r_roll, pose_world_cam.t)


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    cam_pos = torch.tensor([[0.0, 0.0, 0.0]])  # (1, 3)
    target = torch.tensor([[0.0, 0.0, 1.0]])  # camera looks along +Z

    R_wc = view_axes_from_points(cam_pos, target)[0]  # (3, 3)
    t_wc = cam_pos[0]

    plt.show()
