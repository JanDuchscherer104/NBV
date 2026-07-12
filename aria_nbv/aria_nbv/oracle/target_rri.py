r"""Target-aware Oracle RRI scoring over finite candidate tables.

This module scores valid candidate rows with target-specific point-mesh RRI.
The current generation path samples a privileged GT target task upstream; this
scorer uses its OBB as an oracle/evaluation crop. Missing targets, empty mesh
crops, sparse current support, or unusable depth are expected invalidity cases
and surface as typed `TargetRriInvalidity` outcomes.

Scene RRI may be emitted as a diagnostic from the same candidate point clouds,
but it must not replace target RRI labels in thesis-core rollout stores.

Theory:
    Target-conditioned rollout scoring joins two intentionally separate
    contracts. Candidate generation receives a sanitized target descriptor;
    the scorer receives the full Oracle task to crop evaluation geometry and
    compute target-RRI labels. Candidate scores therefore measure improvement
    for the selected task without exposing GT identity or crop state through
    the descriptor contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING

import torch
from pydantic import Field, field_validator

from ..rendering.candidate_depth_renderer import CandidateDepthRendererConfig
from ..rri_metrics.returns import log_error_gain, root_normalized_gain
from ..utils import BaseConfig, Console, TargetConfig, Verbosity
from ._scoring import PreparedRriScorerConfig, _CandidateRriScoringEngine, _root_error_tensor
from .evidence import (
    OracleEvidenceInvalidReason,
    OracleRriState,
    RriEvaluationPointCloudSource,
    RriRewardMode,
    _OracleEvidenceError,
    canonical_fuse_points,
    crop_mesh_to_obb,
    crop_padded_pointclouds_to_obb,
    crop_points_to_obb,
    target_aabb_from_points,
    target_gt_obb_world,
)
from .labels import OracleCandidateEvaluation, OracleCandidateLabels, RetainedOracleEvidence

if TYPE_CHECKING:
    from efm3d.aria.obb import ObbTW

    from ..data_handling.efm_views import EfmSnippetView
    from ..data_handling.offline.dataset import VinOfflineSample
    from ..oracle.target_selection import TargetCandidateRow
    from ..pose_generation.types import CandidateSamplingResult

TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1 = "gt_obb_oriented_any_vertex_v1"
"""Target crop policy: keep mesh faces with any vertex inside the matched oriented GT OBB."""

SCENE_CROP_POLICY_SNIPPET_EXTENT_V1 = "snippet_occupancy_extent_v1"
"""Scene-RRI crop policy matching the existing snippet occupancy-extent scorer."""


@dataclass(frozen=True, slots=True)
class TargetRriInvalidity:
    """Expected target-scoring failure with a stable semantic reason."""

    reason: OracleEvidenceInvalidReason
    message: str


class TargetRriScorerConfig(TargetConfig["TargetRriScorer"]):
    """Config-as-factory wrapper for target-cropped oracle-RRI rollout scoring."""

    @property
    def target_type(self) -> type["TargetRriScorer"]:
        return TargetRriScorer

    depth: CandidateDepthRendererConfig = Field(default_factory=lambda: CandidateDepthRendererConfig())
    """Depth renderer used once per candidate table before target/scene scoring."""

    oracle: PreparedRriScorerConfig = Field(
        default_factory=lambda: PreparedRriScorerConfig(fusion_voxel_size_m=0.02, fusion_max_points=200_000)
    )
    """Point-mesh oracle metric configuration shared by target and scene RRI."""

    backprojection_stride: int = Field(default=1, ge=1)
    """Pixel stride for backprojecting rendered candidate depths."""

    target_crop_margin_m: float = Field(default=0.0, ge=0.0)
    """Optional symmetric margin applied in GT-OBB local coordinates."""

    min_current_target_points: int = Field(default=1, ge=1)
    """Minimum current observed/support points inside the target crop."""

    include_scene_rri: bool = True
    """Whether to compute diagnostic scene RRI from the same point-cloud batch."""

    eval_point_cloud_source: RriEvaluationPointCloudSource = RriEvaluationPointCloudSource.ASE_GT_DEPTH_ROOT
    """Oracle current/root point-cloud source used for target and scene labels."""

    eval_camera_label: str = "rgb"
    """Camera stream used for ASE-depth root evaluation points."""

    eval_depth_far_m: float | None = None
    """Maximum ASE root depth to retain; defaults to the renderer zfar."""

    eval_fusion_voxel_size_m: float = Field(default=0.02, ge=0.0)
    """Voxel size used to canonical-fuse root and selected-history eval points."""

    eval_fusion_max_points: int | None = Field(default=200_000, ge=1)
    """Maximum retained current-eval points after canonical fusion."""

    target_eval_max_points: int = Field(default=50_000, ge=1)
    """Maximum retained oracle/eval points after target-local crop fusion."""

    reward_mode: RriRewardMode = RriRewardMode.ROOT_NORMALIZED_GAIN
    """Candidate score used for rollout selection."""

    target_crop_policy: str = TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1
    """Explicit target mesh crop policy stored as rollout lineage."""

    scene_crop_policy: str = SCENE_CROP_POLICY_SNIPPET_EXTENT_V1
    """Diagnostic scene-RRI crop policy matching the scene-level scorer."""

    verbosity: Verbosity = Field(default=Verbosity.NORMAL)
    """Console verbosity."""

    is_debug: bool = False
    """Enable debug logging in scorer dependencies."""

    log_timing: bool = False
    """Emit per-call timing diagnostics for rollout evidence generation."""

    _coerce_verbosity = field_validator("verbosity", mode="before")(BaseConfig._coerce_verbosity)

    @field_validator("target_crop_policy")
    @classmethod
    def _known_target_crop_policy(cls, value: str) -> str:
        if value != TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1:
            raise ValueError(f"Unsupported target_crop_policy={value!r}.")
        return value

    @field_validator("scene_crop_policy")
    @classmethod
    def _known_scene_crop_policy(cls, value: str) -> str:
        if value != SCENE_CROP_POLICY_SNIPPET_EXTENT_V1:
            raise ValueError(f"Unsupported scene_crop_policy={value!r}.")
        return value


class TargetRriScorer:
    """Evaluate valid candidates with target-cropped oracle RRI.

    The scorer renders candidate depth, backprojects world-frame point clouds,
    crops current and candidate points to the matched target OBB, crops the mesh
    with the configured policy, and returns target-RRI labels plus audit metrics.
    Invalid target crops abort the target row rather than producing low labels.
    """

    def __init__(
        self,
        config: TargetRriScorerConfig,
        *,
        sample: EfmSnippetView,
        target_sample: "VinOfflineSample",
        target_row: TargetCandidateRow,
    ) -> None:
        self.config = config
        self.sample = sample
        self.target_sample = target_sample
        self.target_row = target_row
        self.console = (
            Console.with_prefix(self.__class__.__name__)
            .set_verbosity(self.config.verbosity)
            .set_debug(self.config.is_debug)
        )
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
        self._target_obb_world: ObbTW | None = None
        self._initial_invalidity: TargetRriInvalidity | None = None
        try:
            self._target_obb_world = target_gt_obb_world(target_row, target_sample)
        except _OracleEvidenceError as exc:
            self._initial_invalidity = TargetRriInvalidity(reason=exc.reason, message=str(exc))

    @property
    def invalidity(self) -> TargetRriInvalidity | None:
        """Return evidence invalidity known before candidate scoring."""

        return self._initial_invalidity

    def __call__(
        self,
        candidates: CandidateSamplingResult,
        state: OracleRriState,
        step_index: int,
    ) -> OracleCandidateEvaluation | TargetRriInvalidity:
        del step_index
        if self._initial_invalidity is not None:
            return self._initial_invalidity
        try:
            return self._score(candidates, state)
        except _OracleEvidenceError as exc:
            return TargetRriInvalidity(reason=exc.reason, message=str(exc))

    def _score(self, candidates: CandidateSamplingResult, state: OracleRriState) -> OracleCandidateEvaluation:
        """Return target labels for a candidate table with valid root evidence."""

        if self.sample.mesh_verts is None or self.sample.mesh_faces is None:
            raise ValueError("TargetRriScorer requires sample.mesh_verts and sample.mesh_faces.")
        if self._target_obb_world is None:
            raise RuntimeError("TargetRriScorer has neither a target OBB nor an initial invalidity outcome.")

        call_start_s = perf_counter()
        render_start_s = perf_counter()
        depths = self._engine.render_candidate_depths(candidates)
        render_s = perf_counter() - render_start_s
        backproject_start_s = perf_counter()
        point_clouds = self._engine.backproject_candidate_points(depths)
        backproject_s = perf_counter() - backproject_start_s
        crop_start_s = perf_counter()
        device = point_clouds.points.device
        dtype = point_clouds.points.dtype
        target_obb = self._target_obb_world.to(device=device, dtype=dtype)
        mesh_verts = self.sample.mesh_verts.to(device=device, dtype=dtype)
        mesh_faces = self.sample.mesh_faces.to(device=device)
        target_mesh_verts, target_mesh_faces = crop_mesh_to_obb(
            mesh_verts,
            mesh_faces,
            target_obb,
            margin_m=self.config.target_crop_margin_m,
        )
        target_extent = target_aabb_from_points(target_mesh_verts, margin_m=self.config.target_crop_margin_m)

        target_points_t = crop_points_to_obb(
            self._engine.current_eval_points(state, device=device, dtype=dtype, max_points=None),
            target_obb,
            margin_m=self.config.target_crop_margin_m,
        )
        target_points_t = canonical_fuse_points(
            target_points_t,
            voxel_size_m=float(self.config.eval_fusion_voxel_size_m),
            max_points=int(self.config.target_eval_max_points),
        )
        if target_points_t.shape[0] < int(self.config.min_current_target_points):
            raise _OracleEvidenceError(
                OracleEvidenceInvalidReason.TARGET_CURRENT_SUPPORT_INSUFFICIENT,
                "Target crop contains too few current points for target-RRI evaluation.",
            )

        target_points_q, target_lengths_q = crop_padded_pointclouds_to_obb(
            point_clouds.points,
            point_clouds.lengths,
            target_obb,
            margin_m=self.config.target_crop_margin_m,
            voxel_size_m=float(self.config.eval_fusion_voxel_size_m),
            max_points=int(self.config.target_eval_max_points),
        )
        crop_s = perf_counter() - crop_start_s

        target_oracle_start_s = perf_counter()
        target_rri = self._engine.score(
            points_t=target_points_t,
            points_q=target_points_q,
            lengths_q=target_lengths_q,
            gt_verts=target_mesh_verts,
            gt_faces=target_mesh_faces,
            extend=target_extent,
        )
        target_oracle_s = perf_counter() - target_oracle_start_s
        target_root_error = state.root_metric("target_root_pm_dist")
        target_root_error_t = _root_error_tensor(
            target_root_error,
            fallback=target_rri.pm_dist_before,
            device=device,
            dtype=dtype,
        )
        target_root_gain = root_normalized_gain(
            target_rri.pm_dist_before,
            target_rri.pm_dist_after,
            target_root_error_t,
        )
        metrics = {
            "rri": target_rri.rri,
            "target_rri": target_rri.rri,
            "target_root_gain": target_root_gain,
            "target_root_pm_dist": target_root_error_t.expand_as(target_rri.rri),
            "target_log_error_gain": log_error_gain(target_rri.pm_dist_before, target_rri.pm_dist_after),
            "target_pm_dist_before": target_rri.pm_dist_before,
            "target_pm_dist_after": target_rri.pm_dist_after,
            "target_pm_acc_before": target_rri.pm_acc_before,
            "target_pm_comp_before": target_rri.pm_comp_before,
            "target_pm_acc_after": target_rri.pm_acc_after,
            "target_pm_comp_after": target_rri.pm_comp_after,
            "target_candidate_support": target_lengths_q.to(device=device, dtype=dtype),
            "target_current_support": torch.full_like(target_rri.rri, float(target_points_t.shape[0])),
        }

        scene_oracle_s = 0.0
        if self.config.include_scene_rri:
            scene_points_t = self._engine.current_eval_points(
                state,
                device=device,
                dtype=dtype,
                max_points=self.config.eval_fusion_max_points,
            )
            scene_oracle_start_s = perf_counter()
            scene_rri = self._engine.score(
                points_t=scene_points_t,
                points_q=point_clouds.points,
                lengths_q=point_clouds.lengths,
                gt_verts=mesh_verts,
                gt_faces=mesh_faces,
                extend=point_clouds.occupancy_bounds,
            )
            scene_oracle_s = perf_counter() - scene_oracle_start_s
            scene_root_error = state.root_metric("scene_root_pm_dist")
            scene_root_error_t = _root_error_tensor(
                scene_root_error,
                fallback=scene_rri.pm_dist_before,
                device=device,
                dtype=dtype,
            )
            metrics.update(
                scene_rri=scene_rri.rri,
                scene_root_gain=root_normalized_gain(
                    scene_rri.pm_dist_before,
                    scene_rri.pm_dist_after,
                    scene_root_error_t,
                ),
                scene_root_pm_dist=scene_root_error_t.expand_as(scene_rri.rri),
                scene_log_error_gain=log_error_gain(scene_rri.pm_dist_before, scene_rri.pm_dist_after),
                scene_pm_dist_before=scene_rri.pm_dist_before,
                scene_pm_dist_after=scene_rri.pm_dist_after,
                scene_pm_acc_before=scene_rri.pm_acc_before,
                scene_pm_comp_before=scene_rri.pm_comp_before,
                scene_pm_acc_after=scene_rri.pm_acc_after,
                scene_pm_comp_after=scene_rri.pm_comp_after,
            )

        if self.config.log_timing:
            self.console.log(
                "Target scorer timing "
                f"valid={int(candidates.mask_valid.sum().item())} "
                f"render_s={render_s:.3f} backproject_s={backproject_s:.3f} crop_s={crop_s:.3f} "
                f"target_oracle_s={target_oracle_s:.3f} scene_oracle_s={scene_oracle_s:.3f} "
                f"total_s={perf_counter() - call_start_s:.3f}",
            )

        scores = target_root_gain if self.config.reward_mode is RriRewardMode.ROOT_NORMALIZED_GAIN else target_rri.rri
        score_label = (
            "target_root_gain" if self.config.reward_mode is RriRewardMode.ROOT_NORMALIZED_GAIN else "target_rri"
        )

        return OracleCandidateEvaluation(
            labels=OracleCandidateLabels(
                scores=scores,
                score_label=score_label,
                metrics=metrics,
                candidate_shell_indices=torch.nonzero(
                    candidates.mask_valid.to(device=scores.device, dtype=torch.bool),
                    as_tuple=False,
                ).reshape(-1),
                provenance="target_rri",
            ),
            evidence=RetainedOracleEvidence(
                candidate_point_clouds_world=point_clouds.points,
                candidate_point_cloud_lengths=point_clouds.lengths,
                target_eval_current_points_world=target_points_t,
                target_eval_candidate_points_world=target_points_q,
                target_eval_candidate_point_lengths=target_lengths_q,
                target_eval_crop_policy=self.config.target_crop_policy,
                target_eval_voxel_size_m=float(self.config.eval_fusion_voxel_size_m),
                target_eval_max_points=int(self.config.target_eval_max_points),
            ),
        )


__all__ = [
    "SCENE_CROP_POLICY_SNIPPET_EXTENT_V1",
    "TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1",
    "TargetRriInvalidity",
    "TargetRriScorer",
    "TargetRriScorerConfig",
]
