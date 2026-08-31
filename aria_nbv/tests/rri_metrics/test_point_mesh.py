"""Tests for bounded prepared point--mesh batches."""

from __future__ import annotations

import torch

from aria_nbv.geometry import PreparedMeshQuery
from aria_nbv.geometry.point_mesh import tensor_identity_token
from aria_nbv.rri_metrics import point_mesh


def _mesh() -> tuple[torch.Tensor, torch.Tensor]:
    verts = torch.tensor(
        [[-1.0, -1.0, 0.0], [1.0, -1.0, 0.0], [1.0, 1.0, 0.0], [-1.0, 1.0, 0.0]],
        dtype=torch.float32,
    )
    faces = torch.tensor([[0, 1, 2], [0, 2, 3]], dtype=torch.int64)
    return verts, faces


def test_chunked_shared_mesh_matches_full_batch() -> None:
    torch.manual_seed(0)
    verts, faces = _mesh()
    points = torch.randn((5, 7, 3), dtype=torch.float32)
    lengths = torch.tensor([7, 6, 5, 4, 3], dtype=torch.long)
    prepared = PreparedMeshQuery(verts, faces, device="cpu", dtype=torch.float32)

    full = point_mesh.chamfer_prepared_point_mesh_batched(
        points,
        lengths,
        prepared,
    )
    chunked = point_mesh.chamfer_prepared_point_mesh_batched(
        points,
        lengths,
        prepared,
        candidate_chunk_size=2,
    )

    assert torch.allclose(chunked.accuracy, full.accuracy)
    assert torch.allclose(chunked.completeness, full.completeness)
    assert torch.allclose(chunked.bidirectional, full.bidirectional)


def test_chunking_bounds_materialized_triangle_rows(monkeypatch) -> None:
    torch.manual_seed(0)
    verts, faces = _mesh()
    points = torch.randn((5, 7, 3), dtype=torch.float32)
    lengths = torch.full((5,), 7, dtype=torch.long)
    triangle_rows: list[int] = []
    original = point_mesh.point_face_distance

    def record_point_face_distance(*args, **kwargs):
        triangle_rows.append(int(args[2].shape[0]))
        return original(*args, **kwargs)

    monkeypatch.setattr(point_mesh, "point_face_distance", record_point_face_distance)

    prepared = PreparedMeshQuery(verts, faces, device="cpu", dtype=torch.float32)
    point_mesh.chamfer_prepared_point_mesh_batched(
        points,
        lengths,
        prepared,
        candidate_chunk_size=2,
    )

    assert triangle_rows == [2 * faces.shape[0], 2 * faces.shape[0], faces.shape[0]]


def test_derived_cache_token_rejects_gradient_bearing_tensors() -> None:
    tensor = torch.ones(3, requires_grad=True)

    assert tensor_identity_token(tensor) is None
    assert tensor_identity_token(tensor.detach()) is not None
