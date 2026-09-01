"""Tests for pose_generation plotting helpers."""

# ruff: noqa: S101

from __future__ import annotations

import plotly.graph_objects as go  # type: ignore[import-untyped]
import pytest
import torch
from efm3d.aria import CameraTW, PoseTW

from aria_nbv.pose_generation.config import TargetShellCenterConfig, TargetShellSupportMode
from aria_nbv.pose_generation.plotting import (
    plot_candidate_centers_simple,
    plot_candidate_frusta_simple,
    plot_paired_gaze_support,
    plot_position_sphere,
    plot_proposal_sequence_support,
    plot_target_shell_support,
    plot_view_jitter_support,
)
from aria_nbv.pose_generation.types import CandidateSamplingResult
from aria_nbv.pose_generation.utils import rejected_pose_tensor


def _make_candidates(num: int = 2) -> CandidateSamplingResult:
    width = torch.full((num,), 4.0)
    height = torch.full((num,), 4.0)
    fx = torch.full((num,), 2.0)
    fy = torch.full((num,), 2.0)
    cx = torch.full((num,), 1.5)
    cy = torch.full((num,), 1.5)

    t_cam_rig = PoseTW.from_Rt(
        torch.eye(3).repeat(num, 1, 1),
        torch.stack([torch.tensor([0.0, 0.0, 1.0 + i]) for i in range(num)], dim=0),
    )
    cam = CameraTW.from_parameters(
        width=width,
        height=height,
        fx=fx,
        fy=fy,
        cx=cx,
        cy=cy,
        T_camera_rig=t_cam_rig,
        dist_params=torch.zeros(0),
    )

    reference_pose = PoseTW.from_Rt(torch.eye(3), torch.zeros(3))
    poses_world_cam = reference_pose @ t_cam_rig.inverse()
    mask_valid = torch.tensor([True] + [False] * (num - 1))
    return CandidateSamplingResult(
        views=cam,
        reference_pose=reference_pose,
        mask_valid=mask_valid,
        masks={},
        shell_poses=poses_world_cam,
        shell_offsets_ref=None,
        sampling_pose=None,
    )


def test_rejected_pose_tensor() -> None:
    candidates = _make_candidates(num=2)
    rejected = rejected_pose_tensor(candidates)
    assert rejected is not None
    assert rejected.shape[0] == 1


def test_plot_candidate_centers_simple() -> None:
    candidates = _make_candidates(num=2)
    fig = plot_candidate_centers_simple(candidates, title="centers", use_valid=True)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_plot_candidate_frusta_simple() -> None:
    candidates = _make_candidates(num=2)
    fig = plot_candidate_frusta_simple(candidates, scale=0.5, max_frustums=2)
    assert isinstance(fig, go.Figure)


def test_plot_target_shell_support_exposes_boundary_validity_and_gaze() -> None:
    candidates = _make_candidates(num=3)
    candidates.mask_valid = torch.tensor([True, False, True])
    candidates.component_name = ("target_shell",) * 3
    config = TargetShellCenterConfig(
        radius_min_m=0.6,
        radius_max_m=1.2,
        support_mode=TargetShellSupportMode.UPPER_ANGULAR_BOX,
        azimuth_half_width_deg=100.0,
        elevation_min_deg=0.0,
        elevation_max_deg=35.0,
    )

    fig = plot_target_shell_support(
        candidates,
        target_center_world=torch.tensor([-1.0, 0.0, 0.0]),
        config=config,
        seed=17,
    )

    assert isinstance(fig, go.Figure)
    assert {trace.name for trace in fig.data} == {
        "valid candidates",
        "rejected candidates",
        "camera forward axes",
        "configured inner support",
        "configured outer support",
        "target and actor",
    }
    assert "upper_angular_box" in fig.layout.title.text
    assert "attempted=3" in fig.layout.title.text
    assert "valid=2" in fig.layout.title.text
    assert "seed=17" in fig.layout.title.text


