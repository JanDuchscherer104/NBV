"""Tests for the live counterfactual rollout panel helpers."""

# ruff: noqa: S101, SLF001

from __future__ import annotations

import json
from collections.abc import Generator, Iterable
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TypeVar, cast

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest
import streamlit as st
import torch
import zarr
from efm3d.aria.camera import CameraTW
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
    validity_support,
)
from aria_nbv.configs import PathConfig
from aria_nbv.data_handling.vin_store.dataset import VinOfflineSample
from aria_nbv.oracle.labels import OracleCandidateEvaluation, OracleCandidateLabels, RetainedOracleEvidence
from aria_nbv.oracle.pipelines.evaluated_rollout import EvaluatedRollout, EvaluatedRolloutStep
from aria_nbv.oracle.scene_rri import SceneRriScorerConfig
from aria_nbv.oracle.target_rri import TargetRriScorerConfig
from aria_nbv.oracle.target_selection import OracleTargetTask, TargetTaskIdentityStatus
from aria_nbv.pose_generation import (
    CandidateMixtureViewGeneratorConfig,
    CandidatePositionMode,
    CandidateViewGeneratorConfig,
    SamplingStrategy,
    ViewDirectionMode,
)
from aria_nbv.pose_generation.config import SampledCenterConfig, SphericalViewJitterConfig, UniformSphereConfig
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

_T = TypeVar("_T")
_R = TypeVar("_R")


def _record(items: list[_T], item: _T, result: _R) -> _R:
    items.append(item)
    return result


def _element_labels(elements: Iterable[Any]) -> list[str]:
    return [str(element.label) for element in elements]


stored_rollouts_page = SimpleNamespace(
    st=__import__("streamlit"),
    _TEMPORAL_METRIC_LABELS=reconstruction_return._TEMPORAL_METRIC_LABELS,
    _activate_query_store=inspect_rerun._activate_query_store,
    _apply_query_state=inspect_rerun._apply_query_state,
    _clear_query_state=inspect_rerun._clear_query_state,
    _clear_stored_rollout_caches=session._clear_stored_rollout_caches,
    _consume_pending_promotion=inspect_rerun._consume_pending_promotion,
    _evaluate_query_frame=inspect_rerun._evaluate_query_frame,
    _query_key=inspect_rerun._query_key,
    _query_namespace=inspect_rerun._query_namespace,
    _render_store_selector=overview_topology._render_store_selector,
    _temporal_evidence_role=reconstruction_return._temporal_evidence_role,
    _temporal_theory=reconstruction_return._temporal_theory,
    _temporal_summary_figure=reconstruction_return._temporal_summary_figure,
)

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


def _evaluated_single_step(
    result: Any, transition: Any, *, metrics: Any = None, evidence: Any = None
) -> EvaluatedRollout:
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
def isolated_path_config(tmp_path: Path) -> Generator[PathConfig, None, None]:
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


