import pytest
import torch

from aria_nbv.oracle._scoring import PreparedRriScorerConfig, _canonical_fused_unions, _crop_mesh_to_aabb


def _unit_square_mesh(device: torch.device, *, dtype: torch.dtype) -> tuple[torch.Tensor, torch.Tensor]:
    """Return a small, deterministic mesh for distance tests."""

    verts = torch.tensor(
        [
            [-1.0, -1.0, 0.0],
            [1.0, -1.0, 0.0],
            [1.0, 1.0, 0.0],
            [-1.0, 1.0, 0.0],
        ],
        device=device,
        dtype=dtype,
    )
    faces = torch.tensor([[0, 1, 2], [0, 2, 3]], device=device, dtype=torch.int64)
    return verts, faces


def test_oracle_rri_handles_empty_candidate_pointclouds():
    """If a candidate contributes zero points, then P_{t∪q} == P_t and RRI==0."""

    torch.manual_seed(0)
    device = torch.device("cpu")
    dtype = torch.float32

    gt_verts, gt_faces = _unit_square_mesh(device, dtype=dtype)
    points_t = torch.randn((64, 3), device=device, dtype=dtype)

    num_candidates = 3
    max_points_q = 16
    points_q = torch.randn((num_candidates, max_points_q, 3), device=device, dtype=dtype)
    lengths_q = torch.tensor([max_points_q, 0, max_points_q], device=device, dtype=torch.long)
    extend = torch.tensor([-2, 2, -2, 2, -2, 2], device=device, dtype=dtype)

    out = (
        PreparedRriScorerConfig()
        .setup_target()
        .score(
            points_t=points_t,
            points_q=points_q,
            lengths_q=lengths_q,
            gt_verts=gt_verts,
            gt_faces=gt_faces,
            extend=extend,
        )
    )

    # Candidate 1 has no points; distances after must equal before and RRI must be 0.
    assert float(out.rri[1].item()) == 0.0
    assert torch.allclose(out.pm_dist_after[1], out.pm_dist_before[1], atol=1e-6)
    assert torch.allclose(out.pm_acc_after[1], out.pm_acc_before[1], atol=1e-6)
    assert torch.allclose(out.pm_comp_after[1], out.pm_comp_before[1], atol=1e-6)


def test_crop_mesh_to_aabb_preserves_device_dtype_and_reindexes_faces() -> None:
    device = torch.device("cpu")
    dtype = torch.float32
    verts = torch.tensor(
        [
            [-1.0, -1.0, 0.0],
            [0.0, -1.0, 0.0],
            [-1.0, 0.0, 0.0],
            [10.0, 10.0, 0.0],
            [11.0, 10.0, 0.0],
            [10.0, 11.0, 0.0],
        ],
        device=device,
        dtype=dtype,
    )
    faces = torch.tensor([[0, 1, 2], [3, 4, 5]], device=device, dtype=torch.int64)
    aabb = torch.tensor([-1.1, 0.1, -1.1, 0.1, -0.1, 0.1], device=device, dtype=dtype)

    verts_crop, faces_crop = _crop_mesh_to_aabb(verts, faces, aabb)

    assert verts_crop.device == verts.device
    assert verts_crop.dtype == verts.dtype
    assert faces_crop.device == faces.device
    assert faces_crop.dtype == faces.dtype
    assert int(faces_crop.max().item()) < verts_crop.shape[0]
    assert verts_crop.shape[0] < verts.shape[0]


def test_crop_mesh_to_aabb_rejects_empty_crop() -> None:
    device = torch.device("cpu")
    dtype = torch.float32
    verts, faces = _unit_square_mesh(device, dtype=dtype)
    aabb = torch.tensor([10.0, 11.0, 10.0, 11.0, 10.0, 11.0], device=device, dtype=dtype)

    with pytest.raises(ValueError, match="no mesh faces"):
        _crop_mesh_to_aabb(verts, faces, aabb)


def test_capped_union_preserves_candidate_points_when_root_saturates() -> None:
    root = torch.stack(
        [torch.tensor([float(index), 0.0, 0.0], dtype=torch.float32) for index in range(100)],
        dim=0,
    )
    query = torch.tensor([[[1000.0, 0.0, 0.0]]], dtype=torch.float32)
    lengths = torch.tensor([1], dtype=torch.long)

    fused, fused_lengths = _canonical_fused_unions(
        points_t=root,
        points_q=query,
        lengths_q=lengths,
        voxel_size_m=0.0,
        max_points=10,
    )

    assert int(fused_lengths[0].item()) == 10
    assert torch.isclose(fused[0, :10, 0], torch.tensor(1000.0)).any()


def test_prepared_reference_reuses_crop_mesh_and_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    import aria_nbv.oracle._scoring as scoring

    verts, faces = _unit_square_mesh(torch.device("cpu"), dtype=torch.float32)
    points_t = torch.randn((16, 3), dtype=torch.float32)
    extend = torch.tensor([-2, 2, -2, 2, -2, 2], dtype=torch.float32)
    scorer = PreparedRriScorerConfig().setup_target()
    crop_calls = 0
    original_crop = scoring._crop_mesh_to_aabb

    def record_crop(*args, **kwargs):
        nonlocal crop_calls
        crop_calls += 1
        return original_crop(*args, **kwargs)

    monkeypatch.setattr(scoring, "_crop_mesh_to_aabb", record_crop)

    first = scorer._prepare_reference(points_t=points_t, gt_verts=verts, gt_faces=faces, extend=extend)
    second = scorer._prepare_reference(points_t=points_t, gt_verts=verts, gt_faces=faces, extend=extend)
    points_t.add_(1.0)
    third = scorer._prepare_reference(points_t=points_t, gt_verts=verts, gt_faces=faces, extend=extend)
    fourth = scorer._prepare_reference(points_t=points_t.clone(), gt_verts=verts, gt_faces=faces, extend=extend)

    assert first is second
    assert all(
        source is expected for source, expected in zip(first.sources, (points_t, verts, faces, extend), strict=True)
    )
    assert third is not first
    assert fourth is not third
    assert crop_calls == 3