def test_plot_view_jitter_support_shows_components_validity_and_bounds() -> None:
    candidates = _make_candidates(num=3)
    candidates.mask_valid = torch.tensor([True, False, True])
    candidates.component_name = ("forward", "forward", "target")
    candidates.extras.update(
        {
            "view_jitter_yaw_deg": torch.tensor([-60.0, 0.0, 60.0]),
            "view_jitter_pitch_deg": torch.tensor([-30.0, 0.0, 30.0]),
            "view_jitter_azimuth_limit_deg": torch.full((3,), 60.0),
            "view_jitter_elevation_limit_deg": torch.full((3,), 30.0),
        }
    )

    fig = plot_view_jitter_support(candidates)

    assert isinstance(fig, go.Figure)
    assert {trace.name for trace in fig.data} == {"forward · valid", "forward · invalid", "target · valid"}
    assert len(fig.layout.shapes) == 3
    assert fig.layout.xaxis.range == pytest.approx((-64.8, 64.8))
    assert fig.layout.yaxis.range == pytest.approx((-33.6, 33.6))


def test_plot_proposal_sequence_support_encodes_order_replica_and_validity() -> None:
    candidates = _make_candidates(num=3)
    candidates.mask_valid = torch.tensor([True, False, True])
    candidates.component_name = ("forward", "target", "target")
    candidates.extras.update(
        {
            "proposal_sequence_index": torch.tensor([4, 5, 6]),
            "proposal_replica": torch.full((3,), 2),
        }
    )

    fig = plot_proposal_sequence_support(candidates)

    assert isinstance(fig, go.Figure)
    assert {trace.name for trace in fig.data} == {"valid", "invalid", "reference pose"}
    assert list(fig.data[0].marker.color) == [4, 6]
    assert fig.data[0].customdata[0].tolist() == [4, 2, "forward"]
    assert fig.data[0].marker.coloraxis == "coloraxis"
    assert fig.data[1].marker.coloraxis == "coloraxis"
    assert fig.layout.coloraxis.cmin == pytest.approx(4.0)
    assert fig.layout.coloraxis.cmax == pytest.approx(6.0)
    assert fig.layout.xaxis.scaleanchor == "y"


def test_plot_paired_gaze_support_shows_shared_centers_and_two_variants() -> None:
    candidates = _make_candidates(num=4)
    candidates.component_name = ("target", "target", "forward", "forward")
    candidates.extras.update(
        {
            "position_pair_id": torch.tensor([0, 1, 0, 1]),
            "gaze_variant_id": torch.tensor([0, 0, 1, 1]),
        }
    )

    fig = plot_paired_gaze_support(candidates)

    assert isinstance(fig, go.Figure)
    assert {trace.name for trace in fig.data} == {
        "gaze variant 0",
        "gaze variant 0 endpoint",
        "gaze variant 1",
        "gaze variant 1 endpoint",
        "shared center",
        "reference pose",
    }
    assert list(fig.data[-2].customdata) == [0, 1]


def test_plot_paired_gaze_support_annotates_all_sentinel_provenance() -> None:
    candidates = _make_candidates(num=2)
    candidates.position_pair_id = torch.full((2,), -1, dtype=torch.int64)
    candidates.gaze_variant_id = torch.full((2,), -1, dtype=torch.int64)

    fig = plot_paired_gaze_support(candidates)

    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0
    assert len(fig.layout.annotations) == 1
    assert "no paired-center" in fig.layout.annotations[0].text


def test_plot_position_sphere_with_dirs() -> None:
    candidates = _make_candidates(num=3)
    offsets, dirs = candidates.get_offsets_and_dirs_ref()
    fig = plot_position_sphere(
        offsets.detach().cpu().numpy(),
        dirs=dirs.detach().cpu().numpy(),
        show_axes=False,
    )
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 2
