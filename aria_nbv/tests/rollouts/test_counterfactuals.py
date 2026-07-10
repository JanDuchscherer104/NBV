"""Tests for multi-step counterfactual pose rollout utilities."""

# ruff: noqa: S101

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

pytest.importorskip("efm3d")

import numpy as np
import plotly.graph_objects as go  # type: ignore[import-untyped]
import torch
import trimesh
from efm3d.aria import CameraTW, PoseTW
from efm3d.aria.obb import ObbTW
from pytorch3d.renderer.cameras import PerspectiveCameras

from aria_nbv.data_handling import CompactObbBlock, TargetCandidateRow
from aria_nbv.data_handling.offline.dataset import VinOfflineOracleBlock, VinOfflineSample
from aria_nbv.pose_generation import (
    CandidateGenerationRuntimeContext,
    CandidateMixtureComponentConfig,
    CandidateMixtureViewGeneratorConfig,
    CandidatePositionMode,
    CandidateSamplingResult,
    CandidateViewGeneratorConfig,
    SamplingStrategy,
    ViewDirectionMode,
)
from aria_nbv.pose_generation.plotting import (
    CounterfactualPlotBuilder,
    plot_counterfactual_paths_simple,
    plot_counterfactual_step_simple,
)
from aria_nbv.rendering import CandidateDepthRendererConfig
from aria_nbv.rendering.candidate_pointclouds import CandidatePointClouds
from aria_nbv.rollouts import (
    CounterfactualCandidateEvaluation,
    CounterfactualPoseGenerator,
    CounterfactualPoseGeneratorConfig,
    CounterfactualSelectionPolicy,
    CounterfactualTargetOracleRriScorerConfig,
    CounterfactualTrajectory,
    RolloutLineage,
    RolloutZarrRecord,
)
from aria_nbv.rollouts.target_counterfactuals import (
    TargetRriInvalidError,
    _crop_mesh_to_obb,
    _crop_padded_pointclouds_to_obb,
    _crop_points_to_obb,
)
from aria_nbv.rri_metrics.eval_pointclouds import RriEvaluationPointCloudSource, RriRewardMode
from aria_nbv.rri_metrics.oracle_rri import OracleRRIConfig
from aria_nbv.utils.data_plotting import get_frustum_segments


