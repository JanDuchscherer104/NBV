"""Unit tests for VIN v3 plotting helpers."""

# ruff: noqa: S101

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
import torch
from efm3d.aria import PoseTW
from efm3d.aria.aria_constants import (
    ARIA_POINTS_DIST_STD,
    ARIA_POINTS_INV_DIST_STD,
    ARIA_POINTS_TIME_NS,
    ARIA_POINTS_VOL_MAX,
    ARIA_POINTS_VOL_MIN,
    ARIA_POINTS_WORLD,
    ARIA_POSE_T_WORLD_RIG,
    ARIA_POSE_TIME_NS,
)

from aria_nbv.data_handling.raw.views import EfmSnippetView
from aria_nbv.vin.diagnostics.plotting import (
    build_backbone_evidence_figures,
    build_field_slice_figures,
    build_geometry_overview_figure,
    build_lff_empirical_figures,
    build_pos_grid_linearity_figure,
    build_pose_enc_pca_figure,
    build_pose_grid_pca_figure,
    build_pose_grid_slices_figure,
    build_pose_vec_histogram,
    build_scene_field_evidence_figures,
    build_se3_closure_figure,
    build_semidense_projection_feature_figure,
    build_semidense_projection_figure,
    build_voxel_inbounds_figure,
    build_voxel_roundtrip_figure,
)
from aria_nbv.vin.types import EvlBackboneOutput

try:
    from pytorch3d.renderer.cameras import PerspectiveCameras  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - optional dependency
    PerspectiveCameras = None  # type: ignore[assignment]


class DummyLff(torch.nn.Module):
    def __init__(self, input_dim: int = 9, fourier_dim: int = 4) -> None:
        super().__init__()
        self.Wr = torch.nn.Parameter(torch.randn(fourier_dim, input_dim))
        self.fourier_dim = fourier_dim
        self.mlp = torch.nn.Linear(fourier_dim * 2, fourier_dim * 2, bias=False)


def _make_snippet() -> EfmSnippetView:
    t_world_rig = PoseTW.from_Rt(
        torch.eye(3).repeat(2, 1, 1),
        torch.tensor([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]),
    )
    points_world = torch.tensor(
        [
            [
                [0.0, 0.0, 0.0],
                [1.0, 1.0, 1.0],
                [2.0, 0.0, 0.0],
            ],
        ],
        dtype=torch.float32,
    )
    efm = {
        ARIA_POSE_T_WORLD_RIG: t_world_rig,
        ARIA_POSE_TIME_NS: torch.tensor([0, 10], dtype=torch.int64),
        "pose/gravity_in_world": torch.tensor([0.0, 0.0, -9.81]),
        ARIA_POINTS_WORLD: points_world,
        ARIA_POINTS_DIST_STD: torch.zeros((1, 3), dtype=torch.float32),
        ARIA_POINTS_INV_DIST_STD: torch.zeros((1, 3), dtype=torch.float32),
        ARIA_POINTS_TIME_NS: torch.tensor([0], dtype=torch.int64),
        ARIA_POINTS_VOL_MIN: torch.tensor([-1.0, -1.0, -1.0]),
        ARIA_POINTS_VOL_MAX: torch.tensor([1.0, 1.0, 1.0]),
        "points/lengths": torch.tensor([3], dtype=torch.int64),
    }
    return EfmSnippetView(
        efm=efm,
        scene_id="scene",
        snippet_id="snippet",
    )


def _make_backbone(*, pts_world: torch.Tensor | None = None) -> EvlBackboneOutput:
    t_world_voxel = PoseTW.from_Rt(
        torch.eye(3).unsqueeze(0),
        torch.zeros(1, 3),
    )
    voxel_extent = torch.tensor([-1.0, 1.0, -1.0, 1.0, -1.0, 1.0], dtype=torch.float32)
    occ_pr = torch.rand(1, 1, 2, 2, 2)
    return EvlBackboneOutput(
        t_world_voxel=t_world_voxel,
        voxel_extent=voxel_extent,
        occ_pr=occ_pr,
        pts_world=pts_world,
    )


def _make_debug() -> SimpleNamespace:
    backbone_out = _make_backbone()
    candidate_center_rig_m = torch.tensor([[[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]]])
    candidate_valid = torch.tensor([[True, False]])
    field_in = torch.rand(1, 2, 2, 2, 2)
    field = torch.rand(1, 2, 2, 2, 2)
    pose_enc = torch.rand(1, 2, 8)
    pose_vec = torch.rand(1, 2, 9)
    return SimpleNamespace(
        backbone_out=backbone_out,
        candidate_center_rig_m=candidate_center_rig_m,
        candidate_valid=candidate_valid,
        field_in=field_in,
        field=field,
        pose_enc=pose_enc,
        pose_vec=pose_vec,
    )


