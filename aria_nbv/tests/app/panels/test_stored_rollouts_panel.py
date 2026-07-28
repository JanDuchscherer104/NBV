"""Behavior tests for the modular persisted-rollout inspector."""

# ruff: noqa: S101, SLF001

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest
import zarr
from streamlit.testing.v1 import AppTest

from aria_nbv.app import panels as panel_dispatcher
from aria_nbv.app.panels import _stored_rollouts_page as coordinator
from aria_nbv.app.panels import stored_rollouts as public_panel
from aria_nbv.app.panels._stored_rollouts import (
    candidate_generation,
    inspect_rerun,
    oracle_headroom,
    reconstruction_return,
    shared,
    validity_support,
)
from aria_nbv.app.panels._stored_rollouts import session as stored_session
from aria_nbv.configs import PathConfig
from aria_nbv.rollouts.zarr_store import write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records

_PATH_CONFIG_FIELDS = (
    "root",
    "data_root",
    "data_root_massive",
    "checkpoints",
    "external_checkpoints",
    "wandb",
    "optuna",
    "configs_dir",
    "url_dir",
    "metadata_cache",
    "offline_cache_dir",
    "ase_meshes",
    "processed_meshes",
    "external_dir",
)


@pytest.fixture
def isolated_path_config(tmp_path: Path):
    original = PathConfig()
    original_values = {field: getattr(original, field) for field in _PATH_CONFIG_FIELDS}
    (tmp_path / ".configs").mkdir()
    (tmp_path / ".configs" / "rerun_offline.toml").write_text("", encoding="utf-8")
    cfg = PathConfig(
        root=tmp_path,
        data_root=tmp_path / ".data",
        configs_dir=tmp_path / ".configs",
        offline_cache_dir=Path("offline_cache"),
    )
    try:
        yield cfg
    finally:
        PathConfig(**original_values)


def _stored_rollouts_app(tmp_path: Path) -> AppTest:
    script = tmp_path / "render_stored_rollouts_panel.py"
    script.write_text(
        "from aria_nbv.app.panels.stored_rollouts import render_stored_rollouts_panel\n"
        "render_stored_rollouts_panel()\n",
        encoding="utf-8",
    )
    return AppTest.from_file(str(script), default_timeout=15)


def _metric_values(app: AppTest) -> dict[str, str]:
    return {metric.label: metric.value for metric in app.metric}


def _select_section(app: AppTest, section: str) -> AppTest:
    """Select the page's single-choice segmented control by its public label."""

    control = next(item for item in app.segmented_control if item.label == "Rollout supervision section")
    control.set_value(section)
    return app.run()


def _write_current_store(paths: PathConfig, *, name: str = "current.zarr", horizon: int = 1) -> Path:
    written = write_rollout_zarr_store(
        paths.offline_cache_dir / name,
        build_rollout_records(horizon=horizon, num_samples=8, seed=47)[:2],
    )
    return written.store_dir


def test_public_dispatcher_keeps_the_stable_stored_rollout_entry_point() -> None:
    assert public_panel.render_stored_rollouts_panel is panel_dispatcher.render_stored_rollouts_panel


def test_current_store_renders_overview_and_a_single_segmented_section(isolated_path_config, tmp_path: Path) -> None:
    _write_current_store(isolated_path_config)

    app = _stored_rollouts_app(tmp_path).run()

    assert not app.exception
    assert [header.value for header in app.header] == ["Rollout Supervision"]
    assert [control.options for control in app.segmented_control] == [list(coordinator._SECTIONS)]
    assert "Trust & Topology" in [subheader.value for subheader in app.subheader]
    assert _metric_values(app)["Validation"] == "OK"
    assert _metric_values(app)["Factual Rollout Traces"] == "2"
    assert _metric_values(app)["Candidate Rows"] == "32"
    assert _metric_values(app)["Actor-Valid Target Tasks"] == "2 / 2"
    assert _metric_values(app)["Actor-Valid Tasks with Rollouts"] == "2 / 2"
    assert {button.label for button in app.get("download_button")} >= {
        "Download invariant CSV",
        "Download topology JSON",
    }


