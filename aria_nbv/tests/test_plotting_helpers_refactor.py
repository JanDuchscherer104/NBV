"""Unit tests for plotting helpers moved out of panels."""

# ruff: noqa: S101

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go  # type: ignore[import-untyped]
import torch
from efm3d.aria import CameraTW, PoseTW
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
from matplotlib import pyplot as plt

import aria_nbv.rri_metrics.plotting as rri_plotting
from aria_nbv.data_handling.efm_views import EfmCameraView, EfmSnippetView
from aria_nbv.rendering.candidate_pointclouds import CandidatePointClouds
from aria_nbv.rendering.plotting import plot_candidate_pointcloud_scene
from aria_nbv.rri_metrics.rri import RriResult
from aria_nbv.utils import plotting as utils_plotting
from aria_nbv.utils.data_plotting import pose_world_cam, semidense_points_for_frame
from aria_nbv.vin.diagnostics.plotting import _parameter_distribution


def _make_camera(num_frames: int = 2) -> CameraTW:
    width = torch.full((num_frames,), 4.0)
    height = torch.full((num_frames,), 4.0)
    fx = torch.full((num_frames,), 2.0)
    fy = torch.full((num_frames,), 2.0)
    cx = torch.full((num_frames,), 1.5)
    cy = torch.full((num_frames,), 1.5)
    t_cam = PoseTW.from_Rt(
        torch.eye(3).repeat(num_frames, 1, 1),
        torch.zeros(num_frames, 3),
    )
    return CameraTW.from_parameters(
        width=width,
        height=height,
        fx=fx,
        fy=fy,
        cx=cx,
        cy=cy,
        T_camera_rig=t_cam,
        dist_params=torch.zeros(0),
    )


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
                [float("nan"), float("nan"), float("nan")],
                [2.0, 2.0, 2.0],
            ],
            [
                [3.0, 3.0, 3.0],
                [4.0, 4.0, 4.0],
                [5.0, 5.0, 5.0],
                [6.0, 6.0, 6.0],
            ],
        ],
        dtype=torch.float32,
    )
    efm = {
        ARIA_POSE_T_WORLD_RIG: t_world_rig,
        ARIA_POSE_TIME_NS: torch.tensor([0, 10], dtype=torch.int64),
        "pose/gravity_in_world": torch.tensor([0.0, 0.0, -9.81]),
        ARIA_POINTS_WORLD: points_world,
        ARIA_POINTS_DIST_STD: torch.zeros((2, 4), dtype=torch.float32),
        ARIA_POINTS_INV_DIST_STD: torch.zeros((2, 4), dtype=torch.float32),
        ARIA_POINTS_TIME_NS: torch.tensor([0, 10], dtype=torch.int64),
        ARIA_POINTS_VOL_MIN: torch.tensor([-1.0, -1.0, -1.0]),
        ARIA_POINTS_VOL_MAX: torch.tensor([1.0, 1.0, 1.0]),
        "points/lengths": torch.tensor([2, 1], dtype=torch.int64),
    }
    return EfmSnippetView(
        efm=efm,
        scene_id="scene",
        snippet_id="snippet",
    )


def _make_rri_result(num: int = 3) -> RriResult:
    values = torch.linspace(0.1, 0.3, num)
    return RriResult(
        rri=values,
        pm_dist_before=torch.full((num,), 0.5),
        pm_dist_after=torch.linspace(0.4, 0.6, num),
        pm_acc_before=torch.full((num,), 0.2),
        pm_comp_before=torch.full((num,), 0.3),
        pm_acc_after=torch.linspace(0.1, 0.2, num),
        pm_comp_after=torch.linspace(0.2, 0.4, num),
    )


def _make_candidate_pcs() -> CandidatePointClouds:
    points = torch.tensor(
        [
            [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0], [1.0, 0.0, 0.0]],
            [[0.0, 1.0, 0.0], [0.5, 1.0, 0.0], [float("nan"), float("nan"), float("nan")]],
        ],
        dtype=torch.float32,
    )
    lengths = torch.tensor([3, 2], dtype=torch.int64)
    semidense_points = torch.zeros((1, 3), dtype=torch.float32)
    semidense_length = torch.tensor([1], dtype=torch.int64)
    occupancy_bounds = torch.tensor([-1.0, 1.0, -1.0, 1.0, -1.0, 1.0], dtype=torch.float32)
    return CandidatePointClouds(
        points=points,
        lengths=lengths,
        semidense_points=semidense_points,
        semidense_length=semidense_length,
        occupancy_bounds=occupancy_bounds,
    )


