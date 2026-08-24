"""Focused presentation tests for stored-rollout geometry diagnostics."""

# ruff: noqa: S101, SLF001

from __future__ import annotations

import inspect
from contextlib import nullcontext
from dataclasses import asdict, replace
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest
import streamlit as st

pytest.importorskip("efm3d")

from aria_nbv.app.panels._stored_rollouts import candidate_generation, validity_support
from aria_nbv.rollouts.inspection import GeometryFrame


def _frame(frame_id: str = "proposal:7:10:target_aligned_z_up", *, step_index: int = 0) -> GeometryFrame:
    identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    return GeometryFrame(
        frame_id=frame_id,
        rollout_row_id=7,
        step_row_id=10 + step_index,
        step_index=step_index,
        origin_kind="expansion_pose",
        expansion_pose_source="root" if step_index == 0 else "previous_selected",
        scale_kind="current_target_distance",
        alignment="target_aligned_z_up",
        scale_m=2.0,
        initial_scale_m=2.0,
        target_x=1.0,
        target_y=0.0,
        target_z=0.0,
        reference_axis_x=identity[0],
        reference_axis_y=identity[1],
        reference_axis_z=identity[2],
        target_axis_x=identity[0],
        target_axis_y=identity[1],
        target_axis_z=identity[2],
        rig_target_yaw_error_deg=15.0 + step_index,
        target_elevation_deg=5.0 + step_index,
    )


def test_pose_axis_frames_hide_by_default_and_bound_advanced_overlay() -> None:
    frames = pd.DataFrame(
        [
            asdict(
                replace(
                    _frame(),
                    frame_id=f"proposal:7:{index}:target_aligned_z_up",
                    step_index=index,
                )
            )
            for index in range(40)
        ]
    )

    assert candidate_generation._pose_axis_frames(frames, mode="Hidden").empty
    selected = candidate_generation._pose_axis_frames(
        frames,
        mode="One frame",
        frame_id="proposal:7:9:target_aligned_z_up",
    )
    assert selected["frame_id"].tolist() == ["proposal:7:9:target_aligned_z_up"]
    assert len(candidate_generation._pose_axis_frames(frames, mode="All frames")) == 32


def test_geometry_anchors_can_withhold_pose_triads_without_hiding_context() -> None:
    frame_rows = pd.DataFrame([asdict(_frame())])
    figure = go.Figure()

    candidate_generation._add_geometry_anchors(
        figure,
        frame_rows,
        three_dimensional=True,
        axis_frames=frame_rows.iloc[0:0],
    )

    assert {trace.name for trace in figure.data if trace.name is not None} == {
        "Reference pose (all at origin)",
        "Observed target center",
    }


def test_normalized_radius_figure_exposes_unit_target_range_threshold() -> None:
    geometry = pd.DataFrame(
        {
            "step_index": [0, 0, 1, 1],
            "position": ["forward_local", "forward_local", "lateral_target_bypass", "lateral_target_bypass"],
            "normalized_radius": [0.2, 0.4, 0.8, 1.2],
        }
    )

    figure = candidate_generation._normalized_radius_figure(geometry)

    assert sorted(float(value) for trace in figure.data for value in trace.y) == [0.2, 0.4, 0.8, 1.2]
    assert any(shape.y0 == 1.0 and shape.y1 == 1.0 for shape in figure.layout.shapes)


def test_bounded_geometry_is_default_visible_in_admission_surface() -> None:
    """The bounded geometry plots are immediately discoverable without a hidden extra disclosure."""

    source = inspect.getsource(validity_support._render_targets_and_support)
    assert '"Bounded candidate geometry and reward plots"' in source
    assert "expanded=True" in source


