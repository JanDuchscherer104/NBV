"""Tests for the live counterfactual rollout panel helpers."""

# ruff: noqa: S101, SLF001

from __future__ import annotations

import json
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
from aria_nbv.app.panels import counterfactual_rollouts as rollout_panel
from aria_nbv.app.panels import data as data_panel
from aria_nbv.app.panels import stored_rollouts as stored_rollouts_panel
from aria_nbv.configs import PathConfig
from aria_nbv.oracle.target_rri import TargetRriScorerConfig
from aria_nbv.oracle.target_selection import TargetCandidateRow
from aria_nbv.pose_generation import (
    CandidateMixtureViewGeneratorConfig,
    CandidateViewGeneratorConfig,
    ViewDirectionMode,
)
from aria_nbv.pose_generation.types import CandidateSamplingResult
from aria_nbv.rollouts import (
    CounterfactualRolloutResult,
    CounterfactualSelectionPolicy,
    CounterfactualStepResult,
    CounterfactualTrajectory,
    RolloutZarrStoreReader,
    write_rollout_zarr_store,
)
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


def _target_row(*, gt_label_valid: bool = True) -> TargetCandidateRow:
    return TargetCandidateRow(
        scene_id="scene_a",
        snippet_id="snippet_1",
        source="detected_obbs",
        source_index=2,
        target_row_id=4,
        target_id="scene_a:snippet_1:detected_obbs:2",
        sem_id=3,
        inst_id=62,
        class_name="chair",
        confidence=0.9,
        center_world=(1.0, 2.0, 3.0),
        extents=(0.5, 0.6, 0.7),
        pose_world_object=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 2.0, 3.0),
        relative_pose_reference_object=tuple(float(v) for v in range(12)),
        projected_area_pixels=64.0,
        projected_area_fraction=0.01,
        semidense_support_count=5,
        evl_support_count=7,
        effective_support_count=12.0,
        visibility_score=0.8,
        support_score=0.7,
        deficit_score=0.1,
        score=0.75,
        eligible=True,
        invalid_reason_bitset=0,
        primary_invalid_reason=0,
        selected_rank=0,
        gt_label_valid=gt_label_valid,
        gt_target_row_id=9,
        gt_target_id="gt:9",
        gt_match_iou=0.5,
        gt_match_score=0.5,
        gt_match_status="accepted",
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


def test_target_rows_table_preserves_score_decomposition() -> None:
    row = rollout_panel._target_rows_table((_target_row(),))[0]

    assert row["confidence"] == pytest.approx(0.9)
    assert row["projected_area_px"] == pytest.approx(64.0)
    assert row["semidense_support"] == 5
    assert row["evl_support"] == 7
    assert row["effective_support"] == pytest.approx(12.0)
    assert row["visibility_score"] == pytest.approx(0.8)
    assert row["support_score"] == pytest.approx(0.7)
    assert row["selection_score"] == pytest.approx(0.75)
    assert row["gt_match_score"] == pytest.approx(0.5)


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
        selection_policy="oracle_greedy",
        selected_depth_m=torch.tensor([[1.0, 2.0], [3.0, float("nan")]], dtype=torch.float32),
        selected_depth_valid_mask=torch.tensor([[True, True], [False, True]], dtype=torch.bool),
    )
    rollouts = SimpleNamespace(trajectories=[SimpleNamespace(steps=[step])])

    rows = rollout_panel._live_selected_depth_rows(rollouts)

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
        selection_policy="oracle_greedy",
        selected_depth_m=None,
        selected_depth_valid_mask=None,
    )
    rollouts = SimpleNamespace(trajectories=[SimpleNamespace(steps=[step])])

    rows = rollout_panel._live_selected_depth_rows(rollouts)

    assert rows[0]["available"] is False
    assert "not retained" in str(rows[0]["warning"])


