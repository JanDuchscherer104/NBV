"""Tests for semidense point handling in plotting utilities."""

import numpy as np
import torch

from aria_nbv.data_handling.raw.views import EfmPointsView


def test_semidense_points_respects_lengths_and_filters_nan() -> None:
    points_world = torch.tensor(
        [
            [
                [0.0, 0.0, 0.0],
                [1.0, 1.0, 1.0],
                [5.0, 5.0, 5.0],
                [float("nan"), float("nan"), float("nan")],
            ],
            [
                [2.0, 2.0, 2.0],
                [7.0, 7.0, 7.0],
                [8.0, 8.0, 8.0],
                [9.0, 9.0, 9.0],
            ],
        ],
        dtype=torch.float32,
    )
    sem = EfmPointsView(
        points_world=points_world,
        dist_std=torch.zeros((2, 4), dtype=torch.float32),
        inv_dist_std=torch.zeros((2, 4), dtype=torch.float32),
        time_ns=torch.zeros(2, dtype=torch.int64),
        volume_min=torch.zeros(3, dtype=torch.float32),
        volume_max=torch.ones(3, dtype=torch.float32),
        lengths=torch.tensor([2, 1], dtype=torch.int64),
    )

    pts_np = sem.collapse_points(max_points=None).cpu().numpy()
    pts_set = {tuple(row) for row in np.round(pts_np, decimals=6)}

    assert pts_set == {(0.0, 0.0, 0.0), (1.0, 1.0, 1.0), (2.0, 2.0, 2.0)}


def test_semidense_points_caps_max_points() -> None:
    torch.manual_seed(0)
    frame0 = torch.stack([torch.tensor([float(i), 0.0, 0.0]) for i in range(6)], dim=0)
    frame1 = frame0 + 100.0  # ensure unique points after collapse
    points_world = torch.stack([frame0, frame1], dim=0)
    sem = EfmPointsView(
        points_world=points_world,
        dist_std=torch.zeros((2, 6), dtype=torch.float32),
        inv_dist_std=torch.zeros((2, 6), dtype=torch.float32),
        time_ns=torch.zeros(2, dtype=torch.int64),
        volume_min=torch.zeros(3, dtype=torch.float32),
        volume_max=torch.ones(3, dtype=torch.float32),
        lengths=torch.tensor([6, 6], dtype=torch.int64),
    )

    pts_np = sem.collapse_points(max_points=5).cpu().numpy()
    pts_set = {tuple(row) for row in np.round(pts_np, decimals=6)}
    expected_pool = {
        tuple(row)
        for row in np.round(torch.vstack([frame0, frame1]).cpu().numpy(), decimals=6)  # type: ignore[arg-type]
    }

    assert pts_np.shape == (5, 3)
    assert pts_set.issubset(expected_pool)
