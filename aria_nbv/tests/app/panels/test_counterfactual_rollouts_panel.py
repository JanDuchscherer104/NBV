"""Tests for the live counterfactual rollout panel helpers."""

# ruff: noqa: S101, SLF001

from __future__ import annotations

import json
from contextlib import nullcontext
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import torch
import zarr
from efm3d.aria import CameraTW
from efm3d.aria.pose import PoseTW
from streamlit.testing.v1 import AppTest

from aria_nbv.app import panels as panel_dispatcher
from aria_nbv.app import scene_view
from aria_nbv.app.panels import common as panel_common
from aria_nbv.app.panels import counterfactual_rollouts as rollout_panel
from aria_nbv.app.panels import data as data_panel
from aria_nbv.app.panels import stored_rollouts as stored_rollouts_panel
from aria_nbv.app.panels._stored_rollouts import (
    candidate_generation,
    inspect_rerun,
    overview_topology,
    reconstruction_return,
    session,
    shared,
)
from aria_nbv.configs import PathConfig
from aria_nbv.oracle.labels import OracleCandidateEvaluation, OracleCandidateLabels, RetainedOracleEvidence
from aria_nbv.oracle.pipelines.evaluated_rollout import EvaluatedRollout, EvaluatedRolloutStep
from aria_nbv.oracle.target_rri import TargetRriScorerConfig
from aria_nbv.oracle.target_selection import OracleTargetTask, TargetTaskIdentityStatus
from aria_nbv.pose_generation import (
    CandidateMixtureViewGeneratorConfig,
    CandidateViewGeneratorConfig,
    ViewDirectionMode,
)
from aria_nbv.pose_generation.types import CandidateSamplingResult
from aria_nbv.rollouts import (
    CounterfactualRolloutResult,
    CounterfactualTrajectory,
    RolloutZarrStoreReader,
)
from aria_nbv.rollouts.inspection import candidate_audit_rows
from aria_nbv.rollouts.replay.policy import CounterfactualSelectionPolicy
from aria_nbv.rollouts.replay.state import CounterfactualStepResult
from aria_nbv.rollouts.zarr_store import write_rollout_zarr_store
from aria_nbv.targets import TargetDescriptor
from tests.rollout_fixtures import build_rollout_records


