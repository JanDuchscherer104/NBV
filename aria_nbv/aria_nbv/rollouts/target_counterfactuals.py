r"""Target-aware oracle RRI scoring for counterfactual rollouts.

This module scores valid candidate rows with target-specific point-mesh RRI.
The actor selects an observed/predicted target record upstream; this scorer then
uses the matched GT OBB only as an oracle/evaluation crop. Missing GT matches,
ambiguous matches, empty mesh crops, sparse current support, or unusable depth
are expected invalidity cases and surface as `TargetRriInvalidError`.

Scene RRI may be emitted as a diagnostic from the same candidate point clouds,
but it must not replace target RRI labels in thesis-core rollout stores.

Theory:
    Target-conditioned rollout scoring joins two intentionally separate
    contracts. The actor-visible selector provides a target row and optional
    target center for candidate sampling; the scorer uses the post-selection GT
    match only to crop oracle/eval geometry and compute target-RRI labels.
    Candidate scores therefore measure improvement for the selected target
    without making GT OBBs, GT mesh crops, or all-candidate renders visible to
    V1 actor policies.
"""

from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING

import torch
from pydantic import Field, field_validator

from ..data_handling._target_selection import target_gt_obb_world
from ..rendering.candidate_depth_renderer import CandidateDepthRendererConfig
from ..rendering.candidate_pointclouds import build_candidate_pointclouds
from ..rri_metrics.eval_pointclouds import (
    RootEvalPointCloud,
    RriEvaluationPointCloudSource,
    RriRewardMode,
    build_root_eval_pointcloud,
    canonical_fuse_points,
)
from ..rri_metrics.oracle_rri import OracleRRIConfig
from ..utils import BaseConfig, Console, TargetConfig, Verbosity
from .counterfactuals import (
    CounterfactualCandidateEvaluation,
    CounterfactualMetricBundle,
    CounterfactualTrajectory,
    _eval_depth_far_m,
    _log_error_gain,
    _root_error_for_metric,
    _root_error_tensor,
    _root_normalized_gain,
    _root_token,
)

if TYPE_CHECKING:
    from efm3d.aria.obb import ObbTW

    from ..data_handling._offline_dataset import VinOfflineSample
    from ..data_handling._target_selection import TargetCandidateRow
    from ..data_handling.efm_views import EfmSnippetView
    from ..pose_generation.types import CandidateSamplingResult

TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1 = "gt_obb_oriented_any_vertex_v1"
"""Target crop policy: keep mesh faces with any vertex inside the matched oriented GT OBB."""

SCENE_CROP_POLICY_SNIPPET_EXTENT_V1 = "snippet_occupancy_extent_v1"
"""Scene-RRI crop policy matching the existing snippet occupancy-extent scorer."""


class TargetRriInvalidError(ValueError):
    """Expected data invalidity that prevents target-RRI labeling for a row."""


