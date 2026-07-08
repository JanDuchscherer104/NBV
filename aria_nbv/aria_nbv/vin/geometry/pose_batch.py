"""Pose-batch shape helpers for VIN candidate scorers.

VIN scorer inputs use :class:`efm3d.aria.pose.PoseTW` tensors with explicit
candidate and batch axes. These helpers centralize the tolerated shorthand
forms before model code computes relative poses, projection grids, or rollout
candidate scores.
"""

from __future__ import annotations

from typing import TypeVar

from efm3d.aria.pose import PoseTW

PoseBatchT = TypeVar("PoseBatchT", bound=PoseTW)


def ensure_candidate_batch(candidate_poses_world_cam: PoseBatchT) -> PoseBatchT:
    """Ensure candidate camera poses are shaped as ``PoseTW["B N 12"]``.

    Args:
        candidate_poses_world_cam: Candidate camera poses ``T_w_c`` with shape
            ``PoseTW["N 12"]`` for one snippet or ``PoseTW["B N 12"]`` for a
            batch.

    Returns:
        Candidate poses with an explicit batch axis.

    Raises:
        ValueError: If the pose tensor is neither ``(N, 12)`` nor
            ``(B, N, 12)``.
    """
    if candidate_poses_world_cam.ndim == 2:
        return candidate_poses_world_cam.unsqueeze(0)
    if candidate_poses_world_cam.ndim != 3:
        raise ValueError(
            "candidate_poses_world_cam must have shape (N,12) or (B,N,12).",
        )
    return candidate_poses_world_cam


def ensure_pose_batch(pose: PoseBatchT, *, batch_size: int, name: str) -> PoseBatchT:
    """Broadcast one pose tensor to the VIN batch size.

    Args:
        pose: Pose tensor with shape ``PoseTW["12"]``, ``PoseTW["1 12"]``, or
            ``PoseTW["B 12"]``.
        batch_size: Required batch size ``B``.
        name: Human-readable input name used in validation errors.

    Returns:
        ``pose`` shaped as ``PoseTW["B 12"]``.

    Raises:
        ValueError: If ``pose`` has an unsupported rank or a non-broadcastable
            batch dimension.
    """
    if pose.ndim == 1:
        pose = pose.unsqueeze(0)
    elif pose.ndim != 2:
        raise ValueError(
            f"{name} must have shape (12,) or (B,12), got ndim={pose.ndim}.",
        )
    if int(pose.shape[0]) == batch_size:
        return pose
    if int(pose.shape[0]) == 1:
        if isinstance(pose, PoseTW):
            return PoseTW(pose._data.expand(batch_size, 12))
        return pose.expand(batch_size, 12)
    raise ValueError(
        f"{name} must have batch size 1 or {batch_size}, got {int(pose.shape[0])}.",
    )


__all__ = ["ensure_candidate_batch", "ensure_pose_batch"]
