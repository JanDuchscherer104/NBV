"""Differentiable point-to-mesh geometry for candidate validity pruning.

This module provides the point-to-triangle distance primitive used by pruning
rules. Candidate sampling, validity policy, and mask/reason aggregation remain
with the pose generator and rule layer.

Inputs use world-frame metres and preserve the caller's Torch device/dtype.
PyTorch3D backend errors propagate to the caller; CUDA inputs never silently
fall back to CPU computation.
"""

from __future__ import annotations

import torch

DEVICE_FWD = [0.0, 0.0, 1.0]


def point_mesh_distance(points: torch.Tensor, verts: torch.Tensor, faces: torch.Tensor) -> torch.Tensor:
    """Compute point-to-mesh distances using PyTorch3D.

    Args:
        points: ``(N, 3)`` points in world frame.
        verts: ``(V, 3)`` mesh vertices.
        faces: ``(F, 3)`` mesh faces (indices into ``verts``).

    Returns:
        ``(N,)`` distances in metres on the same device/dtype as ``points``.
    """

    from pytorch3d.loss.point_mesh_distance import (  # type: ignore[import-untyped]
        _DEFAULT_MIN_TRIANGLE_AREA,
        point_face_distance,
    )

    device = points.device
    dtype = points.dtype
    points = points.to(device)
    verts = verts.to(device)
    faces = faces.to(device)

    def _point_face_distance_on_current_device() -> torch.Tensor:
        tris = verts[faces]
        points_first_idx = torch.zeros(1, device=points.device, dtype=torch.int64)
        tris_first_idx = torch.zeros(1, device=points.device, dtype=torch.int64)
        return point_face_distance(
            points,
            points_first_idx,
            tris,
            tris_first_idx,
            points.shape[0],
            _DEFAULT_MIN_TRIANGLE_AREA,
        )

    dist_sq = _point_face_distance_on_current_device()
    return torch.sqrt(dist_sq).to(device=device, dtype=dtype)


__all__ = ["point_mesh_distance"]
