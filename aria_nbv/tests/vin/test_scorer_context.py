"""Tests for shared VIN scorer tensor-preparation helpers."""

# ruff: noqa: S101

import pytest
import torch
from efm3d.aria.pose import PoseTW

from aria_nbv.vin.scorer_context import apply_vin_scorer_film, build_vin_scorer_scene_field
from aria_nbv.vin.types import EvlBackboneOutput


def _make_backbone_out(*, free_input: torch.Tensor | None = None) -> EvlBackboneOutput:
    occ_pr = torch.tensor([[[[[0.2]], [[0.8]]]]], dtype=torch.float32)
    occ_input = torch.tensor([[[[[0.25]], [[0.75]]]]], dtype=torch.float32)
    cent_pr = torch.tensor([[[[[0.4]], [[0.6]]]]], dtype=torch.float32)
    counts = torch.tensor([[[[1.0]], [[3.0]]]], dtype=torch.float32)
    pts_world = torch.zeros((1, 2, 1, 1, 3), dtype=torch.float32)
    voxel_extent = torch.tensor([[-1.0, 1.0, -1.0, 1.0, -1.0, 1.0]], dtype=torch.float32)
    t_world_voxel = PoseTW.from_Rt(
        torch.eye(3, dtype=torch.float32).unsqueeze(0),
        torch.zeros((1, 3), dtype=torch.float32),
    )
    return EvlBackboneOutput(
        occ_feat=None,
        obb_feat=None,
        occ_pr=occ_pr,
        occ_input=occ_input,
        free_input=free_input,
        counts=counts,
        counts_m=None,
        cent_pr=cent_pr,
        pts_world=pts_world,
        t_world_voxel=t_world_voxel,
        voxel_extent=voxel_extent,
    )


def test_build_vin_scorer_scene_field_uses_soft_unknown_contract() -> None:
    """Scorer fields should use ``unknown = 1 - counts_norm``."""
    out = _make_backbone_out()

    field_in, aux = build_vin_scorer_scene_field(
        out,
        scene_field_channels=["counts_norm", "unknown", "new_surface_prior"],
        model_name="VinModelV3",
    )

    counts = out.counts.to(dtype=torch.float32)  # type: ignore[union-attr]
    max_counts = counts.amax(dim=(-3, -2, -1), keepdim=True).clamp_min(1.0)
    expected_counts_norm = (torch.log1p(counts) / torch.log1p(max_counts)).unsqueeze(1)
    expected_unknown = 1.0 - expected_counts_norm
    assert torch.allclose(aux["counts_norm"], expected_counts_norm)
    assert torch.allclose(aux["unknown"], expected_unknown)
    assert not torch.allclose(aux["unknown"], 1.0 - aux["observed"])
    assert torch.allclose(aux["new_surface_prior"], expected_unknown * aux["occ_pr"])
    assert torch.allclose(field_in[:, 0], expected_counts_norm[:, 0])


def test_build_vin_scorer_scene_field_uses_raw_occ_input_fallback() -> None:
    """Absent free_input should fall back to observed * (1 - occ_input)."""
    out = _make_backbone_out()

    _field_in, aux = build_vin_scorer_scene_field(
        out,
        scene_field_channels=["free_input"],
        model_name="VinModelV3",
    )

    expected = aux["observed"] * (1.0 - aux["occ_input"])
    assert torch.allclose(aux["free_input"], expected)
    assert aux["free_input"].flatten().tolist() == pytest.approx([0.75, 0.25])


def test_build_vin_scorer_scene_field_preserves_free_input_and_channel_order() -> None:
    """Provided free-space evidence should be preserved and ordered as requested."""
    free_input = torch.tensor([[[[[0.1]], [[0.9]]]]], dtype=torch.float32)
    out = _make_backbone_out(free_input=free_input)

    field_in, aux = build_vin_scorer_scene_field(
        out,
        scene_field_channels=["cent_pr", "free_input", "occ_pr"],
        model_name="VinModelV2",
    )

    assert torch.allclose(aux["free_input"], free_input)
    assert torch.allclose(field_in[:, 0], aux["cent_pr"][:, 0])
    assert torch.allclose(field_in[:, 1], free_input[:, 0])
    assert torch.allclose(field_in[:, 2], aux["occ_pr"][:, 0])


def test_build_vin_scorer_scene_field_rejects_unknown_channel() -> None:
    """Invalid channel names should report the owning model config surface."""
    out = _make_backbone_out()

    with pytest.raises(ValueError, match=r"VinModelV2\.scene_field_channels"):
        build_vin_scorer_scene_field(
            out,
            scene_field_channels=["occ_pr", "not_a_channel"],
            model_name="VinModelV2",
        )


def test_apply_vin_scorer_film_uses_shared_formula() -> None:
    """FiLM helper should apply global * (1 + gamma) + beta."""
    global_feat = torch.ones((1, 2, 3), dtype=torch.float32)
    cond_feat = torch.tensor([[[2.0], [4.0]]], dtype=torch.float32)
    film = torch.nn.Linear(1, 6, bias=False)
    with torch.no_grad():
        film.weight.copy_(
            torch.tensor(
                [
                    [1.0],
                    [2.0],
                    [3.0],
                    [4.0],
                    [5.0],
                    [6.0],
                ],
                dtype=torch.float32,
            ),
        )

    out = apply_vin_scorer_film(global_feat, cond_feat, film=film, norm=None)
    film_out = film(cond_feat)
    gamma, beta = film_out.chunk(2, dim=-1)

    assert torch.allclose(out, global_feat * (1.0 + gamma) + beta)


def test_apply_vin_scorer_film_preserves_single_condition_broadcast() -> None:
    """A ``(B, 1, F)`` conditioning tensor should broadcast across candidates."""
    global_feat = torch.ones((2, 3, 2), dtype=torch.float32)
    cond_feat = torch.tensor([[[1.0]], [[3.0]]], dtype=torch.float32)
    film = torch.nn.Linear(1, 4, bias=False)
    with torch.no_grad():
        film.weight.fill_(1.0)

    out = apply_vin_scorer_film(global_feat, cond_feat, film=film, norm=None)

    assert out.shape == global_feat.shape
    assert torch.allclose(out[0], torch.full((3, 2), 3.0))
    assert torch.allclose(out[1], torch.full((3, 2), 7.0))