def test_vin_plotting_core_figures() -> None:
    debug = _make_debug()
    snippet = _make_snippet()
    ref_pose = PoseTW.from_Rt(torch.eye(3).unsqueeze(0), torch.zeros(1, 3))
    cand_poses = PoseTW.from_Rt(
        torch.eye(3).repeat(2, 1, 1),
        torch.tensor([[0.0, 0.0, 0.5], [1.0, 0.0, 0.5]]),
    )

    fig_geom = build_geometry_overview_figure(
        debug,
        snippet=snippet,
        reference_pose_world_rig=ref_pose,
        candidate_poses_world_cam=cand_poses,
        show_frustum=False,
        show_gt_obbs=False,
    )
    assert fig_geom.data

    figs_backbone = build_backbone_evidence_figures(debug, occ_threshold=0.0, max_points=10)
    assert figs_backbone

    figs_scene = build_scene_field_evidence_figures(
        debug,
        channel_names=["occ_pr", "feat"],
        occ_threshold=0.0,
        max_points=10,
    )
    assert figs_scene

    fig_roundtrip = build_voxel_roundtrip_figure(debug)
    assert fig_roundtrip.data

    fig_se3 = build_se3_closure_figure(cand_poses, ref_pose)
    assert fig_se3.data

    fig_inbounds = build_voxel_inbounds_figure(
        cand_poses, debug.backbone_out.t_world_voxel, debug.backbone_out.voxel_extent
    )
    assert fig_inbounds.data

    pos_grid = torch.rand(1, 3, 2, 2, 2)
    fig_linearity = build_pos_grid_linearity_figure(pos_grid, debug.backbone_out.voxel_extent)
    assert fig_linearity.data


def test_vin_plotting_encoding_figures() -> None:
    debug = _make_debug()
    pose_vec = debug.pose_vec
    pose_enc = debug.pose_enc

    fig_hist = build_pose_vec_histogram(pose_vec, dim_index=0)
    assert fig_hist.data

    fig_pca = build_pose_enc_pca_figure(pose_enc)
    assert fig_pca.data

    pos_grid = torch.rand(1, 3, 2, 2, 2)
    fig_slices = build_pose_grid_slices_figure(pos_grid, axis="D", index=0)
    assert fig_slices.data

    pos_proj = torch.nn.Linear(3, 8, bias=False)
    fig_grid_pca = build_pose_grid_pca_figure(pos_grid, pos_proj=pos_proj, max_points=10)
    assert fig_grid_pca.data

    lff = DummyLff(input_dim=pose_vec.shape[-1], fourier_dim=4)
    figs_lff = build_lff_empirical_figures(pose_vec, lff, max_features=4, hist_bins=10, max_points=10)
    assert "lff_empirical_fourier_hist" in figs_lff


def test_vin_plotting_field_slices() -> None:
    debug = _make_debug()
    field = debug.field[0]
    figs = build_field_slice_figures(field, channel_names=["c0", "c1"], max_channels=2)
    assert figs


def test_vin_plotting_evidence_uses_pts_world() -> None:
    pts_world = torch.tensor([[[10.0, 20.0, 30.0]]], dtype=torch.float32)
    t_world_voxel = PoseTW.from_Rt(
        torch.eye(3).unsqueeze(0),
        torch.zeros(1, 3),
    )
    voxel_extent = torch.tensor([-1.0, 1.0, -1.0, 1.0, -1.0, 1.0], dtype=torch.float32)
    backbone_out = EvlBackboneOutput(
        t_world_voxel=t_world_voxel,
        voxel_extent=voxel_extent,
        occ_pr=torch.ones(1, 1, 1, 1, 1),
        occ_input=torch.ones(1, 1, 1, 1, 1),
        counts=torch.ones(1, 1, 1, 1),
        pts_world=pts_world,
    )
    debug = SimpleNamespace(
        backbone_out=backbone_out,
        field_in=torch.ones(1, 1, 1, 1, 1),
    )

    figs_scene = build_scene_field_evidence_figures(
        debug,
        channel_names=["occ_pr"],
        occ_threshold=0.0,
        max_points=10,
    )
    assert "occ_pr" in figs_scene
    scene_scatter = figs_scene["occ_pr"].data[0]
    assert np.isclose(scene_scatter.x[0], 10.0)
    assert np.isclose(scene_scatter.y[0], 20.0)
    assert np.isclose(scene_scatter.z[0], 30.0)

    figs_backbone = build_backbone_evidence_figures(debug, occ_threshold=0.0, max_points=10)
    assert "occ_pr" in figs_backbone
    backbone_scatter = figs_backbone["occ_pr"].data[0]
    assert np.isclose(backbone_scatter.x[0], 10.0)
    assert np.isclose(backbone_scatter.y[0], 20.0)
    assert np.isclose(backbone_scatter.z[0], 30.0)


@pytest.mark.skipif(PerspectiveCameras is None, reason="PyTorch3D not available")
def test_vin_plotting_semidense_projection() -> None:
    if PerspectiveCameras is None:
        return

    points_world = torch.tensor([[[0.0, 0.0, 2.0], [0.5, 0.0, 2.5], [-0.5, 0.0, 3.0]]])
    cams = PerspectiveCameras(
        R=torch.eye(3).unsqueeze(0),
        T=torch.zeros(1, 3),
        focal_length=torch.tensor([[100.0, 100.0]]),
        principal_point=torch.tensor([[50.0, 50.0]]),
        image_size=torch.tensor([[100.0, 100.0]]),
    )
    fig = build_semidense_projection_figure(
        points_world,
        p3d_cameras=cams,
        candidate_index=0,
        show_frustum=False,
    )
    assert fig.data

    fig_with_frustum = build_semidense_projection_figure(
        points_world,
        p3d_cameras=cams,
        candidate_index=0,
        show_frustum=True,
    )
    assert any(getattr(trace, "name", "") == "candidate frustum" for trace in fig_with_frustum.data)

    fig_maps = build_semidense_projection_feature_figure(
        points_world,
        p3d_cameras=cams,
        candidate_index=0,
        grid_size=4,
        max_points=100,
        semidense_obs_count_max=10.0,
        semidense_inv_dist_std_min=0.0,
        semidense_inv_dist_std_p95=0.02,
    )
    assert fig_maps.data
