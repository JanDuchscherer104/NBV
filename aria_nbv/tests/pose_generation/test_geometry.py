"""Tests for point-to-mesh geometry backend behavior."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest
import torch

from aria_nbv.pose_generation import geometry


class _FakeTensor:
    device = torch.device("cuda:0")
    dtype = torch.float32
    requires_grad = False
    shape = (1, 3)

    def __init__(self) -> None:
        self.cpu_calls = 0

    def __getitem__(self, _index: object) -> "_FakeTensor":
        return self

    def to(self, *_args: object, **_kwargs: object) -> "_FakeTensor":
        return self

    def cpu(self) -> "_FakeTensor":
        self.cpu_calls += 1
        return self


class _TorchProxy:
    Tensor = torch.Tensor
    device = torch.device
    int64 = torch.int64

    @staticmethod
    def is_grad_enabled() -> bool:
        return False

    @staticmethod
    def is_inference_mode_enabled() -> bool:
        return False

    @staticmethod
    def zeros(*_args: object, **_kwargs: object) -> _FakeTensor:
        return _FakeTensor()

    @staticmethod
    def sqrt(_value: object) -> object:
        raise AssertionError("sqrt should not run when the backend fails")


def test_cuda_backend_error_propagates_without_cpu_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    points = _FakeTensor()
    verts = _FakeTensor()
    faces = _FakeTensor()
    backend_error = RuntimeError("Not compiled with GPU support")

    def fail_point_face_distance(*_args: object, **_kwargs: object) -> torch.Tensor:
        raise backend_error

    monkeypatch.setattr(
        "pytorch3d.loss.point_mesh_distance.point_face_distance",
        fail_point_face_distance,
    )
    monkeypatch.setattr(geometry, "torch", _TorchProxy)

    with pytest.raises(RuntimeError, match="Not compiled with GPU support") as raised:
        geometry.point_mesh_distance(points, verts, faces)

    assert raised.value is backend_error
    assert points.cpu_calls == verts.cpu_calls == faces.cpu_calls == 0


def test_prepared_mesh_query_reuses_materialized_triangles(monkeypatch: pytest.MonkeyPatch) -> None:
    verts = torch.tensor(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        dtype=torch.float32,
    )
    faces = torch.tensor([[0, 1, 2]], dtype=torch.int64)
    points = torch.tensor([[0.25, 0.25, 1.0]], dtype=torch.float32)
    observed_triangles: list[torch.Tensor] = []

    def fake_point_face_distance(
        _points: torch.Tensor,
        _points_first_idx: torch.Tensor,
        triangles: torch.Tensor,
        _triangles_first_idx: torch.Tensor,
        _max_points: int,
        _min_triangle_area: float,
    ) -> torch.Tensor:
        observed_triangles.append(triangles)
        return torch.ones(points.shape[0], dtype=points.dtype)

    monkeypatch.setattr(
        "pytorch3d.loss.point_mesh_distance.point_face_distance",
        fake_point_face_distance,
    )

    query = geometry.PreparedMeshQuery(verts, faces, device="cpu", dtype=torch.float32)
    first = query.point_distance(points)
    second = query.point_distance(points)

    assert torch.equal(first, second)
    assert len(observed_triangles) == 2
    assert query.triangles is not None
    assert all(triangles is query.triangles for triangles in observed_triangles)


def test_prepared_mesh_query_rematerializes_autograd_triangles(monkeypatch: pytest.MonkeyPatch) -> None:
    verts = torch.tensor(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        dtype=torch.float64,
        requires_grad=True,
    )
    faces = torch.tensor([[0, 1, 2]], dtype=torch.int64)
    points = torch.tensor([[0.25, 0.25, 1.0]], dtype=torch.float32)
    observed_triangles: list[torch.Tensor] = []

    def fake_point_face_distance(
        _points: torch.Tensor,
        _points_first_idx: torch.Tensor,
        triangles: torch.Tensor,
        _triangles_first_idx: torch.Tensor,
        max_points: int,
        _min_triangle_area: float,
    ) -> torch.Tensor:
        observed_triangles.append(triangles)
        return triangles.square().sum().expand(max_points)

    monkeypatch.setattr(
        "pytorch3d.loss.point_mesh_distance.point_face_distance",
        fake_point_face_distance,
    )

    query = geometry.PreparedMeshQuery(verts, faces, device="cpu", dtype=torch.float32)
    first = query.point_distance(points)
    first.sum().backward()
    first_grad = verts.grad.detach().clone()
    verts.grad = None

    second = query.point_distance(points)
    second.sum().backward()

    assert torch.equal(first, second)
    assert torch.equal(verts.grad, first_grad)
    assert len(observed_triangles) == 2
    assert observed_triangles[0] is not observed_triangles[1]
    assert query.verts is None
    assert query.triangles is None


def test_prepared_mesh_query_reuses_inference_triangles_for_grad_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verts = torch.tensor(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        dtype=torch.float32,
        requires_grad=True,
    )
    faces = torch.tensor([[0, 1, 2]], dtype=torch.int64)
    points = torch.tensor([[0.25, 0.25, 1.0]], dtype=torch.float32)
    observed_triangles: list[torch.Tensor] = []

    def fake_point_face_distance(
        points: torch.Tensor,
        _points_first_idx: torch.Tensor,
        triangles: torch.Tensor,
        _triangles_first_idx: torch.Tensor,
        _max_points: int,
        _min_triangle_area: float,
    ) -> torch.Tensor:
        observed_triangles.append(triangles)
        return torch.ones(points.shape[0], dtype=points.dtype, device=points.device)

    monkeypatch.setattr(
        "pytorch3d.loss.point_mesh_distance.point_face_distance",
        fake_point_face_distance,
    )
    query = geometry.PreparedMeshQuery(verts, faces, device="cpu", dtype=torch.float32)
    with torch.inference_mode():
        query.point_distance(points)
        query.point_distance(points)

    assert len(observed_triangles) == 2
    assert observed_triangles[0] is observed_triangles[1]
    assert observed_triangles[0].is_inference()
    assert query.triangles is observed_triangles[0]


def test_prepared_mesh_query_rebuilds_inference_cache_for_autograd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verts = torch.tensor(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        dtype=torch.float32,
    )
    faces = torch.tensor([[0, 1, 2]], dtype=torch.int64)
    inference_points = torch.tensor([[0.25, 0.25, 1.0]], dtype=torch.float32)
    grad_points = inference_points.detach().clone().requires_grad_()
    observed_bundles: list[tuple[torch.Tensor, torch.Tensor, torch.Tensor]] = []

    def fake_point_face_distance(
        points: torch.Tensor,
        points_first_idx: torch.Tensor,
        triangles: torch.Tensor,
        triangles_first_idx: torch.Tensor,
        _max_points: int,
        _min_triangle_area: float,
    ) -> torch.Tensor:
        observed_bundles.append((triangles, points_first_idx, triangles_first_idx))
        return points.square().sum(dim=1) + triangles.square().sum() * 0.0

    monkeypatch.setattr(
        "pytorch3d.loss.point_mesh_distance.point_face_distance",
        fake_point_face_distance,
    )

    query = geometry.PreparedMeshQuery(verts, faces, device="cpu", dtype=torch.float32)
    with torch.inference_mode():
        query.point_distance(inference_points)
    query.point_distance(grad_points).sum().backward()

    assert len(observed_bundles) == 2
    assert all(tensor.is_inference() for tensor in observed_bundles[0])
    assert all(not tensor.is_inference() for tensor in observed_bundles[1])
    assert grad_points.grad is not None
    assert query.triangles is observed_bundles[1][0]


def test_prepared_mesh_query_rejects_mutated_source_tensors() -> None:
    verts = torch.tensor(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        dtype=torch.float32,
    )
    faces = torch.tensor([[0, 1, 2]], dtype=torch.int64)
    query = geometry.PreparedMeshQuery(verts, faces, device="cpu", dtype=torch.float32)

    assert query.matches(verts, faces, device="cpu", dtype=torch.float32, mesh=None)

    verts.add_(1.0)
    assert not query.matches(verts, faces, device="cpu", dtype=torch.float32, mesh=None)


def test_prepared_mesh_query_resolves_unindexed_cuda_for_reuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verts = torch.zeros((3, 3), dtype=torch.float32)
    faces = torch.zeros((1, 3), dtype=torch.int64)
    query = object.__new__(geometry.PreparedMeshQuery)
    query._source_verts = verts
    query._source_faces = faces
    query._source_verts_version = verts._version
    query._source_faces_version = faces._version
    query._source_mesh = None
    query._device = torch.device("cuda")
    query._dtype = torch.float32
    query._materialized_device = torch.device("cuda:2")
    monkeypatch.setattr(torch.cuda, "current_device", lambda: 2)

    assert query.matches(verts, faces, device="cuda", dtype=torch.float32, mesh=None)


def test_prepared_mesh_query_rejects_unindexed_cuda_after_device_switch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verts = torch.zeros((3, 3), dtype=torch.float32)
    faces = torch.zeros((1, 3), dtype=torch.int64)
    query = object.__new__(geometry.PreparedMeshQuery)
    query._source_verts = verts
    query._source_faces = faces
    query._source_verts_version = verts._version
    query._source_faces_version = faces._version
    query._source_mesh = None
    query._device = torch.device("cuda")
    query._dtype = torch.float32
    query._materialized_device = torch.device("cuda:0")
    monkeypatch.setattr(torch.cuda, "current_device", lambda: 1)

    assert not query.matches(verts, faces, device="cuda", dtype=torch.float32, mesh=None)
    replacement = geometry.PreparedMeshQuery.acquire(
        query,
        verts,
        faces,
        device="cuda",
        dtype=torch.float32,
    )
    assert replacement is not query
    assert replacement._materialized_device is None


def test_prepared_mesh_query_ray_adapter_forwards_bounds_and_reuses_engine() -> None:
    class FakeRayIntersector:
        def __init__(self) -> None:
            self.calls: list[tuple[np.ndarray, np.ndarray, bool]] = []

        def intersects_location(
            self,
            ray_origins: np.ndarray,
            ray_directions: np.ndarray,
            *,
            multiple_hits: bool,
        ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
            self.calls.append((ray_origins, ray_directions, multiple_hits))
            return (
                np.array([[2.0, 0.0, 0.0], [0.5, 0.0, 0.0]], dtype=np.float32),
                np.array([0, 1], dtype=np.int64),
                np.array([0, 0], dtype=np.int64),
            )

    ray = FakeRayIntersector()
    mesh = cast(Any, SimpleNamespace(ray=ray))
    verts = torch.zeros((3, 3), dtype=torch.float32)
    faces = torch.zeros((1, 3), dtype=torch.int64)
    query = geometry.PreparedMeshQuery(verts, faces, device="cuda", dtype=torch.float32, mesh=mesh)
    assert query.verts is None
    assert query.faces is None
    assert query.triangles is None
    origins = np.zeros((2, 3), dtype=np.float32)
    directions = np.ones((2, 3), dtype=np.float32)
    max_distance = np.array([1.0, 2.0], dtype=np.float32)

    first = query.intersects_any(
        origins,
        directions,
        max_distance=max_distance,
        use_pyembree=False,
    )
    second = query.intersects_any(
        origins,
        directions,
        max_distance=max_distance,
        use_pyembree=False,
    )

    assert len(ray.calls) == 2
    assert ray.calls[0][0] is origins
    assert ray.calls[0][1] is directions
    assert ray.calls[0][2] is False
    assert first.dtype == second.dtype == np.bool_
    assert first.tolist() == second.tolist() == [False, True]
    assert query.verts is None
    assert query.faces is None
    assert query.triangles is None


def test_prepared_mesh_query_uses_pyembree_location_api(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePyembreeIntersector:
        def __init__(self, _mesh: object) -> None:
            pass

        def intersects_location(
            self,
            ray_origins: np.ndarray,
            ray_directions: np.ndarray,
            *,
            multiple_hits: bool,
        ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
            assert multiple_hits is False
            return (
                ray_origins + ray_directions * 0.5,
                np.arange(ray_origins.shape[0], dtype=np.int64),
                np.zeros(ray_origins.shape[0], dtype=np.int64),
            )

    module = SimpleNamespace(RayMeshIntersector=FakePyembreeIntersector)
    monkeypatch.setitem(sys.modules, "trimesh.ray.ray_pyembree", module)
    mesh = cast(Any, SimpleNamespace())
    query = geometry.PreparedMeshQuery(
        torch.zeros((3, 3)),
        torch.zeros((1, 3), dtype=torch.int64),
        device="cuda",
        dtype=torch.float32,
        mesh=mesh,
    )

    intersections = query.intersects_any(
        np.zeros((1, 3), dtype=np.float32),
        np.array([[1.0, 0.0, 0.0]], dtype=np.float32),
        max_distance=np.array([1.0], dtype=np.float32),
        use_pyembree=True,
    )

    assert intersections.tolist() == [True]
    assert query.triangles is None


def test_prepared_mesh_query_bounds_real_trimesh_ray_to_endpoint() -> None:
    import trimesh

    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    mesh.apply_translation((10.0, 0.0, 0.0))
    query = geometry.PreparedMeshQuery(
        torch.from_numpy(mesh.vertices).to(torch.float32),
        torch.from_numpy(mesh.faces).to(torch.int64),
        device="cuda",
        dtype=torch.float32,
        mesh=mesh,
    )
    origins = np.zeros((1, 3), dtype=np.float32)
    directions = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)

    before_endpoint = query.intersects_any(
        origins,
        directions,
        max_distance=np.array([1.0], dtype=np.float32),
        use_pyembree=False,
    )
    through_mesh = query.intersects_any(
        origins,
        directions,
        max_distance=np.array([11.0], dtype=np.float32),
        use_pyembree=False,
    )

    assert before_endpoint.tolist() == [False]
    assert through_mesh.tolist() == [True]
    assert query.triangles is None


def test_prepared_mesh_query_accepts_inference_tensors_without_reusing_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_triangles: list[torch.Tensor] = []

    def fake_point_face_distance(
        points: torch.Tensor,
        _points_first_idx: torch.Tensor,
        triangles: torch.Tensor,
        _triangles_first_idx: torch.Tensor,
        _max_points: int,
        _min_triangle_area: float,
    ) -> torch.Tensor:
        observed_triangles.append(triangles)
        return torch.ones(points.shape[0], dtype=points.dtype)

    monkeypatch.setattr(
        "pytorch3d.loss.point_mesh_distance.point_face_distance",
        fake_point_face_distance,
    )

    with torch.inference_mode():
        verts = torch.tensor(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            dtype=torch.float32,
        )
        faces = torch.tensor([[0, 1, 2]], dtype=torch.int64)
        points = torch.tensor([[0.25, 0.25, 1.0]], dtype=torch.float32)
        first = geometry.PreparedMeshQuery.acquire(None, verts, faces, device="cpu", dtype=torch.float32)

        assert torch.equal(first.point_distance(points), torch.ones(1))
        assert not first.matches(verts, faces, device="cpu", dtype=torch.float32, mesh=None)

        second = geometry.PreparedMeshQuery.acquire(first, verts, faces, device="cpu", dtype=torch.float32)

    assert second is not first
    assert len(observed_triangles) == 1
