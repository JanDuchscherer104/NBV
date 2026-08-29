"""Prepared mesh state shared by candidate pruning and RRI kernels."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, cast

import numpy as np
import torch
from numpy.typing import NDArray

if TYPE_CHECKING:
    import trimesh


class _ProximityQuery(Protocol):
    def signed_distance(
        self,
        points: NDArray[np.floating[Any]],
    ) -> NDArray[np.floating[Any]]: ...


class _RayIntersector(Protocol):
    def intersects_any(
        self,
        ray_origins: NDArray[np.floating[Any]],
        ray_directions: NDArray[np.floating[Any]],
        *,
        multiple_hits: bool,
        max_distance: NDArray[np.floating[Any]],
    ) -> NDArray[np.bool_]: ...


def _tensor_version(tensor: torch.Tensor) -> int | None:
    """Return the mutation counter, or ``None`` when Torch does not expose one."""

    try:
        return int(tensor._version)
    except (AttributeError, RuntimeError):
        return None


def tensor_identity_token(tensor: torch.Tensor) -> tuple[object, ...] | None:
    """Return a mutation-sensitive identity token, or ``None`` when unsafe to cache."""

    version = _tensor_version(tensor)
    if version is None:
        return None
    return (
        id(tensor),
        version,
        tuple(tensor.shape),
        tuple(tensor.stride()),
        tensor.storage_offset(),
        tensor.device,
        tensor.dtype,
    )


def _resolved_device(device: torch.device | str) -> torch.device:
    """Resolve an unindexed CUDA device to the accelerator Torch will use."""

    resolved = torch.device(device)
    if resolved.type == "cuda" and resolved.index is None:
        return torch.device("cuda", torch.cuda.current_device())
    return resolved


def _matches_versioned_tensor(
    tensor: torch.Tensor,
    expected: torch.Tensor,
    expected_version: int | None,
) -> bool:
    """Return whether identity and an observable mutation counter still match."""

    current_version = _tensor_version(tensor)
    return (
        expected_version is not None
        and current_version is not None
        and tensor is expected
        and current_version == expected_version
    )


class PreparedMeshQuery:
    """Prepare immutable mesh state once for repeated geometric queries.

    The module hides normalized tensors, materialized triangles, PyTorch3D
    batch-index tensors, and lazy Trimesh adapters behind one interface. A
    query is valid only while its source tensors and optional CPU mesh remain
    immutable. Inference-mode tensors are valid for one query but deliberately
    uncacheable because Torch does not expose their mutation counters.

    Args:
        verts ``Tensor["V 3", float]``: World-frame vertices in metres.
        faces ``Tensor["F 3", int]``: Triangle indices into ``verts``.
        device: Device used by point-distance kernels.
        dtype: Floating-point dtype used by point-distance kernels.
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
        self.verts = verts.to(device=device, dtype=dtype)
        self.faces = faces.to(device=device, dtype=torch.int64)
        self._prepared_verts_version = _tensor_version(self.verts)
        self._prepared_faces_version = _tensor_version(self.faces)
        self.triangles = self.verts[self.faces]
        self.points_first_idx = torch.zeros(1, device=device, dtype=torch.int64)
        self.triangles_first_idx = torch.zeros(1, device=device, dtype=torch.int64)
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
            (
                _matches_versioned_tensor(verts, self._source_verts, self._source_verts_version)
                or _matches_versioned_tensor(verts, self.verts, self._prepared_verts_version)
            )
            and (
                _matches_versioned_tensor(faces, self._source_faces, self._source_faces_version)
                or _matches_versioned_tensor(faces, self.faces, self._prepared_faces_version)
            )
            and mesh is self._source_mesh
            and self.verts.device == _resolved_device(device)
            and self.verts.dtype == dtype
        )

    def matches_request(
        self,
        verts: torch.Tensor,
        faces: torch.Tensor,
        *,
        device: torch.device | str,
        dtype: torch.dtype,
        mesh: "trimesh.Trimesh | None",
    ) -> bool:
        """Validate immediate use against exact sources, including inference tensors.

        Matching unavailable mutation counters are safe only at this explicit
        request boundary. :meth:`matches` remains fail-closed for cross-request
        cache reuse.
        """

        return (
            verts is self._source_verts
            and faces is self._source_faces
            and _tensor_version(verts) == self._source_verts_version
            and _tensor_version(faces) == self._source_faces_version
            and mesh is self._source_mesh
            and self.verts.device == _resolved_device(device)
            and self.verts.dtype == dtype
        )

    def point_distance(self, points: torch.Tensor, *, squared: bool = False) -> torch.Tensor:
        """Return point-to-mesh distances for matching device/dtype points.

        Args:
            points ``Tensor["N 3", float]``: World-frame points in metres.
            squared: Return squared distances when true.

        Returns:
            ``Tensor["N", float]`` distances in metres or square metres.

        Raises:
            ValueError: If points do not match the prepared device and dtype.
        """

        from pytorch3d.loss.point_mesh_distance import (
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
        return dist_sq if squared else torch.sqrt(dist_sq)

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
        intersections = engine.intersects_any(
            origins,
            directions,
            multiple_hits=False,
            max_distance=max_distance,
        )
        return np.asarray(intersections, dtype=np.bool_)


__all__ = ["PreparedMeshQuery"]