def test_live_depth_target_overlays_project_descriptor_target() -> None:
    step = SimpleNamespace(
        selected_depth_focal_px=(100.0, 100.0),
        selected_depth_principal_point_px=(50.0, 50.0),
        selected_pose_world=PoseTW.from_matrix3x4(torch.eye(3, 4).unsqueeze(0)),
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


def test_format_rollout_option_includes_context_and_nan_beam() -> None:
    reader = _FakeRolloutReader(
        {
            "rollouts/rollout_row_id": np.asarray([0], dtype=np.int64),
            "rollouts/policy_id": np.asarray([0], dtype=np.int32),
            "rollouts/scene_id": np.asarray([0], dtype=np.int32),
            "rollouts/target_row_id": np.asarray([0], dtype=np.int64),
            "rollouts/chain_id": np.asarray([0], dtype=np.int32),
            "rollouts/horizon": np.asarray([1], dtype=np.int16),
            "rollouts/branch_factor": np.asarray([1], dtype=np.int16),
            "rollouts/beam_width": np.asarray([-1], dtype=np.int16),
            "dictionaries/policy": _json_dictionary_array(["random_valid"]),
            "dictionaries/scene": _json_dictionary_array(["81286"]),
        }
    )

    assert stored_rollouts_panel.format_rollout_option(reader, 0) == (
        "0 · scene 81286 · target 0 · random_valid · chain 0 · H=1 · B=1 · beam=NaN"
    )


def test_format_rollout_store_option_includes_schema_validation_and_counts(tmp_path) -> None:
    row = {
        "path": (tmp_path / "rollouts_v1_smoke.zarr").as_posix(),
        "schema_status": "stale",
        "validation_ok": False,
        "observed_rollouts": 18,
        "observed_steps": 54,
        "observed_candidates": 270,
    }

    label = stored_rollouts_panel.format_rollout_store_option(row, root=tmp_path)

    assert label == "rollouts_v1_smoke.zarr · stale · FAILED · R/S/C=18/54/270"


def test_candidate_distribution_frame_coerces_display_fields() -> None:
    audit_df = pd.DataFrame(
        [
            {
                "candidate_row_id": "7",
                "rollout_row_id": 1,
                "step_index": "0",
                "center_x": "1.25",
                "center_y": "2.5",
                "center_z": "3.75",
                "selected": True,
                "actor_action": None,
                "q_train": False,
                "position": None,
                "strategy": "target_bearing_local",
                "mixture": "component_a",
                "invalid_reason": None,
                "motion_yaw_delta_deg": "45.5",
                "target_bearing_yaw_deg": "-32.0",
                "target_root_gain": "0.125",
            }
        ]
    )

    df = stored_rollouts_panel._candidate_distribution_frame(audit_df)

    assert df.loc[0, "candidate_row_id"] == pytest.approx(7.0)
    assert df.loc[0, "center_x"] == pytest.approx(1.25)
    assert bool(df.loc[0, "actor_action"]) is False
    assert df.loc[0, "position"] == "unknown"
    assert df.loc[0, "invalid_reason"] == "unknown"
    assert df.loc[0, "motion_yaw_delta_deg"] == pytest.approx(45.5)


def test_candidate_angle_frame_keeps_available_sources() -> None:
    diagnostics_df = pd.DataFrame(
        {
            "target_bearing_yaw_deg": [-90.0, np.nan, 45.0],
            "motion_yaw_delta_deg": [0.0, 30.0, np.nan],
        }
    )

    angle_df = stored_rollouts_panel._candidate_angle_frame(diagnostics_df)

    assert set(angle_df["angle_source"]) == {"target bearing yaw", "motion yaw delta"}
    assert angle_df["angle_deg"].tolist() == [-90.0, 45.0, 0.0, 30.0]


def test_target_selection_frame_coerces_scores_and_masks() -> None:
    targets = pd.DataFrame(
        [
            {
                "target_row_id": "4",
                "source": None,
                "class": "chair",
                "confidence": "0.9",
                "selection_rank": "1",
                "selection_score": "0.75",
                "target_valid": None,
                "gt_label_valid": True,
                "gt_match_status": None,
                "projected_area_fraction": "0.01",
            }
        ]
    )

    df = stored_rollouts_panel._target_selection_frame(targets)

    assert df.loc[0, "target_row_id"] == pytest.approx(4.0)
    assert df.loc[0, "selection_score"] == pytest.approx(0.75)
    assert bool(df.loc[0, "target_valid"]) is False
    assert bool(df.loc[0, "gt_label_valid"]) is True
    assert df.loc[0, "source"] == "unknown"
    assert df.loc[0, "gt_match_status"] == "unknown"


def test_first_available_numeric_skips_absent_and_empty_columns() -> None:
    df = pd.DataFrame(
        {
            "projected_area_fraction": [np.nan, np.nan],
            "projected_area_pixels": [32.0, np.nan],
        }
    )

    assert (
        stored_rollouts_panel._first_available_numeric(
            df,
            ("effective_support", "projected_area_fraction", "projected_area_pixels"),
        )
        == "projected_area_pixels"
    )
    assert stored_rollouts_panel._first_available_numeric(df, ("missing",)) is None


def test_stored_rollouts_page_exercises_current_schema_features(isolated_path_config, tmp_path) -> None:
    write_rollout_zarr_store(
        isolated_path_config.offline_cache_dir / "current.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=47)[:1],
    )

    app = _stored_rollouts_app(tmp_path).run()

    assert not app.exception
    assert [header.value for header in app.header] == ["Stored Rollout Zarr"]
    assert "Rollout Stores" in [subheader.value for subheader in app.subheader]
    assert "Selected Rollout Row" in [subheader.value for subheader in app.subheader]
    assert _metric_values(app)["Validation"] == "OK"
    assert _metric_values(app)["Rollouts"] == "1"
    assert _metric_values(app)["Steps"] == "1"
    assert _metric_values(app)["Candidates"] == "12"
    assert _metric_values(app)["Discovered stores"] == "1"
    assert _metric_values(app)["Current valid stores"] == "1"
    assert _metric_values(app)["Blocked stores"] == "0"
    assert _metric_values(app)["Observed R/S"] == "1/1"
    assert _metric_values(app)["Q-train candidates"] == "12"
    assert {selectbox.label for selectbox in app.selectbox} >= {
        "rollouts.zarr store",
        "Selected-depth step",
        "Geometry / label metric",
        "Color / split by",
        "Target breakdown",
        "Rollout row",
    }
    assert {text_input.label for text_input in app.text_input} >= {
        "Manual rollouts.zarr path",
        "Rerun inspector config",
        "RRD save directory",
    }
    assert {number_input.label for number_input in app.number_input} >= {
        "Rerun web-viewer port",
        "Rerun gRPC/proxy port",
        "Selected-depth row limit",
        "Candidate audit row limit (0 = all)",
        "Min valid fanout",
    }
    assert {slider.label for slider in app.slider} >= {
        "Dominant invalid fraction",
        "High target score",
        "Max selected step (m)",
    }
    assert {button.label for button in app.button} >= {"Open in Native Rerun", "Open in Rerun Web Viewer"}
    assert len(app.get("plotly_chart")) >= 8
    assert len(app.dataframe) >= 10
    assert not app.error


def test_stored_rollouts_page_keeps_stale_store_diagnostics_visible(isolated_path_config, tmp_path) -> None:
    stale_path = isolated_path_config.offline_cache_dir / "stale.zarr"
    stale_root = zarr.open_group(stale_path, mode="w")
    stale_root.attrs["schema_version"] = "0.6-rollout-core"
    stale_root.create_group("rollouts").create_array("rollout_row_id", data=np.arange(2, dtype=np.int64))
    stale_root.create_group("steps").create_array("step_row_id", data=np.arange(4, dtype=np.int64))
    stale_root.create_group("candidates").create_array("candidate_row_id", data=np.arange(8, dtype=np.int64))

    app = _stored_rollouts_app(tmp_path).run()

    assert not app.exception
    assert _metric_values(app)["Validation"] == "FAILED"
    assert _metric_values(app)["Rollouts"] == "2"
    assert _metric_values(app)["Steps"] == "4"
    assert _metric_values(app)["Candidates"] == "8"
    assert _metric_values(app)["Discovered stores"] == "1"
    assert _metric_values(app)["Current valid stores"] == "0"
    assert _metric_values(app)["Blocked stores"] == "1"
    assert _metric_values(app)["Observed R/S"] == "2/4"
    assert not any(selectbox.label == "Rollout row" for selectbox in app.selectbox)
    assert any("requires a store that passes" in info.value for info in app.info)
    assert any("Unsupported rollout Zarr schema_version" in error.value for error in app.error)


def test_stored_candidate_rows_decode_strategy_and_mixture_names(tmp_path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=37)[:1],
    )
    reader = RolloutZarrStoreReader(result.store_dir)

    rows = stored_rollouts_panel.candidate_rows_for_rollout(reader, 0)

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
        assert kwargs["target_row"] is target
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
        selected_metrics={"rri": 0.75, "target_rri": 0.75},
    )
    trajectory = CounterfactualTrajectory(
        root_pose_world=root_pose,
        steps=[step],
        cumulative_score=0.75,
        cumulative_rri=0.75,
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

    rows = rollout_panel._counterfactual_trajectory_rows(rollouts)

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
        selected_metrics={"target_rri": 0.2},
        metric_vectors={"target_rri": torch.tensor([0.0, 100.0, 0.2, 100.0])},
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

    rows = rollout_panel._trajectory_metric_rows(rollouts)

    assert set(rows.columns).isdisjoint({"fanout_min", "fanout_mean", "fanout_max"})
    assert rows.loc[0, "fanout_q025"] == pytest.approx(np.quantile([0.0, 0.2], 0.025))
    assert rows.loc[0, "fanout_q975"] == pytest.approx(np.quantile([0.0, 0.2], 0.975))
    assert rows.loc[0, "top_target_rri"] == pytest.approx([0.2, 0.0])


def test_valid_step_metric_values_rejects_mask_metric_length_mismatch() -> None:
    step = SimpleNamespace(
        candidates=SimpleNamespace(mask_valid=torch.tensor([True, False, True])),
        metric_vectors={"target_rri": torch.tensor([0.0, 0.1, 0.2, 0.3])},
    )

    with pytest.raises(ValueError, match="Candidate validity mask shape"):
        rollout_panel._valid_step_metric_values(step, "target_rri")


def test_valid_step_metric_values_accepts_compact_valid_vectors() -> None:
    step = SimpleNamespace(
        candidates=SimpleNamespace(mask_valid=torch.tensor([True, False, True, True])),
        metric_vectors={"target_root_gain": torch.tensor([0.5, float("nan"), 0.9])},
    )

    values = rollout_panel._valid_step_metric_values(step, "target_root_gain")

    assert values.tolist() == pytest.approx([0.5, 0.9])


def test_live_step_candidate_score_rows_align_compact_valid_vectors() -> None:
    step = SimpleNamespace(
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
        metric_vectors={"target_root_gain": torch.tensor([0.2, 0.8])},
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
        metric_vectors={"target_rri": torch.tensor([0.3, 100.0, 0.7])},
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
