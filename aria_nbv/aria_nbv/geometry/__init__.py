"""Shared prepared geometry kernels used across ARIA-NBV domains."""

from .point_mesh import PreparedMeshQuery, bounded_ray_intersects_any

__all__ = ["bounded_ray_intersects_any", "PreparedMeshQuery"]