def test_reconstruction_section_uses_automatic_metric_plan_without_temporal_selectors(
    isolated_path_config,
    tmp_path: Path,
) -> None:
    _write_current_store(isolated_path_config, horizon=2)

    app = _select_section(_stored_rollouts_app(tmp_path).run(), "Reconstruction & Return")

    assert not app.exception
    assert "Reconstruction & Return" in [subheader.value for subheader in app.subheader]
    labels = {selectbox.label for selectbox in app.selectbox}
    assert "Temporal metric" not in labels
    assert "Temporal grouping class" not in labels
    assert "Temporal grouping field" not in labels
    assert {multiselect.label for multiselect in app.multiselect} >= {"Scenes", "Policies", "Horizons"}
    assert "Download all-metric summary CSV" in {button.label for button in app.get("download_button")}


def test_stale_store_keeps_metadata_and_blocks_scientific_sections(isolated_path_config, tmp_path: Path) -> None:
    stale_path = isolated_path_config.offline_cache_dir / "stale.zarr"
    stale_root = zarr.open_group(stale_path, mode="w")
    stale_root.attrs["schema_version"] = "0.6-rollout-core"
    stale_root.create_group("rollouts").create_array("rollout_row_id", data=np.arange(2, dtype=np.int64))
    stale_root.create_group("steps").create_array("step_row_id", data=np.arange(4, dtype=np.int64))
    stale_root.create_group("candidates").create_array("candidate_row_id", data=np.arange(8, dtype=np.int64))

    app = _select_section(_stored_rollouts_app(tmp_path).run(), "Oracle Headroom & Policies")

    assert not app.exception
    assert _metric_values(app)["Validation"] == "BLOCKED"
    assert any("Scientific evidence and Rerun are disabled" in warning.value for warning in app.warning)
    assert any("Unsupported rollout Zarr schema_version" in error.value for error in app.error)
    assert "Download stale-store diagnostics JSON" in {button.label for button in app.get("download_button")}


def test_missing_depth_disables_only_the_depth_preview(isolated_path_config, tmp_path: Path) -> None:
    store_path = _write_current_store(isolated_path_config, name="missing-depth.zarr")
    zarr.open_group(store_path, mode="a").attrs["selected_depth_enabled"] = False

    app = _select_section(_stored_rollouts_app(tmp_path).run(), "Inspect & Rerun")

    assert not app.exception
    session = stored_session.open_stored_rollout_session(store_path, inventory_row=None)
    assert session.capabilities.selected_depth is False
    assert "Download selected-step candidate CSV" in {button.label for button in app.get("download_button")}
    assert "Launch Rerun" in {button.label for button in app.button}


