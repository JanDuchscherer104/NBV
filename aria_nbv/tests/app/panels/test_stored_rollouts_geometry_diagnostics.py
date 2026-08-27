"""Focused presentation tests for stored-rollout geometry diagnostics."""

# ruff: noqa: S101, SLF001

from __future__ import annotations

import inspect
from contextlib import nullcontext
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest
import streamlit as st

pytest.importorskip("efm3d")

from aria_nbv.app.panels._stored_rollouts import candidate_generation, s2_directions, validity_support
from aria_nbv.reporting import ReportColumn, ReportSnapshot, ReportTable, SourceIdentity
from aria_nbv.rollouts.inspection import GeometryFrame
from aria_nbv.rollouts.s2_analysis import S2AnalysisConfig
from aria_nbv.rollouts.s2_plotting import s2_direction_figure


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


def test_target_s2_figures_render_complete_heatmaps_and_projection_overlays() -> None:
    """Both S² channels retain a 3D heatmap with target-frame unit-vector points."""

    payload = {
        "movement_counts": np.asarray([[0, 2], [1, 0]], dtype=np.int64),
        "view_direction_counts": np.asarray([[3, 0], [0, 1]], dtype=np.int64),
        "frustum_counts": np.asarray([[1, 1], [0, 0]], dtype=np.int64),
        "movement_projection": np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32),
        "movement_projection_normalized_lengths": np.asarray([0.75], dtype=np.float32),
        "movement_projection_rollout_row_ids": np.asarray([7], dtype=np.int64),
        "movement_projection_step_indices": np.asarray([0], dtype=np.int64),
        "view_direction_projection": np.asarray([[0.0, 1.0, 0.0]], dtype=np.float32),
        "view_direction_projection_rollout_row_ids": np.asarray([7], dtype=np.int64),
        "view_direction_projection_step_indices": np.asarray([1], dtype=np.int64),
        "frustum_projection": np.asarray([[0.0, 0.0, 1.0]], dtype=np.float32),
        "frustum_projection_rollout_row_ids": np.asarray([7], dtype=np.int64),
        "frustum_projection_step_indices": np.asarray([1], dtype=np.int64),
    }

    movement = s2_direction_figure(payload, channel="movement")
    view = s2_direction_figure(payload, channel="view_direction")
    frustum = s2_direction_figure(payload, channel="frustum")

    for figure, expected_count, expected_name in (
        (movement, 3, "acquisition 1 (t=0)"),
        (view, 4, "acquisition 2 (t=1)"),
        (frustum, 2, "acquisition 2 (t=1)"),
    ):
        assert isinstance(figure.data[0], go.Surface)
        assert int(np.asarray(figure.data[0].surfacecolor).sum()) == expected_count
        assert isinstance(figure.data[1], go.Scatter3d)
        assert figure.data[1].name == expected_name
        assert figure.layout.scene.xaxis.title.text == "target xᵉ"
        assert figure.layout.scene.yaxis.title.text == "target yᵉ"
        assert figure.layout.scene.zaxis.title.text == "target zᵉ"
        assert np.asarray(figure.data[1].marker.color).tolist() == [7]


def test_target_s2_panel_dispatches_one_shared_report_transaction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The panel binds a store but delegates acquisition, analysis, and plotting."""

    snapshot = _s2_snapshot()
    bound_paths: list[tuple[Path, ...]] = []
    requests: list[tuple[str, ...]] = []
    rendered: list[ReportSnapshot] = []

    class Builder:
        def build(self, request: Any) -> ReportSnapshot:
            requests.append(request.section_ids)
            return snapshot

    class Recipe:
        def rollout_s2_section(self, section_id: str) -> Any:
            assert section_id == "s2"
            return SimpleNamespace(analysis=S2AnalysisConfig())

        def bind_rollout_stores(self, store_paths: tuple[Path, ...]) -> "Recipe":
            bound_paths.append(store_paths)
            return self

        def setup_target(self) -> Builder:
            return Builder()

        def to_toml(self) -> str:
            return "schema_version = 'aria-nbv-report-config-v1'\n"

    monkeypatch.setattr(st, "markdown", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(st, "caption", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(st, "button", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(st, "status", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(st, "session_state", {})
    monkeypatch.setattr(st, "info", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(st, "warning", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(s2_directions, "render_report_snapshot", lambda value, **_kwargs: rendered.append(value))

    store_path = tmp_path / "store.zarr"
    s2_directions.render_s2_report_preview(
        store_path=store_path,
        store_identity="store-content",
        recipe=Recipe(),  # type: ignore[arg-type]
        section_id="s2",
        recipe_label="test-recipe.toml",
        key_prefix="test",
    )

    assert bound_paths == [(store_path,)]
    assert requests == [("s2",)]
    assert rendered == [snapshot]


def test_target_s2_support_summary_keeps_empty_support_and_exclusions_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty snapshot retains both support and addressed exclusion evidence."""

    warnings: list[str] = []
    monkeypatch.setattr(st, "warning", lambda message, **_kwargs: warnings.append(message))
    monkeypatch.setattr(st, "caption", lambda *_args, **_kwargs: None)

    snapshot = _s2_snapshot(movement_count=0, view_direction_count=0, issue_count=1)
    s2_directions._render_support_summary(snapshot, section_id="s2")

    assert warnings == [
        "No finite factual selected-action directions survived the rollout-owned reducer.",
        "The reducer retained 1 addressed exclusions; inspect `s2.table.issues` below.",
    ]
    assert snapshot.result("s2.table.issues").rows == (("s01", "missing_target"),)


def test_target_s2_streamlit_adapter_has_no_domain_computation_or_plot_builder() -> None:
    """Keep the app adapter presentation-only as the owner boundary evolves."""

    source = Path(s2_directions.__file__).read_text(encoding="utf-8")
    assert "numpy" not in source
    assert "pandas" not in source
    assert "import plotly" not in source.lower()
    assert "from plotly" not in source.lower()
    assert "RolloutZarrStoreReader" not in source
    assert "s2_target_direction_histogram" not in source
    assert "def s2_direction_figure" not in source


def _s2_snapshot(
    *,
    movement_count: int = 1,
    view_direction_count: int = 1,
    issue_count: int = 0,
) -> ReportSnapshot:
    columns = tuple(
        ReportColumn(name, None)
        for name in (
            "source_sample_count",
            "source_snippet_count",
            "source_scene_count",
            "target_count",
            "rollout_count",
            "store_rollout_count",
            "selected_step_count",
            "movement_count",
            "view_direction_count",
            "issue_count",
        )
    )
    support = ReportTable(
        id="s2.table.support",
        columns=columns,
        rows=((1, 1, 1, 1, 1, 1, 1, movement_count, view_direction_count, issue_count),),
        source_ids=("rollout",),
    )
    issues = ReportTable(
        id="s2.table.issues",
        columns=(ReportColumn("store_slot", None), ReportColumn("code", None)),
        rows=(("s01", "missing_target"),) if issue_count else (),
        source_ids=("rollout",),
    )
    return ReportSnapshot.create(
        evidence_status="pilot",
        config_sha256="a" * 64,
        notation_sha256="b" * 64,
        source_identities=(SourceIdentity("rollout", "rollout", "c" * 64, ()),),
        quantities=(),
        tables=(support, issues),
        figures=(),
        resolved_recipe=b"schema_version = 'aria-nbv-report-config-v1'\n",
    )


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