class CounterfactualTargetOracleRriScorerConfig(TargetConfig["CounterfactualTargetOracleRriScorer"]):
    """Config-as-factory wrapper for target-cropped oracle-RRI rollout scoring."""

    @property
    def target_type(self) -> type["CounterfactualTargetOracleRriScorer"]:
        """Return the target-aware oracle scorer constructed by this config."""

        return CounterfactualTargetOracleRriScorer

    depth: CandidateDepthRendererConfig = Field(default_factory=lambda: CandidateDepthRendererConfig())
    """Depth renderer used once per candidate table before target/scene scoring."""

    oracle: OracleRRIConfig = Field(
        default_factory=lambda: OracleRRIConfig(fusion_voxel_size_m=0.02, fusion_max_points=200_000)
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


class CounterfactualTargetOracleRriScorer:
    """Evaluate valid candidates with target-cropped oracle RRI.

    The scorer renders candidate depth, backprojects world-frame point clouds,
    crops current and candidate points to the matched target OBB, crops the mesh
    with the configured policy, and returns target-RRI labels plus audit metrics.
    Invalid target crops abort the target row rather than producing low labels.
    """

    def __init__(
        self,
        config: CounterfactualTargetOracleRriScorerConfig,
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
        self._depth_renderer = self.config.depth.setup_target()
        self._oracle = self.config.oracle.setup_target()
        self._root_eval: RootEvalPointCloud | None = None
        self._root_eval_token: tuple[float, ...] | None = None
        try:
            self._target_obb_world = target_gt_obb_world(target_row, target_sample)
        except ValueError as exc:
            raise TargetRriInvalidError(str(exc)) from exc

    def __call__(
        self,
        candidates: CandidateSamplingResult,
        trajectory: CounterfactualTrajectory,
        step_index: int,
    ) -> CounterfactualCandidateEvaluation:
        del step_index

        if self.sample.mesh_verts is None or self.sample.mesh_faces is None:
            raise ValueError("CounterfactualTargetOracleRriScorer requires sample.mesh_verts and sample.mesh_faces.")

        call_start_s = perf_counter()
        render_start_s = perf_counter()
        depths = self._depth_renderer.render(self.sample, candidates)
        render_s = perf_counter() - render_start_s
        backproject_start_s = perf_counter()
        point_clouds = build_candidate_pointclouds(
            self.sample,
            depths,
            stride=self.config.backprojection_stride,
        )
        backproject_s = perf_counter() - backproject_start_s
        crop_start_s = perf_counter()
        device = point_clouds.points.device
        dtype = point_clouds.points.dtype
        target_obb = self._target_obb_world.to(device=device, dtype=dtype)
        mesh_verts = self.sample.mesh_verts.to(device=device, dtype=dtype)
        mesh_faces = self.sample.mesh_faces.to(device=device)
        target_mesh_verts, target_mesh_faces = _crop_mesh_to_obb(
            mesh_verts,
            mesh_faces,
            target_obb,
            margin_m=self.config.target_crop_margin_m,
        )
        target_extent = _aabb_from_points(target_mesh_verts, margin_m=self.config.target_crop_margin_m)

        target_points_t = _crop_points_to_obb(
            self._current_eval_points(trajectory, device=device, dtype=dtype, max_points=None),
            target_obb,
            margin_m=self.config.target_crop_margin_m,
        )
        target_points_t = canonical_fuse_points(
            target_points_t,
            voxel_size_m=float(self.config.eval_fusion_voxel_size_m),
            max_points=int(self.config.target_eval_max_points),
        )
        if target_points_t.shape[0] < int(self.config.min_current_target_points):
            raise TargetRriInvalidError("Target crop contains too few current points for target-RRI evaluation.")

        target_points_q, target_lengths_q = _crop_padded_pointclouds_to_obb(
            point_clouds.points,
            point_clouds.lengths,
            target_obb,
            margin_m=self.config.target_crop_margin_m,
            voxel_size_m=float(self.config.eval_fusion_voxel_size_m),
            max_points=int(self.config.target_eval_max_points),
        )
        crop_s = perf_counter() - crop_start_s

        target_oracle_start_s = perf_counter()
        target_rri = self._oracle.score(
            points_t=target_points_t,
            points_q=target_points_q,
            lengths_q=target_lengths_q,
            gt_verts=target_mesh_verts,
            gt_faces=target_mesh_faces,
            extend=target_extent,
        )
        target_oracle_s = perf_counter() - target_oracle_start_s
        target_root_error = _root_error_for_metric(trajectory, "target_root_pm_dist")
        target_root_error_t = _root_error_tensor(
            target_root_error,
            fallback=target_rri.pm_dist_before,
            device=device,
            dtype=dtype,
        )
        target_root_gain = _root_normalized_gain(
            target_rri.pm_dist_before,
            target_rri.pm_dist_after,
            target_root_error_t,
        )
        metrics = CounterfactualMetricBundle(
            rri=target_rri.rri,
            target_rri=target_rri.rri,
            target_root_gain=target_root_gain,
            target_root_pm_dist=target_root_error_t.expand_as(target_rri.rri),
            target_log_error_gain=_log_error_gain(target_rri.pm_dist_before, target_rri.pm_dist_after),
            target_pm_dist_before=target_rri.pm_dist_before,
            target_pm_dist_after=target_rri.pm_dist_after,
            target_pm_acc_before=target_rri.pm_acc_before,
            target_pm_comp_before=target_rri.pm_comp_before,
            target_pm_acc_after=target_rri.pm_acc_after,
            target_pm_comp_after=target_rri.pm_comp_after,
            target_candidate_support=target_lengths_q.to(device=device, dtype=dtype),
            target_current_support=torch.full_like(target_rri.rri, float(target_points_t.shape[0])),
        )

        scene_oracle_s = 0.0
        if self.config.include_scene_rri:
            scene_points_t = self._current_eval_points(
                trajectory,
                device=device,
                dtype=dtype,
                max_points=self.config.eval_fusion_max_points,
            )
            scene_oracle_start_s = perf_counter()
            scene_rri = self._oracle.score(
                points_t=scene_points_t,
                points_q=point_clouds.points,
                lengths_q=point_clouds.lengths,
                gt_verts=mesh_verts,
                gt_faces=mesh_faces,
                extend=point_clouds.occupancy_bounds,
            )
            scene_oracle_s = perf_counter() - scene_oracle_start_s
            metrics.scene_rri = scene_rri.rri
            scene_root_error = _root_error_for_metric(trajectory, "scene_root_pm_dist")
            scene_root_error_t = _root_error_tensor(
                scene_root_error,
                fallback=scene_rri.pm_dist_before,
                device=device,
                dtype=dtype,
            )
            metrics.scene_root_gain = _root_normalized_gain(
                scene_rri.pm_dist_before,
                scene_rri.pm_dist_after,
                scene_root_error_t,
            )
            metrics.scene_root_pm_dist = scene_root_error_t.expand_as(scene_rri.rri)
            metrics.scene_log_error_gain = _log_error_gain(scene_rri.pm_dist_before, scene_rri.pm_dist_after)
            metrics.scene_pm_dist_before = scene_rri.pm_dist_before
            metrics.scene_pm_dist_after = scene_rri.pm_dist_after
            metrics.scene_pm_acc_before = scene_rri.pm_acc_before
            metrics.scene_pm_comp_before = scene_rri.pm_comp_before
            metrics.scene_pm_acc_after = scene_rri.pm_acc_after
            metrics.scene_pm_comp_after = scene_rri.pm_comp_after

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

        return CounterfactualCandidateEvaluation(
            scores=scores,
            score_label=score_label,
            metrics=metrics,
            candidate_point_clouds_world=point_clouds.points,
            candidate_point_cloud_lengths=point_clouds.lengths,
            target_eval_current_points_world=target_points_t,
            target_eval_candidate_points_world=target_points_q,
            target_eval_candidate_point_lengths=target_lengths_q,
            target_eval_crop_policy=self.config.target_crop_policy,
            target_eval_voxel_size_m=float(self.config.eval_fusion_voxel_size_m),
            target_eval_max_points=int(self.config.target_eval_max_points),
        )

    def _current_eval_points(
        self,
        trajectory: CounterfactualTrajectory,
        *,
        device: torch.device,
        dtype: torch.dtype,
        max_points: int | None,
    ) -> torch.Tensor:
        root_eval = self._root_eval_for(trajectory)
        points_t = root_eval.points_world.to(device=device, dtype=dtype)
        history_points = trajectory.accumulated_points_world()
        if history_points.numel() > 0:
            points_t = torch.cat([points_t, history_points.to(device=device, dtype=dtype)], dim=0)
        return canonical_fuse_points(
            points_t,
            voxel_size_m=float(self.config.eval_fusion_voxel_size_m),
            max_points=max_points,
        )

    def _root_eval_for(self, trajectory: CounterfactualTrajectory) -> RootEvalPointCloud:
        token = _root_token(trajectory)
        if self._root_eval is None or self._root_eval_token != token:
            self._root_eval = build_root_eval_pointcloud(
                self.sample,
                source=self.config.eval_point_cloud_source,
                camera_label=self.config.eval_camera_label,  # type: ignore[arg-type]
                reference_pose_world=trajectory.root_pose_world,
                reference_time_ns=trajectory.root_time_ns,
                reference_trajectory_index=trajectory.root_trajectory_index,
                reference_frame_index=trajectory.root_frame_index,
                stride=int(self.config.backprojection_stride),
                far_m=_eval_depth_far_m(
                    source=self.config.eval_point_cloud_source,
                    configured=self.config.eval_depth_far_m,
                    depth_renderer=self._depth_renderer,
                ),
                voxel_size_m=float(self.config.eval_fusion_voxel_size_m),
                max_points=None,
            )
            self._root_eval_token = token
        return self._root_eval


def _crop_points_to_obb(points: torch.Tensor, obb: ObbTW, *, margin_m: float = 0.0) -> torch.Tensor:
    if points.numel() == 0:
        return points.reshape(0, 3)
    pts = points.reshape(-1, points.shape[-1])[:, :3]
    mask = _points_inside_obb_mask(pts, obb, margin_m=margin_m)
    return pts[mask]


def _crop_padded_pointclouds_to_obb(
    points: torch.Tensor,
    lengths: torch.Tensor,
    obb: ObbTW,
    *,
    margin_m: float = 0.0,
    voxel_size_m: float = 0.0,
    max_points: int | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    cropped: list[torch.Tensor] = []
    lengths_out: list[int] = []
    for row_index in range(points.shape[0]):
        length = int(lengths[row_index].detach().cpu().item())
        row = _crop_points_to_obb(points[row_index, :length, :3], obb, margin_m=margin_m)
        row = canonical_fuse_points(row, voxel_size_m=voxel_size_m, max_points=max_points)
        cropped.append(row)
        lengths_out.append(int(row.shape[0]))
    max_len = max(max(lengths_out), 1)
    output = torch.zeros((points.shape[0], max_len, 3), device=points.device, dtype=points.dtype)
    for row_index, row in enumerate(cropped):
        if row.numel() > 0:
            output[row_index, : row.shape[0], :] = row.to(device=points.device, dtype=points.dtype)
    return output, torch.tensor(lengths_out, device=points.device, dtype=torch.long)


def _crop_mesh_to_obb(
    verts: torch.Tensor,
    faces: torch.Tensor,
    obb: ObbTW,
    *,
    margin_m: float = 0.0,
) -> tuple[torch.Tensor, torch.Tensor]:
    if verts.numel() == 0 or faces.numel() == 0:
        raise TargetRriInvalidError("Target oriented OBB crop requires a non-empty scene mesh.")
    vertex_inside = _points_inside_obb_mask(verts.reshape(-1, 3), obb, margin_m=margin_m)
    face_indices = faces.reshape(-1, 3).to(device=verts.device, dtype=torch.long)
    face_keep = vertex_inside[face_indices].any(dim=1)
    if not bool(face_keep.any().item()):
        raise TargetRriInvalidError("Target oriented OBB crop contains no mesh faces.")
    kept_faces = face_indices[face_keep]
    unique_vertices, inverse = torch.unique(kept_faces.reshape(-1), sorted=True, return_inverse=True)
    cropped_verts = verts[unique_vertices].reshape(-1, 3)
    cropped_faces = inverse.reshape(-1, 3).to(dtype=torch.long)
    return cropped_verts, cropped_faces


def _points_inside_obb_mask(points: torch.Tensor, obb: ObbTW, *, margin_m: float = 0.0) -> torch.Tensor:
    pts = points.reshape(-1, points.shape[-1])[:, :3]
    finite = torch.isfinite(pts).all(dim=-1)
    local = obb.T_world_object.inverse().transform(pts).reshape(-1, 3)
    lower = obb.bb3_min_object.reshape(-1, 3)[0].to(device=pts.device, dtype=pts.dtype) - float(margin_m)
    upper = obb.bb3_max_object.reshape(-1, 3)[0].to(device=pts.device, dtype=pts.dtype) + float(margin_m)
    return finite & torch.all((local >= lower) & (local <= upper), dim=-1)


def _aabb_from_points(points: torch.Tensor, *, margin_m: float = 0.0) -> torch.Tensor:
    pts = points.reshape(-1, points.shape[-1])[:, :3]
    if pts.numel() == 0:
        raise TargetRriInvalidError("Cannot build target crop extent from an empty point set.")
    lower = pts.min(dim=0).values - float(margin_m)
    upper = pts.max(dim=0).values + float(margin_m)
    return torch.stack([lower[0], upper[0], lower[1], upper[1], lower[2], upper[2]]).to(dtype=pts.dtype)


__all__ = [
    "CounterfactualTargetOracleRriScorer",
    "CounterfactualTargetOracleRriScorerConfig",
    "SCENE_CROP_POLICY_SNIPPET_EXTENT_V1",
    "TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1",
    "TargetRriInvalidError",
]
