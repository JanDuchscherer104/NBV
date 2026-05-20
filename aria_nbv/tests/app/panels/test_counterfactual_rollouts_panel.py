"""Tests for the live counterfactual rollout panel helpers."""

# ruff: noqa: S101, SLF001

from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from efm3d.aria import CameraTW
from efm3d.aria.pose import PoseTW

from aria_nbv.app import scene_view
from aria_nbv.app.config import RlPageConfig
from aria_nbv.app.panels import counterfactual_rollouts as rollout_panel
from aria_nbv.app.panels import data as data_panel
from aria_nbv.app.panels import stored_rollouts as stored_rollouts_panel
from aria_nbv.data_handling import TargetCandidateRow
from aria_nbv.pose_generation import (
    CandidateMixtureViewGeneratorConfig,
    CandidateViewGeneratorConfig,
    CounterfactualRolloutResult,
    CounterfactualSelectionPolicy,
    CounterfactualStepResult,
    CounterfactualTargetOracleRriScorerConfig,
    CounterfactualTrajectory,
    ViewDirectionMode,
)
from aria_nbv.pose_generation.types import CandidateSamplingResult
from aria_nbv.rollouts import RolloutZarrStoreReader, write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records


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
        pose_world_object=tuple(float(v) for v in range(12)),
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


def test_active_target_info_documents_actor_visible_and_gt_eval_boundary() -> None:
    info = rollout_panel._ACTIVE_TARGET_INFO

    assert "actor-visible" in info
    assert "GT-only" in info
    assert "target 0" in info
    assert "EFM semantic-id map" in info
    assert "window" in info
    assert "sem=..." in info


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

    monkeypatch.setattr(CounterfactualTargetOracleRriScorerConfig, "setup_target", _fake_setup_target)

    context = rollout_panel._score_context_for_mode(
        scoring_mode=rollout_panel.LiveRolloutScoringMode.TARGET_RRI,
        sample=fake_sample,  # type: ignore[arg-type]
        target=target,
        target_scorer_config=CounterfactualTargetOracleRriScorerConfig(),
        scene_scorer_config=rollout_panel.CounterfactualOracleRriScorerConfig(),
    )

    assert context.score_label == "target_rri"
    assert context.evaluator is fake_evaluator
    assert context.runtime_context is not None
    assert context.runtime_context.target_id == target.target_id
    assert torch.equal(context.runtime_context.target_center_world, torch.tensor([1.0, 2.0, 3.0]))


def test_target_rri_score_context_rejects_gt_invalid_target() -> None:
    with pytest.raises(ValueError, match="not GT-label valid"):
        rollout_panel._score_context_for_mode(
            scoring_mode=rollout_panel.LiveRolloutScoringMode.TARGET_RRI,
            sample=SimpleNamespace(efm_snippet_view=object()),  # type: ignore[arg-type]
            target=_target_row(gt_label_valid=False),
            target_scorer_config=CounterfactualTargetOracleRriScorerConfig(),
            scene_scorer_config=rollout_panel.CounterfactualOracleRriScorerConfig(),
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

    assert fig.layout.title.text == "Valid-candidate target-RRI empirical 95% band"
    assert "CI" not in fig.layout.title.text
    assert any(trace.fill == "tonexty" for trace in fig.data)
    assert any("selected target_root_gain" in str(trace.name) for trace in fig.data)
    assert not any("candidate min" in str(trace.name) for trace in fig.data)
    assert not any("candidate mean" in str(trace.name) for trace in fig.data)
    assert not any("candidate max" in str(trace.name) for trace in fig.data)


def test_rl_page_is_hidden_by_default() -> None:
    assert RlPageConfig().enabled is False
