"""Differentiable point-to-mesh geometry for candidate validity pruning.

This module provides the point-to-triangle distance primitive used by pruning
rules. Candidate sampling, validity policy, and mask/reason aggregation remain
with the pose generator and rule layer.

Inputs use world-frame metres and preserve the caller's Torch device/dtype.
PyTorch3D backend errors propagate to the caller; CUDA inputs never silently
fall back to CPU computation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import torch

if TYPE_CHECKING:
    import trimesh  # type: ignore[import-untyped]

DEVICE_FWD = [0.0, 0.0, 1.0]


class PreparedMeshQuery:
    """Prepared point-distance and CPU query state for one immutable mesh.

    The query owns device/dtype-normalized mesh tensors and materializes the
    PyTorch3D triangle table once. Optional Trimesh proximity and ray adapters
    are initialized lazily and then reused by every pruning rule sharing this
    query. Callers must create a new query after mutating the source mesh.

    Args:
        verts ``Tensor["V 3", float]``: World-frame vertices in metres.
        faces ``Tensor["F 3", int]``: Triangle indices into ``verts``.
        device: Device used by candidate points and PyTorch3D kernels.
        dtype: Floating-point dtype used by candidate points.
        mesh: Optional CPU Trimesh adapter for signed-distance and ray queries.
    """

    def __init__(
        self,
        verts: torch.Tensor,
        faces: torch.Tensor,
        *,
        device: torch.device | str,
        dtype: torch.dtype,
        mesh: "trimesh.Trimesh | None" = None,
    ) -> None:
        target_device = device
        self._source_verts = verts
        self._source_faces = faces
        self._source_mesh = mesh
        self.verts = verts.to(device=target_device, dtype=dtype)
        self.faces = faces.to(device=target_device, dtype=torch.int64)
        self.triangles = self.verts[self.faces]
        self.points_first_idx = torch.zeros(1, device=target_device, dtype=torch.int64)
        self.triangles_first_idx = torch.zeros(1, device=target_device, dtype=torch.int64)
        self.mesh = mesh
        self._proximity_query: Any | None = None
        self._ray_engines: dict[bool, Any] = {}

    def matches(
        self,
        verts: torch.Tensor,
        faces: torch.Tensor,
        *,
        device: torch.device | str,
        dtype: torch.dtype,
        mesh: "trimesh.Trimesh | None",
    ) -> bool:
        """Return whether this query can safely serve the supplied mesh inputs."""

        return (
            verts is self._source_verts
            and faces is self._source_faces
            and mesh is self._source_mesh
            and self.verts.device == torch.device(device)
            and self.verts.dtype == dtype
        )

    def point_distance(self, points: torch.Tensor) -> torch.Tensor:
        """Return point-to-mesh distances for matching device/dtype points.

        Args:
            points ``Tensor["N 3", float]``: World-frame points in metres.

        Returns:
            ``Tensor["N", float]`` distances in metres.

        Raises:
            ValueError: If points do not match the prepared device and dtype.
        """

        from pytorch3d.loss.point_mesh_distance import (  # type: ignore[import-untyped]
            _DEFAULT_MIN_TRIANGLE_AREA,
            point_face_distance,
        )

        if points.device != self.verts.device or points.dtype != self.verts.dtype:
            raise ValueError(
                "PreparedMeshQuery points must match the prepared mesh device and dtype "
                f"({self.verts.device}, {self.verts.dtype}); got ({points.device}, {points.dtype})."
            )
        dist_sq = point_face_distance(
            points,
            self.points_first_idx,
            self.triangles,
            self.triangles_first_idx,
            points.shape[0],
            _DEFAULT_MIN_TRIANGLE_AREA,
        )
        return torch.sqrt(dist_sq)

    def signed_distance(self, points: torch.Tensor) -> torch.Tensor:
        """Return absolute Trimesh signed distances on the points' device."""

        if self.mesh is None:
            raise ValueError("PreparedMeshQuery requires a Trimesh mesh for signed-distance queries.")
        if self._proximity_query is None:
            import trimesh  # type: ignore[import-untyped]

            self._proximity_query = trimesh.proximity.ProximityQuery(self.mesh)
        distances = self._proximity_query.signed_distance(points.detach().cpu().numpy())
        return torch.from_numpy(distances).to(device=points.device, dtype=points.dtype).abs()

    def ray_engine(self, *, use_pyembree: bool) -> Any:
        """Return one cached Trimesh ray adapter for the requested backend."""

        if self.mesh is None:
            raise ValueError("PreparedMeshQuery requires a Trimesh mesh for ray queries.")
        engine = self._ray_engines.get(use_pyembree)
        if engine is None:
            if use_pyembree:
                from trimesh.ray.ray_pyembree import RayMeshIntersector  # type: ignore[import-untyped]

                engine = RayMeshIntersector(self.mesh)
            else:
                engine = self.mesh.ray
            self._ray_engines[use_pyembree] = engine
        return engine


def point_mesh_distance(points: torch.Tensor, verts: torch.Tensor, faces: torch.Tensor) -> torch.Tensor:
    """Compute point-to-mesh distances using PyTorch3D.

    Args:
        points: ``(N, 3)`` points in world frame.
        verts: ``(V, 3)`` mesh vertices.
        faces: ``(F, 3)`` mesh faces (indices into ``verts``).

    Returns:
        ``(N,)`` distances in metres on the same device/dtype as ``points``.
    """

    device = points.device
    dtype = points.dtype
    prepared = PreparedMeshQuery(verts, faces, device=device, dtype=dtype)
    return prepared.point_distance(points).to(device=device, dtype=dtype)


__all__ = ["PreparedMeshQuery", "point_mesh_distance"]
