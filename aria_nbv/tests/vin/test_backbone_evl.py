"""Tests for EVL backbone adapter feature-family filtering."""

from __future__ import annotations

from pathlib import Path

import omegaconf
import pytest
import torch

from aria_nbv.vin.backbones.evl import (
    _normalize_evl_model_config_paths,
    filter_backbone_output_for_features_mode,
    resolve_free_input,
)
from aria_nbv.vin.types import EvlBackboneOutput

PoseTW = __import__("efm3d.aria.pose", fromlist=["PoseTW"]).PoseTW


def _pose() -> PoseTW:
    """Return a single identity world<-voxel pose."""

    return PoseTW.from_Rt(torch.eye(3, dtype=torch.float32).unsqueeze(0), torch.zeros((1, 3), dtype=torch.float32))


def _backbone_output() -> EvlBackboneOutput:
    """Build a mixed head/neck EVL output without loading EVL."""

    grid = torch.ones((1, 1, 2, 2, 2), dtype=torch.float32)
    return EvlBackboneOutput(
        t_world_voxel=_pose(),
        voxel_extent=torch.tensor([-1.0, 1.0, -1.0, 1.0, -1.0, 1.0], dtype=torch.float32),
        voxel_feat=torch.ones((1, 4, 2, 2, 2), dtype=torch.float32),
        occ_feat=torch.ones((1, 4, 2, 2, 2), dtype=torch.float32),
        obb_feat=torch.ones((1, 4, 2, 2, 2), dtype=torch.float32),
        occ_pr=grid,
        occ_input=grid,
        free_input=grid,
        counts=torch.ones((1, 2, 2, 2), dtype=torch.int64),
        counts_m=torch.ones((1, 2, 2, 2), dtype=torch.int64),
        voxel_select_t=torch.zeros((1, 1), dtype=torch.int64),
        cent_pr=grid,
        bbox_pr=torch.ones((1, 7, 2, 2, 2), dtype=torch.float32),
        clas_pr=torch.ones((1, 3, 2, 2, 2), dtype=torch.float32),
        cent_pr_nms=grid,
        pts_world=torch.zeros((1, 8, 3), dtype=torch.float32),
        feat2d_upsampled={"rgb": torch.ones((1, 1, 2, 2, 2), dtype=torch.float32)},
        token2d={"rgb": torch.ones((1, 1, 2, 2, 2), dtype=torch.float32)},
    )


def test_features_mode_heads_drops_neck_and_internal_features() -> None:
    """``features_mode='heads'`` should keep EVL head outputs only."""

    filtered = filter_backbone_output_for_features_mode(_backbone_output(), features_mode="heads")

    assert filtered.occ_pr is not None  # noqa: S101
    assert filtered.cent_pr is not None  # noqa: S101
    assert filtered.bbox_pr is not None  # noqa: S101
    assert filtered.voxel_feat is None  # noqa: S101
    assert filtered.occ_feat is None  # noqa: S101
    assert filtered.obb_feat is None  # noqa: S101
    assert filtered.feat2d_upsampled == {}  # noqa: S101
    assert filtered.token2d == {}  # noqa: S101


def test_free_input_native_requires_upstream_and_preserves_typed_provenance() -> None:
    native = torch.full((1, 1, 2, 2, 2), 0.25)
    resolved, provenance = resolve_free_input(mode="native", native_free_input=native, counts=None, occ_input=None)
    assert torch.equal(resolved, native)  # noqa: S101
    assert provenance == "native_evl_v1"  # noqa: S101
    with pytest.raises(RuntimeError, match="requires EVL to provide"):
        resolve_free_input(mode="native", native_free_input=None, counts=None, occ_input=None)


def test_free_input_derived_uses_observed_complement_formula() -> None:
    counts = torch.tensor([[[[0, 2]], [[1, 0]]]], dtype=torch.int64)
    occ_input = torch.tensor([[[[[0.2, 0.3]], [[0.4, 0.5]]]]])
    resolved, provenance = resolve_free_input(
        mode="derived", native_free_input=torch.full_like(occ_input, 99), counts=counts, occ_input=occ_input
    )
    expected = (counts > 0).unsqueeze(1) * (1 - occ_input)
    assert torch.equal(resolved, expected)  # noqa: S101
    assert provenance == "derived_observed_complement_occ_input_v1"  # noqa: S101


def test_features_mode_neck_drops_head_outputs() -> None:
    """``features_mode='neck'`` should keep neck/internal feature families."""

    filtered = filter_backbone_output_for_features_mode(_backbone_output(), features_mode="neck")

    assert filtered.voxel_feat is not None  # noqa: S101
    assert filtered.occ_feat is not None  # noqa: S101
    assert filtered.obb_feat is not None  # noqa: S101
    assert filtered.occ_pr is None  # noqa: S101
    assert filtered.occ_input is None  # noqa: S101
    assert filtered.counts is None  # noqa: S101
    assert filtered.bbox_pr is None  # noqa: S101


def test_normalize_evl_model_config_paths_rebases_stale_absolute_assets(tmp_path: Path) -> None:
    """Stale machine-local EFM paths should resolve to the current checkout."""

    ckpt = tmp_path / ".logs" / "ckpts" / "dinov2_vitb14_reg4_pretrain.pth"
    taxonomy = tmp_path / "external" / "efm3d" / "efm3d" / "config" / "taxonomy" / "ase_sem_name_to_id.csv"
    ckpt.parent.mkdir(parents=True)
    taxonomy.parent.mkdir(parents=True)
    ckpt.write_bytes(b"checkpoint")
    taxonomy.write_text("name,id\n", encoding="utf-8")

    config = omegaconf.OmegaConf.create(
        {
            "taxonomy_file": "/home/jandu/repos/NBV/external/efm3d/efm3d/config/taxonomy/ase_sem_name_to_id.csv",
            "video_backbone": {
                "image_tokenizer": {
                    "ckpt_path": "/home/jandu/repos/NBV/.logs/ckpts/dinov2_vitb14_reg4_pretrain.pth",
                },
            },
        },
    )

    normalized = _normalize_evl_model_config_paths(config, root=tmp_path)

    assert normalized.taxonomy_file == str(taxonomy)  # noqa: S101
    assert normalized.video_backbone.image_tokenizer.ckpt_path == str(ckpt)  # noqa: S101
