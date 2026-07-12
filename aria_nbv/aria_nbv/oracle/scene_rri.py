r"""Scene-level Oracle RRI scoring over finite candidate tables."""

from __future__ import annotations

from typing import TYPE_CHECKING

import torch
from pydantic import Field, field_validator

from ..rendering.candidate_depth_renderer import CandidateDepthRendererConfig
from ..rri_metrics.returns import log_error_gain, root_normalized_gain
from ..utils import BaseConfig, TargetConfig, Verbosity
from ._scoring import PreparedRriScorerConfig, _CandidateRriScoringEngine, _root_error_tensor
from .evidence import (
    OracleRriState,
    RriEvaluationPointCloudSource,
    RriRewardMode,
)
from .labels import OracleCandidateEvaluation, OracleCandidateLabels, RetainedOracleEvidence

if TYPE_CHECKING:
    from ..data_handling import EfmSnippetView
    from ..pose_generation.types import CandidateSamplingResult


class SceneRriScorerConfig(TargetConfig["SceneRriScorer"]):
    """Configure scene-level Oracle RRI scoring for finite candidates."""

    @property
    def target_type(self) -> type["SceneRriScorer"]:
        return SceneRriScorer

    depth: CandidateDepthRendererConfig = Field(default_factory=CandidateDepthRendererConfig)
    oracle: PreparedRriScorerConfig = Field(
        default_factory=lambda: PreparedRriScorerConfig(fusion_voxel_size_m=0.02, fusion_max_points=200_000)
    )
    backprojection_stride: int = Field(default=1, ge=1)
    eval_point_cloud_source: RriEvaluationPointCloudSource = RriEvaluationPointCloudSource.ASE_GT_DEPTH_ROOT
    eval_camera_label: str = "rgb"
    eval_depth_far_m: float | None = None
    eval_fusion_voxel_size_m: float = Field(default=0.02, ge=0.0)
    eval_fusion_max_points: int | None = Field(default=200_000, ge=1)
    reward_mode: RriRewardMode = RriRewardMode.ROOT_NORMALIZED_GAIN
    verbosity: Verbosity = Field(default=Verbosity.NORMAL)
    is_debug: bool = False

    _coerce_verbosity = field_validator("verbosity", mode="before")(BaseConfig._coerce_verbosity)


class SceneRriScorer:
    """Prepare scene evidence and score valid candidate views with Oracle RRI."""

    def __init__(self, config: SceneRriScorerConfig, *, sample: EfmSnippetView) -> None:
        self.config = config
        self.sample = sample
        self._engine = _CandidateRriScoringEngine(
            sample=sample,
            depth=config.depth,
            oracle=config.oracle,
            backprojection_stride=config.backprojection_stride,
            eval_point_cloud_source=config.eval_point_cloud_source,
            eval_camera_label=config.eval_camera_label,
            eval_depth_far_m=config.eval_depth_far_m,
            eval_fusion_voxel_size_m=config.eval_fusion_voxel_size_m,
        )

    def __call__(
        self,
        candidates: CandidateSamplingResult,
        state: OracleRriState,
        step_index: int,
    ) -> OracleCandidateEvaluation:
        """Score valid candidates without depending on rollout-owned DTOs."""

        del step_index
        if self.sample.mesh_verts is None or self.sample.mesh_faces is None:
            raise ValueError("SceneRriScorer requires sample.mesh_verts and sample.mesh_faces.")

        point_clouds = self._engine.render_candidate_points(candidates)
        points_t = self._engine.current_eval_points(
            state,
            device=point_clouds.points.device,
            dtype=point_clouds.points.dtype,
            max_points=self.config.eval_fusion_max_points,
        )
        rri = self._engine.score(
            points_t=points_t,
            points_q=point_clouds.points,
            lengths_q=point_clouds.lengths,
            gt_verts=self.sample.mesh_verts.to(device=point_clouds.points.device, dtype=point_clouds.points.dtype),
            gt_faces=self.sample.mesh_faces.to(device=point_clouds.points.device),
            extend=point_clouds.occupancy_bounds,
        )
        root_error = _root_error_tensor(
            state.root_metric("root_pm_dist"),
            fallback=rri.pm_dist_before,
            device=rri.rri.device,
            dtype=rri.rri.dtype,
        )
        root_gain = root_normalized_gain(rri.pm_dist_before, rri.pm_dist_after, root_error)
        log_gain = log_error_gain(rri.pm_dist_before, rri.pm_dist_after)
        scores = root_gain if self.config.reward_mode is RriRewardMode.ROOT_NORMALIZED_GAIN else rri.rri
        score_label = (
            "oracle_root_gain" if self.config.reward_mode is RriRewardMode.ROOT_NORMALIZED_GAIN else "oracle_rri"
        )
        return OracleCandidateEvaluation(
            labels=OracleCandidateLabels(
                scores=scores,
                score_label=score_label,
                metrics={
                    "rri": rri.rri,
                    "root_gain": root_gain,
                    "root_pm_dist": root_error.expand_as(rri.rri),
                    "log_error_gain": log_gain,
                },
                candidate_shell_indices=torch.nonzero(
                    candidates.mask_valid.to(device=scores.device, dtype=torch.bool),
                    as_tuple=False,
                ).reshape(-1),
                provenance="scene_rri",
            ),
            evidence=RetainedOracleEvidence(
                candidate_point_clouds_world=point_clouds.points,
                candidate_point_cloud_lengths=point_clouds.lengths,
            ),
        )


__all__ = ["SceneRriScorer", "SceneRriScorerConfig"]