def test_inspector_refresh_clears_candidate_population_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refresh clears every native inspector cache, including population evidence."""

    cleared: list[str] = []
    for name in (
        "_cached_inventory",
        "_cached_candidate_population_cached",
        "_cached_projection_cached",
        "_cached_topology_cached",
        "_cached_failures_cached",
        "_cached_evidence_bundle_cached",
        "_cached_store_bundle_cached",
        "_cached_corpus_summary",
    ):
        monkeypatch.setattr(session, name, SimpleNamespace(clear=lambda name=name: cleared.append(name)))

    session._clear_stored_rollout_caches()

    assert set(cleared) == {
        "_cached_inventory",
        "_cached_candidate_population_cached",
        "_cached_projection_cached",
        "_cached_topology_cached",
        "_cached_failures_cached",
        "_cached_evidence_bundle_cached",
        "_cached_store_bundle_cached",
        "_cached_corpus_summary",
    }


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


def _evaluated_single_step(result, transition, *, metrics=None, evidence=None) -> EvaluatedRollout:
    labels = OracleCandidateLabels(
        scores=torch.as_tensor([transition.selection_score], dtype=torch.float32),
        score_label=transition.selection_score_label,
        metrics={} if metrics is None else metrics,
        candidate_shell_indices=torch.as_tensor([transition.selected_shell_index], dtype=torch.long),
        provenance="test",
    )
    return EvaluatedRollout(
        result=result,
        steps={
            (0, transition.step_index): EvaluatedRolloutStep(
                transition=transition,
                evaluation=OracleCandidateEvaluation(
                    labels=labels,
                    evidence=RetainedOracleEvidence() if evidence is None else evidence,
                ),
            )
        },
    )


@pytest.fixture
def isolated_path_config(tmp_path):
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


def test_manual_non_zarr_path_is_passed_to_existing_readonly_selector(monkeypatch, tmp_path: Path) -> None:
    """Campaign handoff remains an explicit path override, not discovery."""
    selected = (tmp_path / "campaign-shard").resolve()
    overview_topology.st.session_state["rollout_store_manual_path"] = str(selected)

    class _Column:
        def selectbox(self, *args, **kwargs):
            raise AssertionError("empty inventory must not discover stores")

        def info(self, *args, **kwargs):
            return None

        def metric(self, *args, **kwargs):
            return None

        def button(self, *args, **kwargs):
            return False

    class _Expander:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(overview_topology.st, "columns", lambda *_args, **_kwargs: (_Column(), _Column()))
    monkeypatch.setattr(overview_topology.st, "expander", lambda *_args, **_kwargs: _Expander())
    monkeypatch.setattr(
        overview_topology.st,
        "text_input",
        lambda _label, value="", **kwargs: overview_topology.st.session_state[kwargs["key"]],
    )
    result = overview_topology._render_store_selector(PathConfig(), [])
    assert result == ((selected,), selected)


def _set_stored_rollout_workspace(app: AppTest, workspace: str) -> AppTest:
    app.session_state["stored_rollouts_section"] = workspace
    return app.run()


def _dummy_camera() -> CameraTW:
    return CameraTW.from_surreal(
        width=torch.tensor([64.0]),
        height=torch.tensor([64.0]),
        type_str="Pinhole",
        params=torch.tensor([[60.0, 60.0, 32.0, 32.0]]),
        gain=torch.zeros(1),
        exposure_s=torch.zeros(1),
        valid_radius=torch.tensor([64.0]),
        T_camera_rig=PoseTW.from_matrix3x4(torch.eye(3, 4).unsqueeze(0)),
    )


def _candidate_result_for_pose(pose: PoseTW) -> CandidateSamplingResult:
    return CandidateSamplingResult(
        views=_dummy_camera(),
        reference_pose=pose,
        mask_valid=torch.tensor([True]),
        masks={},
        shell_poses=pose,
    )


def _target_row(*, gt_label_valid: bool = True) -> OracleTargetTask:
    return OracleTargetTask(
        source_index=9,
        target_row_id=4,
        target_id="scene_a:snippet_1:gt_obbs_oracle:9",
        descriptor=TargetDescriptor(
            sem_id=3,
            class_name="chair",
            pose_world_object=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 2.0, 3.0),
            extents_m=(0.5, 0.6, 0.7),
            relative_pose_reference_object=tuple(float(v) for v in range(12)),
        ),
        inst_id=62,
        confidence=0.9,
        selected_rank=0,
        selection_probability=1.0,
        identity_status=(
            TargetTaskIdentityStatus.MATCHED.value if gt_label_valid else TargetTaskIdentityStatus.UNMATCHED.value
        ),
    )


class _FakeRolloutReader:
    def __init__(self, arrays: dict[str, np.ndarray]) -> None:
        self.arrays = arrays

    def array(self, path: str) -> np.ndarray:
        return self.arrays[path]


def _json_dictionary_array(values: list[str]) -> np.ndarray:
    return np.frombuffer(json.dumps(values).encode("utf-8"), dtype=np.uint8)


def test_live_dataset_config_loads_vin_offline_sample_assets(tmp_path) -> None:
    cfg = rollout_panel._build_live_dataset_config(store_dir=tmp_path, split="all")

    assert cfg.return_format == "sample"
    assert cfg.include_efm_snippet is True
    assert cfg.include_gt_mesh is True
    assert cfg.load_backbone is True
    assert cfg.load_detected_obbs is True
    assert cfg.load_gt_obbs is True
    assert cfg.load_candidates is False
    assert cfg.load_depths is False
    assert cfg.load_candidate_pcs is False


def test_default_target_mixture_uses_requested_budget_16() -> None:
    counts = rollout_panel._target_mixture_counts_from_budget(16)

    assert counts == {
        "target_bearing_local": 5,
        "forward_local": 5,
        "lateral_target_bypass": 3,
        "local_refinement": 2,
        "revisit_backtrack": 1,
    }


def test_live_rollout_device_options_default_cuda_when_torch_cuda_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rollout_panel.torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(rollout_panel, "_pytorch3d_cuda_rasterization_available", lambda: False)

    assert rollout_panel._live_rollout_device_options() == ["cuda", "cpu"]


def test_live_rollout_device_options_stay_cpu_only_without_torch_cuda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rollout_panel.torch.cuda, "is_available", lambda: False)

    assert rollout_panel._live_rollout_device_options() == ["cpu"]


def test_cuda_preflight_fails_with_actionable_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rollout_panel.torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(rollout_panel, "_pytorch3d_cuda_rasterization_available", lambda: False)

    with pytest.raises(RuntimeError, match="PyTorch3D rasterizer"):
        rollout_panel._validate_live_rollout_device("cuda")


def test_live_depth_config_uses_explicit_cpu_device() -> None:
    cfg = rollout_panel._live_depth_config(max_candidates=16, device="cpu")

    assert str(cfg.device) == "cpu"
    assert str(cfg.renderer.device) == "cpu"
    assert cfg.max_candidates_final == 16


def test_rollout_scene_defaults_are_minimal_evidence_view() -> None:
    defaults = rollout_panel.ROLLOUT_SCENE_DEFAULTS

    assert defaults.show_mesh is True
    assert defaults.mesh_opacity <= 0.2
    assert defaults.semidense_mode == "off"
    assert defaults.show_trajectory is False
    assert defaults.show_frustum is False
    assert defaults.show_scene_bounds is False
    assert defaults.show_crop_bounds is False
    assert defaults.show_gt_obbs is False


def test_data_and_rollout_pages_share_scene_control_helper() -> None:
    assert data_panel.scene_plot_options_ui is scene_view.scene_plot_options_ui
    assert rollout_panel.scene_plot_options_ui is scene_view.scene_plot_options_ui


def test_loaded_sample_info_documents_target_table_columns() -> None:
    table_columns = set(rollout_panel._target_rows_table((_target_row(),))[0])

    for column in table_columns:
        assert f"`{column}`" in rollout_panel._LOADED_SAMPLE_INFO


def test_target_rows_table_exposes_compact_task_audit() -> None:
    row = rollout_panel._target_rows_table((_target_row(),))[0]

    assert row["target_row_id"] == 4
    assert row["selected_rank"] == 0
    assert row["class"] == "chair"
    assert row["sem_id"] == 3
    assert row["inst_id"] == 62
    assert row["confidence"] == pytest.approx(0.9)
    assert row["selection_probability"] == pytest.approx(1.0)
    assert row["admitted"] is True
    assert row["identity_status"] == TargetTaskIdentityStatus.MATCHED.value


def test_active_target_info_documents_descriptor_and_oracle_boundary() -> None:
    info = rollout_panel._ACTIVE_TARGET_INFO

    assert "sanitized target descriptor" in info
    assert "Oracle evaluation" in info
    assert "target 0" in info
    assert "EFM semantic-id map" in info
    assert "window" in info
    assert "sem=..." in info


def test_live_selected_depth_rows_summarize_retained_depth() -> None:
    step = SimpleNamespace(
        step_index=0,
        selection_score=0.75,
        selection_score_label="target_rri",
        selection_policy="oracle_greedy",
        selected_shell_index=0,
    )
    result = SimpleNamespace(trajectories=[SimpleNamespace(steps=[step])])
    evaluated = _evaluated_single_step(
        result,
        step,
        evidence=RetainedOracleEvidence(
            selected_depth_m=torch.tensor([[1.0, 2.0], [3.0, float("nan")]], dtype=torch.float32),
            selected_depth_valid_mask=torch.tensor([[True, True], [False, True]], dtype=torch.bool),
        ),
    )

    rows = rollout_panel._live_selected_depth_rows(evaluated)

    assert len(rows) == 1
    row = rows[0]
    assert row["available"] is True
    assert row["valid_fraction"] == pytest.approx(0.75)
    assert row["finite_fraction"] == pytest.approx(0.5)
    assert row["depth_min_m"] == pytest.approx(1.0)
    assert row["depth_mean_m"] == pytest.approx(1.5)
    assert row["depth_max_m"] == pytest.approx(2.0)


def test_live_selected_depth_rows_report_unretained_depth() -> None:
    step = SimpleNamespace(
        step_index=0,
        selection_score=0.75,
        selection_score_label="target_rri",
        selection_policy="oracle_greedy",
        selected_shell_index=0,
    )
    result = SimpleNamespace(trajectories=[SimpleNamespace(steps=[step])])

    rows = rollout_panel._live_selected_depth_rows(_evaluated_single_step(result, step))

    assert rows[0]["available"] is False
    assert "not retained" in str(rows[0]["warning"])


def test_live_depth_target_overlays_project_descriptor_target() -> None:
    step = SimpleNamespace(
        transition=SimpleNamespace(selected_pose_world=PoseTW.from_matrix3x4(torch.eye(3, 4).unsqueeze(0))),
        evaluation=SimpleNamespace(
            evidence=SimpleNamespace(
                selected_depth_focal_px=(100.0, 100.0),
                selected_depth_principal_point_px=(50.0, 50.0),
            )
        ),
    )

    overlays = rollout_panel._live_depth_target_overlays(
        step,
        sample=SimpleNamespace(),
        target=_target_row(gt_label_valid=False),
        show_actor_target=True,
        show_gt_target=False,
    )

    assert len(overlays) == 1
    assert overlays[0].name == "Descriptor target OBB"
    assert overlays[0].corners_px.shape == (8, 2)


def test_stored_rollouts_page_exercises_current_schema_features(isolated_path_config, tmp_path) -> None:
    write_rollout_zarr_store(
        isolated_path_config.offline_cache_dir / "current.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=47)[:1],
    )

    app = _stored_rollouts_app(tmp_path).run()

    assert not app.exception
    assert [header.value for header in app.header] == ["Rollout Supervision"]
    assert all("\\n+" not in markdown.value for markdown in app.markdown)
    assert "Active-store validation" in [subheader.value for subheader in app.subheader]
    assert _metric_values(app)["Validation"] == "OK"
    assert _metric_values(app)["Rollouts"] == "1"
    assert _metric_values(app)["Steps"] == "1"
    assert _metric_values(app)["Candidates"] == "12"
    assert [tab.label for tab in app.tabs] == [
        "Overview",
        "Reward & reconstruction",
        "Admission & feasibility",
        "Failures",
        "Drill-down",
    ]
    assert not any(selectbox.label == "Rollout row" for selectbox in app.selectbox)
    assert "Download invariant CSV" not in {button.label for button in app.get("download_button")}
    advanced = next(
        toggle for toggle in app.toggle if toggle.label == "Show advanced validation, topology, and raw metadata"
    )
    assert advanced.value is False
    assert not app.error

    app = _set_stored_rollout_workspace(app, "Reward & reconstruction")
    assert not app.exception
    assert "Scientific evidence" in [subheader.value for subheader in app.subheader]
    assert _metric_values(app)["Matched comparison eligible"] == "NO"
    assert any("comparison is blocked" in warning.value for warning in app.warning)
    assert not any(selectbox.label == "Rollout row" for selectbox in app.selectbox)
    assert {selectbox.label for selectbox in app.selectbox} >= {
        "Temporal metric",
        "Temporal grouping class",
        "Temporal grouping field",
        "Raw trajectory rollout",
    }
    assert "Download temporal summary CSV" in {button.label for button in app.get("download_button")}
    assert sum(toggle.label == "Logarithmic y-axis" for toggle in app.toggle) == 2
    grouping_class = next(selectbox for selectbox in app.selectbox if selectbox.label == "Temporal grouping class")
    grouping_class.set_value("Selected-action provenance (descriptive, non-causal)")
    app.session_state["stored_rollouts_section"] = "Reward & reconstruction"
    app = app.run()
    assert not app.exception
    assert any("descriptive and post-selection" in warning.value for warning in app.warning)
    extra_evidence = next(
        toggle for toggle in app.toggle if toggle.label == "Load branching, rank/regret, and root-relative evidence"
    )
    extra_evidence.set_value(True)
    app.session_state["stored_rollouts_section"] = "Reward & reconstruction"
    app = app.run()
    assert not app.exception
    assert {button.label for button in app.get("download_button")} >= {
        "Download branching provenance CSV",
        "Download selected rank/regret CSV",
        "Download root-relative geometry CSV",
    }

    app = _set_stored_rollout_workspace(app, "Admission & feasibility")
    assert not app.exception
    assert "Targets and action support" in [subheader.value for subheader in app.subheader]
    assert {button.label for button in app.get("download_button")} >= {
        "Download target protocol CSV",
        "Download mask combinations CSV",
        "Download candidate provenance flow CSV",
        "Download selected-action policy/rank flow CSV",
        "Download exact selected-step evidence CSV",
    }
    assert {item.label for item in app.multiselect} >= {"Flow policies", "Flow rollout depths"}
    assert "Download family support CSV" not in {button.label for button in app.get("download_button")}
    aggregates = next(toggle for toggle in app.toggle if toggle.label == "Load complete candidate aggregate breakdowns")
    aggregates.set_value(True)
    app.session_state["stored_rollouts_section"] = "Admission & feasibility"
    app = app.run()
    assert not app.exception
    assert "Download family support CSV" in {button.label for button in app.get("download_button")}
    assert "Geometry / label distribution" in {selectbox.label for selectbox in app.selectbox}
    assert "Load bounded candidate geometry and reward plots" not in {toggle.label for toggle in app.toggle}

    app = _set_stored_rollout_workspace(app, "Failures")
    assert not app.exception
    assert "Active-store failure detail" in [subheader.value for subheader in app.subheader]
    assert "Minimum valid fanout" in {item.label for item in app.number_input}
    assert "Dominant invalidity fraction" in {item.label for item in app.slider}

    app = _set_stored_rollout_workspace(app, "Drill-down")
    assert not app.exception
    assert "Drill-down" in [subheader.value for subheader in app.subheader]
    assert {selectbox.label for selectbox in app.selectbox} >= {
        "Query scope",
        "Rollout row",
        "Step row",
        "Matched row to promote",
        "Layer preset",
        "Launch mode",
    }
    assert {button.label for button in app.get("download_button")} >= {
        "Download selected-step candidate CSV",
        "Download queried rows CSV",
        "Download deterministic evidence bundle",
    }
    assert {button.label for button in app.button} >= {
        "Apply query",
        "Clear query",
        "Promote queried row",
        "Launch Rerun",
    }


def test_stored_rollouts_corpus_reward_and_admission_are_plot_first(isolated_path_config, tmp_path) -> None:
    """Corpus plots are visible after explicit build while raw rows stay inside expanders."""

    records = build_rollout_records(horizon=2, num_samples=6, seed=247)[:1]
    write_rollout_zarr_store(isolated_path_config.offline_cache_dir / "first.zarr", records)
    write_rollout_zarr_store(isolated_path_config.offline_cache_dir / "second.zarr", records)

    app = _stored_rollouts_app(tmp_path).run()
    next(button for button in app.button if button.label == "Build corpus summary").click()
    app = app.run()
    app = _set_stored_rollout_workspace(app, "Reward & reconstruction")

    assert not app.exception
    assert "Corpus reward and reconstruction" in [header.value for header in app.subheader]
    assert len(app.get("plotly_chart")) >= 2
    assert any("rows and CSV" in expander.label for expander in app.expander)

    app = _set_stored_rollout_workspace(app, "Admission & feasibility")

    assert not app.exception
    assert "Corpus admission and feasibility" in [header.value for header in app.subheader]
    assert any("Target-admission rows and CSV" == expander.label for expander in app.expander)


def test_stored_rollouts_page_keeps_stale_store_diagnostics_visible(isolated_path_config, tmp_path) -> None:
    stale_path = isolated_path_config.offline_cache_dir / "stale.zarr"
    stale_root = zarr.open_group(stale_path, mode="w")
    stale_root.attrs["schema_version"] = "0.6-rollout-core"
    stale_root.create_group("rollouts").create_array("rollout_row_id", data=np.arange(2, dtype=np.int64))
    stale_root.create_group("steps").create_array("step_row_id", data=np.arange(4, dtype=np.int64))
    stale_root.create_group("candidates").create_array("candidate_row_id", data=np.arange(8, dtype=np.int64))

    app = _stored_rollouts_app(tmp_path).run()

    assert not app.exception
    assert _metric_values(app)["Validation"] == "BLOCKED"
    assert _metric_values(app)["Rollouts"] == "2"
    assert _metric_values(app)["Steps"] == "4"
    assert _metric_values(app)["Candidates"] == "8"
    assert not any(selectbox.label == "Rollout row" for selectbox in app.selectbox)
    advanced = next(
        toggle for toggle in app.toggle if toggle.label == "Show advanced validation, topology, and raw metadata"
    )
    advanced.set_value(True)
    app = app.run()
    assert {button.label for button in app.get("download_button")} >= {
        "Download store metadata JSON",
        "Download topology JSON",
    }

    app = _set_stored_rollout_workspace(app, "Reward & reconstruction")
    assert not app.exception
    assert any("disabled because this store" in warning.value for warning in app.warning)
    assert any("Unsupported rollout Zarr schema_version" in error.value for error in app.error)
    assert not any(selectbox.label == "Rollout row" for selectbox in app.selectbox)
    assert "Download stale-store diagnostics JSON" in {button.label for button in app.get("download_button")}


def test_stored_rollouts_missing_depth_disables_only_depth_preview(isolated_path_config, tmp_path) -> None:
    result = write_rollout_zarr_store(
        isolated_path_config.offline_cache_dir / "missing-depth.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=48)[:1],
    )
    root = zarr.open_group(result.store_dir, mode="a")
    root.attrs["selected_depth_enabled"] = False

    app = _stored_rollouts_app(tmp_path).run()
    app = _set_stored_rollout_workspace(app, "Drill-down")

    assert not app.exception
    assert any("No selected-depth row" in info.value for info in app.info)
    assert "Download selected-step candidate CSV" in {button.label for button in app.get("download_button")}
    assert "Launch Rerun" in {button.label for button in app.button}


def test_stored_rollouts_large_store_stays_on_lightweight_trust_workspace(isolated_path_config, tmp_path) -> None:
    write_rollout_zarr_store(
        isolated_path_config.offline_cache_dir / "large.zarr",
        build_rollout_records(horizon=3, num_samples=12, seed=49),
    )

    app = _stored_rollouts_app(tmp_path).run()

    assert not app.exception
    assert "Active-store validation" in [subheader.value for subheader in app.subheader]
    assert not any(selectbox.label in {"Rollout row", "Step row", "Launch mode"} for selectbox in app.selectbox)
    assert not any(number.label == "Candidate preview row limit" for number in app.number_input)


def test_stored_rollouts_default_candidate_geometry_is_visible(
    isolated_path_config,
    tmp_path,
) -> None:
    """Admission opens bounded 2D/3D geometry without an extra toggle."""

    write_rollout_zarr_store(
        isolated_path_config.offline_cache_dir / "flow.zarr",
        build_rollout_records(horizon=2, num_samples=8, seed=50)[:2],
    )
    session._clear_stored_rollout_caches()

    app = _stored_rollouts_app(tmp_path).run()
    app = _set_stored_rollout_workspace(app, "Admission & feasibility")

    assert not app.exception
    assert "Download candidate provenance flow CSV" in {button.label for button in app.get("download_button")}
    assert "Download family support CSV" not in {button.label for button in app.get("download_button")}
    assert "Load bounded candidate geometry and reward plots" not in {toggle.label for toggle in app.toggle}
    assert "Geometry / label distribution" in {selectbox.label for selectbox in app.selectbox}


def test_candidate_geometry_diagnostics_include_root_relative_3d_view(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default geometry diagnostics retain height instead of hover-only depth."""

    captured: list[object] = []
    monkeypatch.setattr(candidate_generation.st, "expander", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(candidate_generation.st, "caption", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(candidate_generation.st, "selectbox", lambda _label, options: options[0])
    monkeypatch.setattr(
        candidate_generation,
        "_render_plot",
        lambda figure, _explanation: captured.append(figure),
    )
    candidates = pd.DataFrame({"motion_step_length_m": [0.2]})
    root_geometry = pd.DataFrame(
        {
            "root_relative_x_m": [0.1, 0.2],
            "root_relative_y_m": [0.3, 0.4],
            "root_relative_z_m": [0.5, 0.6],
            "position": ["forward_local", "forward_local"],
            "selected": [False, True],
        }
    )

    candidate_generation._render_candidate_geometry_diagnostics(
        candidates,
        root_geometry,
        total_candidates=2,
    )

    assert any(trace.type == "scatter3d" for figure in captured for trace in figure.data)


def test_stored_rollouts_default_evidence_defers_selected_rank_flow(
    isolated_path_config,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Evidence defaults defer all candidate-derived projections until explicitly requested."""

    write_rollout_zarr_store(
        isolated_path_config.offline_cache_dir / "lazy-heavy.zarr",
        build_rollout_records(horizon=2, num_samples=8, seed=51)[:2],
    )
    session._clear_stored_rollout_caches()
    original_projection = reconstruction_return._cached_projection
    heavy_calls = dict.fromkeys(("candidates", "candidate_group", "ranks", "root_geometry", "tree"), 0)

    def spy_projection(store_path: str, projection: str, **kwargs):
        if projection in heavy_calls:
            heavy_calls[projection] += 1
        return original_projection(store_path, projection, **kwargs)

    monkeypatch.setattr(reconstruction_return, "_cached_projection", spy_projection)
    app = _stored_rollouts_app(tmp_path).run()
    app = _set_stored_rollout_workspace(app, "Reward & reconstruction")

    assert not app.exception
    assert heavy_calls == {
        "candidates": 0,
        "candidate_group": 0,
        "ranks": 0,
        "root_geometry": 0,
        "tree": 0,
    }


def test_stored_rollout_evidence_roles_are_explicit() -> None:
    """Actor diagnostics and privileged oracle outcomes must not share a badge."""

    expected = {
        "cumulative_target_root_gain": "oracle/evaluation",
        "selected_target_root_gain": "oracle/evaluation",
        "selected_target_rri": "oracle/evaluation",
        "marginal_target_rri": "oracle/evaluation",
        "valid_fanout": "actor-visible",
        "invalid_fraction": "actor-visible",
        "selected_probability": "actor-visible",
        "selected_entropy": "actor-visible",
    }
    assert set(reconstruction_return._TEMPORAL_METRIC_LABELS.values()) == set(expected)
    assert {metric: reconstruction_return._temporal_evidence_role(metric) for metric in expected} == expected
    with pytest.raises(ValueError, match="no explicit evidence role"):
        reconstruction_return._temporal_evidence_role("derived_q_h")


def test_branching_probability_entropy_plot_is_actor_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    """The restored branching plot must use the same actor-visible role owner."""

    captured: list[shared.ScientificExplanation] = []
    steps = pd.DataFrame(
        [
            {
                "rollout_row_id": 0,
                "policy": "greedy",
                "step_index": 0,
                "selected_probability": 0.75,
                "selected_entropy": 0.4,
            }
        ]
    )
    monkeypatch.setattr(
        reconstruction_return,
        "_render_plot",
        lambda _figure, explanation: captured.append(explanation),
    )

    reconstruction_return._render_branching_evidence(steps, pd.DataFrame())

    assert [explanation.evidence_role for explanation in captured] == ["actor-visible"]


def test_selected_rank_regret_explanation_is_oracle_evaluation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rank/regret derives from privileged target gain, not a training cache."""

    captured: list[shared.ScientificExplanation] = []

    def fake_projection(_store_path: str, projection: str, **_kwargs):
        if projection == "ranks":
            return [
                {
                    "selected_rank": 2,
                    "regret_to_best": 0.25,
                    "policy": "greedy",
                    "rollout_row_id": 0,
                    "step_row_id": 0,
                    "valid_candidate_count": 4,
                }
            ]
        if projection == "root_geometry":
            return []
        raise AssertionError(projection)

    def capture_plot(_figure, explanation):
        captured.append(explanation)

    monkeypatch.setattr(reconstruction_return, "_cached_projection", fake_projection)
    monkeypatch.setattr(reconstruction_return, "_render_plot", capture_plot)
    monkeypatch.setattr(reconstruction_return, "_download_frame", lambda *_args, **_kwargs: None)

    reconstruction_return._render_selected_rank_and_geometry("store.zarr")

    assert [explanation.evidence_role for explanation in captured] == ["oracle/evaluation"]


def test_query_state_is_namespaced_deterministic_and_preserves_last_valid_result() -> None:
    """Query transitions should be explicit, copied, deterministic, and failure-preserving."""

    rollout_namespace = inspect_rerun._query_namespace("store-a", "Rollout summaries", "not_applicable")
    step_namespace = inspect_rerun._query_namespace("store-a", "Factual steps", "not_applicable")
    other_store_namespace = inspect_rerun._query_namespace("store-b", "Factual steps", "not_applicable")
    assert len({rollout_namespace, step_namespace, other_store_namespace}) == 3
    assert inspect_rerun._query_key(rollout_namespace, "rollout_widget") != inspect_rerun._query_key(
        step_namespace, "rollout_widget"
    )

    source = pd.DataFrame(
        [
            {"step_row_id": 2, "rollout_row_id": 1, "gain": -0.2, "actor_action": True},
            {"step_row_id": 1, "rollout_row_id": 0, "gain": 0.7, "actor_action": True},
            {"step_row_id": 0, "rollout_row_id": 0, "gain": 0.1, "actor_action": False},
        ],
        index=[9, 8, 7],
    )
    original = source.copy(deep=True)
    state = {
        inspect_rerun._query_key(step_namespace, "draft_expression"): "gain > 0.5 and actor_action",
        inspect_rerun._query_key(step_namespace, "rollout_widget"): 1,
        inspect_rerun._query_key(step_namespace, "step_widget"): 2,
    }

    inspect_rerun._apply_query_state(state, step_namespace, source)
    result = state[inspect_rerun._query_key(step_namespace, "last_valid_result")]

    pd.testing.assert_frame_equal(source, original)
    assert list(result.columns) == sorted(source.columns)
    assert isinstance(result.index, pd.RangeIndex)
    assert result[["rollout_row_id", "step_row_id"]].values.tolist() == [[0, 1]]
    assert len(pd.read_csv(StringIO(result.to_csv(index=False)))) == 1
    with pytest.raises(Exception, match="secret"):
        secret = 0.5
        inspect_rerun._evaluate_query_frame(source, "gain > @secret")
    assert secret == 0.5
    valid_result = result.copy()

    state[inspect_rerun._query_key(step_namespace, "draft_expression")] = "unknown_column > 0"
    inspect_rerun._apply_query_state(state, step_namespace, source)

    pd.testing.assert_frame_equal(
        state[inspect_rerun._query_key(step_namespace, "last_valid_result")],
        valid_result,
    )
    assert "UndefinedVariableError" in state[inspect_rerun._query_key(step_namespace, "last_error")]
    assert state[inspect_rerun._query_key(step_namespace, "rollout_widget")] == 1
    assert state[inspect_rerun._query_key(step_namespace, "step_widget")] == 2

    inspect_rerun._clear_query_state(state, step_namespace)
    assert state[inspect_rerun._query_key(step_namespace, "rollout_widget")] == 1
    assert state[inspect_rerun._query_key(step_namespace, "step_widget")] == 2
    assert inspect_rerun._query_key(step_namespace, "last_valid_result") not in state


def test_query_store_change_and_pending_promotion_are_fail_closed() -> None:
    """Store changes should purge prior query state and stale promotion ids should preserve selection."""

    namespace = inspect_rerun._query_namespace("store-a", "Candidates", "Selected step")
    state = {
        "stored_rollouts_active_query_store": "store-a",
        inspect_rerun._query_key(namespace, "draft_expression"): "selected",
        inspect_rerun._query_key(namespace, "last_error"): "old error",
        inspect_rerun._query_key(namespace, "pending_promotion"): {
            "rollout_row_id": 4,
            "step_row_id": 9,
        },
    }

    inspect_rerun._activate_query_store(state, "store-b")

    assert state == {"stored_rollouts_active_query_store": "store-b"}

    namespace = inspect_rerun._query_namespace("store-b", "Candidates", "Explicit full store")
    rollout_key = inspect_rerun._query_key(namespace, "rollout_widget")
    step_key = inspect_rerun._query_key(namespace, "step_widget")
    pending_key = inspect_rerun._query_key(namespace, "pending_promotion")
    state.update({rollout_key: 0, step_key: 1, pending_key: {"rollout_row_id": 7, "step_row_id": 12}})

    error = inspect_rerun._consume_pending_promotion(
        state,
        namespace,
        rollout_ids=[0, 7],
        steps_by_rollout={0: [1], 7: [11]},
    )

    assert "stale step_row_id=12" in str(error)
    assert state[rollout_key] == 0
    assert state[step_key] == 1
    assert pending_key not in state

    state[pending_key] = {"rollout_row_id": 7, "step_row_id": 11}
    assert (
        inspect_rerun._consume_pending_promotion(
            state,
            namespace,
            rollout_ids=[0, 7],
            steps_by_rollout={0: [1], 7: [11]},
        )
        is None
    )
    assert state[rollout_key] == 7
    assert state[step_key] == 11


def test_candidate_query_source_routes_full_store_only_for_explicit_population(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Candidate query populations should retain bounded reader filters until full store is explicit."""

    calls: list[tuple[int | None, int | None]] = []

    def fake_projection(
        _store_path: str,
        projection: str,
        *,
        rollout_row_id: int | None = None,
        step_row_id: int | None = None,
        **_kwargs,
    ) -> list[dict[str, object]]:
        assert projection == "candidates"
        calls.append((rollout_row_id, step_row_id))
        return []

    monkeypatch.setattr(inspect_rerun, "_cached_projection", fake_projection)
    kwargs = {
        "store_path": "/store.zarr",
        "scope": "Candidates",
        "rollout_id": 7,
        "step_id": 11,
        "all_steps": pd.DataFrame(),
    }

    inspect_rerun._query_source_frame(**kwargs, candidate_population="Selected step")
    inspect_rerun._query_source_frame(**kwargs, candidate_population="Selected rollout")
    inspect_rerun._query_source_frame(**kwargs, candidate_population="Explicit full store")

    assert calls == [(7, 11), (7, None), (None, None)]


def test_stored_rollouts_query_apply_invalid_recovery_and_candidate_promotion(
    isolated_path_config,
    tmp_path,
) -> None:
    """App query workflow should preserve valid results and promote a candidate's owning step."""

    write_rollout_zarr_store(
        isolated_path_config.offline_cache_dir / "queries.zarr",
        build_rollout_records(horizon=2, num_samples=8, seed=51)[:2],
    )
    session._clear_stored_rollout_caches()
    app = _stored_rollouts_app(tmp_path).run()
    app = _set_stored_rollout_workspace(app, "Drill-down")
    scope = next(item for item in app.selectbox if item.label == "Query scope")
    scope.set_value("Candidates")
    app.session_state["stored_rollouts_section"] = "Drill-down"
    app = app.run()
    population = next(item for item in app.selectbox if item.label == "Candidate population")
    population.set_value("Explicit full store")
    app.session_state["stored_rollouts_section"] = "Drill-down"
    app = app.run()
    assert any("Explicit full-store candidate query selected" in warning.value for warning in app.warning)

    expression = next(item for item in app.text_area if item.label == "Pandas query expression")
    expression.set_value("rollout_row_id == 1 and step_index == 1 and selected")
    next(button for button in app.button if button.label == "Apply query").click()
    app.session_state["stored_rollouts_section"] = "Drill-down"
    app = app.run()
    assert not app.exception
    assert any("matched rows: 1" in caption.value for caption in app.caption)
    assert "Download queried rows CSV" in {button.label for button in app.get("download_button")}

    expression = next(item for item in app.text_area if item.label == "Pandas query expression")
    expression.set_value("unknown_column > 0")
    next(button for button in app.button if button.label == "Apply query").click()
    app.session_state["stored_rollouts_section"] = "Drill-down"
    app = app.run()
    assert not app.exception
    assert any("last valid result is preserved" in error.value for error in app.error)
    assert any("matched rows: 1" in caption.value for caption in app.caption)

    next(button for button in app.button if button.label == "Promote queried row").click()
    app.session_state["stored_rollouts_section"] = "Drill-down"
    app = app.run()

    assert not app.exception
    assert next(item for item in app.selectbox if item.label == "Rollout row").value == 1
    assert next(item for item in app.selectbox if item.label == "Step row").value == 3


def test_temporal_summary_figure_contains_population_median_iqr_and_exact_counts() -> None:
    """Population chart traces should contain aggregate statistics, never rollout trajectories."""

    summary = pd.DataFrame(
        [
            {
                "metric": "selected_target_root_gain",
                "units": "fraction",
                "step_index": step,
                "policy": policy,
                "total_count": 4,
                "finite_count": 3,
                "missing_count": 1,
                "store_count": 2,
                "median": 0.2 + step,
                "q25": 0.1 + step,
                "q75": 0.3 + step,
                "mean": 0.21 + step,
                "min": 0.0 + step,
                "max": 0.4 + step,
            }
            for policy in ("greedy", "softmax")
            for step in (0, 1)
        ]
    )

    figure = reconstruction_return._temporal_summary_figure(
        summary,
        group_field="policy",
        metric_label="Selected one-step target root gain",
    )

    median_traces = [trace for trace in figure.data if trace.mode == "lines+markers"]
    assert {trace.name for trace in median_traces} == {"greedy", "softmax"}
    assert all(trace.customdata.shape == (2, 9) for trace in median_traces)
    assert all(np.asarray(trace.x).tolist() == [1, 2] for trace in median_traces)
    assert all(
        np.asarray(trace.customdata)[:, :3].tolist() == [[0.0, 3.0, 4.0], [1.0, 3.0, 4.0]] for trace in median_traces
    )
    assert all(np.asarray(trace.customdata)[:, 4].tolist() == [2.0, 2.0] for trace in median_traces)
    assert figure.layout.xaxis.title.text == "acquisition number (1 = first selected view; root baseline omitted)"
    assert sum(trace.fill == "tonexty" for trace in figure.data) == 2
    assert not any("rollout" in str(trace.name).lower() for trace in figure.data)


def test_log_y_axis_control_copies_figure_and_preserves_linear_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every opted-in plot gets an independent, non-mutating axis control."""

    original = rollout_panel.go.Figure(rollout_panel.go.Scatter(x=[0, 1], y=[1.0, 10.0]))
    monkeypatch.setattr(panel_common.st, "toggle", lambda *_args, **_kwargs: False)

    linear, enabled = panel_common._plot_with_y_axis_control(original, key="plot-a")

    assert enabled is False
    assert linear.layout.yaxis.type == "linear"
    assert original.layout.yaxis.type is None


def test_log_y_axis_control_warns_and_sets_log_scale(monkeypatch: pytest.MonkeyPatch) -> None:
    """The logarithmic option must disclose its non-positive-value limitation."""

    captions: list[str] = []
    monkeypatch.setattr(panel_common.st, "toggle", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(panel_common.st, "caption", captions.append)

    rendered, enabled = panel_common._plot_with_y_axis_control(
        rollout_panel.go.Figure(rollout_panel.go.Scatter(y=[0.0, 1.0, 10.0])),
        key="plot-b",
    )

    assert enabled is True
    assert rendered.layout.yaxis.type == "log"
    assert captions == ["Logarithmic y-axis: zero and negative observations are not visible in this plot."]


def test_live_quality_plot_unifies_context_axis_control_and_chart(monkeypatch: pytest.MonkeyPatch) -> None:
    """Live over-time plots must use one contextual plotting seam."""

    info: list[tuple[str, str]] = []
    controls: list[str] = []
    charts: list[object] = []
    figure = rollout_panel.go.Figure(rollout_panel.go.Scatter(y=[1.0]))
    monkeypatch.setattr(rollout_panel, "_info_popover", lambda label, text: info.append((label, text)))
    monkeypatch.setattr(
        rollout_panel,
        "_plot_with_y_axis_control",
        lambda fig, *, key: controls.append(key) or (fig, False),
    )
    monkeypatch.setattr(rollout_panel.st, "plotly_chart", lambda fig, **_kwargs: charts.append(fig))

    rollout_panel._render_live_quality_plot(
        figure,
        label="selected return",
        context="Interpret this trajectory.",
        log_y_key="plot-c",
    )

    assert controls == ["plot-c"]
    assert charts == [figure]
    assert info[0][0] == "selected return"
    assert "Axis scale" in info[0][1]
    assert "zero and negative" in info[0][1]


def test_stored_rollout_plots_have_one_contextual_rendering_owner() -> None:
    """No stored-rollout plot may bypass its scientific explanation popover."""

    source = Path(shared.__file__).read_text(encoding="utf-8")

    assert source.count("st.plotly_chart(") == 1
    assert "st.plotly_chart(rendered" in source
    assert shared.plot_control_key("summary", "a") != shared.plot_control_key("summary", "b")


def test_candidate_flow_figure_preserves_stage_specific_nodes_and_counts() -> None:
    """Candidate Sankey should present one informative proposal-signature stage."""

    flow = pd.DataFrame(
        [
            {
                "source_id": "root:scoped_candidates",
                "source_label": "All candidates in active scope (5; valid + invalid)",
                "source_stage": "root",
                "target_id": "proposal:forward|forward_local|forward_rig",
                "target_label": "forward · center=forward_local · view=forward_rig",
                "target_stage": "proposal",
                "count": 5,
                "root_denominator": 5,
                "store_candidate_count": 5,
                "fraction_of_root": 1.0,
            },
            {
                "source_id": "proposal:forward|forward_local|forward_rig",
                "source_label": "forward · center=forward_local · view=forward_rig",
                "source_stage": "proposal",
                "target_id": "actor_validity:actor_valid",
                "target_label": "actor_valid",
                "target_stage": "actor_validity",
                "count": 5,
                "root_denominator": 5,
                "store_candidate_count": 5,
                "fraction_of_root": 1.0,
            },
        ]
    )

    figure = candidate_generation._candidate_flow_figure(flow)
    sankey = figure.data[0]

    assert figure.layout.title.text == "Candidate provenance and support flow"
    assert list(sankey.link.value) == [5, 5]
    assert list(sankey.node.label).count("forward · center=forward_local · view=forward_rig") == 1
    assert list(sankey.node.customdata) == ["root", "proposal", "actor_validity"]


def test_selected_action_flow_groups_policy_temperature_and_exact_rri_ranks() -> None:
    """Selected-action flow should expose policy mechanics without hiding exact low ranks."""

    ranks = pd.DataFrame(
        [
            {
                "policy": "temperature_softmax",
                "temperature": 1.0,
                "selected_candidate_row_id": 10,
                "target_rri_rank": 3,
            },
            {
                "policy": "oracle_greedy",
                "temperature": np.nan,
                "selected_candidate_row_id": 11,
                "target_rri_rank": 1,
            },
            {
                "policy": "temperature_softmax",
                "temperature": 1.0,
                "selected_candidate_row_id": 12,
                "target_rri_rank": None,
            },
        ]
    )

    flow = candidate_generation._selected_action_flow_rows(ranks)
    figure = candidate_generation._selected_action_flow_figure(flow)
    sankey = figure.data[0]

    assert figure.layout.title.text == "Selected-action policy and target-RRI rank flow"
    assert sum(row["count"] for row in flow if row["source_stage"] == "selected_root") == 3
    assert sum(row["count"] for row in flow if row["target_stage"] == "target_rri_rank") == 3
    assert {row["root_denominator"] for row in flow} == {3}
    assert "temperature_softmax (τ=1)" in set(sankey.node.label)
    assert {"1", "3", "unavailable"} <= set(sankey.node.label)


def test_stored_rollout_download_helpers_are_lazy_complete_and_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CSV/JSON downloads should defer bytes until click and avoid eager media URLs."""

    downloads: list[dict[str, object]] = []
    captions: list[str] = []
    csv_calls = 0
    json_calls = 0
    serialize_csv = shared.serialize_frame_csv
    serialize_json = shared.serialize_json

    def count_csv(frame: pd.DataFrame) -> bytes:
        nonlocal csv_calls
        csv_calls += 1
        return serialize_csv(frame)

    def count_json(payload: object) -> bytes:
        nonlocal json_calls
        json_calls += 1
        return serialize_json(payload)

    monkeypatch.setattr(shared, "serialize_frame_csv", count_csv)
    monkeypatch.setattr(shared, "serialize_json", count_json)
    monkeypatch.setattr(
        shared.st,
        "download_button",
        lambda label, **kwargs: downloads.append({"label": label, **kwargs}),
    )
    monkeypatch.setattr(shared.st, "caption", captions.append)
    frame = pd.DataFrame({"rollout_row_id": [2, 3, 5], "note": ["a,b", "line\nbreak", "plain"]})
    payload = {"z": np.int64(2), "a": ["first"]}

    shared.download_frame("CSV", "rows.csv", frame)
    shared.download_json("JSON", "rows.json", payload)

    assert csv_calls == 0
    assert json_calls == 0
    assert all(callable(download["data"]) for download in downloads)
    assert all(download["on_click"] == "ignore" for download in downloads)
    assert all("stale media URLs" in str(download["help"]) for download in downloads)
    assert downloads[0]["data"]() == frame.to_csv(index=False).encode("utf-8")
    assert downloads[1]["data"]() == b'{\n  "a": [\n    "first"\n  ],\n  "z": 2\n}\n'
    assert csv_calls == 1
    assert json_calls == 1
    assert captions == ["Export rows: 3 (complete filtered dataset)."]


def test_stored_candidate_rows_decode_strategy_and_mixture_names(tmp_path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=37)[:1],
    )
    reader = RolloutZarrStoreReader(result.store_dir)

    rows = candidate_audit_rows(reader, rollout_row_id=0)

    assert rows[0]["strategy"] != ""
    assert rows[0]["position"] == "forward_local"
    assert rows[0]["mixture"] != ""


def test_stored_rollouts_panel_is_publicly_exported() -> None:
    assert stored_rollouts_panel.render_stored_rollouts_panel is panel_dispatcher.render_stored_rollouts_panel


def test_target_rri_candidate_config_uses_target_aware_mixture() -> None:
    cfg = rollout_panel._candidate_config_for_live_rollout(
        scoring_mode=rollout_panel.LiveRolloutScoringMode.TARGET_RRI,
        candidate_budget=16,
        seed=7,
        device="cpu",
    )

    assert isinstance(cfg, CandidateMixtureViewGeneratorConfig)
    assert cfg.total_count == 16
    assert cfg.base.num_samples == 16
    assert [component.name for component in cfg.components] == [
        "target_bearing_local",
        "forward_local",
        "lateral_target_bypass",
        "local_refinement",
        "revisit_backtrack",
    ]
    assert [component.count for component in cfg.components] == [5, 5, 3, 2, 1]
    assert cfg.components[0].strategy is ViewDirectionMode.TARGET_POINT


def test_geometry_candidate_config_has_requested_count_without_mixture() -> None:
    cfg = rollout_panel._candidate_config_for_live_rollout(
        scoring_mode=rollout_panel.LiveRolloutScoringMode.GEOMETRY,
        candidate_budget=16,
        seed=7,
        device="cpu",
    )

    assert isinstance(cfg, CandidateViewGeneratorConfig)
    assert cfg.num_samples == 16


def test_geometry_mode_rejects_oracle_greedy_without_rri_scorer() -> None:
    with pytest.raises(ValueError, match="oracle_greedy requires an RRI scorer"):
        rollout_panel._validate_policy_for_scoring_mode(
            scoring_mode=rollout_panel.LiveRolloutScoringMode.GEOMETRY,
            selection_policy=CounterfactualSelectionPolicy.ORACLE_GREEDY,
        )


def test_target_rri_score_context_uses_selected_target_runtime_context(monkeypatch: pytest.MonkeyPatch) -> None:
    target = _target_row()
    fake_sample = SimpleNamespace(efm_snippet_view=object())
    fake_evaluator = object()

    def _fake_setup_target(self, **kwargs):  # noqa: ANN001
        assert kwargs["target_sample"] is fake_sample
        assert kwargs["target_task"] is target
        return fake_evaluator

    monkeypatch.setattr(TargetRriScorerConfig, "setup_target", _fake_setup_target)

    context = rollout_panel._score_context_for_mode(
        scoring_mode=rollout_panel.LiveRolloutScoringMode.TARGET_RRI,
        sample=fake_sample,  # type: ignore[arg-type]
        target=target,
        target_scorer_config=TargetRriScorerConfig(),
        scene_scorer_config=rollout_panel.SceneRriScorerConfig(),
    )

    assert context.score_label == "target_rri"
    assert context.evaluator.scorer is fake_evaluator
    assert context.runtime_context is not None
    assert context.runtime_context.target_id.startswith("target-")
    assert context.runtime_context.target_id != target.target_id
    assert torch.equal(context.runtime_context.target_center_world, torch.tensor([1.0, 2.0, 3.0]))


def test_target_rri_score_context_rejects_gt_invalid_target() -> None:
    with pytest.raises(ValueError, match="not GT-label valid"):
        rollout_panel._score_context_for_mode(
            scoring_mode=rollout_panel.LiveRolloutScoringMode.TARGET_RRI,
            sample=SimpleNamespace(efm_snippet_view=object()),  # type: ignore[arg-type]
            target=_target_row(gt_label_valid=False),
            target_scorer_config=TargetRriScorerConfig(),
            scene_scorer_config=rollout_panel.SceneRriScorerConfig(),
        )


def test_counterfactual_trajectory_rows_capture_step_count_score_and_final_pose() -> None:
    root_pose = PoseTW.from_Rt(torch.eye(3), torch.zeros(3))
    selected_pose = PoseTW.from_Rt(torch.eye(3), torch.tensor([1.0, 2.0, 3.0]))
    step = CounterfactualStepResult(
        step_index=0,
        candidates=_candidate_result_for_pose(selected_pose),
        selected_valid_index=0,
        selected_shell_index=0,
        selection_score=0.75,
        selection_score_label="target_rri",
    )
    trajectory = CounterfactualTrajectory(
        root_pose_world=root_pose,
        steps=[step],
        cumulative_score=0.75,
        terminated_early=False,
    )
    rollouts = CounterfactualRolloutResult(
        root_pose_world=root_pose,
        trajectories=[trajectory],
        horizon=1,
        branch_factor=1,
        beam_width=None,
        selection_policy="oracle_greedy",
        score_label="target_rri",
    )

    evaluated = _evaluated_single_step(
        rollouts,
        step,
        metrics={"rri": torch.tensor([0.75]), "target_rri": torch.tensor([0.75])},
    )
    rows = rollout_panel._counterfactual_trajectory_rows(evaluated)

    assert len(rows) == 1
    assert rows[0]["steps"] == 1
    assert rows[0]["cumulative_score"] == 0.75
    assert rows[0]["cumulative_rri"] == 0.75
    assert rows[0]["final_x"] == 1.0
    assert rows[0]["final_y"] == 2.0
    assert rows[0]["final_z"] == 3.0


def test_trajectory_metric_rows_use_empirical_95_band_not_min_mean_max() -> None:
    step = CounterfactualStepResult(
        step_index=0,
        candidates=SimpleNamespace(mask_valid=torch.tensor([True, False, True, False])),
        selected_valid_index=0,
        selected_shell_index=0,
        selection_score=0.2,
        selection_score_label="target_rri",
    )
    rollouts = CounterfactualRolloutResult(
        root_pose_world=PoseTW.from_Rt(torch.eye(3), torch.zeros(3)),
        trajectories=[
            CounterfactualTrajectory(root_pose_world=PoseTW.from_Rt(torch.eye(3), torch.zeros(3)), steps=[step])
        ],
        horizon=1,
        branch_factor=1,
        beam_width=None,
        selection_policy="temperature_softmax",
        score_label="target_rri",
    )

    evaluated = _evaluated_single_step(
        rollouts,
        step,
        metrics={"target_rri": torch.tensor([0.0, 100.0, 0.2, 100.0])},
    )
    rows = rollout_panel._trajectory_metric_rows(evaluated)

    assert set(rows.columns).isdisjoint({"fanout_min", "fanout_mean", "fanout_max"})
    assert rows.loc[0, "fanout_q025"] == pytest.approx(np.quantile([0.0, 0.2], 0.025))
    assert rows.loc[0, "fanout_q975"] == pytest.approx(np.quantile([0.0, 0.2], 0.975))
    assert rows.loc[0, "top_target_rri"] == pytest.approx([0.2, 0.0])


def test_valid_step_metric_values_rejects_mask_metric_length_mismatch() -> None:
    step = SimpleNamespace(
        transition=SimpleNamespace(candidates=SimpleNamespace(mask_valid=torch.tensor([True, False, True]))),
        evaluation=SimpleNamespace(labels=SimpleNamespace(metrics={"target_rri": torch.tensor([0.0, 0.1, 0.2, 0.3])})),
    )

    with pytest.raises(ValueError, match="Candidate validity mask shape"):
        rollout_panel._valid_step_metric_values(step, "target_rri")


def test_valid_step_metric_values_accepts_compact_valid_vectors() -> None:
    step = SimpleNamespace(
        transition=SimpleNamespace(candidates=SimpleNamespace(mask_valid=torch.tensor([True, False, True, True]))),
        evaluation=SimpleNamespace(
            labels=SimpleNamespace(metrics={"target_root_gain": torch.tensor([0.5, float("nan"), 0.9])})
        ),
    )

    values = rollout_panel._valid_step_metric_values(step, "target_root_gain")

    assert values.tolist() == pytest.approx([0.5, 0.9])


def test_live_step_diagnostics_reads_replay_transition_candidates(monkeypatch) -> None:
    candidates = object()
    observed = []
    monkeypatch.setattr(rollout_panel, "_info_popover", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        rollout_panel,
        "candidate_result_diagnostic_counts",
        lambda value: observed.append(value) or {},
    )
    monkeypatch.setattr(rollout_panel.st, "info", lambda *_args, **_kwargs: None)

    rollout_panel._render_live_step_candidate_diagnostics(
        SimpleNamespace(candidates=candidates),
        None,
    )

    assert observed == [candidates]


def test_live_step_candidate_score_rows_align_compact_valid_vectors() -> None:
    step = SimpleNamespace(
        transition=SimpleNamespace(
            candidates=SimpleNamespace(
                mask_valid=torch.tensor([True, False, True]),
                position_id=torch.tensor([1, 2, 3]),
                strategy_id=torch.tensor([0, 1, 2]),
                mixture_id=torch.tensor([0, 1, 2]),
                sampler_probability=torch.tensor([0.2, 0.3, 0.5]),
                component_name=("forward", "target", "lateral"),
            ),
            selected_valid_index=1,
            selected_shell_index=2,
            selection_scores=torch.tensor([0.1, 0.9]),
            selection_probabilities=torch.tensor([0.25, 0.75]),
            selection_logits=torch.tensor([-1.0, 1.0]),
        ),
        evaluation=SimpleNamespace(labels=SimpleNamespace(metrics={"target_root_gain": torch.tensor([0.2, 0.8])})),
    )

    rows = rollout_panel._live_step_candidate_score_rows(step)

    assert [row["shell_index"] for row in rows] == [0, 2]
    assert rows[0]["position"] == "forward_local"
    assert rows[1]["position"] == "lateral_target_bypass"
    assert rows[1]["selected"] is True
    assert rows[1]["selection_score"] == pytest.approx(0.9)
    assert rows[1]["selection_probability"] == pytest.approx(0.75)
    assert rows[1]["target_root_gain"] == pytest.approx(0.8)
    assert rows[1]["sampler_probability"] == pytest.approx(0.5)
    assert rows[1]["component"] == "lateral"


def test_live_step_candidate_score_rows_align_full_shell_vectors() -> None:
    step = SimpleNamespace(
        transition=SimpleNamespace(
            candidates=SimpleNamespace(
                mask_valid=torch.tensor([True, False, True]),
                position_id=None,
                strategy_id=None,
                mixture_id=None,
                sampler_probability=None,
                component_name=None,
            ),
            selected_valid_index=0,
            selected_shell_index=0,
            selection_scores=torch.tensor([0.1, -1.0, 0.9]),
            selection_probabilities=None,
            selection_logits=None,
        ),
        evaluation=SimpleNamespace(labels=SimpleNamespace(metrics={"target_rri": torch.tensor([0.3, 100.0, 0.7])})),
    )

    rows = rollout_panel._live_step_candidate_score_rows(step)

    assert [row["selection_score"] for row in rows] == pytest.approx([0.1, 0.9])
    assert [row["target_rri"] for row in rows] == pytest.approx([0.3, 0.7])
    assert rollout_panel._first_available_step_score_metric(pd.DataFrame(rows)) == "target_rri"


def test_fanout_band_figure_uses_filled_band_and_selected_line() -> None:
    rows = rollout_panel.pd.DataFrame(
        [
            {
                "trajectory": 0,
                "step": 1,
                "selected_target_rri": 0.2,
                "fanout_q025": 0.05,
                "fanout_q975": 0.8,
            },
            {
                "trajectory": 0,
                "step": 2,
                "selected_target_rri": 0.3,
                "fanout_q025": 0.02,
                "fanout_q975": 0.5,
            },
        ]
    )

    fig = rollout_panel._build_fanout_band_figure(rows)

    assert fig.layout.title.text == "Valid-candidate empirical central 95% range"
    assert "CI" not in fig.layout.title.text
    assert any(trace.fill == "tonexty" for trace in fig.data)
    assert any("selected target_root_gain" in str(trace.name) for trace in fig.data)
    assert not any("candidate min" in str(trace.name) for trace in fig.data)
    assert not any("candidate mean" in str(trace.name) for trace in fig.data)
    assert not any("candidate max" in str(trace.name) for trace in fig.data)


def test_live_rollout_metric_info_contains_canonical_equations() -> None:
    info_text = "\n".join(
        [
            rollout_panel._LIVE_TRAJECTORY_OBJECTIVE_INFO,
            rollout_panel._LIVE_SELECTED_RETURN_INFO,
            rollout_panel._LIVE_FANOUT_BAND_INFO,
            rollout_panel._LIVE_TOPK_CANDIDATE_INFO,
            rollout_panel._LIVE_ENDPOINT_METRIC_INFO,
        ]
    )

    assert r"J_{e,\Delta}^{(H)}" in info_text
    assert r"G_0^{(H)}" in info_text
    assert r"r_{t,\mathrm{root}}^e" in info_text
    assert r"\mathrm{RRI}_{t,\mathrm{state}}^e" in info_text
    assert r"L_e^{(H)}" in info_text
    assert r"\operatorname{TopK}" in info_text
    assert "not a statistical confidence interval" in info_text
