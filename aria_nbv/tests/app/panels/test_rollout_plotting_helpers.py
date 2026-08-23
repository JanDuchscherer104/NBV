"""Regression tests for the shared rollout 3D plotting seam."""

# ruff: noqa: S101

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import pytest

from aria_nbv.utils.data_plotting import add_pose_axes_to_figure, configure_3d_scene


def test_pose_axes_and_scene_are_shared_and_dimensionally_explicit() -> None:
    figure = add_pose_axes_to_figure(
        go.Figure(),
        np.zeros((1, 3)),
        np.eye(3)[None, ...],
        title="Rollout pose axes",
        scale=0.12,
    )
    configure_3d_scene(
        figure,
        axis_titles=("target-forward / d₀", "target-lateral / d₀", "up / d₀"),
    )

    assert len(figure.data) == 3
    assert figure.data[0].name == "Rollout pose axes"
    assert figure.layout.scene.aspectmode == "data"
    assert figure.layout.scene.xaxis.title.text == "target-forward / d₀"


@pytest.mark.parametrize(
    ("centers", "axes"),
    [
        (np.zeros((2, 3)), np.eye(3)),
        (np.zeros((2, 2)), np.eye(3)[None, ...]),
        (np.zeros((1, 3)), np.zeros((2, 3, 3))),
    ],
)
def test_pose_axes_reject_mismatched_shapes(centers: np.ndarray, axes: np.ndarray) -> None:
    with pytest.raises(ValueError):
        add_pose_axes_to_figure(go.Figure(), centers, axes)