def test_manual_non_zarr_path_is_passed_to_existing_readonly_selector(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Campaign handoff remains an explicit path override, not discovery."""
    selected = (tmp_path / "campaign-shard").resolve()
    stored_rollouts_page.st.session_state["rollout_store_manual_path"] = str(selected)

    class _Column:
        def selectbox(self, *args: Any, **kwargs: Any) -> None:
            raise AssertionError("empty inventory must not discover stores")

        def info(self, *args: Any, **kwargs: Any) -> Any:
            return None

        def metric(self, *args: Any, **kwargs: Any) -> Any:
            return None

        def button(self, *args: Any, **kwargs: Any) -> Any:
            return False

    class _Expander:
        def __enter__(self) -> Any:
            return self

        def __exit__(self, *args: Any) -> Any:
            return False

    monkeypatch.setattr(stored_rollouts_page.st, "columns", lambda *_args, **_kwargs: (_Column(), _Column()))
    monkeypatch.setattr(stored_rollouts_page.st, "expander", lambda *_args, **_kwargs: _Expander())
    monkeypatch.setattr(
        stored_rollouts_page.st,
        "text_input",
        lambda _label, value="", **kwargs: stored_rollouts_page.st.session_state[kwargs["key"]],
    )
    result = stored_rollouts_page._render_store_selector(PathConfig(), [])
    assert result == ((selected,), selected)


def _set_stored_rollout_workspace(app: AppTest, workspace: str) -> AppTest:
    app.session_state["stored_rollouts_section"] = workspace
    return app.run()


def _dummy_camera() -> CameraTW:
    return cast(
        CameraTW,
        CameraTW.from_surreal(
            width=torch.tensor([64.0]),
            height=torch.tensor([64.0]),
            type_str="Pinhole",
            params=torch.tensor([[60.0, 60.0, 32.0, 32.0]]),
            gain=torch.zeros(1),
            exposure_s=torch.zeros(1),
            valid_radius=torch.tensor([64.0]),
            T_camera_rig=PoseTW.from_matrix3x4(torch.eye(3, 4).unsqueeze(0)),
        ),
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


def test_live_dataset_config_loads_vin_offline_sample_assets(tmp_path: Path) -> None:
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
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(rollout_panel, "_pytorch3d_cuda_rasterization_available", lambda: False)

    assert rollout_panel._live_rollout_device_options() == ["cuda", "cpu"]


def test_live_rollout_device_options_stay_cpu_only_without_torch_cuda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    assert rollout_panel._live_rollout_device_options() == ["cpu"]


def test_cuda_preflight_fails_with_actionable_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(rollout_panel, "_pytorch3d_cuda_rasterization_available", lambda: False)

    with pytest.raises(RuntimeError, match="PyTorch3D rasterizer"):
        rollout_panel._validate_live_rollout_device("cuda")


def test_live_depth_config_uses_explicit_cpu_device() -> None:
    cfg = rollout_panel._live_depth_config(max_candidates=16, device="cpu")

    assert str(cfg.device) == "cpu"
    assert str(cfg.renderer.device) == "cpu"
    assert cfg.max_candidates_final == 16


def test_rollout_scene_defaults_are_minimal_evidence_view() -> None:
    defaults = scene_view.ROLLOUT_SCENE_DEFAULTS

    assert defaults.show_mesh is True
    assert defaults.mesh_opacity <= 0.2
    assert defaults.semidense_mode == "off"
    assert defaults.show_trajectory is False
    assert defaults.show_frustum is False
    assert defaults.show_scene_bounds is False
    assert defaults.show_crop_bounds is False
    assert defaults.show_gt_obbs is False


def test_data_and_rollout_pages_share_scene_control_helper() -> None:
    assert vars(data_panel)["scene_plot_options_ui"] is scene_view.scene_plot_options_ui
    assert vars(rollout_panel)["scene_plot_options_ui"] is scene_view.scene_plot_options_ui


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
        cast(EvaluatedRolloutStep, step),
        sample=cast(VinOfflineSample, SimpleNamespace()),
        target=_target_row(gt_label_valid=False),
        show_actor_target=True,
        show_gt_target=False,
    )

    assert len(overlays) == 1
    assert overlays[0].name == "Descriptor target OBB"
    assert overlays[0].corners_px.shape == (8, 2)


def test_stored_rollouts_page_exercises_current_schema_features(isolated_path_config: Any, tmp_path: Path) -> None:
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
    assert _element_labels(app.tabs) == [
        "Overview",
        "Reward & reconstruction",
        "Admission & feasibility",
        "Failures",
        "Drill-down",
    ]
    assert not any(selectbox.label == "Rollout row" for selectbox in app.selectbox)
    assert "Download invariant CSV" not in set(_element_labels(app.get("download_button")))
    advanced = next(
        toggle for toggle in app.toggle if toggle.label == "Show advanced validation, topology, and raw metadata"
    )
    assert advanced.value is False
    assert not app.error

    next(button for button in app.button if button.label == "Build corpus summary").click()
    app = app.run()
    app = _set_stored_rollout_workspace(app, "Reward & reconstruction")
    assert not app.exception
    assert "Corpus reward and reconstruction" in [subheader.value for subheader in app.subheader]
    # Step 0 is the first factual selected action, so a one-step fixture still
    # has both reward plots plus the endpoint distribution.
    assert len(app.get("plotly_chart")) >= 2
    assert any("rows and CSV" in expander.label for expander in app.expander)

    app = _set_stored_rollout_workspace(app, "Admission & feasibility")
    assert not app.exception
    assert "Targets and action support" in [subheader.value for subheader in app.subheader]
    assert any("Active-store drill-down · Admission & feasibility" in item.value for item in app.markdown)
    assert any("Active store full path:" in item.value for item in app.caption)
    assert any("strictly > 0.20" in item.value and "exactly one" in item.value for item in app.info)
    assert "Download target protocol CSV" in set(_element_labels(app.get("download_button")))
    assert "Download mask combinations CSV" in set(_element_labels(app.get("download_button")))
    assert any(toggle.label == "Load complete candidate aggregate breakdowns" for toggle in app.toggle)
    assert any(expander.label == "Bounded candidate geometry and reward plots" for expander in app.expander)

    app = _set_stored_rollout_workspace(app, "Failures")
    assert not app.exception
    assert "Active-store failure detail" in [subheader.value for subheader in app.subheader]
    assert any("Active-store drill-down · Failures" in item.value for item in app.markdown)
    assert any("It is not a corpus aggregate" in item.value for item in app.info)
    assert "Minimum valid fanout" in {item.label for item in app.number_input}
    assert "Dominant invalidity fraction" in {item.label for item in app.slider}

    app = _set_stored_rollout_workspace(app, "Drill-down")
    assert not app.exception
    assert not any("Drill-down is unavailable" in warning.value for warning in app.warning)
    assert "Query scope" in {selectbox.label for selectbox in app.selectbox}
    assert "Rollout row" in {selectbox.label for selectbox in app.selectbox}
    assert "Download selected-chain CSV" in set(_element_labels(app.get("download_button")))
    assert "Refresh stores" in {button.label for button in app.button}


def test_stored_rollouts_page_keeps_stale_store_diagnostics_visible(isolated_path_config: Any, tmp_path: Path) -> None:
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
    assert set(_element_labels(app.get("download_button"))) >= {
        "Download store metadata JSON",
        "Download topology JSON",
    }

    app = _set_stored_rollout_workspace(app, "Reward & reconstruction")
    assert not app.exception
    assert any("Build the corpus summary" in info.value for info in app.info)
    assert not any(selectbox.label == "Rollout row" for selectbox in app.selectbox)


def test_stored_rollouts_missing_depth_disables_only_depth_preview(isolated_path_config: Any, tmp_path: Path) -> None:
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
    assert "Download selected-step candidate CSV" in set(_element_labels(app.get("download_button")))
    assert "Launch Rerun" in {button.label for button in app.button}


def test_stored_rollouts_large_store_stays_on_lightweight_trust_workspace(
    isolated_path_config: Any, tmp_path: Path
) -> None:
    write_rollout_zarr_store(
        isolated_path_config.offline_cache_dir / "large.zarr",
        build_rollout_records(horizon=3, num_samples=12, seed=49),
    )

    app = _stored_rollouts_app(tmp_path).run()

    assert not app.exception
    assert "Active-store validation" in [subheader.value for subheader in app.subheader]
    assert not any(selectbox.label in {"Rollout row", "Step row", "Launch mode"} for selectbox in app.selectbox)
    assert not any(number.label == "Candidate preview row limit" for number in app.number_input)


def test_stored_rollouts_default_candidate_flow_does_not_load_heavy_audit(
    isolated_path_config: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Opening support flow keeps candidate reads bounded and avoids the heavy aggregate audit."""

    write_rollout_zarr_store(
        isolated_path_config.offline_cache_dir / "flow.zarr",
        build_rollout_records(horizon=2, num_samples=8, seed=50)[:2],
    )
    session.clear_rollout_page_caches()

    limits: list[int | None] = []

    def bounded_audit(*_args: Any, **kwargs: Any) -> Any:
        limits.append(kwargs.get("limit"))
        return []

    monkeypatch.setattr(session, "candidate_audit_rows", bounded_audit)
    app = _stored_rollouts_app(tmp_path).run()
    app = _set_stored_rollout_workspace(app, "Admission & feasibility")

    assert not app.exception
    assert limits and all(limit == 50_000 for limit in limits)
    assert "Download target protocol CSV" in set(_element_labels(app.get("download_button")))
    assert "Download family support CSV" not in set(_element_labels(app.get("download_button")))


def test_bounded_geometry_reads_exact_limit_without_heavy_population_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, int]] = []
    rendered: list[tuple[pd.DataFrame, int]] = []

    class Handle:
        validation = SimpleNamespace(num_candidates=60)

        def candidates(self, *, limit: int) -> Any:
            calls.append(("candidates", limit))
            return [{"target_distance_m": 2.0, "normalized_radius": 0.5}]

        def proposal_geometry(self, *, limit: int) -> Any:
            calls.append(("proposal_geometry", limit))
            return {"points": [], "frames": []}

        def trajectory_geometry(self) -> Any:
            calls.append(("trajectory_geometry", 0))
            return {"points": [], "frames": []}

    monkeypatch.setattr(
        validity_support,
        "_render_candidate_geometry_diagnostics",
        lambda candidates, _proposal, _trajectory, *, total_candidates: rendered.append((candidates, total_candidates)),
    )

    validity_support._render_bounded_candidate_geometry(Handle(), limit=17)

    assert calls == [("candidates", 17), ("proposal_geometry", 17), ("trajectory_geometry", 0)]
    assert len(rendered) == 1
    assert rendered[0][0]["target_distance_m"].tolist() == [2.0]
    assert rendered[0][1] == 60