def test_utils_plotting_helpers_smoke() -> None:
    values = np.array([[0.0, 1.0], [2.0, 3.0]], dtype=float)
    rgb = utils_plotting._scalar_to_rgb(values, percentile=99.0, symmetric=False)
    assert rgb.shape == values.shape + (3,)
    assert rgb.dtype == np.uint8

    fig = utils_plotting._plot_slice_grid(
        [values, values + 1.0],
        titles=["a", "b"],
        title="grid",
    )
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2

    hist = utils_plotting._histogram_overlay(
        [("a", values.reshape(-1)), ("b", (values + 1.0).reshape(-1))],
        bins=4,
        title="hist",
        xaxis_title="x",
        log1p_counts=False,
    )
    assert isinstance(hist, go.Figure)
    assert len(hist.data) == 2

    fig_mpl, ax = plt.subplots()
    utils_plotting._plot_hist_counts_mpl(values, bins=4, log_y=True, ax=ax)
    assert ax.get_yscale() == "log"
    plt.close(fig_mpl)


def test_rri_plotting_reexports() -> None:
    vals = np.array([0.0, 1.0, 2.0], dtype=float)
    fig = utils_plotting._histogram_overlay(
        [("a", vals)],
        bins=3,
        title="rri",
        xaxis_title="x",
        log1p_counts=False,
    )
    assert isinstance(fig, go.Figure)

    fig_mpl, ax = plt.subplots()
    utils_plotting._plot_hist_counts_mpl(vals, bins=3, log_y=False, ax=ax)
    assert ax.get_yscale() == "linear"
    plt.close(fig_mpl)


def test_rri_plotting_figures() -> None:
    rri = _make_rri_result()
    labels = ["0", "1", "2"]
    color_map = rri_plotting.rri_color_map(labels)

    fig_rri = rri_plotting.plot_rri_scores(rri, labels, color_map, title="rri")
    assert isinstance(fig_rri, go.Figure)
    assert len(fig_rri.data) == 1

    fig_dist = rri_plotting.plot_pm_distances(rri, labels, color_map, title="dist")
    assert isinstance(fig_dist, go.Figure)
    assert len(fig_dist.data) == 2

    fig_acc = rri_plotting.plot_pm_accuracy(rri, labels, color_map, title="acc")
    assert isinstance(fig_acc, go.Figure)
    assert len(fig_acc.data) == 2

    fig_comp = rri_plotting.plot_pm_completeness(rri, labels, color_map, title="comp")
    assert isinstance(fig_comp, go.Figure)
    assert len(fig_comp.data) == 2

    sample = _make_snippet()
    poses = PoseTW.from_Rt(
        torch.eye(3).repeat(2, 1, 1),
        torch.tensor([[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]]),
    )
    cam = _make_camera(num_frames=2)
    pcs = _make_candidate_pcs()
    fig_scene = plot_candidate_pointcloud_scene(
        sample,
        poses,
        cam,
        pcs,
        candidate_ids=[0, 1],
        selected_ids=[0],
        color_map=color_map,
        title="scene",
        max_sem_pts=10,
        show_frusta=True,
    )
    assert isinstance(fig_scene, go.Figure)
    assert len(fig_scene.data) > 0


def test_vin_parameter_distribution() -> None:
    class Dummy(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.linear = torch.nn.Linear(3, 4, bias=False)
            self.frozen = torch.nn.Parameter(torch.zeros(2), requires_grad=False)

    model = Dummy()
    df = _parameter_distribution(model, trainable_only=True)
    assert "linear" in set(df["module"])
    assert "frozen" not in set(df["module"])


def test_data_plotting_helpers() -> None:
    sample = _make_snippet()
    cam = _make_camera()
    cam_view = EfmCameraView(
        images=torch.zeros(2, 3, 4, 4),
        calib=cam,
        time_ns=torch.tensor([0, 10], dtype=torch.int64),
        frame_ids=torch.tensor([0, 1], dtype=torch.int64),
    )

    pose_wc, cam_tw = pose_world_cam(sample, cam_view, frame_idx=1)
    assert isinstance(cam_tw, CameraTW)
    assert torch.allclose(pose_wc.t, torch.tensor([1.0, 0.0, 0.0]))

    pts_all = semidense_points_for_frame(sample, None, all_frames=True)
    assert pts_all.shape[0] == 3

    pts_frame = semidense_points_for_frame(sample, None, all_frames=False)
    assert pts_frame.shape[0] == 2
