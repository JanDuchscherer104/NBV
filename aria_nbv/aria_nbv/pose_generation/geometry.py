"""Differentiable point-to-mesh geometry for candidate validity pruning.

This compatibility owner exposes the shared policy-free mesh query while pose
generation continues to own pruning policy, masks, and reason aggregation.
"""

from __future__ import annotations

import torch

from ..geometry import PreparedMeshQuery, bounded_ray_intersects_any

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

    prepared = PreparedMeshQuery(verts, faces, device=points.device, dtype=points.dtype)
    return prepared.point_distance(points).to(device=points.device, dtype=points.dtype)


__all__ = ["bounded_ray_intersects_any", "PreparedMeshQuery", "point_mesh_distance"]