def test_stored_rollouts_default_evidence_defers_selected_rank_flow(
    isolated_path_config: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Evidence defaults defer all candidate-derived projections until explicitly requested."""

    write_rollout_zarr_store(
        isolated_path_config.offline_cache_dir / "lazy-heavy.zarr",
        build_rollout_records(horizon=2, num_samples=8, seed=51)[:2],
    )
    session.clear_rollout_page_caches()
    for name in ("ranks", "root_geometry", "tree"):
        monkeypatch.setattr(
            session.StoredRolloutSession,
            name,
            lambda _self, _name=name, **_kwargs: pytest.fail(f"unexpected heavy projection: {_name}"),
        )
    app = _stored_rollouts_app(tmp_path).run()
    app = _set_stored_rollout_workspace(app, "Reward & reconstruction")

    assert not app.exception


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
    assert set(stored_rollouts_page._TEMPORAL_METRIC_LABELS.values()) == set(expected)
    assert {metric: stored_rollouts_page._temporal_evidence_role(metric) for metric in expected} == expected
    with pytest.raises(ValueError, match="no explicit evidence role"):
        stored_rollouts_page._temporal_evidence_role("derived_q_h")
    assert stored_rollouts_page._temporal_theory("selected_probability") is not None
    assert stored_rollouts_page._temporal_theory("valid_fanout") is not None
    assert stored_rollouts_page._temporal_theory("selected_entropy") is not None
    with pytest.raises(ValueError, match="no theory mapping"):
        stored_rollouts_page._temporal_theory("derived_q_h")


def test_branching_probability_entropy_plot_is_actor_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    """The restored branching plot must use the same actor-visible role owner."""

    captured: list[panel_common.ScientificExplanation] = []
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

    captured: list[panel_common.ScientificExplanation] = []

    class Handle:
        def ranks(self, **_kwargs: Any) -> Any:
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

        def root_geometry(self, **_kwargs: Any) -> Any:
            return []

    def capture_plot(_figure: Any, explanation: Any) -> None:
        captured.append(explanation)

    monkeypatch.setattr(reconstruction_return, "_render_plot", capture_plot)
    monkeypatch.setattr(reconstruction_return, "_download_frame", lambda *_args, **_kwargs: None)

    reconstruction_return._render_selected_rank_and_geometry(Handle())

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
    state: dict[str, Any] = {
        stored_rollouts_page._query_key(step_namespace, "draft_expression"): "gain > 0.5 and actor_action",
        stored_rollouts_page._query_key(step_namespace, "rollout_widget"): 1,
        stored_rollouts_page._query_key(step_namespace, "step_widget"): 2,
    }

    stored_rollouts_page._apply_query_state(state, step_namespace, source)
    result = cast(pd.DataFrame, state[stored_rollouts_page._query_key(step_namespace, "last_valid_result")])

    pd.testing.assert_frame_equal(source, original)
    assert list(result.columns) == sorted(source.columns)
    assert isinstance(result.index, pd.RangeIndex)
    assert result[["rollout_row_id", "step_row_id"]].values.tolist() == [[0, 1]]
    assert len(pd.read_csv(StringIO(result.to_csv(index=False)))) == 1
    with pytest.raises(Exception, match="secret"):
        secret = 0.5
        stored_rollouts_page._evaluate_query_frame(source, "gain > @secret")
    assert secret == 0.5
    valid_result = result.copy()

    state[stored_rollouts_page._query_key(step_namespace, "draft_expression")] = "unknown_column > 0"
    stored_rollouts_page._apply_query_state(state, step_namespace, source)

    pd.testing.assert_frame_equal(
        state[stored_rollouts_page._query_key(step_namespace, "last_valid_result")],
        valid_result,
    )
    assert "UndefinedVariableError" in state[stored_rollouts_page._query_key(step_namespace, "last_error")]
    assert state[stored_rollouts_page._query_key(step_namespace, "rollout_widget")] == 1
    assert state[stored_rollouts_page._query_key(step_namespace, "step_widget")] == 2

    stored_rollouts_page._clear_query_state(state, step_namespace)
    assert state[stored_rollouts_page._query_key(step_namespace, "rollout_widget")] == 1
    assert state[stored_rollouts_page._query_key(step_namespace, "step_widget")] == 2
    assert stored_rollouts_page._query_key(step_namespace, "last_valid_result") not in state


def test_query_store_change_and_pending_promotion_are_fail_closed() -> None:
    """Store changes should purge prior query state and stale promotion ids should preserve selection."""

    namespace = stored_rollouts_page._query_namespace("store-a", "Candidates", "Selected step")
    state: dict[str, Any] = {
        "stored_rollouts_active_query_store": "store-a",
        stored_rollouts_page._query_key(namespace, "draft_expression"): "selected",
        stored_rollouts_page._query_key(namespace, "last_error"): "old error",
        stored_rollouts_page._query_key(namespace, "pending_promotion"): {
            "rollout_row_id": 4,
            "step_row_id": 9,
        },
    }

    stored_rollouts_page._activate_query_store(state, "store-b")

    assert state == {"stored_rollouts_active_query_store": "store-b"}

    namespace = stored_rollouts_page._query_namespace("store-b", "Candidates", "Explicit full store")
    rollout_key = stored_rollouts_page._query_key(namespace, "rollout_widget")
    step_key = stored_rollouts_page._query_key(namespace, "step_widget")
    pending_key = stored_rollouts_page._query_key(namespace, "pending_promotion")
    state.update({rollout_key: 0, step_key: 1, pending_key: {"rollout_row_id": 7, "step_row_id": 12}})

    error = stored_rollouts_page._consume_pending_promotion(
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
        stored_rollouts_page._consume_pending_promotion(
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

    class Handle:
        def candidates(self, **kwargs: Any) -> Any:
            calls.append((kwargs.get("rollout_row_id"), kwargs.get("step_row_id")))
            return []

    handle = Handle()
    all_steps = pd.DataFrame()
    inspect_rerun._query_source_frame(
        handle,
        scope="Candidates",
        rollout_id=7,
        step_id=11,
        all_steps=all_steps,
        candidate_population="Selected step",
    )
    inspect_rerun._query_source_frame(
        handle,
        scope="Candidates",
        rollout_id=7,
        step_id=11,
        all_steps=all_steps,
        candidate_population="Selected rollout",
    )
    inspect_rerun._query_source_frame(
        handle,
        scope="Candidates",
        rollout_id=7,
        step_id=11,
        all_steps=all_steps,
        candidate_population="Explicit full store",
    )

    assert calls == [(7, 11), (7, None), (None, None)]


def test_stored_rollouts_query_apply_invalid_recovery_and_candidate_promotion(
    isolated_path_config: Any,
    tmp_path: Path,
) -> None:
    """App query workflow should preserve valid results and promote a candidate's owning step."""

    write_rollout_zarr_store(
        isolated_path_config.offline_cache_dir / "queries.zarr",
        build_rollout_records(horizon=2, num_samples=8, seed=51)[:2],
    )
    stored_rollouts_page._clear_stored_rollout_caches()
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
    assert "Download queried rows CSV" in set(_element_labels(app.get("download_button")))

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

    figure = stored_rollouts_page._temporal_summary_figure(
        summary,
        group_field="policy",
        metric_label="Selected one-step target root gain",
    )

    median_traces = [trace for trace in figure.data if trace.mode == "lines+markers"]
    assert {trace.name for trace in median_traces} == {"greedy", "softmax"}
    assert all(trace.customdata.shape == (2, 7) for trace in median_traces)
    assert all(list(trace.x) == [1, 2] for trace in median_traces)
    assert all(np.asarray(trace.customdata)[:, :2].tolist() == [[3.0, 4.0], [3.0, 4.0]] for trace in median_traces)
    assert sum(trace.fill == "tonexty" for trace in figure.data) == 2
    assert not any("rollout" in str(trace.name).lower() for trace in figure.data)


def test_corpus_reward_figure_uses_one_based_acquisitions_and_exact_context() -> None:
    """Corpus reward plots shift factual steps to one-based acquisitions."""

    rows = pd.DataFrame(
        [
            {
                "metric": "cumulative_target_root_gain",
                "units": "fraction",
                "contract_id": "contract-a",
                "contract": "contract A",
                "profile": "rich-60",
                "policy": "temperature_softmax",
                "temperature": temperature,
                "horizon": 8,
                "branch_factor": 1,
                "beam_width": 1,
                "step_index": step,
                "store_count": 3,
                "total_count": 4,
                "finite_count": 3,
                "missing_count": 1,
                "median": 0.1 * step,
                "q25": 0.05 * step,
                "q75": 0.15 * step,
                "iqr_width": 0.1 * step,
            }
            for temperature in (0.5,)
            for step in (0, 7)
        ]
    )

    figure = reconstruction_return._corpus_temporal_figure(rows, metric_label="Cumulative target root gain")

    median_traces = [trace for trace in figure.data if trace.mode == "lines+markers"]
    assert len(median_traces) == 1
    assert list(median_traces[0].x) == [1, 8]
    assert median_traces[0].name == "rich-60 · softmax · T=0.5 · H=8 · B=1 · beam=1"
    assert "temperature_softmax" not in median_traces[0].name
    assert median_traces[0].customdata[0, 4] == "contract-a"
    assert "contract_id=%{customdata[4]}" in median_traces[0].hovertemplate


def test_corpus_reward_figure_disambiguates_compact_labels_for_contract_facets() -> None:
    """Contract facets stay distinct without putting full hashes in every legend entry."""

    rows = pd.DataFrame(
        [
            {
                "metric": "cumulative_target_root_gain",
                "contract_id": contract,
                "contract": f"candidate contract {contract}",
                "profile": "rich-60",
                "policy": "temperature_softmax",
                "temperature": 0.5,
                "horizon": 8,
                "branch_factor": 1,
                "beam_width": 1,
                "step_index": 0,
                "store_count": 1,
                "total_count": 1,
                "finite_count": 1,
                "iqr_width": 0.0,
                "median": 0.1,
                "q25": 0.1,
                "q75": 0.1,
            }
            for contract in ("contract-alpha", "contract-beta")
        ]
    )

    figure = reconstruction_return._corpus_temporal_figure(rows, metric_label="Cumulative target root gain")

    names = [trace.name for trace in figure.data if trace.mode == "lines+markers"]
    assert names == [
        "rich-60 · softmax · T=0.5 · H=8 · B=1 · beam=1 · contract=contract-alp",
        "rich-60 · softmax · T=0.5 · H=8 · B=1 · beam=1 · contract=contract-bet",
    ]
    assert all(len(name) < 100 for name in names)
    assert {trace.customdata[0, 4] for trace in figure.data if trace.mode == "lines+markers"} == {
        "contract-alpha",
        "contract-beta",
    }
    assert "acquisition number" in figure.layout.xaxis.title.text
    assert "factual step_index + 1" in figure.layout.xaxis.title.text


def test_corpus_reward_figure_keeps_same_contract_cohorts_as_separate_traces() -> None:
    """Candidate/rollout lineage cohorts must not be connected into one trace."""

    rows = pd.DataFrame(
        [
            {
                "metric": "cumulative_target_root_gain",
                "contract_id": "contract-a",
                "contract": "contract A",
                "profile": "rich-60",
                "policy": "temperature_softmax",
                "temperature": 0.5,
                "horizon": 8,
                "branch_factor": 1,
                "beam_width": 1,
                "generation_cohort_id": cohort,
                "step_index": step,
                "store_count": 1,
                "total_count": 1,
                "finite_count": 1,
                "iqr_width": 0.0,
                "median": 0.1 * step,
                "q25": 0.1 * step,
                "q75": 0.1 * step,
            }
            for cohort in ("cohort-alpha", "cohort-beta")
            for step in (0, 1)
        ]
    )
    rows["median"] = rows["median"] + rows["generation_cohort_id"].map({"cohort-alpha": 0.0, "cohort-beta": 0.2})
    rows["q25"] = rows["median"]
    rows["q75"] = rows["median"]

    figure = reconstruction_return._corpus_temporal_figure(rows, metric_label="Cumulative target root gain")

    median_traces = [trace for trace in figure.data if trace.mode == "lines+markers"]
    assert len(median_traces) == 2
    names = {str(trace.name) for trace in median_traces}
    assert any("cohort=cohort-alpha" in name for name in names)
    assert any("cohort=cohort-beta" in name for name in names)
    assert all("generation_cohort=%{customdata[12]}" in str(trace.hovertemplate) for trace in median_traces)


def test_corpus_reward_figure_exposes_series_and_contributing_cohorts() -> None:
    """A pooled trace remains auditable through its scientific series metadata."""

    rows = pd.DataFrame(
        [
            {
                "metric": "cumulative_target_root_gain",
                "contract_id": "contract-a",
                "contract": "contract A",
                "profile": "rich-60",
                "policy": "temperature_softmax",
                "temperature": 0.5,
                "horizon": 8,
                "branch_factor": 1,
                "beam_width": 1,
                "generation_series_id": "series-a",
                "generation_cohort_ids_json": '["cohort-a","cohort-b"]',
                "generation_cohort_payloads_json": '{"cohort-a":"payload-a","cohort-b":"payload-b"}',
                "step_index": 0,
                "store_count": 2,
                "total_count": 2,
                "finite_count": 2,
                "iqr_width": 0.2,
                "median": 0.2,
                "q25": 0.1,
                "q75": 0.3,
            }
        ]
    )
    figure = reconstruction_return._corpus_temporal_figure(rows, metric_label="Cumulative target root gain")
    trace = next(trace for trace in figure.data if trace.mode == "lines+markers")
    assert trace.customdata[0, 12] == "series-a"
    assert trace.customdata[0, 13] == '["cohort-a","cohort-b"]'
    assert "series=%{customdata[12]}" in trace.hovertemplate
    assert "cohorts=%{customdata[13]}" in trace.hovertemplate


def test_log_y_axis_control_copies_figure_and_preserves_linear_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every opted-in plot gets an independent, non-mutating axis control."""

    original = go.Figure(go.Scatter(x=[0, 1], y=[1.0, 10.0]))
    monkeypatch.setattr(st, "toggle", lambda *_args, **_kwargs: False)

    linear, enabled = panel_common._plot_with_y_axis_control(original, key="plot-a")

    assert enabled is False
    assert linear.layout.yaxis.type == "linear"
    assert original.layout.yaxis.type is None


def test_log_y_axis_control_warns_and_sets_log_scale(monkeypatch: pytest.MonkeyPatch) -> None:
    """The logarithmic option must disclose its non-positive-value limitation."""

    captions: list[str] = []
    monkeypatch.setattr(st, "toggle", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(st, "caption", captions.append)

    rendered, enabled = panel_common._plot_with_y_axis_control(
        go.Figure(go.Scatter(y=[0.0, 1.0, 10.0])),
        key="plot-b",
    )

    assert enabled is True
    assert rendered.layout.yaxis.type == "log"
    assert captions == ["Logarithmic y-axis: zero and negative observations are not visible in this plot."]


def test_live_quality_plot_unifies_context_axis_control_and_chart(monkeypatch: pytest.MonkeyPatch) -> None:
    """Live over-time plots must use one contextual plotting seam."""

    info: list[tuple[str, str]] = []
    controls: list[str] = []
    charts: list[Any] = []
    figure = go.Figure(go.Scatter(y=[1.0]))
    monkeypatch.setattr(rollout_panel, "_info_popover", lambda label, text: info.append((label, text)))
    monkeypatch.setattr(
        rollout_panel,
        "_plot_with_y_axis_control",
        lambda fig, *, key: _record(controls, key, (fig, False)),
    )
    monkeypatch.setattr(st, "plotly_chart", lambda fig, **_kwargs: charts.append(fig))

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

    source = Path(panel_common.__file__).read_text(encoding="utf-8")

    assert source.count("st.plotly_chart(") == 1
    assert "        rendered,\n" in source
    assert panel_common.plot_control_key("summary", "a") != panel_common.plot_control_key("summary", "b")


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

    downloads: list[dict[str, Any]] = []
    captions: list[str] = []
    csv_calls = 0
    json_calls = 0
    serialize_csv = panel_common.serialize_frame_csv
    serialize_json = panel_common.serialize_json

    def count_csv(frame: pd.DataFrame) -> bytes:
        nonlocal csv_calls
        csv_calls += 1
        return serialize_csv(frame)

    def count_json(payload: Any) -> bytes:
        nonlocal json_calls
        json_calls += 1
        return serialize_json(payload)

    monkeypatch.setattr(panel_common, "serialize_frame_csv", count_csv)
    monkeypatch.setattr(panel_common, "serialize_json", count_json)
    monkeypatch.setattr(
        st,
        "download_button",
        lambda label, **kwargs: downloads.append({"label": label, **kwargs}),
    )
    monkeypatch.setattr(st, "caption", captions.append)
    frame = pd.DataFrame({"rollout_row_id": [2, 3, 5], "note": ["a,b", "line\nbreak", "plain"]})
    payload = {"z": np.int64(2), "a": ["first"]}

    panel_common.download_frame("CSV", "rows.csv", frame)
    panel_common.download_json("JSON", "rows.json", payload)

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


def test_stored_candidate_rows_decode_strategy_and_mixture_names(tmp_path: Path) -> None:
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
        device=torch.device("cpu"),
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
    assert cfg.components[0].gazes[0].mode is ViewDirectionMode.TARGET_POINT


def test_toml_candidate_profile_loads_target_shell_and_applies_runtime_overrides() -> None:
    profile_path = Path(__file__).resolve().parents[4] / ".configs" / "build_rollouts_v3_target_shell_experiment.toml"
    profile = rollout_panel._load_live_candidate_profile(profile_path)

    cfg = rollout_panel._candidate_config_for_live_rollout(
        scoring_mode=rollout_panel.LiveRolloutScoringMode.TARGET_RRI,
        candidate_budget=60,
        seed=73,
        device=torch.device("cpu"),
        profile=profile,
    )

    assert isinstance(cfg, CandidateMixtureViewGeneratorConfig)
    assert cfg.total_count == 60
    target_shell = next(component for component in cfg.components if component.name == "target_shell")
    assert target_shell.center.kind == "target_shell"
    assert cfg.base.device == torch.device("cpu")
    assert cfg.base.seed == 73


def test_target_mixture_preserves_spherical_direction_sampling_with_roll() -> None:
    base = CandidateViewGeneratorConfig(
        num_samples=5,
        ensure_collision_free=False,
        ensure_free_space=False,
        min_distance_to_mesh=0.0,
        view_sampling_strategy=SamplingStrategy.UNIFORM_SPHERE,
        view_max_azimuth_deg=0.0,
        view_max_elevation_deg=0.0,
        view_roll_jitter_deg=5.0,
        device="cpu",
    )

    cfg = rollout_panel._target_mixture_config(
        base,
        counts={
            "target_bearing_local": 1,
            "forward_local": 1,
            "lateral_target_bypass": 1,
            "local_refinement": 1,
            "revisit_backtrack": 1,
        },
    )

    for component in cfg.components:
        jitter = component.gazes[0].jitter
        assert isinstance(jitter, SphericalViewJitterConfig)
        assert isinstance(jitter.distribution, UniformSphereConfig)
        assert jitter.roll_half_width_deg == pytest.approx(5.0)


def test_target_mixture_delegates_legacy_center_projection_with_radius_overrides() -> None:
    base = CandidateViewGeneratorConfig(
        num_samples=5,
        sampling_strategy=SamplingStrategy.FORWARD_POWERSPHERICAL,
        kappa=11.0,
        min_radius=0.45,
        max_radius=1.55,
        min_elev_deg=-8.0,
        max_elev_deg=16.0,
        delta_azimuth_deg=145.0,
        ensure_collision_free=False,
        ensure_free_space=False,
        min_distance_to_mesh=0.0,
        device="cpu",
    )

    cfg = rollout_panel._target_mixture_config(
        base,
        counts={
            "target_bearing_local": 1,
            "forward_local": 1,
            "lateral_target_bypass": 1,
            "local_refinement": 1,
            "revisit_backtrack": 1,
        },
    )

    expected = {
        "target_bearing_local": SampledCenterConfig.from_legacy(
            base,
            mode=CandidatePositionMode.TARGET_BEARING_LOCAL,
        ),
        "forward_local": SampledCenterConfig.from_legacy(
            base,
            mode=CandidatePositionMode.FORWARD_LOCAL,
        ),
        "lateral_target_bypass": SampledCenterConfig.from_legacy(
            base,
            mode=CandidatePositionMode.LATERAL_TARGET_BYPASS,
        ),
        "local_refinement": SampledCenterConfig.from_legacy(
            base,
            mode=CandidatePositionMode.LOCAL_REFINEMENT,
            min_radius_m=0.2,
            max_radius_m=0.7,
        ),
        "revisit_backtrack": SampledCenterConfig.from_legacy(
            base,
            mode=CandidatePositionMode.REVISIT_BACKTRACK,
            min_radius_m=0.25,
            max_radius_m=0.9,
        ),
    }
    assert {component.name: component.center for component in cfg.components} == expected


def test_geometry_candidate_config_has_requested_count_without_mixture() -> None:
    cfg = rollout_panel._candidate_config_for_live_rollout(
        scoring_mode=rollout_panel.LiveRolloutScoringMode.GEOMETRY,
        candidate_budget=16,
        seed=7,
        device=torch.device("cpu"),
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

    def _fake_setup_target(self: TargetRriScorerConfig, **kwargs: Any) -> Any:
        assert kwargs["target_sample"] is fake_sample
        assert kwargs["target_task"] is target
        return fake_evaluator

    monkeypatch.setattr(TargetRriScorerConfig, "setup_target", _fake_setup_target)

    context = rollout_panel._score_context_for_mode(
        scoring_mode=rollout_panel.LiveRolloutScoringMode.TARGET_RRI,
        sample=fake_sample,  # type: ignore[arg-type]
        target=target,
        target_scorer_config=TargetRriScorerConfig(),
        scene_scorer_config=SceneRriScorerConfig(),
    )

    assert context.score_label == "target_rri"
    assert context.evaluator is not None
    assert context.evaluator.scorer is fake_evaluator
    runtime_context = context.runtime_context
    assert runtime_context is not None
    assert runtime_context.target_id is not None
    assert runtime_context.target_id.startswith("target-")
    assert runtime_context.target_id != target.target_id
    assert runtime_context.target_center_world is not None
    assert torch.equal(runtime_context.target_center_world, torch.tensor([1.0, 2.0, 3.0]))


def test_target_rri_score_context_rejects_gt_invalid_target() -> None:
    with pytest.raises(ValueError, match="not GT-label valid"):
        rollout_panel._score_context_for_mode(
            scoring_mode=rollout_panel.LiveRolloutScoringMode.TARGET_RRI,
            sample=SimpleNamespace(efm_snippet_view=object()),  # type: ignore[arg-type]
            target=_target_row(gt_label_valid=False),
            target_scorer_config=TargetRriScorerConfig(),
            scene_scorer_config=SceneRriScorerConfig(),
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
        candidates=cast(
            CandidateSamplingResult,
            SimpleNamespace(mask_valid=torch.tensor([True, False, True, False])),
        ),
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
        rollout_panel._valid_step_metric_values(cast(EvaluatedRolloutStep, step), "target_rri")


def test_valid_step_metric_values_accepts_compact_valid_vectors() -> None:
    step = SimpleNamespace(
        transition=SimpleNamespace(candidates=SimpleNamespace(mask_valid=torch.tensor([True, False, True, True]))),
        evaluation=SimpleNamespace(
            labels=SimpleNamespace(metrics={"target_root_gain": torch.tensor([0.5, float("nan"), 0.9])})
        ),
    )

    values = rollout_panel._valid_step_metric_values(cast(EvaluatedRolloutStep, step), "target_root_gain")

    assert values.tolist() == pytest.approx([0.5, 0.9])


def test_live_step_diagnostics_reads_replay_transition_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    candidates = cast(CandidateSamplingResult, SimpleNamespace())
    observed: list[CandidateSamplingResult] = []
    monkeypatch.setattr(rollout_panel, "_info_popover", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        rollout_panel,
        "candidate_result_diagnostic_counts",
        lambda value: _record(observed, value, {}),
    )
    monkeypatch.setattr(st, "info", lambda *_args, **_kwargs: None)

    rollout_panel._render_live_step_candidate_diagnostics(
        cast(CounterfactualStepResult, SimpleNamespace(candidates=candidates)),
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

    rows = rollout_panel._live_step_candidate_score_rows(cast(EvaluatedRolloutStep, step))

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

    rows = rollout_panel._live_step_candidate_score_rows(cast(EvaluatedRolloutStep, step))

    assert [row["selection_score"] for row in rows] == pytest.approx([0.1, 0.9])
    assert [row["target_rri"] for row in rows] == pytest.approx([0.3, 0.7])
    assert rollout_panel._first_available_step_score_metric(pd.DataFrame(rows)) == "target_rri"


def test_fanout_band_figure_uses_filled_band_and_selected_line() -> None:
    rows = pd.DataFrame(
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
    assert any(
        f"selected {panel_common.current_scientific_label('selected_target_rri')}" in str(trace.name)
        for trace in fig.data
    )
    assert not any("Selected one-step target root gain" in str(trace.name) for trace in fig.data)
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