def test_orientation_diagnostics_keep_frame_and_selected_populations_explicit() -> None:
    frames = pd.DataFrame(
        [
            asdict(_frame()),
            asdict(replace(_frame(), frame_id="proposal:7:11:x", step_index=1)),
        ]
    )
    geometry = pd.DataFrame(
        {
            "rollout_row_id": [7, 7, 7],
            "step_index": [0, 0, 1],
            "position": ["forward_local", "target_bearing_local", "local_refinement"],
            "selected": [False, True, True],
            "target_facing_error_deg": [90.0, 2.0, 4.0],
        }
    )

    rows = candidate_generation._orientation_diagnostic_rows(geometry, frames)

    assert rows.groupby("diagnostic", dropna=False).size().to_dict() == {
        "Rig-to-target yaw error": 2,
        "Selected camera-to-target error": 2,
        "Target elevation": 2,
    }
    selected = rows.loc[rows["diagnostic"] == "Selected camera-to-target error"]
    assert selected["angle_deg"].tolist() == [2.0, 4.0]
    assert np.isfinite(selected["angle_deg"]).all()

    figure = candidate_generation._orientation_diagnostic_figure(rows)
    assert sum(len(trace.y) for trace in figure.data) == len(rows)


def test_geometry_renderer_keeps_proposal_and_trajectory_frames_projection_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proposal anchors never reuse factual trajectory frames."""

    captured_axis_frames: list[pd.DataFrame] = []
    captured_trajectory_frames: list[pd.DataFrame] = []
    monkeypatch.setattr(st, "expander", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(st, "caption", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(candidate_generation, "_render_plot", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        candidate_generation,
        "_add_geometry_anchors",
        lambda _figure, _frames, *, axis_frames, **_kwargs: captured_axis_frames.append(axis_frames.copy()),
    )

    def trajectory_figure(_points: pd.DataFrame, frames: pd.DataFrame) -> go.Figure:
        captured_trajectory_frames.append(frames.copy())
        return go.Figure()

    monkeypatch.setattr(candidate_generation, "_trajectory_figure", trajectory_figure)
    candidates = pd.DataFrame([{"candidate_row_id": 1}])
    proposal_frames = pd.DataFrame([{"frame_id": "proposal-frame"}])
    trajectory_frames = pd.DataFrame([{"frame_id": "trajectory-frame"}])
    proposal = {"points": [{"x": 1.0, "y": 2.0, "z": 3.0}], "frames": proposal_frames.to_dict("records")}
    trajectory = {
        "points": [{"x": 0.0, "y": 0.0, "z": 0.0, "path_order": 0}],
        "frames": trajectory_frames.to_dict("records"),
    }

    candidate_generation._render_candidate_geometry_diagnostics(candidates, proposal, trajectory, total_candidates=1)

    assert [frame["frame_id"].tolist() for frame in captured_axis_frames] == [["proposal-frame"]]
    assert [frame["frame_id"].tolist() for frame in captured_trajectory_frames] == [["trajectory-frame"]]


def test_geometry_explanations_use_distinct_canonical_normalization_equations(monkeypatch: pytest.MonkeyPatch) -> None:
    explanations: list[Any] = []
    monkeypatch.setattr(st, "expander", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(st, "caption", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        candidate_generation, "_render_plot", lambda _figure, explanation: explanations.append(explanation)
    )
    monkeypatch.setattr(candidate_generation, "_add_geometry_anchors", lambda *_args, **_kwargs: None)

    candidate_generation._render_candidate_geometry_diagnostics(
        pd.DataFrame([{"candidate_row_id": 1}]),
        {"points": [{"x": 1.0, "y": 2.0, "z": 3.0}]},
        {"points": [{"x": 0.0, "y": 0.0, "z": 0.0, "path_order": 0, "rollout_row_id": 1}]},
        total_candidates=1,
    )

    theory_by_question = {ex.question: ex.theory for ex in explanations}
    assert theory_by_question[
        "Do candidate families cover the intended local motion support around each proposal expansion pose?"
    ].equation_ids == ("spatial.candidate_proposal_support_normalization",)
    assert theory_by_question[
        "Do candidate families cover the intended local motion support around each proposal expansion pose?"
    ].symbol_ids == ("oracle.candidate_qti", "oracle.center", "entity.center", "spatial.ref_pose")
    assert theory_by_question["How did the factual selected pose move from the rollout root?"].equation_ids == (
        "spatial.rollout_trajectory_normalization",
    )
    assert theory_by_question["How did the factual selected pose move from the rollout root?"].symbol_ids == (
        "oracle.candidate_qti",
        "oracle.center",
        "entity.center",
        "spatial.ref_pose",
    )
