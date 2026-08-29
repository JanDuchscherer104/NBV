"""Differentiable point-to-mesh geometry for candidate validity pruning.

This module provides the point-to-triangle distance primitive used by pruning
rules. Candidate sampling, validity policy, and mask/reason aggregation remain
with the pose generator and rule layer.

Inputs use world-frame metres and preserve the caller's Torch device/dtype.
PyTorch3D backend errors propagate to the caller; CUDA inputs never silently
fall back to CPU computation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, cast

import numpy as np
import torch
from numpy.typing import NDArray

if TYPE_CHECKING:
    import trimesh

DEVICE_FWD = [0.0, 0.0, 1.0]


class _ProximityQuery(Protocol):
    def signed_distance(
        self,
        points: NDArray[np.floating[Any]],
    ) -> NDArray[np.floating[Any]]: ...


class _RayIntersector(Protocol):
    def intersects_location(
        self,
        ray_origins: NDArray[np.floating[Any]],
        ray_directions: NDArray[np.floating[Any]],
        *,
        multiple_hits: bool,
    ) -> tuple[NDArray[np.floating[Any]], NDArray[np.int64], NDArray[np.int64]]: ...


def _tensor_version(tensor: torch.Tensor) -> int | None:
    """Return the mutation counter, or ``None`` when Torch does not expose one."""

    try:
        return int(tensor._version)
    except (AttributeError, RuntimeError):
        return None


def _resolved_device(device: torch.device | str) -> torch.device:
    """Resolve an unindexed CUDA device to the accelerator Torch will use."""

    resolved = torch.device(device)
    if resolved.type == "cuda" and resolved.index is None:
        return torch.device("cuda", torch.cuda.current_device())
    return resolved


def _devices_match(left: torch.device, right: torch.device | str) -> bool:
    """Compare requested devices without resolving identical lazy CUDA requests."""

    requested = torch.device(right)
    if left == requested:
        return True
    return bool(left.type == requested.type == "cuda" and _resolved_device(left) == _resolved_device(requested))


def bounded_ray_intersects_any(
    engine: _RayIntersector,
    origins: NDArray[np.floating[Any]],
    directions: NDArray[np.floating[Any]],
    *,
    max_distance: NDArray[np.floating[Any]],
) -> NDArray[np.bool_]:
    """Return first-hit intersections bounded by each ray segment length."""

    locations, ray_indices, _triangle_indices = engine.intersects_location(
        origins,
        directions,
        multiple_hits=False,
    )
    intersections = np.zeros(origins.shape[0], dtype=np.bool_)
    if ray_indices.size == 0:
        return intersections
    hit_distances = np.linalg.norm(locations - origins[ray_indices], axis=1)
    bounds = max_distance[ray_indices]
    tolerance = np.finfo(np.float32).eps * np.maximum(1.0, np.abs(bounds)) * 8.0
    intersections[ray_indices[hit_distances <= bounds + tolerance]] = True
    return intersections


class PreparedMeshQuery:
    """Prepared point-distance and CPU query state for one immutable mesh.

    The query materializes device/dtype-normalized PyTorch3D tensors only when
    point-distance evaluation needs them. Optional Trimesh proximity and ray
    adapters are also initialized lazily and then reused by every pruning rule
    sharing this query. :meth:`acquire` rejects reuse after source mutation.
    Inference-mode tensors remain valid for one query but are deliberately not
    reused because Torch does not expose their mutation counters.

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
        self._source_verts = verts
        self._source_faces = faces
        self._source_verts_version = _tensor_version(verts)
        self._source_faces_version = _tensor_version(faces)
        self._source_mesh = mesh
        self._device = torch.device(device)
        self._dtype = dtype
        self._materialized_device: torch.device | None = None
        self.verts: torch.Tensor | None = None
        self.faces: torch.Tensor | None = None
        self.triangles: torch.Tensor | None = None
        self.points_first_idx: torch.Tensor | None = None
        self.triangles_first_idx: torch.Tensor | None = None
        self.mesh = mesh
        self._proximity_query: _ProximityQuery | None = None
        self._ray_engines: dict[bool, _RayIntersector] = {}

    @classmethod
    def acquire(
        cls,
        current: PreparedMeshQuery | None,
        verts: torch.Tensor,
        faces: torch.Tensor,
        *,
        device: torch.device | str,
        dtype: torch.dtype,
        mesh: "trimesh.Trimesh | None" = None,
    ) -> PreparedMeshQuery:
        """Reuse a matching query or prepare one for the supplied mesh contract."""

        if current is not None and current.matches(
            verts,
            faces,
            device=device,
            dtype=dtype,
            mesh=mesh,
        ):
            return current
        return cls(verts, faces, device=device, dtype=dtype, mesh=mesh)

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
            self._source_verts_version is not None
            and self._source_faces_version is not None
            and self.matches_request(
                verts,
                faces,
                device=device,
                dtype=dtype,
                mesh=mesh,
            )
        )

    @property
    def is_persistently_reusable(self) -> bool:
        """Return whether source mutation counters permit cross-request reuse."""

        return self._source_verts_version is not None and self._source_faces_version is not None

    def matches_request(
        self,
        verts: torch.Tensor,
        faces: torch.Tensor,
        *,
        device: torch.device | str,
        dtype: torch.dtype,
        mesh: "trimesh.Trimesh | None",
    ) -> bool:
        """Validate a query for immediate use, including inference tensors.

        Unlike :meth:`matches`, this request-scoped check accepts matching
        unavailable mutation counters. Exact tensor and mesh identity still
        prevent a prepared query from serving different geometry.
        """

        verts_version = _tensor_version(verts)
        faces_version = _tensor_version(faces)
        return (
            verts is self._source_verts
            and faces is self._source_faces
            and verts_version == self._source_verts_version
            and faces_version == self._source_faces_version
            and mesh is self._source_mesh
            and self._matches_device(device)
            and self._dtype == dtype
        )

    def _matches_device(self, device: torch.device | str) -> bool:
        """Match the lazy request or the concrete device owning prepared tensors."""

        if self._materialized_device is None:
            return _devices_match(self._device, device)
        return bool(self._materialized_device == _resolved_device(device))

    def _materialize_pytorch3d(self) -> None:
        """Materialize PyTorch3D tensors once, leaving CPU-only queries cheap."""

        if self.triangles is not None:
            return
        target_device = _resolved_device(self._device)
        verts = self._source_verts.to(device=target_device, dtype=self._dtype)
        faces = self._source_faces.to(device=target_device, dtype=torch.int64)
        triangles = verts[faces]
        points_first_idx = torch.zeros(1, device=target_device, dtype=torch.int64)
        triangles_first_idx = torch.zeros(1, device=target_device, dtype=torch.int64)
        self.verts = verts
        self.faces = faces
        self.triangles = triangles
        self.points_first_idx = points_first_idx
        self.triangles_first_idx = triangles_first_idx
        self._materialized_device = target_device

    def point_distance(self, points: torch.Tensor) -> torch.Tensor:
        """Return point-to-mesh distances for matching device/dtype points.

        Args:
            points ``Tensor["N 3", float]``: World-frame points in metres.

        Returns:
            ``Tensor["N", float]`` distances in metres.

        Raises:
            ValueError: If points do not match the prepared device and dtype.
        """

        from pytorch3d.loss.point_mesh_distance import (
            _DEFAULT_MIN_TRIANGLE_AREA,
            point_face_distance,
        )

        expected_device = self._materialized_device or _resolved_device(self._device)
        if points.device != expected_device or points.dtype != self._dtype:
            raise ValueError(
                "PreparedMeshQuery points must match the prepared mesh device and dtype "
                f"({expected_device}, {self._dtype}); got ({points.device}, {points.dtype})."
            )
        self._materialize_pytorch3d()
        assert self.triangles is not None
        assert self.points_first_idx is not None
        assert self.triangles_first_idx is not None
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
            import trimesh

            constructor = cast(
                "Callable[[trimesh.Trimesh], _ProximityQuery]",
                trimesh.proximity.ProximityQuery,
            )
            self._proximity_query = constructor(self.mesh)
        distances = self._proximity_query.signed_distance(points.detach().cpu().numpy())
        return torch.from_numpy(distances).to(device=points.device, dtype=points.dtype).abs()

    def intersects_any(
        self,
        origins: NDArray[np.floating[Any]],
        directions: NDArray[np.floating[Any]],
        *,
        max_distance: NDArray[np.floating[Any]],
        use_pyembree: bool,
    ) -> NDArray[np.bool_]:
        """Return whether each bounded ray intersects the prepared mesh."""

        if self.mesh is None:
            raise ValueError("PreparedMeshQuery requires a Trimesh mesh for ray queries.")
        engine = self._ray_engines.get(use_pyembree)
        if engine is None:
            if use_pyembree:
                from trimesh.ray.ray_pyembree import RayMeshIntersector

                engine = cast(_RayIntersector, RayMeshIntersector(self.mesh))
            else:
                engine = cast(_RayIntersector, self.mesh.ray)
            self._ray_engines[use_pyembree] = engine
        return bounded_ray_intersects_any(
            engine,
            origins,
            directions,
            max_distance=max_distance,
        )


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


__all__ = ["bounded_ray_intersects_any", "PreparedMeshQuery", "point_mesh_distance"]