def _identity_pose(device: torch.device | str = "cpu") -> PoseTW:
    return PoseTW(
        torch.tensor(
            [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            device=device,
        )
    )


def _dummy_camera(device: torch.device | str = "cpu") -> CameraTW:
    return CameraTW.from_surreal(
        width=torch.tensor([64.0], device=device),
        height=torch.tensor([64.0], device=device),
        type_str="Pinhole",
        params=torch.tensor([[60.0, 60.0, 32.0, 32.0]], device=device),
        gain=torch.zeros(1, device=device),
        exposure_s=torch.zeros(1, device=device),
        valid_radius=torch.tensor([64.0], device=device),
        T_camera_rig=PoseTW.from_matrix3x4(torch.eye(3, 4, device=device).unsqueeze(0)),
    )


def _obb(center: tuple[float, float, float], size: tuple[float, float, float]) -> ObbTW:
    half = torch.tensor(size, dtype=torch.float32) / 2.0
    bb3 = torch.tensor([[-half[0], half[0], -half[1], half[1], -half[2], half[2]]], dtype=torch.float32)
    return ObbTW.from_lmc(
        bb3_object=bb3,
        bb2_rgb=torch.zeros((1, 4), dtype=torch.float32),
        bb2_slaml=torch.zeros((1, 4), dtype=torch.float32),
        bb2_slamr=torch.zeros((1, 4), dtype=torch.float32),
        T_world_object=PoseTW.from_Rt(
            torch.eye(3, dtype=torch.float32).reshape(1, 3, 3),
            torch.tensor([center], dtype=torch.float32),
        ),
        sem_id=torch.zeros(1, dtype=torch.int64),
        inst_id=torch.zeros(1, dtype=torch.int64),
        prob=torch.ones(1, dtype=torch.float32),
    )


def _target_row(*, gt_target_row_id: int) -> TargetCandidateRow:
    return TargetCandidateRow(
        scene_id="scene",
        snippet_id="snippet",
        source="detected_obbs",
        source_index=0,
        target_row_id=1,
        target_id="target",
        sem_id=1,
        inst_id=2,
        class_name="chair",
        confidence=0.9,
        center_world=(0.0, 0.0, 0.0),
        extents=(1.0, 1.0, 1.0),
        pose_world_object=tuple(_identity_pose().tensor().reshape(-1).tolist()),
        relative_pose_reference_object=tuple(_identity_pose().tensor().reshape(-1).tolist()),
        projected_area_pixels=100.0,
        projected_area_fraction=0.1,
        semidense_support_count=10,
        evl_support_count=10,
        effective_support_count=10.0,
        visibility_score=1.0,
        support_score=1.0,
        deficit_score=0.0,
        score=1.0,
        eligible=True,
        invalid_reason_bitset=1,
        primary_invalid_reason=0,
        gt_label_valid=True,
        gt_target_row_id=gt_target_row_id,
        gt_target_id="gt-target",
        gt_match_iou=1.0,
        gt_match_score=1.0,
        gt_match_status="matched",
    )


def _candidate_result_for_pose(pose: PoseTW, *, count: int = 1) -> CandidateSamplingResult:
    if count == 1:
        views = _dummy_camera()
        shell = pose
        mask = torch.tensor([True])
    else:
        views = CameraTW(_dummy_camera().tensor().repeat(count, 1))
        shell = PoseTW(pose.tensor().reshape(1, 12).repeat(count, 1))
        mask = torch.ones(count, dtype=torch.bool)
    return CandidateSamplingResult(
        views=views,
        reference_pose=pose,
        mask_valid=mask,
        masks={},
        shell_poses=shell,
    )


def _mesh_triplet(device: torch.device | str = "cpu") -> tuple[trimesh.Trimesh, torch.Tensor, torch.Tensor]:
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    verts = torch.from_numpy(mesh.vertices).to(dtype=torch.float32, device=device)
    faces = torch.from_numpy(mesh.faces).to(dtype=torch.int64, device=device)
    return mesh, verts, faces


def _plot_snippet() -> SimpleNamespace:
    mesh, _, _ = _mesh_triplet()
    return SimpleNamespace(
        mesh=mesh,
        semidense=None,
        trajectory=SimpleNamespace(
            t_world_rig=PoseTW.from_Rt(
                torch.eye(3, dtype=torch.float32).reshape(1, 3, 3),
                torch.zeros(1, 3, dtype=torch.float32),
            )
        ),
    )


def _target_sample_with_gt_obb(obb: ObbTW) -> VinOfflineSample:
    zero = torch.zeros(1, dtype=torch.float32)
    return VinOfflineSample(
        sample_key="sample",
        scene_id="scene",
        snippet_id="snippet",
        vin_snippet=None,
        oracle=VinOfflineOracleBlock(
            candidate_poses_world_cam=_identity_pose(),
            reference_pose_world_rig=_identity_pose(),
            candidate_count=1,
            rri=zero,
            pm_dist_before=zero,
            pm_dist_after=zero,
            pm_acc_before=zero,
            pm_comp_before=zero,
            pm_acc_after=zero,
            pm_comp_after=zero,
            p3d_cameras=PerspectiveCameras(device="cpu"),
        ),
        sample_index=0,
        split="test",
        efm_snippet_view=None,
        gt_obbs=CompactObbBlock(obbs=obb.tensor(), sem_id_to_name=[]),
    )


def test_target_obb_crop_keeps_oriented_membership_not_axis_aligned_shell() -> None:
    obb = _obb((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    points = torch.tensor(
        [
            [0.25, 0.25, 0.25],
            [0.75, 0.0, 0.0],
            [0.0, -0.75, 0.0],
        ],
        dtype=torch.float32,
    )

    cropped = _crop_points_to_obb(points, obb)

    assert cropped.tolist() == [[0.25, 0.25, 0.25]]


def test_target_obb_mesh_crop_keeps_faces_with_any_inside_vertex() -> None:
    obb = _obb((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    verts = torch.tensor(
        [
            [0.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [0.0, 2.0, 0.0],
            [2.0, 2.0, 0.0],
        ],
        dtype=torch.float32,
    )
    faces = torch.tensor([[0, 1, 2], [1, 2, 3]], dtype=torch.int64)

    cropped_verts, cropped_faces = _crop_mesh_to_obb(verts, faces, obb)

    assert cropped_faces.shape == (1, 3)
    assert cropped_verts.shape == (3, 3)


def test_target_obb_mesh_crop_reports_empty_crop_as_target_invalid() -> None:
    obb = _obb((10.0, 10.0, 10.0), (1.0, 1.0, 1.0))
    mesh, verts, faces = _mesh_triplet()

    with pytest.raises(TargetRriInvalidError, match="no mesh faces"):
        _crop_mesh_to_obb(verts, faces, obb)


def test_target_scorer_computes_target_and_scene_rri_from_one_pointcloud_batch(monkeypatch) -> None:
    class _FakeDepthRenderer:
        render_count = 0

        def render(self, sample, candidates):
            del sample, candidates
            self.render_count += 1
            return object()

    class _FakeOracle:
        calls: list[int] = []

        def score(self, *, points_t, points_q, lengths_q, gt_verts, gt_faces, extend):
            del points_t, points_q, lengths_q, gt_faces, extend
            self.calls.append(int(gt_verts.shape[0]))
            values = torch.full((2,), float(gt_verts.shape[0]), dtype=torch.float32)
            return SimpleNamespace(
                rri=values,
                pm_dist_before=values + 1.0,
                pm_dist_after=values + 2.0,
                pm_acc_before=values + 3.0,
                pm_comp_before=values + 4.0,
                pm_acc_after=values + 5.0,
                pm_comp_after=values + 6.0,
            )

    import aria_nbv.rollouts.target_counterfactuals as target_cf

    renderer = _FakeDepthRenderer()
    oracle = _FakeOracle()
    pointcloud_calls = {"count": 0}

    def _fake_pointclouds(sample, depths, *, stride=1):
        del sample, depths, stride
        pointcloud_calls["count"] += 1
        return CandidatePointClouds(
            points=torch.tensor(
                [
                    [[0.1, 0.1, 0.1], [2.0, 2.0, 2.0]],
                    [[0.2, 0.1, 0.1], [3.0, 3.0, 3.0]],
                ],
                dtype=torch.float32,
            ),
            lengths=torch.tensor([2, 2], dtype=torch.long),
            semidense_points=torch.tensor([[0.0, 0.0, 0.0]], dtype=torch.float32),
            semidense_length=torch.tensor([1], dtype=torch.long),
            occupancy_bounds=torch.tensor([-10.0, 10.0, -10.0, 10.0, -10.0, 10.0], dtype=torch.float32),
        )

    monkeypatch.setattr(target_cf, "build_candidate_pointclouds", _fake_pointclouds)
    monkeypatch.setattr(CandidateDepthRendererConfig, "setup_target", lambda self: renderer)
    monkeypatch.setattr(OracleRRIConfig, "setup_target", lambda self: oracle)
    target_obb = _obb((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    row = _target_row(gt_target_row_id=0)
    zero = torch.zeros(1, dtype=torch.float32)
    target_sample = VinOfflineSample(
        sample_key="sample",
        scene_id="scene",
        snippet_id="snippet",
        vin_snippet=None,
        oracle=VinOfflineOracleBlock(
            candidate_poses_world_cam=_identity_pose(),
            reference_pose_world_rig=_identity_pose(),
            candidate_count=1,
            rri=zero,
            pm_dist_before=zero,
            pm_dist_after=zero,
            pm_acc_before=zero,
            pm_comp_before=zero,
            pm_acc_after=zero,
            pm_comp_after=zero,
            p3d_cameras=PerspectiveCameras(device="cpu"),
        ),
        sample_index=0,
        split="test",
        efm_snippet_view=None,
        gt_obbs=CompactObbBlock(obbs=target_obb.tensor(), sem_id_to_name={}),
    )
    sample = SimpleNamespace(
        mesh_verts=torch.tensor(
            [
                [-0.5, -0.5, 0.0],
                [0.5, -0.5, 0.0],
                [0.0, 0.5, 0.0],
                [3.0, 3.0, 0.0],
                [4.0, 3.0, 0.0],
                [3.0, 4.0, 0.0],
            ],
            dtype=torch.float32,
        ),
        mesh_faces=torch.tensor([[0, 1, 2], [3, 4, 5]], dtype=torch.int64),
        semidense=SimpleNamespace(collapse_points=lambda: torch.tensor([[0.0, 0.0, 0.0]], dtype=torch.float32)),
    )
    candidates = _candidate_result_for_pose(_identity_pose(), count=2)
    cfg = CounterfactualTargetOracleRriScorerConfig(
        min_current_target_points=1,
        include_scene_rri=True,
        eval_point_cloud_source=RriEvaluationPointCloudSource.LEGACY_SEMIDENSE_ROOT,
        reward_mode=RriRewardMode.STATE_RELATIVE_RRI,
    )

    evaluation = cfg.setup_target(sample=sample, target_sample=target_sample, target_row=row)(
        candidates,
        CounterfactualTrajectory(root_pose_world=_identity_pose()),
        0,
    )

    assert renderer.render_count == 1
    assert pointcloud_calls["count"] == 1
    assert oracle.calls == [3, 6]
    assert evaluation.score_label == "target_rri"
    assert evaluation.metric_vectors["target_rri"].tolist() == [3.0, 3.0]
    assert evaluation.metric_vectors["scene_rri"].tolist() == [6.0, 6.0]
    assert evaluation.target_eval_current_points_world is not None
    assert evaluation.target_eval_current_points_world.shape == (1, 3)
    assert evaluation.target_eval_candidate_points_world is not None
    assert evaluation.target_eval_candidate_points_world.shape[0] == 2


def test_target_scorer_crops_current_eval_before_global_scene_cap(monkeypatch) -> None:
    class _FakeDepthRenderer:
        def render(self, sample, candidates):
            del sample, candidates
            return object()

    class _FakeOracle:
        def score(self, *, points_t, points_q, lengths_q, gt_verts, gt_faces, extend):
            del points_q, lengths_q, gt_verts, gt_faces, extend
            assert points_t.shape[0] == 1
            values = torch.ones((1,), dtype=torch.float32)
            return SimpleNamespace(
                rri=values,
                pm_dist_before=values,
                pm_dist_after=values * 0.5,
                pm_acc_before=values,
                pm_comp_before=values,
                pm_acc_after=values,
                pm_comp_after=values,
            )

    import aria_nbv.rollouts.target_counterfactuals as target_cf

    monkeypatch.setattr(CandidateDepthRendererConfig, "setup_target", lambda self: _FakeDepthRenderer())
    monkeypatch.setattr(OracleRRIConfig, "setup_target", lambda self: _FakeOracle())
    monkeypatch.setattr(
        target_cf,
        "build_candidate_pointclouds",
        lambda sample, depths, *, stride=1: CandidatePointClouds(
            points=torch.tensor([[[0.0, 0.0, 0.0]]], dtype=torch.float32),
            lengths=torch.tensor([1], dtype=torch.long),
            semidense_points=torch.empty((0, 3), dtype=torch.float32),
            semidense_length=torch.tensor([0], dtype=torch.long),
            occupancy_bounds=torch.tensor([-1.0, 1.0, -1.0, 1.0, -1.0, 1.0], dtype=torch.float32),
        ),
    )
    target_obb = _obb((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    target_sample = _target_sample_with_gt_obb(target_obb)
    sample = SimpleNamespace(
        mesh_verts=torch.tensor(
            [[-0.5, -0.5, 0.0], [0.5, -0.5, 0.0], [0.0, 0.5, 0.0]],
            dtype=torch.float32,
        ),
        mesh_faces=torch.tensor([[0, 1, 2]], dtype=torch.int64),
        semidense=SimpleNamespace(
            collapse_points=lambda: torch.tensor([[3.0, 3.0, 3.0], [0.0, 0.0, 0.0]], dtype=torch.float32)
        ),
    )
    cfg = CounterfactualTargetOracleRriScorerConfig(
        include_scene_rri=False,
        eval_point_cloud_source=RriEvaluationPointCloudSource.LEGACY_SEMIDENSE_ROOT,
        eval_fusion_max_points=1,
        target_eval_max_points=5,
    )

    evaluation = cfg.setup_target(
        sample=sample, target_sample=target_sample, target_row=_target_row(gt_target_row_id=0)
    )(
        _candidate_result_for_pose(_identity_pose(), count=1),
        CounterfactualTrajectory(root_pose_world=_identity_pose()),
        0,
    )

    assert evaluation.target_eval_current_points_world is not None
    assert evaluation.target_eval_current_points_world.tolist() == [[0.0, 0.0, 0.0]]


def test_target_candidate_crop_applies_target_local_budget_after_obb_crop() -> None:
    obb = _obb((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    points = torch.tensor(
        [
            [[5.0, 5.0, 5.0], [0.01, 0.0, 0.0], [0.02, 0.0, 0.0], [0.9, 0.0, 0.0]],
        ],
        dtype=torch.float32,
    )
    cropped, lengths = _crop_padded_pointclouds_to_obb(
        points,
        torch.tensor([4], dtype=torch.long),
        obb,
        voxel_size_m=0.1,
        max_points=2,
    )

    assert lengths.tolist() == [1]
    assert cropped.shape == (1, 1, 3)


def _default_extent(device: torch.device | str = "cpu") -> torch.Tensor:
    return torch.tensor([-10.0, 10.0, -10.0, 10.0, -10.0, 10.0], dtype=torch.float32, device=device)


def _make_rollout_config(
    *,
    horizon: int = 3,
    branch_factor: int = 1,
    beam_width: int | None = None,
    branch_factor_schedule: list[int] | None = None,
    stochastic_branch_factors: list[int] | None = None,
    stochastic_branch_probabilities: list[float] | None = None,
    selection_policy: CounterfactualSelectionPolicy = CounterfactualSelectionPolicy.FARTHEST_FROM_HISTORY,
    selection_temperature: float = 1.0,
    robust_temperature_logits: bool = True,
    min_sibling_yaw_deg: float = 0.0,
    require_sibling_strategy_diversity: bool = False,
) -> CounterfactualPoseGeneratorConfig:
    candidate_cfg = CandidateViewGeneratorConfig(
        num_samples=16,
        min_radius=0.5,
        max_radius=0.5,
        ensure_collision_free=False,
        ensure_free_space=False,
        min_distance_to_mesh=0.0,
        sampling_strategy=SamplingStrategy.UNIFORM_SPHERE,
        view_max_azimuth_deg=0.0,
        view_max_elevation_deg=0.0,
        verbosity=0,
        seed=0,
        is_debug=True,
    )
    return CounterfactualPoseGeneratorConfig(
        candidate_config=candidate_cfg,
        horizon=horizon,
        branch_factor=branch_factor,
        beam_width=beam_width,
        branch_factor_schedule=branch_factor_schedule,
        stochastic_branch_factors=stochastic_branch_factors,
        stochastic_branch_probabilities=stochastic_branch_probabilities,
        selection_policy=selection_policy,
        selection_temperature=selection_temperature,
        robust_temperature_logits=robust_temperature_logits,
        min_sibling_yaw_deg=min_sibling_yaw_deg,
        require_sibling_strategy_diversity=require_sibling_strategy_diversity,
        verbosity=0,
    )


def _run_rollouts(
    *,
    horizon: int = 3,
    branch_factor: int = 1,
    beam_width: int | None = None,
    branch_factor_schedule: list[int] | None = None,
    stochastic_branch_factors: list[int] | None = None,
    stochastic_branch_probabilities: list[float] | None = None,
    selection_policy: CounterfactualSelectionPolicy = CounterfactualSelectionPolicy.FARTHEST_FROM_HISTORY,
    selection_temperature: float = 1.0,
    robust_temperature_logits: bool = True,
    score_candidates=None,
):
    cfg = _make_rollout_config(
        horizon=horizon,
        branch_factor=branch_factor,
        beam_width=beam_width,
        branch_factor_schedule=branch_factor_schedule,
        stochastic_branch_factors=stochastic_branch_factors,
        stochastic_branch_probabilities=stochastic_branch_probabilities,
        selection_policy=selection_policy,
        selection_temperature=selection_temperature,
        robust_temperature_logits=robust_temperature_logits,
    )
    generator = CounterfactualPoseGenerator(cfg)
    mesh, verts, faces = _mesh_triplet(cfg.candidate_config.device)
    return generator.generate(
        reference_pose=_identity_pose(device=cfg.candidate_config.device),
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        camera_calib_template=_dummy_camera(cfg.candidate_config.device),
        occupancy_extent=_default_extent(cfg.candidate_config.device),
        score_candidates=score_candidates,
    )


def _fake_rri_evaluator(result, trajectory, step_index):
    del trajectory

    valid_poses = result.poses_world_cam()
    centers = valid_poses.t.reshape(-1, 3)
    scores = torch.linspace(0.1, 0.1 * centers.shape[0], centers.shape[0], device=centers.device)
    scores = scores + float(step_index)
    candidate_points = centers.unsqueeze(1).repeat(1, 2, 1)
    lengths = torch.full((centers.shape[0],), 2, dtype=torch.long, device=centers.device)
    return CounterfactualCandidateEvaluation(
        scores=scores,
        score_label="oracle_rri",
        metric_vectors={"rri": scores, "target_rri": scores},
        candidate_point_clouds_world=candidate_points,
        candidate_point_cloud_lengths=lengths,
    )


def _expected_frustum_trace(cam: CameraTW, pose: PoseTW, *, scale: float) -> np.ndarray:
    return np.concatenate(
        [
            np.vstack([segment, np.full((1, 3), np.nan, dtype=float)])
            for segment in get_frustum_segments(cam, pose, scale)
        ],
        axis=0,
    )


def test_counterfactual_rollout_greedy_length_and_step_radius() -> None:
    rollouts = _run_rollouts(horizon=3, branch_factor=1)
    assert len(rollouts.trajectories) == 1

    trajectory = rollouts.trajectories[0]
    assert len(trajectory.steps) == 3

    positions = trajectory.pose_chain_world().t
    step_lengths = torch.linalg.norm(positions[1:] - positions[:-1], dim=1)
    assert torch.allclose(step_lengths, torch.full_like(step_lengths, 0.5), atol=1e-4)


def test_counterfactual_rollout_beam_width_caps_frontier() -> None:
    rollouts = _run_rollouts(horizon=2, branch_factor=3, beam_width=2)
    assert len(rollouts.trajectories) == 2
    assert all(len(traj.steps) == 2 for traj in rollouts.trajectories)


def test_counterfactual_branch_factor_schedule_controls_expansion_per_step() -> None:
    rollouts = _run_rollouts(
        horizon=2,
        branch_factor=3,
        branch_factor_schedule=[2, 1],
        beam_width=3,
        score_candidates=_fake_rri_evaluator,
    )

    assert len(rollouts.trajectories) == 2
    assert all(len(traj.steps) == 2 for traj in rollouts.trajectories)


def test_counterfactual_stochastic_branch_factor_is_seeded_and_overrides_fixed_branch_count() -> None:
    rollouts_a = _run_rollouts(
        horizon=1,
        branch_factor=3,
        stochastic_branch_factors=[1, 2],
        stochastic_branch_probabilities=[0.0, 1.0],
        score_candidates=_fake_rri_evaluator,
    )
    rollouts_b = _run_rollouts(
        horizon=1,
        branch_factor=3,
        stochastic_branch_factors=[1, 2],
        stochastic_branch_probabilities=[0.0, 1.0],
        score_candidates=_fake_rri_evaluator,
    )

    selected_a = [trajectory.steps[0].selected_shell_index for trajectory in rollouts_a.trajectories]
    selected_b = [trajectory.steps[0].selected_shell_index for trajectory in rollouts_b.trajectories]

    assert len(selected_a) == 2
    assert selected_a == selected_b


def test_counterfactual_branch_controls_reject_ambiguous_schedule() -> None:
    with pytest.raises(ValueError, match="either branch_factor_schedule or stochastic_branch_factors"):
        _make_rollout_config(branch_factor_schedule=[1], stochastic_branch_factors=[1])


def test_counterfactual_simple_plots_return_figures() -> None:
    rollouts = _run_rollouts(horizon=2, branch_factor=1)
    trajectory = rollouts.trajectories[0]

    path_fig = plot_counterfactual_paths_simple(rollouts)
    step_fig = plot_counterfactual_step_simple(trajectory, step_index=0)

    assert isinstance(path_fig, go.Figure)
    assert isinstance(step_fig, go.Figure)
    assert len(path_fig.data) >= 2
    assert len(step_fig.data) >= 2


def test_counterfactual_plot_builder_adds_actor_visible_target_obb() -> None:
    rollouts = _run_rollouts(horizon=1, branch_factor=1)
    target = _target_row(gt_target_row_id=0)

    fig = (
        CounterfactualPlotBuilder.from_rollouts(
            _plot_snippet(),  # type: ignore[arg-type]
            rollouts,
            title="target",
        )
        .add_actor_visible_target_obb(target)
        .finalize()
    )

    target_traces = [trace for trace in fig.data if trace.name == "Active target / actor-visible"]
    assert len(target_traces) == 1
    assert np.nanmin(np.asarray(target_traces[0].x, dtype=float)) == pytest.approx(-0.5)
    assert np.nanmax(np.asarray(target_traces[0].x, dtype=float)) == pytest.approx(0.5)


def test_counterfactual_plot_builder_adds_matched_gt_target_obb() -> None:
    rollouts = _run_rollouts(horizon=1, branch_factor=1)
    target = _target_row(gt_target_row_id=0)
    sample = _target_sample_with_gt_obb(_obb((2.0, 0.0, 0.0), (1.0, 1.0, 1.0)))

    fig = (
        CounterfactualPlotBuilder.from_rollouts(
            _plot_snippet(),  # type: ignore[arg-type]
            rollouts,
            title="gt target",
        )
        .add_matched_gt_target_obb(sample, target)
        .finalize()
    )

    target_traces = [trace for trace in fig.data if trace.name == "Matched GT / evaluation crop"]
    assert len(target_traces) == 1
    assert np.nanmin(np.asarray(target_traces[0].x, dtype=float)) == pytest.approx(1.5)
    assert np.nanmax(np.asarray(target_traces[0].x, dtype=float)) == pytest.approx(2.5)


def test_counterfactual_plot_builder_keeps_actor_obb_when_gt_target_invalid() -> None:
    rollouts = _run_rollouts(horizon=1, branch_factor=1)
    target = replace(
        _target_row(gt_target_row_id=0),
        gt_label_valid=False,
        gt_target_row_id=None,
        gt_match_status="unmatched_gt",
    )
    builder = CounterfactualPlotBuilder.from_rollouts(
        _plot_snippet(),  # type: ignore[arg-type]
        rollouts,
        title="invalid target",
    ).add_actor_visible_target_obb(target)

    with pytest.raises(ValueError, match="not GT-label valid"):
        builder.add_matched_gt_target_obb(_target_sample_with_gt_obb(_obb((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))), target)

    fig = builder.finalize()
    assert any(trace.name == "Active target / actor-visible" for trace in fig.data)


def test_counterfactual_selected_pose_world_uses_raw_candidate_pose_without_second_cw90() -> None:
    rollouts = _run_rollouts(horizon=1, branch_factor=1, score_candidates=_fake_rri_evaluator)
    trajectory = rollouts.trajectories[0]
    step = trajectory.steps[0]
    raw_pose_row = step.candidates.poses_world_cam().tensor().reshape(-1, 12)[step.selected_valid_index]

    assert torch.allclose(step.selected_pose_world.tensor().reshape(-1), raw_pose_row)
    assert torch.allclose(trajectory.pose_chain_world().tensor().reshape(-1, 12)[1], raw_pose_row)


def test_counterfactual_selected_frusta_are_colored_and_use_raw_candidate_pose() -> None:
    rollouts = _run_rollouts(horizon=1, branch_factor=1, score_candidates=_fake_rri_evaluator)
    step = rollouts.trajectories[0].steps[0]
    raw_pose = step.candidates.poses_world_cam()[step.selected_valid_index]
    expected = _expected_frustum_trace(step.selected_view, raw_pose, scale=0.6)

    fig = (
        CounterfactualPlotBuilder.from_rollouts(
            _plot_snippet(),  # type: ignore[arg-type]
            rollouts,
            title="selected frusta",
        )
        .add_counterfactual_selected_frusta()
        .finalize()
    )

    frustum_traces = [trace for trace in fig.data if "target_rri=" in str(trace.name)]
    assert frustum_traces
    assert frustum_traces[0].line.color != "crimson"
    actual = np.column_stack([frustum_traces[0].x, frustum_traces[0].y, frustum_traces[0].z]).astype(float)
    np.testing.assert_allclose(actual, expected, equal_nan=True)


def test_counterfactual_step_shell_frusta_are_colored_and_use_raw_candidate_poses() -> None:
    rollouts = _run_rollouts(horizon=1, branch_factor=1, score_candidates=_fake_rri_evaluator)
    step = rollouts.trajectories[0].steps[0]
    expected = _expected_frustum_trace(step.candidates.views[0], step.candidates.poses_world_cam()[0], scale=0.5)

    fig = (
        CounterfactualPlotBuilder.from_rollouts(
            _plot_snippet(),  # type: ignore[arg-type]
            rollouts,
            title="step frusta",
        )
        .add_counterfactual_step_shell(trajectory_index=0, step_index=0, show_frusta=True)
        .finalize()
    )

    frustum_traces = [trace for trace in fig.data if "target_rri=" in str(trace.name)]
    assert frustum_traces
    actual = np.column_stack([frustum_traces[0].x, frustum_traces[0].y, frustum_traces[0].z]).astype(float)
    np.testing.assert_allclose(actual, expected, equal_nan=True)


def test_counterfactual_rollout_tracks_cumulative_rri_and_selected_point_clouds() -> None:
    rollouts = _run_rollouts(horizon=2, branch_factor=1, score_candidates=_fake_rri_evaluator)
    trajectory = rollouts.trajectories[0]

    expected_rri = sum(step.selected_metrics["rri"] for step in trajectory.steps)
    assert trajectory.cumulative_rri == pytest.approx(expected_rri)
    assert trajectory.cumulative_score == pytest.approx(expected_rri)
    assert trajectory.accumulated_points_world().shape == (4, 3)
    assert rollouts.score_label == "oracle_rri"


def test_temperature_softmax_masks_invalid_candidates_and_reproduces_selection() -> None:
    rollouts_a = _run_rollouts(
        horizon=1,
        branch_factor=1,
        selection_policy=CounterfactualSelectionPolicy.TEMPERATURE_SOFTMAX,
        selection_temperature=1.0,
        score_candidates=_fake_rri_evaluator,
    )
    rollouts_b = _run_rollouts(
        horizon=1,
        branch_factor=1,
        selection_policy=CounterfactualSelectionPolicy.TEMPERATURE_SOFTMAX,
        selection_temperature=1.0,
        score_candidates=_fake_rri_evaluator,
    )

    step_a = rollouts_a.trajectories[0].steps[0]
    step_b = rollouts_b.trajectories[0].steps[0]

    assert step_a.selection_policy == CounterfactualSelectionPolicy.TEMPERATURE_SOFTMAX.value
    assert step_a.selection_probabilities is not None
    assert torch.all(step_a.selection_probabilities >= 0)
    assert torch.isclose(step_a.selection_probabilities.sum(), torch.tensor(1.0))
    assert step_a.selected_valid_index == step_b.selected_valid_index
    assert step_a.selected_shell_index == step_b.selected_shell_index

    assert step_a.selection_probabilities.shape[0] == int(step_a.candidates.mask_valid.sum().item())
    assert step_a.selection_temperature == pytest.approx(1.0)
    assert step_a.selected_log_probability is not None


def test_temperature_softmax_branch_factor_samples_distinct_candidates() -> None:
    rollouts = _run_rollouts(
        horizon=1,
        branch_factor=3,
        selection_policy=CounterfactualSelectionPolicy.TEMPERATURE_SOFTMAX,
        selection_temperature=1.0,
        score_candidates=_fake_rri_evaluator,
    )

    selected = [trajectory.steps[0].selected_shell_index for trajectory in rollouts.trajectories]

    assert len(selected) == 3
    assert len(set(selected)) == 3


def test_temperature_softmax_uses_robust_logits_invariant_to_affine_score_scale() -> None:
    def _affine_evaluator(scale: float, offset: float):
        def _evaluate(result, trajectory, step_index):
            del trajectory, step_index
            valid_poses = result.poses_world_cam()
            num_valid = int(valid_poses.t.reshape(-1, 3).shape[0])
            base = torch.linspace(0.1, 1.0, num_valid, device=valid_poses.t.device)
            scores = base * scale + offset
            return CounterfactualCandidateEvaluation(
                scores=scores,
                score_label="affine_score",
                metric_vectors={"rri": scores},
            )

        return _evaluate

    small = _run_rollouts(
        horizon=1,
        branch_factor=1,
        selection_policy=CounterfactualSelectionPolicy.TEMPERATURE_SOFTMAX,
        selection_temperature=0.75,
        score_candidates=_affine_evaluator(1.0, 0.0),
    )
    large = _run_rollouts(
        horizon=1,
        branch_factor=1,
        selection_policy=CounterfactualSelectionPolicy.TEMPERATURE_SOFTMAX,
        selection_temperature=0.75,
        score_candidates=_affine_evaluator(1000.0, 100.0),
    )

    small_step = small.trajectories[0].steps[0]
    large_step = large.trajectories[0].steps[0]

    assert small_step.selected_shell_index == large_step.selected_shell_index
    assert small_step.selection_logits is not None
    assert large_step.selection_logits is not None
    assert torch.allclose(small_step.selection_logits, large_step.selection_logits)
    assert torch.allclose(small_step.selection_probabilities, large_step.selection_probabilities)


def test_greedy_branch_selection_can_require_strategy_diversity() -> None:
    base_cfg = CandidateViewGeneratorConfig(
        num_samples=6,
        oversample_factor=1.0,
        min_radius=0.6,
        max_radius=0.6,
        ensure_collision_free=False,
        ensure_free_space=False,
        min_distance_to_mesh=0.0,
        view_max_azimuth_deg=0.0,
        view_max_elevation_deg=0.0,
        verbosity=0,
        seed=0,
        is_debug=True,
    )
    mixture_cfg = CandidateMixtureViewGeneratorConfig(
        base=base_cfg,
        components=[
            CandidateMixtureComponentConfig(
                name="forward",
                count=3,
                view_mode=ViewDirectionMode.FORWARD_RIG,
                position_mode=CandidatePositionMode.FORWARD_LOCAL,
            ),
            CandidateMixtureComponentConfig(
                name="towards",
                count=3,
                view_mode=ViewDirectionMode.RADIAL_TOWARDS,
                position_mode=CandidatePositionMode.FORWARD_LOCAL,
            ),
            CandidateMixtureComponentConfig(
                name="away",
                count=3,
                view_mode=ViewDirectionMode.RADIAL_AWAY,
                position_mode=CandidatePositionMode.FORWARD_LOCAL,
            ),
        ],
    )
    cfg = CounterfactualPoseGeneratorConfig(
        candidate_config=mixture_cfg,
        horizon=1,
        branch_factor=3,
        selection_policy=CounterfactualSelectionPolicy.ORACLE_GREEDY,
        require_sibling_strategy_diversity=True,
        verbosity=0,
    )
    generator = CounterfactualPoseGenerator(cfg)
    mesh, verts, faces = _mesh_triplet(cfg.candidate_config.device)

    rollouts = generator.generate(
        reference_pose=_identity_pose(device=cfg.candidate_config.device),
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        camera_calib_template=_dummy_camera(cfg.candidate_config.device),
        occupancy_extent=_default_extent(cfg.candidate_config.device),
        score_candidates=_fake_rri_evaluator,
    )

    selected_strategy_ids = [
        int(trajectory.steps[0].candidates.strategy_id[trajectory.steps[0].selected_shell_index].item())
        for trajectory in rollouts.trajectories
    ]
    assert len(selected_strategy_ids) == 3
    assert len(set(selected_strategy_ids)) == 3


def test_counterfactual_selection_ignores_nonfinite_evaluator_scores() -> None:
    def _nonfinite_evaluator(result, trajectory, step_index):
        del trajectory, step_index
        valid_poses = result.poses_world_cam()
        num_valid = int(valid_poses.t.reshape(-1, 3).shape[0])
        scores = torch.linspace(0.0, 1.0, num_valid, device=valid_poses.t.device)
        scores[0] = float("nan")
        if scores.numel() > 1:
            scores[1] = float("inf")
        return CounterfactualCandidateEvaluation(
            scores=scores,
            score_label="stress_score",
            metric_vectors={"rri": torch.nan_to_num(scores, nan=0.0, posinf=0.0)},
        )

    greedy = _run_rollouts(
        horizon=1,
        branch_factor=1,
        selection_policy=CounterfactualSelectionPolicy.ORACLE_GREEDY,
        score_candidates=_nonfinite_evaluator,
    )
    softmax = _run_rollouts(
        horizon=1,
        branch_factor=1,
        selection_policy=CounterfactualSelectionPolicy.TEMPERATURE_SOFTMAX,
        score_candidates=_nonfinite_evaluator,
    )

    greedy_step = greedy.trajectories[0].steps[0]
    softmax_step = softmax.trajectories[0].steps[0]

    assert torch.isfinite(torch.tensor(greedy_step.selection_score))
    assert greedy_step.selection_logits is not None
    assert not torch.isfinite(greedy_step.selection_logits[:2]).any()
    assert softmax_step.selection_probabilities is not None
    assert torch.isfinite(softmax_step.selection_probabilities).all()
    assert softmax_step.selection_probabilities[:2].tolist() == [0.0, 0.0]


def test_counterfactual_path_plot_uses_rri_colorbar_when_available() -> None:
    rollouts = _run_rollouts(horizon=2, branch_factor=1, score_candidates=_fake_rri_evaluator)

    fig = plot_counterfactual_paths_simple(rollouts)

    assert isinstance(fig, go.Figure)
    assert any("rri=" in str(trace.name) for trace in fig.data if getattr(trace, "name", None))
    assert any(
        getattr(getattr(trace, "marker", None), "showscale", False) for trace in fig.data if hasattr(trace, "marker")
    )


def test_candidate_sampling_roundtrip_preserves_valid_pose_order_and_cw90_display_is_read_only() -> None:
    cfg = _make_rollout_config(horizon=1, branch_factor=1)
    generator = CounterfactualPoseGenerator(cfg)
    mesh, verts, faces = _mesh_triplet(cfg.candidate_config.device)
    candidates = generator._candidate_generator.generate(  # noqa: SLF001
        reference_pose=_identity_pose(device=cfg.candidate_config.device),
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        camera_calib_template=_dummy_camera(cfg.candidate_config.device),
        occupancy_extent=_default_extent(cfg.candidate_config.device),
    )
    views_before = candidates.views.tensor().detach().clone()
    reference_before = candidates.reference_pose.tensor().detach().clone()
    poses_before = candidates.poses_world_cam().tensor().detach().clone()

    candidates.get_offsets_and_dirs_ref(display_rotate=True)

    assert torch.equal(candidates.views.tensor(), views_before)
    assert torch.equal(candidates.reference_pose.tensor(), reference_before)
    assert torch.equal(candidates.poses_world_cam().tensor(), poses_before)

    decoded = type(candidates).from_serializable(candidates.to_serializable(), device=torch.device("cpu"))

    assert torch.equal(decoded.mask_valid.cpu(), candidates.mask_valid.cpu())
    assert torch.allclose(decoded.shell_poses.tensor(), candidates.shell_poses.to(device="cpu").tensor())
    assert torch.allclose(decoded.poses_world_cam().tensor(), candidates.poses_world_cam().to(device="cpu").tensor())


def test_candidate_depth_renderer_reports_full_shell_candidate_indices() -> None:
    shell = PoseTW(
        torch.cat(
            [
                torch.eye(3, dtype=torch.float32).reshape(1, 9).repeat(4, 1),
                torch.arange(4, dtype=torch.float32).reshape(4, 1).expand(4, 3),
            ],
            dim=1,
        )
    )
    camera = _dummy_camera()
    camera_data = camera.tensor().repeat(2, 1)
    candidates = CandidateSamplingResult(
        views=CameraTW(camera_data),
        reference_pose=_identity_pose(),
        mask_valid=torch.tensor([False, True, False, True]),
        masks={},
        shell_poses=shell,
    )
    renderer = CandidateDepthRendererConfig(device="cpu", max_candidates_final=2, verbosity=0).setup_target()

    _, _, candidate_indices = renderer._select_candidate_views(candidates)  # noqa: SLF001

    assert candidate_indices.tolist() == [1, 3]


def test_candidate_depth_renderer_renders_selected_compact_index_at_exact_size() -> None:
    mesh, verts, faces = _mesh_triplet()
    sample = SimpleNamespace(
        has_mesh=True,
        mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
    )
    candidates = _candidate_result_for_pose(_identity_pose(), count=2)
    renderer = CandidateDepthRendererConfig(
        device="cpu",
        max_candidates_final=1,
        resolution_scale=0.1,
        output_width_px=240,
        output_height_px=240,
        verbosity=0,
    ).setup_target()

    batch = renderer.render_compact_indices(sample, candidates, [1])

    assert batch.depths.shape == (1, 240, 240)
    assert batch.depths_valid_mask.shape == (1, 240, 240)
    assert batch.candidate_indices.tolist() == [1]
    assert torch.isfinite(batch.depths[batch.depths_valid_mask]).all()
    assert torch.all(batch.depths[batch.depths_valid_mask] > 0.0)


def test_candidate_depth_renderer_rejects_ambiguous_candidate_index_mapping() -> None:
    shell = PoseTW(
        torch.cat(
            [
                torch.eye(3, dtype=torch.float32).reshape(1, 9).repeat(4, 1),
                torch.arange(4, dtype=torch.float32).reshape(4, 1).expand(4, 3),
            ],
            dim=1,
        )
    )
    camera = _dummy_camera()
    candidates = CandidateSamplingResult(
        views=CameraTW(camera.tensor().repeat(3, 1)),
        reference_pose=_identity_pose(),
        mask_valid=torch.tensor([False, True, False, True]),
        masks={},
        shell_poses=shell,
    )
    renderer = CandidateDepthRendererConfig(device="cpu", max_candidates_final=3, verbosity=0).setup_target()

    with pytest.raises(ValueError, match="Candidate views cannot be mapped"):
        renderer._select_candidate_views(candidates)  # noqa: SLF001


def test_rollout_zarr_record_carries_rollout_result_and_lineage() -> None:
    rollouts = _run_rollouts(horizon=2, branch_factor=1, score_candidates=_fake_rri_evaluator)
    record = RolloutZarrRecord(
        result=rollouts,
        rollout_id_prefix="test-rollout",
        lineage=RolloutLineage(
            scene_id="scene",
            snippet_id="snippet",
            candidate_config_hash="candidate-hash",
            oracle_config_hash="oracle-hash",
            random_seed=0,
        ),
    )

    lineage = record.lineage_for_chain(0)
    assert lineage.rollout_id == "test-rollout-000000"
    assert lineage.candidate_config_hash == "candidate-hash"
    assert lineage.rollout_policy == rollouts.selection_policy

    trajectory = rollouts.trajectories[0]
    first_step = trajectory.steps[0]
    candidate_valid = first_step.candidates.mask_valid.detach().cpu()
    valid_indices = torch.nonzero(candidate_valid, as_tuple=False).reshape(-1)
    expected_valid_scores = torch.linspace(
        0.1,
        0.1 * valid_indices.numel(),
        valid_indices.numel(),
        dtype=first_step.selection_scores.dtype,
        device=first_step.selection_scores.device,
    )
    assert torch.isclose(
        first_step.selection_scores[first_step.selected_valid_index],
        torch.tensor(first_step.selection_score, dtype=first_step.selection_scores.dtype),
    )
    assert torch.allclose(first_step.metric_vectors["rri"], expected_valid_scores)
    assert trajectory.cumulative_rri == pytest.approx(sum(step.selected_metrics["rri"] for step in trajectory.steps))


def test_counterfactual_rollout_passes_target_runtime_context_to_mixed_sampler() -> None:
    base_cfg = CandidateViewGeneratorConfig(
        num_samples=4,
        oversample_factor=1.0,
        min_radius=0.5,
        max_radius=0.5,
        ensure_collision_free=False,
        ensure_free_space=False,
        min_distance_to_mesh=0.0,
        view_max_azimuth_deg=0.0,
        view_max_elevation_deg=0.0,
        verbosity=0,
        seed=0,
        is_debug=True,
    )
    cfg = CounterfactualPoseGeneratorConfig(
        candidate_config=CandidateMixtureViewGeneratorConfig(
            base=base_cfg,
            components=[
                CandidateMixtureComponentConfig(name="target", count=4, strategy=ViewDirectionMode.TARGET_POINT)
            ],
        ),
        horizon=1,
        branch_factor=1,
        selection_policy=CounterfactualSelectionPolicy.RANDOM_VALID,
        verbosity=0,
    )
    generator = CounterfactualPoseGenerator(cfg)
    mesh, verts, faces = _mesh_triplet(cfg.candidate_config.device)

    with pytest.raises(ValueError, match="target_center_world"):
        generator.generate(
            reference_pose=_identity_pose(device=cfg.candidate_config.device),
            gt_mesh=mesh,
            mesh_verts=verts,
            mesh_faces=faces,
            camera_calib_template=_dummy_camera(cfg.candidate_config.device),
            occupancy_extent=_default_extent(cfg.candidate_config.device),
        )

    rollouts = generator.generate(
        reference_pose=_identity_pose(device=cfg.candidate_config.device),
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        camera_calib_template=_dummy_camera(cfg.candidate_config.device),
        occupancy_extent=_default_extent(cfg.candidate_config.device),
        candidate_runtime_context=CandidateGenerationRuntimeContext(target_center_world=torch.zeros(3)),
    )

    step = rollouts.trajectories[0].steps[0]
    assert step.candidates.strategy_id is not None
    assert step.candidates.mixture_id is not None
    assert step.candidates.strategy_id.unique().tolist() == [3]
