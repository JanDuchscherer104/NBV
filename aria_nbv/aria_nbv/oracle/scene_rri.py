r"""Scene-level Oracle RRI scoring over finite candidate tables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import torch
from pydantic import Field, field_validator

from ..rendering.candidate_depth_renderer import CandidateDepthRendererConfig
from ..rendering.candidate_pointclouds import build_candidate_pointclouds
from ..rri_metrics.returns import log_error_gain, root_normalized_gain
from ..utils import BaseConfig, TargetConfig, Verbosity
from ._scoring import PreparedRriScorerConfig, _root_error_tensor
from .evidence import (
    RootEvalPointCloud,
    RriEvaluationPointCloudSource,
    RriRewardMode,
    _eval_depth_far_m,
    _root_evidence_token,
    build_root_eval_pointcloud,
    canonical_fuse_points,
)

if TYPE_CHECKING:
    from efm3d.aria.pose import PoseTW

    from ..data_handling import EfmSnippetView
    from ..pose_generation.types import CandidateSamplingResult


class SceneRriState(Protocol):
    """Minimal trajectory state consumed by scene-level Oracle scoring."""

    root_pose_world: PoseTW
    root_time_ns: int | None
    root_trajectory_index: int | None
    root_frame_index: int | None

    @property
    def root_pm_dist(self) -> float | None:
        """Return the first finite scene root point-mesh distance, if known."""

    def accumulated_points_world(self) -> torch.Tensor:
        """Return selected-history point clouds in world coordinates."""


@dataclass(frozen=True, slots=True)
class SceneRriEvaluation:
    """Scene scorer output before rollout-specific replay adaptation."""

    scores: torch.Tensor
    score_label: str
    metric_vectors: dict[str, torch.Tensor]
    candidate_point_clouds_world: torch.Tensor
    candidate_point_cloud_lengths: torch.Tensor


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
        self._depth_renderer = self.config.depth.setup_target()
        self._prepared_rri = self.config.oracle.setup_target()
        self._root_eval: RootEvalPointCloud | None = None
        self._root_eval_token: tuple[float, ...] | None = None

    def __call__(
        self,
        candidates: CandidateSamplingResult,
        state: SceneRriState,
        step_index: int,
    ) -> SceneRriEvaluation:
        """Score valid candidates without depending on rollout-owned DTOs."""

        del step_index
        if self.sample.mesh_verts is None or self.sample.mesh_faces is None:
            raise ValueError("SceneRriScorer requires sample.mesh_verts and sample.mesh_faces.")

        depths = self._depth_renderer.render(self.sample, candidates)
        point_clouds = build_candidate_pointclouds(
            self.sample,
            depths,
            stride=self.config.backprojection_stride,
        )
        points_t = self._current_eval_points(
            state,
            device=point_clouds.points.device,
            dtype=point_clouds.points.dtype,
        )
        rri = self._prepared_rri.score(
            points_t=points_t,
            points_q=point_clouds.points,
            lengths_q=point_clouds.lengths,
            gt_verts=self.sample.mesh_verts.to(device=point_clouds.points.device, dtype=point_clouds.points.dtype),
            gt_faces=self.sample.mesh_faces.to(device=point_clouds.points.device),
            extend=point_clouds.occupancy_bounds,
        )
        root_error = _root_error_tensor(
            state.root_pm_dist,
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
        return SceneRriEvaluation(
            scores=scores,
            score_label=score_label,
            metric_vectors={
                "rri": rri.rri,
                "root_gain": root_gain,
                "root_pm_dist": root_error.expand_as(rri.rri),
                "log_error_gain": log_gain,
            },
            candidate_point_clouds_world=point_clouds.points,
            candidate_point_cloud_lengths=point_clouds.lengths,
        )

    def _current_eval_points(
        self,
        state: SceneRriState,
        *,
        device: torch.device,
        dtype: torch.dtype,
    ) -> torch.Tensor:
        root_eval = self._root_eval_for(state)
        points_t = root_eval.points_world.to(device=device, dtype=dtype)
        history_points = state.accumulated_points_world()
        if history_points.numel() > 0:
            points_t = torch.cat([points_t, history_points.to(device=device, dtype=dtype)], dim=0)
        return canonical_fuse_points(
            points_t,
            voxel_size_m=float(self.config.eval_fusion_voxel_size_m),
            max_points=self.config.eval_fusion_max_points,
        )

    def _root_eval_for(self, state: SceneRriState) -> RootEvalPointCloud:
        token = _root_evidence_token(
            state.root_pose_world,
            root_time_ns=state.root_time_ns,
            root_trajectory_index=state.root_trajectory_index,
            root_frame_index=state.root_frame_index,
        )
        if self._root_eval is None or self._root_eval_token != token:
            self._root_eval = build_root_eval_pointcloud(
                self.sample,
                source=self.config.eval_point_cloud_source,
                camera_label=self.config.eval_camera_label,  # type: ignore[arg-type]
                reference_pose_world=state.root_pose_world,
                reference_time_ns=state.root_time_ns,
                reference_trajectory_index=state.root_trajectory_index,
                reference_frame_index=state.root_frame_index,
                stride=int(self.config.backprojection_stride),
                far_m=_eval_depth_far_m(
                    source=self.config.eval_point_cloud_source,
                    configured=self.config.eval_depth_far_m,
                    depth_renderer=self._depth_renderer,
                ),
                voxel_size_m=float(self.config.eval_fusion_voxel_size_m),
                max_points=self.config.eval_fusion_max_points,
            )
            self._root_eval_token = token
        return self._root_eval


__all__ = ["SceneRriEvaluation", "SceneRriScorer", "SceneRriScorerConfig", "SceneRriState"]
