"""Tests for point-to-mesh geometry backend behavior."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest
import torch

from aria_nbv.pose_generation import geometry


class _FakeDevice:
    type = "cuda"


class _FakeTensor:
    device = _FakeDevice()
    dtype = torch.float32
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
    int64 = torch.int64

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
    assert all(triangles is query.triangles for triangles in observed_triangles)


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
    query.verts = cast(Any, SimpleNamespace(device=torch.device("cuda:2"), dtype=torch.float32))
    monkeypatch.setattr(torch.cuda, "current_device", lambda: 2)

    assert query.matches(verts, faces, device="cuda", dtype=torch.float32, mesh=None)


def test_prepared_mesh_query_ray_adapter_forwards_bounds_and_reuses_engine() -> None:
    class FakeRayIntersector:
        def __init__(self) -> None:
            self.calls: list[tuple[np.ndarray, np.ndarray, bool, np.ndarray]] = []

        def intersects_any(
            self,
            ray_origins: np.ndarray,
            ray_directions: np.ndarray,
            *,
            multiple_hits: bool,
            max_distance: np.ndarray,
        ) -> np.ndarray:
            self.calls.append((ray_origins, ray_directions, multiple_hits, max_distance))
            return np.array([0, 1], dtype=np.int64)

    ray = FakeRayIntersector()
    mesh = cast(Any, SimpleNamespace(ray=ray))
    verts = torch.zeros((3, 3), dtype=torch.float32)
    faces = torch.zeros((1, 3), dtype=torch.int64)
    query = geometry.PreparedMeshQuery(verts, faces, device="cpu", dtype=torch.float32, mesh=mesh)
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
    assert ray.calls[0][3] is max_distance
    assert first.dtype == second.dtype == np.bool_
    assert first.tolist() == second.tolist() == [False, True]


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
