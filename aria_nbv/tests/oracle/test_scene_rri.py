"""Contract tests for the scene-level Oracle RRI facade."""

from __future__ import annotations

from types import SimpleNamespace

import torch
from efm3d.aria import PoseTW

import aria_nbv.oracle.scene_rri as scene_rri
from aria_nbv.oracle._scoring import PreparedRriScorerConfig
from aria_nbv.oracle.evidence import RriEvaluationPointCloudSource, RriRewardMode
from aria_nbv.oracle.scene_rri import SceneRriScorerConfig
from aria_nbv.rendering.candidate_depth_renderer import CandidateDepthRendererConfig
from aria_nbv.rendering.candidate_pointclouds import CandidatePointClouds


def _identity_pose() -> PoseTW:
    return PoseTW(torch.eye(3, 4, dtype=torch.float32).reshape(-1))


def test_scene_scorer_prepares_evidence_and_returns_rollout_neutral_metrics(monkeypatch) -> None:
    """The facade should preserve scene score semantics without rollout imports."""

    values = torch.tensor([0.25, 0.5], dtype=torch.float32)
    prepared = SimpleNamespace(
        score=lambda **kwargs: SimpleNamespace(
            rri=values,
            pm_dist_before=torch.tensor([4.0, 4.0]),
            pm_dist_after=torch.tensor([3.0, 2.0]),
        )
    )
    monkeypatch.setattr(PreparedRriScorerConfig, "setup_target", lambda self: prepared)
    monkeypatch.setattr(
        CandidateDepthRendererConfig,
        "setup_target",
        lambda self: SimpleNamespace(render=lambda sample, candidates: object()),
    )
    monkeypatch.setattr(
        scene_rri._CandidateRriScoringEngine,
        "backproject_candidate_points",
        lambda self, depths: CandidatePointClouds(
            points=torch.zeros((2, 3, 3), dtype=torch.float32),
            lengths=torch.tensor([3, 2], dtype=torch.long),
            semidense_points=torch.empty((0, 3), dtype=torch.float32),
            semidense_length=torch.tensor([0], dtype=torch.long),
            occupancy_bounds=torch.tensor([-1.0, 1.0, -1.0, 1.0, -1.0, 1.0]),
        ),
    )
    sample = SimpleNamespace(
        mesh_verts=torch.zeros((3, 3), dtype=torch.float32),
        mesh_faces=torch.tensor([[0, 1, 2]], dtype=torch.long),
        semidense=SimpleNamespace(collapse_points=lambda: torch.tensor([[0.0, 0.0, 0.0]])),
    )
    state = SimpleNamespace(
        root_pose_world=_identity_pose(),
        root_time_ns=None,
        root_trajectory_index=None,
        root_frame_index=None,
        accumulated_points_world=lambda: torch.empty((0, 3), dtype=torch.float32),
        root_metric=lambda name: 8.0 if name == "root_pm_dist" else None,
    )
    scorer = SceneRriScorerConfig(
        eval_point_cloud_source=RriEvaluationPointCloudSource.LEGACY_SEMIDENSE_ROOT,
        reward_mode=RriRewardMode.ROOT_NORMALIZED_GAIN,
    ).setup_target(sample=sample)

    candidates = SimpleNamespace(mask_valid=torch.ones(2, dtype=torch.bool))
    evaluation = scorer(candidates, state, 0)

    assert evaluation.labels.score_label == "oracle_root_gain"
    assert torch.allclose(evaluation.labels.scores, torch.tensor([0.125, 0.25]))
    assert evaluation.labels.metrics["rri"].tolist() == [0.25, 0.5]
    assert evaluation.labels.metrics["root_pm_dist"].tolist() == [8.0, 8.0]
    assert evaluation.evidence.candidate_point_cloud_lengths.tolist() == [3, 2]


def test_scene_scorer_config_preserves_nested_oracle_field_name() -> None:
    """The ownership move must not rename serialized scorer configuration."""

    dumped = SceneRriScorerConfig().model_dump()

    assert "oracle" in dumped
    assert "prepared_rri" not in dumped
