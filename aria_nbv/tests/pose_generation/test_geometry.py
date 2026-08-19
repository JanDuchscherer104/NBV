"""Tests for point-to-mesh geometry backend behavior."""

from __future__ import annotations

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