def test_unopened_candidate_and_qh_sections_are_not_dispatched(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    session = SimpleNamespace(validation=SimpleNamespace(ok=True))
    paths = SimpleNamespace()
    monkeypatch.setattr(coordinator, "render_overview_topology", lambda **_kwargs: calls.append("overview"))
    monkeypatch.setattr(candidate_generation, "render", lambda _session: calls.append("candidate"))
    monkeypatch.setattr(oracle_headroom, "render", lambda _session: calls.append("qh"))

    coordinator._render_selected_section("Overview & Topology", session=session, paths=paths)

    assert calls == ["overview"]


def test_candidate_default_does_not_materialize_candidate_audit(
    isolated_path_config, tmp_path: Path, monkeypatch
) -> None:
    _write_current_store(isolated_path_config, horizon=2)
    stored_session.clear_stored_rollout_caches()

    original = stored_session._cached_candidates
    calls = 0

    def tracked(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(stored_session, "_cached_candidates", tracked)
    app = _select_section(_stored_rollouts_app(tmp_path).run(), "Candidate Generation & Selection")

    assert not app.exception
    assert calls == 0
    assert "Load candidate-wide geometry, calibration, and selection evidence" in {
        button.label for button in app.button
    }


def test_candidate_composition_uses_generator_stages_and_component_legend() -> None:
    figure = candidate_generation._composition_figure(
        pd.DataFrame(
            {
                "dimension": ["policy", "strategy", "position", "mixture"],
                "family": ["oracle_greedy", "forward_rig", "upper_bound_free_shell", "target_point"],
                "sampled_count": [4, 2, 4, 4],
                "actor_valid_rate": [1.0] * 4,
                "sampled_fraction": [1.0, 0.5, 1.0, 1.0],
                "actor_valid_count": [4, 2, 4, 4],
                "selected_share_of_valid_availability": [1.0] * 4,
            }
        )
    )

    assert {value for trace in figure.data for value in trace.x} == {
        "Mixture Component",
        "Candidate Position",
        "View Direction",
    }
    assert {trace.name for trace in figure.data} == {
        "Mixture · Target Point",
        "Position · Upper Bound Free Shell",
        "View · Forward Rig",
    }
    assert not figure.layout.annotations
    assert figure.layout.yaxis.title.text == "Share of Generated Candidates"
    assert list(figure.layout.yaxis.range) == [0.0, 1.0]
    assert figure.layout.legend.title.text == "Persisted Generator Component"
    assert figure.layout.font.size == 18


def test_candidate_selection_plot_separates_selector_from_generator_families() -> None:
    figure = candidate_generation._selection_preference_figure(
        pd.DataFrame(
            {
                "dimension": ["policy", "strategy", "position", "mixture"],
                "family": ["oracle_greedy", "forward_rig", "upper_bound_free_shell", "target_point"],
                "selection_enrichment_vs_valid_availability": [1.0, 1.5, 1.0, 0.75],
                "candidate_count": [8] * 4,
                "actor_valid_count": [6] * 4,
                "selected_count": [2] * 4,
                "valid_availability_share": [1.0, 0.5, 1.0, 1.0],
                "selected_share": [1.0, 0.75, 1.0, 0.75],
            }
        ),
        policy="oracle_greedy",
    )

    assert list(figure.data[0].y) == [
        "Mixture · Target Point",
        "Position · Upper Bound Free Shell",
        "View · Forward Rig",
    ]
    assert list(figure.data[0].x) == [0.75, 1.0, 1.5]
    assert figure.layout.xaxis.title.text == "Selection Enrichment Relative to Valid Availability"
    assert figure.layout.yaxis.title.text == "Generator Component"
    assert "Oracle Greedy" in figure.layout.title.text
    assert len(figure.layout.shapes) == 1


def test_candidate_actor_validity_is_a_two_part_admission_composition() -> None:
    figure = candidate_generation._actor_validity_figure(
        pd.DataFrame(
            {
                "dimension": ["strategy", "position", "mixture"],
                "family": ["forward_rig", "upper_bound_free_shell", "target_point"],
                "sampled_count": [4, 4, 4],
                "actor_valid_count": [3, 2, 4],
                "actor_valid_rate": [0.75, 0.5, 1.0],
            }
        )
    )

    assert [trace.name for trace in figure.data] == ["Actor Valid", "Actor Invalid"]
    assert list(figure.data[0].x) == [1.0, 0.5, 0.75]
    assert list(figure.data[1].x) == [0.0, 0.5, 0.25]
    assert all(sum(values) == pytest.approx(1.0) for values in zip(*(trace.x for trace in figure.data), strict=True))
    assert list(figure.layout.xaxis.range) == [0.0, 1.0]
    assert figure.layout.barmode == "stack"


def test_collision_support_omits_empty_zero_collision_plot() -> None:
    no_collisions = pd.DataFrame(
        {
            "position": ["forward_local", "upper_bound_free_shell"],
            "path_collision": [False, False],
        }
    )
    some_collisions = pd.DataFrame(
        {
            "position": ["forward_local", "forward_local", "upper_bound_free_shell"],
            "path_collision": [False, True, False],
        }
    )

    assert candidate_generation._collision_support_figure(no_collisions) is None
    figure = candidate_generation._collision_support_figure(some_collisions)
    assert figure is not None
    assert set(figure.data[0].y) == {"Forward Local", "Upper Bound Free Shell"}
    assert figure.layout.xaxis.title.text == "Path Collision Rate"
    assert figure.layout.yaxis.title.text == "Candidate Position Family"


def test_target_normalized_motion_figure_anchors_root_and_target() -> None:
    figure = candidate_generation._target_normalized_motion_figure(
        pd.DataFrame(
            {
                "candidate_row_id": [1],
                "step_index": [0],
                "strategy": ["forward_rig"],
                "position": ["upper_bound_free_shell"],
                "selected": [True],
                "actor_action": [True],
                "target_normalized_forward": [0.8],
                "target_normalized_lateral": [0.2],
            }
        )
    )

    traces = {trace.name: trace for trace in figure.data if trace.name}
    assert list(traces["Root"].x) == [0.0]
    assert list(traces["Target"].x) == [1.0]
    assert list(traces["Upper Bound Free Shell · Forward Rig · Selected"].x) == [0.8]
    assert list(figure.data[3].x) == [0.0, 0.8, None]
    assert list(figure.data[3].y) == [0.0, 0.2, None]
    assert figure.layout.xaxis.title.text == "Forward Relative To Root-Target Distance"
    assert figure.layout.yaxis.scaleanchor == "x"


def test_stored_rollout_plot_style_unifies_titles_axes_legends_and_facets(monkeypatch: pytest.MonkeyPatch) -> None:
    figure = go.Figure(go.Scatter(x=[0, 1], y=[1, 2], name="oracle_greedy"))
    figure.update_layout(title="valid_candidate_fanout", legend_title_text="policy_horizon")
    figure.update_xaxes(title_text="step_index")
    figure.update_yaxes(title_text="invalid_candidate_fraction")
    figure.add_annotation(text="metric_label=invalid_candidate_fraction")
    rendered: list[go.Figure] = []
    monkeypatch.setattr(shared.st, "plotly_chart", lambda fig, **_kwargs: rendered.append(fig))

    shared._render_plot(figure)

    assert rendered == [figure]
    assert figure.layout.title.text == "Valid Candidate Fanout"
    assert figure.layout.xaxis.title.text == "Rollout Step"
    assert figure.layout.yaxis.title.text == "Invalid Candidate Fraction"
    assert figure.layout.annotations[0].text == "Invalid Candidate Fraction"
    assert figure.data[0].name == "Oracle Greedy"


def test_temporal_validity_uses_metric_specific_color_and_axis_label() -> None:
    figure = validity_support._temporal_validity_figure(
        pd.DataFrame(
            {
                "policy": ["oracle_greedy"],
                "horizon": [2],
                "step_index": [0],
                "median": [4.0],
                "finite_count": [1],
                "total_count": [1],
                "q25": [4.0],
                "q75": [4.0],
            }
        ),
        y_label="Valid Candidates",
        colors=("#14b8a6",),
    )

    assert figure.layout.xaxis.title.text == "Rollout Step"
    assert figure.layout.yaxis.title.text == "Valid Candidates"
    assert figure.data[0].line.color == "#14b8a6"
    assert figure.data[0].name == "Oracle Greedy · Horizon 2"


def test_invariant_groups_present_contract_categories_instead_of_a_wide_table() -> None:
    evidence = pd.DataFrame(
        {
            "invariant_id": ["q_h_factual_consistency", "selected_actor_mask", "q_train_supervision"],
            "category": ["derived_q_h", "mask", "mask"],
            "status": ["PASS", "PASS", "PASS"],
        }
    )

    groups = validity_support._invariant_groups(evidence)

    assert [category for category, _rows in groups] == ["Derived QH", "Mask"]
    assert [rows["invariant_id"].tolist() for _category, rows in groups] == [
        ["q_h_factual_consistency"],
        ["q_train_supervision", "selected_actor_mask"],
    ]


def test_target_protocol_audit_uses_compositional_coverage_and_match_summary() -> None:
    targets = pd.DataFrame(
        {
            "target_valid": [True, True, False],
            "gt_label_valid": [True, False, True],
            "gt_match_status": ["matched", "unmatched", "matched"],
        }
    )

    summary = validity_support._target_protocol_summary(targets)
    figure = validity_support._target_protocol_matrix_figure(targets)

    assert summary == {
        "target_count": 3,
        "actor_valid_count": 2,
        "gt_label_valid_count": 2,
        "matched_count": 2,
    }
    assert figure.layout.title.text == "Actor Validity × GT-Label Availability"
    assert figure.data[0].z.tolist() == [[1, 1], [1, 0]]


def test_candidate_mask_composition_replaces_raw_booleans_with_named_contract_states() -> None:
    composition = validity_support._candidate_mask_composition(
        pd.DataFrame(
            {
                "actor_action": [False, True, True],
                "oracle_label": [False, True, True],
                "q_train": [False, True, True],
                "selected": [False, False, True],
                "count": [16, 12, 4],
            }
        )
    )
    figure = validity_support._candidate_mask_composition_figure(composition)

    assert composition.to_dict("records") == [
        {"admission_state": "Actor Ineligible", "selection_state": "Not Selected", "count": 16},
        {"admission_state": "QH Admitted", "selection_state": "Not Selected", "count": 12},
        {"admission_state": "QH Admitted", "selection_state": "Selected", "count": 4},
    ]
    assert set(figure.data[0].x) | set(figure.data[1].x) == {"Actor Ineligible", "QH Admitted"}
    assert all("True" not in str(value) and "False" not in str(value) for trace in figure.data for value in trace.x)


def test_clear_stored_rollout_caches_clears_every_session_owned_cache_once(monkeypatch) -> None:
    discovered = {
        value
        for name, value in vars(stored_session).items()
        if (name == "rollout_store_inventory" or name.startswith("_cached_"))
        and callable(getattr(value, "clear", None))
    }
    registered = set(stored_session._SESSION_CACHE_OWNERS)
    assert registered == discovered

    spies: list[Mock] = []
    for cached in stored_session._SESSION_CACHE_OWNERS:
        spy = Mock()
        monkeypatch.setattr(cached, "clear", spy)
        spies.append(spy)

    stored_session.clear_stored_rollout_caches()

    assert all(spy.call_count == 1 for spy in spies)


def test_candidate_heavy_button_materializes_audit_only_after_explicit_request(
    isolated_path_config,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_current_store(isolated_path_config, horizon=2)
    stored_session.clear_stored_rollout_caches()
    original = stored_session._cached_candidates
    calls = 0

    def tracked(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(stored_session, "_cached_candidates", tracked)
    app = _select_section(_stored_rollouts_app(tmp_path).run(), "Candidate Generation & Selection")
    next(
        button
        for button in app.button
        if button.label == "Load candidate-wide geometry, calibration, and selection evidence"
    ).click()
    app = app.run()

    assert not app.exception
    assert calls == 1
    assert "Download normalized candidate evidence CSV" in {button.label for button in app.get("download_button")}


def test_oracle_headroom_section_exposes_exact_blockers_instead_of_unmatched_estimate(
    isolated_path_config,
    tmp_path: Path,
) -> None:
    _write_current_store(isolated_path_config)

    app = _select_section(_stored_rollouts_app(tmp_path).run(), "Oracle Headroom & Policies")

    assert not app.exception
    assert "Oracle Headroom & Policies" in [subheader.value for subheader in app.subheader]
    assert any("Δlook is blocked" in warning.value for warning in app.warning)
    assert any("ηQ is blocked" in info.value for info in app.info)


def test_reconstruction_metric_plan_includes_every_finite_available_quantity() -> None:
    summary = pd.DataFrame(
        [
            {"metric": "cumulative_target_root_gain", "label": "Cumulative root gain", "finite_count": 2},
            {"metric": "selected_entropy", "label": "Selection entropy", "finite_count": 1},
            {"metric": "missing", "label": "Missing", "finite_count": 0},
        ]
    )

    assert reconstruction_return._metric_plan(summary) == {
        "cumulative_target_root_gain": "Cumulative root gain",
        "selected_entropy": "Selection entropy",
    }


def test_failure_lineage_handoff_selects_inspect_section(monkeypatch: pytest.MonkeyPatch) -> None:
    state: dict[str, object] = {}
    monkeypatch.setattr(validity_support.st, "session_state", state)

    validity_support._carry_failure_to_inspect({"rollout_row_id": 7, "step_row_id": 12})

    assert state == {
        "stored_rollout_id": 7,
        "stored_step_id": 12,
        "stored_rollouts_section": "Inspect & Rerun",
    }


def test_direct_inspection_consumes_lineage_handoff_before_selectors(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {"stored_rollout_id": 7, "stored_step_id": 12}
    monkeypatch.setattr(inspect_rerun.st, "session_state", state)

    inspect_rerun._apply_lineage_handoff([5, 7], {5: [9], 7: [11, 12]})

    assert state == {
        "stored_rollout_inspect_rollout": 7,
        "stored_rollout_inspect_step": 12,
    }


def test_validity_text_keeps_invalidity_as_a_mask_reason_contract() -> None:
    assert "never a low reconstruction score" in validity_support._VALIDITY_INFO
    assert "Invalid-reason codes explain rejection" in validity_support._VALIDITY_INFO


def test_validity_section_does_not_own_candidate_generation_or_selection_evidence() -> None:
    assert not hasattr(validity_support, "_render_candidate_provenance_flow")
    assert not hasattr(validity_support, "_render_candidate_aggregate_breakdowns")
    assert not hasattr(validity_support, "_render_candidate_geometry_diagnostics")
    assert not hasattr(validity_support, "_render_selected_action_policy_flow")


def test_download_serializers_keep_complete_rows_and_stable_json() -> None:
    frame = pd.DataFrame({"rollout_row_id": [2, 3], "note": ["a,b", "line\\nbreak"]})

    assert shared._serialize_frame_csv(frame) == frame.to_csv(index=False).encode("utf-8")
    assert shared._serialize_json({"z": np.int64(2), "a": ["first"]}) == (
        b'{\n  "a": [\n    "first"\n  ],\n  "z": 2\n}\n'
    )
