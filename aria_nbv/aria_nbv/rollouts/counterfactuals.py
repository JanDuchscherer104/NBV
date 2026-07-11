r"""Bounded counterfactual pose rollout utilities.

Rollouts regenerate finite candidate tables at each step from the updated pose,
history, and remaining budget. The candidate generator may be single-family or
mixed, but the selected action must satisfy the actor-valid mask. Oracle scores
are supervision/evaluation fields; actor-visible replay rows retain poses,
masks, candidate provenance, and selected-action lineage.

The first thesis-core use is deterministic oracle lookahead and replay data for
finite-candidate value learning. Online simulator training and continuous action
control are outside this module's current contract.

Theory:
    Rollout policies operate over valid finite candidate rows. Heuristic
    policies score distance from history or the current reference; random
    policies sample uniformly over eligible valid rows; oracle policies consume
    evaluator scores such as target root gain. Temperature-softmax selection
    uses robust logits

    $$
    \ell_i =
    \frac{s_i-\operatorname{median}(s)}
         {\operatorname{IQR}(s)\tau},
    $$

    with a standard-deviation fallback for tiny candidate sets, followed by a
    masked softmax over valid candidates. Diversity guards may require sibling
    distance, yaw separation, target-bearing separation, and strategy diversity
    before branches are admitted into the rollout tree. Branch schedules control
    how many sibling transitions are retained per rollout depth.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from math import radians
from time import perf_counter
from typing import TYPE_CHECKING

import torch
from efm3d.aria.pose import PoseTW
from pydantic import Field, field_validator, model_validator

from ..oracle.scene_rri import SceneRriEvaluation
from ..pose_generation.candidate_generation import CandidateViewGenerator, CandidateViewGeneratorConfig
from ..pose_generation.candidate_mixture import (  # noqa: TC001 - Pydantic config field.
    CandidateMixtureViewGeneratorConfig,
)
from ..pose_generation.types import CandidateGenerationRuntimeContext, CandidateSamplingResult
from ..pose_generation.utils import ensure_unbatched_pose
from ..utils import BaseConfig, Console, TargetConfig, Verbosity
from ..utils.frames import rotate_yaw_cw90

if TYPE_CHECKING:
    import trimesh
    from efm3d.aria.camera import CameraTW

    from ..data_handling import EfmSnippetView
    from ..pose_generation.candidate_mixture import CandidateMixtureViewGenerator


def _pose_row(pose: PoseTW) -> torch.Tensor:
    return ensure_unbatched_pose(pose).tensor().reshape(1, -1)


def _pose_batch_len(poses: PoseTW) -> int:
    tensor = poses.tensor()
    return 1 if tensor.ndim == 1 else int(tensor.shape[0])


def _pose_at(poses: PoseTW, index: int) -> PoseTW:
    if _pose_batch_len(poses) == 1:
        if index != 0:
            raise IndexError(f"Pose batch has length 1, cannot index {index}.")
        return ensure_unbatched_pose(poses)
    return ensure_unbatched_pose(poses[index])


def _exact_pose_index(poses: PoseTW, pose: PoseTW) -> int | None:
    pose_rows = poses.tensor().reshape(-1, 12)
    query = ensure_unbatched_pose(pose).tensor().reshape(1, 12).to(device=pose_rows.device, dtype=pose_rows.dtype)
    matches = torch.isclose(pose_rows, query, atol=1e-5, rtol=1e-5).all(dim=1)
    indices = torch.nonzero(matches, as_tuple=False).reshape(-1)
    if indices.numel() == 0:
        return None
    return int(indices[0].detach().cpu().item())


def _time_value(time_ns: torch.Tensor, index: int) -> int:
    times = time_ns.reshape(-1)
    safe_index = max(0, min(int(index), int(times.numel()) - 1))
    return int(times[safe_index].detach().cpu().item())


def _root_error_for_metric(trajectory: "CounterfactualTrajectory", key: str) -> float | None:
    for step in trajectory.steps:
        value = step.selected_metrics.get(key)
        if value is not None and bool(torch.isfinite(torch.tensor(float(value))).item()):
            return float(value)
    return None


def _robust_temperature_logits(*, scores: torch.Tensor, temperature: float) -> torch.Tensor:
    """Return median/IQR-normalized logits for temperature-softmax selection."""

    logits = torch.full_like(scores, float("nan"))
    finite = torch.isfinite(scores)
    if not bool(finite.any().item()):
        return logits
    finite_scores = scores[finite]
    center = torch.median(finite_scores)
    if finite_scores.numel() >= 4:
        q1 = torch.quantile(finite_scores, 0.25)
        q3 = torch.quantile(finite_scores, 0.75)
        scale = (q3 - q1).abs()
    else:
        scale = torch.std(finite_scores, unbiased=False)
    scale = scale.clamp_min(torch.finfo(scores.dtype).eps)
    logits[finite] = (finite_scores - center) / (scale * float(temperature))
    return logits


def _valid_diversity_metadata(
    *,
    candidates: CandidateSamplingResult,
    valid_poses: PoseTW,
) -> _CandidateDiversityMetadata:
    """Build valid-row metadata aligned with ``valid_poses``."""

    shell_indices = candidates.candidate_shell_indices(device=valid_poses.t.device)
    yaw_rad = _pose_yaw_rad(valid_poses)
    strategy_id = None
    if candidates.strategy_id is not None:
        strategy_id = candidates.strategy_id.to(device=valid_poses.t.device, dtype=torch.long).reshape(-1)[
            shell_indices
        ]
    target_bearing = candidates.extras.get("target_bearing_yaw_rad")
    target_bearing_yaw_rad = None
    if torch.is_tensor(target_bearing):
        target_bearing_yaw_rad = target_bearing.to(device=valid_poses.t.device, dtype=valid_poses.t.dtype).reshape(-1)[
            shell_indices
        ]
    return _CandidateDiversityMetadata(
        yaw_rad=yaw_rad,
        strategy_id=strategy_id,
        target_bearing_yaw_rad=target_bearing_yaw_rad,
    )


def _pose_yaw_rad(poses: PoseTW) -> torch.Tensor:
    """Return horizontal yaw of each pose's forward axis."""

    forward = poses.R.reshape(-1, 3, 3)[:, :, 2]
    return torch.atan2(forward[:, 0], forward[:, 2])


def _angular_separation(value: torch.Tensor, selected: list[torch.Tensor]) -> torch.Tensor:
    """Return smallest circular distance from ``value`` to selected angles."""

    if not selected:
        return torch.tensor(float("inf"), device=value.device, dtype=value.dtype)
    selected_t = torch.stack(selected).to(device=value.device, dtype=value.dtype)
    delta = torch.atan2(torch.sin(value - selected_t), torch.cos(value - selected_t)).abs()
    return delta.min()


def _circular_min_delta(values: torch.Tensor, selected: list[torch.Tensor]) -> torch.Tensor:
    """Return per-value smallest circular distance to selected angles."""

    if not selected:
        return torch.full_like(values, float("inf"))
    selected_t = torch.stack(selected).to(device=values.device, dtype=values.dtype)
    delta = torch.atan2(
        torch.sin(values.reshape(-1, 1) - selected_t.reshape(1, -1)),
        torch.cos(values.reshape(-1, 1) - selected_t.reshape(1, -1)),
    ).abs()
    return delta.min(dim=1).values


def _append_diversity_selection(
    *,
    index: int,
    metadata: _CandidateDiversityMetadata,
    selected_yaws: list[torch.Tensor],
    selected_strategies: list[int],
    selected_target_bearings: list[torch.Tensor],
) -> None:
    """Record metadata for an already selected sibling branch."""

    selected_yaws.append(metadata.yaw_rad[index])
    if metadata.strategy_id is not None:
        selected_strategies.append(int(metadata.strategy_id[index].detach().cpu().item()))
    if metadata.target_bearing_yaw_rad is not None:
        selected_target_bearings.append(metadata.target_bearing_yaw_rad[index])


class CounterfactualSelectionPolicy(StrEnum):
    """Built-in policies used to rank valid candidates during rollout expansion."""

    FARTHEST_FROM_HISTORY = "farthest_from_history"
    FARTHEST_FROM_REFERENCE = "farthest_from_reference"
    RANDOM = "random"
    RANDOM_VALID = "random_valid"
    ORACLE_GREEDY = "oracle_greedy"
    TEMPERATURE_SOFTMAX = "temperature_softmax"


@dataclass(slots=True)
class CounterfactualSelectionRecord:
    """Selected valid-candidate index plus the distribution used to draw it."""

    valid_index: int
    logits: torch.Tensor
    probabilities: torch.Tensor
    log_probabilities: torch.Tensor
    entropy: float
    selected_log_probability: float


@dataclass(frozen=True, slots=True)
class _CandidateDiversityMetadata:
    """Optional valid-candidate metadata used by branch diversity guards."""

    yaw_rad: torch.Tensor
    strategy_id: torch.Tensor | None = None
    target_bearing_yaw_rad: torch.Tensor | None = None


@dataclass(slots=True)
class CounterfactualMetricBundle:
    """Typed per-valid-candidate metrics emitted by rollout evaluators."""

    rri: torch.Tensor | None = None
    root_gain: torch.Tensor | None = None
    root_pm_dist: torch.Tensor | None = None
    log_error_gain: torch.Tensor | None = None
    target_rri: torch.Tensor | None = None
    target_root_gain: torch.Tensor | None = None
    target_root_pm_dist: torch.Tensor | None = None
    target_log_error_gain: torch.Tensor | None = None
    scene_rri: torch.Tensor | None = None
    scene_root_gain: torch.Tensor | None = None
    scene_root_pm_dist: torch.Tensor | None = None
    scene_log_error_gain: torch.Tensor | None = None
    target_pm_dist_before: torch.Tensor | None = None
    target_pm_dist_after: torch.Tensor | None = None
    target_pm_acc_before: torch.Tensor | None = None
    target_pm_comp_before: torch.Tensor | None = None
    target_pm_acc_after: torch.Tensor | None = None
    target_pm_comp_after: torch.Tensor | None = None
    target_candidate_support: torch.Tensor | None = None
    target_current_support: torch.Tensor | None = None
    scene_pm_dist_before: torch.Tensor | None = None
    scene_pm_dist_after: torch.Tensor | None = None
    scene_pm_acc_before: torch.Tensor | None = None
    scene_pm_comp_before: torch.Tensor | None = None
    scene_pm_acc_after: torch.Tensor | None = None
    scene_pm_comp_after: torch.Tensor | None = None

    @classmethod
    def from_vectors(cls, vectors: Mapping[str, torch.Tensor] | None) -> "CounterfactualMetricBundle":
        """Build a typed metric bundle from legacy or test vector mappings."""

        if not vectors:
            return cls()
        names = cls.__dataclass_fields__
        values = {name: vectors[name] for name in names if name in vectors}
        return cls(**values)

    def validate(self, *, num_valid: int, device: torch.device, dtype: torch.dtype) -> "CounterfactualMetricBundle":
        """Normalize all present metric vectors and verify valid-candidate length."""

        values: dict[str, torch.Tensor | None] = {}
        for name in self.__dataclass_fields__:
            metric = getattr(self, name)
            if metric is None:
                values[name] = None
                continue
            tensor = torch.as_tensor(metric, device=device, dtype=dtype).reshape(-1)
            if tensor.shape[0] != num_valid:
                raise ValueError(
                    f"Counterfactual evaluator metric '{name}' must return {num_valid} values, got {tensor.shape[0]}.",
                )
            values[name] = tensor
        return CounterfactualMetricBundle(**values)

    def as_vectors(self) -> dict[str, torch.Tensor]:
        """Return present metrics as name-to-vector mapping for trace serialization."""

        return {name: value for name in self.__dataclass_fields__ if (value := getattr(self, name)) is not None}


@dataclass(init=False, slots=True)
class CounterfactualCandidateEvaluation:
    """Structured per-valid-candidate rollout scores and optional diagnostics."""

    scores: torch.Tensor
    score_label: str
    metrics: CounterfactualMetricBundle
    candidate_point_clouds_world: torch.Tensor | None
    candidate_point_cloud_lengths: torch.Tensor | None
    target_eval_current_points_world: torch.Tensor | None
    target_eval_candidate_points_world: torch.Tensor | None
    target_eval_candidate_point_lengths: torch.Tensor | None
    target_eval_crop_policy: str | None
    target_eval_voxel_size_m: float | None
    target_eval_max_points: int | None

    def __init__(
        self,
        *,
        scores: torch.Tensor,
        score_label: str = "score",
        metrics: CounterfactualMetricBundle | None = None,
        metric_vectors: Mapping[str, torch.Tensor] | None = None,
        candidate_point_clouds_world: torch.Tensor | None = None,
        candidate_point_cloud_lengths: torch.Tensor | None = None,
        target_eval_current_points_world: torch.Tensor | None = None,
        target_eval_candidate_points_world: torch.Tensor | None = None,
        target_eval_candidate_point_lengths: torch.Tensor | None = None,
        target_eval_crop_policy: str | None = None,
        target_eval_voxel_size_m: float | None = None,
        target_eval_max_points: int | None = None,
    ) -> None:
        self.scores = scores
        self.score_label = score_label
        self.metrics = metrics if metrics is not None else CounterfactualMetricBundle.from_vectors(metric_vectors)
        self.candidate_point_clouds_world = candidate_point_clouds_world
        self.candidate_point_cloud_lengths = candidate_point_cloud_lengths
        self.target_eval_current_points_world = target_eval_current_points_world
        self.target_eval_candidate_points_world = target_eval_candidate_points_world
        self.target_eval_candidate_point_lengths = target_eval_candidate_point_lengths
        self.target_eval_crop_policy = target_eval_crop_policy
        self.target_eval_voxel_size_m = target_eval_voxel_size_m
        self.target_eval_max_points = target_eval_max_points

    @property
    def metric_vectors(self) -> dict[str, torch.Tensor]:
        """Return present metric vectors by stable metric name."""

        return self.metrics.as_vectors()

    def validate(
        self,
        *,
        num_valid: int,
        device: torch.device,
        dtype: torch.dtype,
    ) -> "CounterfactualCandidateEvaluation":
        """Normalize score vectors and ensure they align with valid candidates."""

        scores = torch.as_tensor(self.scores, device=device, dtype=dtype).reshape(-1)
        if scores.shape[0] != num_valid:
            raise ValueError(f"Counterfactual evaluator must return {num_valid} scores, got {scores.shape[0]}.")

        metrics = self.metrics.validate(num_valid=num_valid, device=device, dtype=dtype)

        candidate_point_clouds_world = self.candidate_point_clouds_world
        candidate_point_cloud_lengths = self.candidate_point_cloud_lengths
        if candidate_point_clouds_world is not None:
            candidate_point_clouds_world = torch.as_tensor(candidate_point_clouds_world, device=device, dtype=dtype)
            if candidate_point_clouds_world.ndim != 3 or candidate_point_clouds_world.shape[0] != num_valid:
                raise ValueError(
                    "Counterfactual evaluator candidate_point_clouds_world must have shape (num_valid, P, 3).",
                )
            if candidate_point_cloud_lengths is None:
                candidate_point_cloud_lengths = torch.full(
                    (num_valid,),
                    candidate_point_clouds_world.shape[1],
                    dtype=torch.long,
                    device=device,
                )
            else:
                candidate_point_cloud_lengths = torch.as_tensor(
                    candidate_point_cloud_lengths,
                    device=device,
                    dtype=torch.long,
                ).reshape(-1)
                if candidate_point_cloud_lengths.shape[0] != num_valid:
                    raise ValueError(
                        "Counterfactual evaluator candidate_point_cloud_lengths must align with num_valid.",
                    )
        elif candidate_point_cloud_lengths is not None:
            raise ValueError("candidate_point_cloud_lengths requires candidate_point_clouds_world.")

        target_eval_current_points_world = self.target_eval_current_points_world
        if target_eval_current_points_world is not None:
            target_eval_current_points_world = torch.as_tensor(
                target_eval_current_points_world,
                device=device,
                dtype=dtype,
            ).reshape(-1, 3)

        target_eval_candidate_points_world = self.target_eval_candidate_points_world
        target_eval_candidate_point_lengths = self.target_eval_candidate_point_lengths
        if target_eval_candidate_points_world is not None:
            target_eval_candidate_points_world = torch.as_tensor(
                target_eval_candidate_points_world,
                device=device,
                dtype=dtype,
            )
            if target_eval_candidate_points_world.ndim != 3 or target_eval_candidate_points_world.shape[0] != num_valid:
                raise ValueError(
                    "target_eval_candidate_points_world must have shape (num_valid, P, 3).",
                )
            if target_eval_candidate_point_lengths is None:
                target_eval_candidate_point_lengths = torch.full(
                    (num_valid,),
                    target_eval_candidate_points_world.shape[1],
                    dtype=torch.long,
                    device=device,
                )
            else:
                target_eval_candidate_point_lengths = torch.as_tensor(
                    target_eval_candidate_point_lengths,
                    device=device,
                    dtype=torch.long,
                ).reshape(-1)
                if target_eval_candidate_point_lengths.shape[0] != num_valid:
                    raise ValueError("target_eval_candidate_point_lengths must align with num_valid.")
        elif target_eval_candidate_point_lengths is not None:
            raise ValueError("target_eval_candidate_point_lengths requires target_eval_candidate_points_world.")

        return CounterfactualCandidateEvaluation(
            scores=scores,
            score_label=self.score_label,
            metrics=metrics,
            candidate_point_clouds_world=candidate_point_clouds_world,
            candidate_point_cloud_lengths=candidate_point_cloud_lengths,
            target_eval_current_points_world=target_eval_current_points_world,
            target_eval_candidate_points_world=target_eval_candidate_points_world,
            target_eval_candidate_point_lengths=target_eval_candidate_point_lengths,
            target_eval_crop_policy=self.target_eval_crop_policy,
            target_eval_voxel_size_m=self.target_eval_voxel_size_m,
            target_eval_max_points=self.target_eval_max_points,
        )

    def selected_metrics(self, valid_index: int) -> dict[str, float]:
        return {name: float(values[valid_index].item()) for name, values in self.metric_vectors.items()}

    def selected_point_cloud(self, valid_index: int) -> torch.Tensor | None:
        if self.candidate_point_clouds_world is None:
            return None
        cloud = self.candidate_point_clouds_world[valid_index]
        if self.candidate_point_cloud_lengths is None:
            return cloud
        length = int(self.candidate_point_cloud_lengths[valid_index].item())
        return cloud[:length]


@dataclass(slots=True)
class CounterfactualStepResult:
    """One selected rollout step."""

    step_index: int
    candidates: CandidateSamplingResult
    selected_valid_index: int
    selected_shell_index: int
    selection_score: float
    selection_score_label: str = "score"
    selection_scores: torch.Tensor | None = None
    selection_policy: str = "unknown"
    selection_temperature: float | None = None
    selection_logits: torch.Tensor | None = None
    selection_probabilities: torch.Tensor | None = None
    selection_log_probabilities: torch.Tensor | None = None
    selection_entropy: float | None = None
    selected_log_probability: float | None = None
    selection_rng_seed: int | None = None
    selected_metrics: dict[str, float] = field(default_factory=dict)
    metric_vectors: dict[str, torch.Tensor] = field(default_factory=dict)
    selected_point_cloud_world: torch.Tensor | None = None
    selected_depth_m: torch.Tensor | None = None
    selected_depth_valid_mask: torch.Tensor | None = None
    selected_depth_focal_px: tuple[float, float] | None = None
    selected_depth_principal_point_px: tuple[float, float] | None = None
    selected_depth_image_size_hw: tuple[int, int] | None = None
    target_eval_current_points_world: torch.Tensor | None = None
    target_eval_candidate_points_world: torch.Tensor | None = None
    target_eval_candidate_point_lengths: torch.Tensor | None = None
    target_eval_crop_policy: str | None = None
    target_eval_voxel_size_m: float | None = None
    target_eval_max_points: int | None = None

    @property
    def selected_pose_world(self) -> PoseTW:
        return _pose_at(self.candidates.poses_world_cam(), self.selected_valid_index)

    @property
    def selected_view(self) -> CameraTW:
        views = self.candidates.views
        if getattr(views, "ndim", 1) > 1:
            return views[self.selected_valid_index]
        return views


@dataclass(slots=True)
class CounterfactualTrajectory:
    """One rollout trajectory rooted at one initial pose."""

    root_pose_world: PoseTW
    root_time_ns: int | None = None
    root_trajectory_index: int | None = None
    root_frame_index: int | None = None
    steps: list[CounterfactualStepResult] = field(default_factory=list)
    cumulative_score: float = 0.0
    cumulative_rri: float | None = None
    terminated_early: bool = False

    @property
    def root_pm_dist(self) -> float | None:
        """Return the first finite scene root point-mesh distance, if known."""

        return _root_error_for_metric(self, "root_pm_dist")

    def final_pose_world(self) -> PoseTW:
        if not self.steps:
            return self.root_pose_world
        return self.steps[-1].selected_pose_world

    def pose_chain_world(self) -> PoseTW:
        rows = [_pose_row(self.root_pose_world)]
        rows.extend(_pose_row(step.selected_pose_world) for step in self.steps)
        return PoseTW(torch.cat(rows, dim=0))

    def history_centers_world(self) -> torch.Tensor:
        return self.pose_chain_world().t.reshape(-1, 3)

    def reference_pose_world(self, step_index: int) -> PoseTW:
        if step_index <= 0 or not self.steps:
            return self.root_pose_world
        return self.steps[step_index - 1].selected_pose_world

    def with_appended_step(self, step: CounterfactualStepResult) -> "CounterfactualTrajectory":
        step_rri = step.selected_metrics.get("rri")
        cumulative_rri = self.cumulative_rri
        if step_rri is not None:
            cumulative_rri = float(step_rri) if cumulative_rri is None else float(cumulative_rri + step_rri)
        return CounterfactualTrajectory(
            root_pose_world=self.root_pose_world,
            root_time_ns=self.root_time_ns,
            root_trajectory_index=self.root_trajectory_index,
            root_frame_index=self.root_frame_index,
            steps=[*self.steps, step],
            cumulative_score=float(self.cumulative_score + step.selection_score),
            cumulative_rri=cumulative_rri,
            terminated_early=False,
        )

    def mark_terminated(self) -> "CounterfactualTrajectory":
        return replace(self, terminated_early=True)

    def accumulated_points_world(self) -> torch.Tensor:
        clouds = [step.selected_point_cloud_world for step in self.steps if step.selected_point_cloud_world is not None]
        if not clouds:
            root = ensure_unbatched_pose(self.root_pose_world)
            return torch.empty((0, 3), device=root.t.device, dtype=root.t.dtype)
        return torch.cat(clouds, dim=0)


@dataclass(slots=True)
class CounterfactualRolloutResult:
    """All trajectories produced by one rollout call."""

    root_pose_world: PoseTW
    trajectories: list[CounterfactualTrajectory]
    horizon: int
    branch_factor: int
    beam_width: int | None
    selection_policy: str | CounterfactualSelectionPolicy
    score_label: str = "score"
    root_time_ns: int | None = None
    root_trajectory_index: int | None = None
    root_frame_index: int | None = None


CounterfactualEvaluatorFn = Callable[
    [CandidateSamplingResult, CounterfactualTrajectory, int],
    CounterfactualCandidateEvaluation | SceneRriEvaluation | torch.Tensor,
]


class CounterfactualPoseGeneratorConfig(TargetConfig["CounterfactualPoseGenerator"]):
    """Configuration for multi-step finite-candidate rollout generation.

    Candidate sampling stays in `pose_generation`: each rollout step regenerates
    a shell from the current pose/history, applies hard validity masks, and
    selects valid actions by the configured policy. Persistence, source-row
    lineage, and `Q_H` replay views are owned by `aria_nbv.rollouts`.
    """

    @property
    def target_type(self) -> type["CounterfactualPoseGenerator"]:
        return CounterfactualPoseGenerator

    candidate_config: CandidateViewGeneratorConfig | CandidateMixtureViewGeneratorConfig = Field(
        default_factory=CandidateViewGeneratorConfig
    )
    horizon: int = Field(default=3, ge=1)
    branch_factor: int = Field(default=2, ge=1)
    beam_width: int | None = Field(default=None, ge=1)
    branch_factor_schedule: list[int] | None = None
    stochastic_branch_factors: list[int] | None = None
    stochastic_branch_probabilities: list[float] | None = None
    selection_policy: CounterfactualSelectionPolicy = CounterfactualSelectionPolicy.FARTHEST_FROM_HISTORY
    selection_temperature: float = Field(default=1.0, gt=0.0)
    robust_temperature_logits: bool = True
    """Normalize temperature-softmax scores by median/IQR before applying temperature."""

    branch_schedule_id: str | None = None
    min_history_distance_m: float = Field(default=0.0, ge=0.0)
    min_sibling_distance_m: float = Field(default=0.0, ge=0.0)
    min_sibling_yaw_deg: float = Field(default=0.0, ge=0.0)
    min_sibling_target_bearing_deg: float = Field(default=0.0, ge=0.0)
    require_sibling_strategy_diversity: bool = False
    seed: int | None = Field(default=0, ge=0)
    log_timing: bool = False
    verbosity: Verbosity = Field(default=Verbosity.NORMAL)
    is_debug: bool = False

    _coerce_verbosity = field_validator("verbosity", mode="before")(BaseConfig._coerce_verbosity)

    @model_validator(mode="after")
    def _validate_branch_controls(self) -> "CounterfactualPoseGeneratorConfig":
        if self.branch_factor_schedule is not None and self.stochastic_branch_factors is not None:
            raise ValueError("Use either branch_factor_schedule or stochastic_branch_factors, not both.")
        if self.branch_factor_schedule is not None:
            if not self.branch_factor_schedule:
                raise ValueError("branch_factor_schedule must be non-empty when set.")
            if any(int(value) < 1 for value in self.branch_factor_schedule):
                raise ValueError("branch_factor_schedule entries must be >= 1.")
        if self.stochastic_branch_factors is not None:
            if not self.stochastic_branch_factors:
                raise ValueError("stochastic_branch_factors must be non-empty when set.")
            if any(int(value) < 1 for value in self.stochastic_branch_factors):
                raise ValueError("stochastic_branch_factors entries must be >= 1.")
        if self.stochastic_branch_probabilities is not None:
            if self.stochastic_branch_factors is None:
                raise ValueError("stochastic_branch_probabilities require stochastic_branch_factors.")
            if len(self.stochastic_branch_probabilities) != len(self.stochastic_branch_factors):
                raise ValueError("stochastic_branch_probabilities must match stochastic_branch_factors length.")
            if any(float(value) < 0.0 for value in self.stochastic_branch_probabilities):
                raise ValueError("stochastic_branch_probabilities entries must be >= 0.")
            if sum(float(value) for value in self.stochastic_branch_probabilities) <= 0.0:
                raise ValueError("stochastic_branch_probabilities must have positive total mass.")
        return self


class CounterfactualPoseGenerator:
    """Expand a multi-step counterfactual pose tree from the current generator.

    The generator returns in-memory trajectories only. Callers such as
    `RolloutDatasetWriter` provide source samples and oracle evaluators, then
    decide which rollout records and diagnostics are retained in standalone
    replay stores.
    """

    def __init__(self, config: CounterfactualPoseGeneratorConfig) -> None:
        self.config = config
        self.console = (
            Console.with_prefix(self.__class__.__name__)
            .set_verbosity(self.config.verbosity)
            .set_debug(self.config.is_debug)
        )
        self._candidate_generator: CandidateViewGenerator | CandidateMixtureViewGenerator = (
            self.config.candidate_config.setup_target()
        )
        self._selection_generator = torch.Generator(device="cpu")
        if self.config.seed is not None:
            self._selection_generator.manual_seed(int(self.config.seed))

    @staticmethod
    def _canonicalize_pose(reference_pose: PoseTW) -> PoseTW:
        return rotate_yaw_cw90(ensure_unbatched_pose(reference_pose))

    @staticmethod
    def _generator_input_pose(reference_pose_world: PoseTW) -> PoseTW:
        return rotate_yaw_cw90(ensure_unbatched_pose(reference_pose_world), undo=True)

    def _configured_reference_frame_index(self) -> int | None:
        candidate_config = self.config.candidate_config
        if hasattr(candidate_config, "base"):
            return getattr(candidate_config.base, "reference_frame_index", None)
        return getattr(candidate_config, "reference_frame_index", None)

    def _typed_sample_root(
        self,
        sample: EfmSnippetView,
        *,
        reference_pose: PoseTW | None,
        device: torch.device,
    ) -> tuple[PoseTW, int | None, int | None, int | None]:
        if reference_pose is not None:
            traj_index = _exact_pose_index(sample.trajectory.t_world_rig, reference_pose)
            root_time = None if traj_index is None else _time_value(sample.trajectory.time_ns, traj_index)
            return reference_pose.to(device=device), root_time, traj_index, None

        cam_view = sample.get_camera(self.config.candidate_config.camera_label)
        frame_index = self._configured_reference_frame_index()
        if frame_index is None:
            traj_count = int(sample.trajectory.time_ns.reshape(-1).numel())
            traj_index = max(traj_count - 1, 0) if traj_count else None
            root_time = None if traj_index is None else _time_value(sample.trajectory.time_ns, traj_index)
            root_frame_index = max(int(cam_view.num_frames) - 1, 0) if cam_view.num_frames else None
            return sample.trajectory.final_pose.to(device=device), root_time, traj_index, root_frame_index

        cam_idx, traj_idx = cam_view.nearest_traj_indices(
            sample.trajectory.time_ns,
            [int(frame_index)],
            default_last=True,
        )
        root_frame_index = int(cam_idx.reshape(-1)[0].detach().cpu().item()) if cam_idx.numel() else int(frame_index)
        if traj_idx.numel() == 0:
            traj_count = int(sample.trajectory.time_ns.reshape(-1).numel())
            traj_index = max(traj_count - 1, 0) if traj_count else None
            root_time = None if traj_index is None else _time_value(sample.trajectory.time_ns, traj_index)
            return sample.trajectory.final_pose.to(device=device), root_time, traj_index, root_frame_index
        traj_index = int(traj_idx.reshape(-1)[0].detach().cpu().item())
        root_time = _time_value(sample.trajectory.time_ns, traj_index)
        return sample.trajectory.t_world_rig[traj_idx].to(device=device), root_time, traj_index, root_frame_index

    def generate_from_typed_sample(
        self,
        sample: EfmSnippetView,
        *,
        reference_pose: PoseTW | None = None,
        score_candidates: CounterfactualEvaluatorFn | None = None,
        candidate_runtime_context: CandidateGenerationRuntimeContext | None = None,
    ) -> CounterfactualRolloutResult:
        """Generate rollout trajectories directly from one typed snippet."""

        if sample.mesh is None or sample.mesh_verts is None or sample.mesh_faces is None:
            raise ValueError("Counterfactual rollouts require sample mesh, mesh_verts, and mesh_faces.")
        device = torch.device(self.config.candidate_config.device)
        cam_view = sample.get_camera(self.config.candidate_config.camera_label)
        resolved_pose, root_time_ns, root_trajectory_index, root_frame_index = self._typed_sample_root(
            sample,
            reference_pose=reference_pose,
            device=device,
        )
        return self.generate(
            reference_pose=resolved_pose,
            gt_mesh=sample.mesh,
            mesh_verts=sample.mesh_verts.to(device=device),
            mesh_faces=sample.mesh_faces.to(device=device),
            camera_calib_template=cam_view.calib.to(device=device),
            occupancy_extent=sample.get_occupancy_extend().to(device=device, dtype=torch.float32),
            score_candidates=score_candidates,
            candidate_runtime_context=candidate_runtime_context,
            root_time_ns=root_time_ns,
            root_trajectory_index=root_trajectory_index,
            root_frame_index=root_frame_index,
        )

    def generate(
        self,
        *,
        reference_pose: PoseTW,
        gt_mesh: "trimesh.Trimesh",
        mesh_verts: torch.Tensor,
        mesh_faces: torch.Tensor,
        camera_calib_template: CameraTW,
        occupancy_extent: torch.Tensor,
        score_candidates: CounterfactualEvaluatorFn | None = None,
        candidate_runtime_context: CandidateGenerationRuntimeContext | None = None,
        root_time_ns: int | None = None,
        root_trajectory_index: int | None = None,
        root_frame_index: int | None = None,
    ) -> CounterfactualRolloutResult:
        """Generate multi-step counterfactual rollouts from one root pose."""

        root_pose_world = self._canonicalize_pose(reference_pose)
        frontier = [
            CounterfactualTrajectory(
                root_pose_world=root_pose_world,
                root_time_ns=root_time_ns,
                root_trajectory_index=root_trajectory_index,
                root_frame_index=root_frame_index,
            )
        ]
        score_label = self.config.selection_policy.value
        candidate_total_s = 0.0
        evaluate_total_s = 0.0
        select_total_s = 0.0
        expanded_nodes = 0
        scored_valid_candidates = 0

        for step_index in range(self.config.horizon):
            self.console.dbg(
                f"Expanding counterfactual rollout step {step_index + 1}/{self.config.horizon}.",
            )
            next_frontier: list[CounterfactualTrajectory] = []
            for frontier_index, trajectory in enumerate(frontier):
                node_start_s = perf_counter()
                candidate_start_s = perf_counter()
                candidates = self._candidate_generator.generate(
                    reference_pose=self._generator_input_pose(trajectory.final_pose_world()),
                    gt_mesh=gt_mesh,
                    mesh_verts=mesh_verts,
                    mesh_faces=mesh_faces,
                    camera_calib_template=camera_calib_template,
                    occupancy_extent=occupancy_extent,
                    runtime_context=candidate_runtime_context,
                )
                candidate_s = perf_counter() - candidate_start_s
                candidate_total_s += candidate_s
                valid_count = int(candidates.mask_valid.sum().item())
                expanded_nodes += 1
                scored_valid_candidates += valid_count
                if valid_count <= 0:
                    self._log_timing(
                        "Rollout timing "
                        f"step={step_index} frontier={frontier_index} valid=0 "
                        f"candidate_s={candidate_s:.3f} node_s={perf_counter() - node_start_s:.3f}",
                    )
                    next_frontier.append(trajectory.mark_terminated())
                    continue

                evaluate_start_s = perf_counter()
                evaluation = self._evaluate_valid_candidates(
                    result=candidates,
                    trajectory=trajectory,
                    step_index=step_index,
                    score_candidates=score_candidates,
                )
                evaluate_s = perf_counter() - evaluate_start_s
                evaluate_total_s += evaluate_s
                score_label = evaluation.score_label
                select_start_s = perf_counter()
                branch_count = self._branch_factor_for_step(step_index)
                selection_records = self._select_valid_candidates(
                    scores=evaluation.scores,
                    candidates=candidates,
                    valid_poses=candidates.poses_world_cam(),
                    trajectory=trajectory,
                    branch_count=branch_count,
                )
                select_s = perf_counter() - select_start_s
                select_total_s += select_s
                self._log_timing(
                    "Rollout timing "
                    f"step={step_index} frontier={frontier_index} valid={valid_count} "
                    f"branch_count={branch_count} selected={len(selection_records)} "
                    f"candidate_s={candidate_s:.3f} evaluate_s={evaluate_s:.3f} "
                    f"select_s={select_s:.3f} node_s={perf_counter() - node_start_s:.3f}",
                )
                if not selection_records:
                    next_frontier.append(trajectory.mark_terminated())
                    continue

                for selection in selection_records:
                    valid_index = selection.valid_index
                    shell_valid = torch.nonzero(candidates.mask_valid, as_tuple=False).reshape(-1)
                    selected_shell_index = int(shell_valid[valid_index].item())
                    step = CounterfactualStepResult(
                        step_index=step_index,
                        candidates=candidates,
                        selected_valid_index=valid_index,
                        selected_shell_index=selected_shell_index,
                        selection_score=float(evaluation.scores[valid_index].item()),
                        selection_score_label=evaluation.score_label,
                        selection_scores=evaluation.scores.detach().clone(),
                        selection_policy=self.config.selection_policy.value,
                        selection_temperature=(
                            self.config.selection_temperature
                            if self.config.selection_policy is CounterfactualSelectionPolicy.TEMPERATURE_SOFTMAX
                            else None
                        ),
                        selection_logits=selection.logits.detach().clone(),
                        selection_probabilities=selection.probabilities.detach().clone(),
                        selection_log_probabilities=selection.log_probabilities.detach().clone(),
                        selection_entropy=selection.entropy,
                        selected_log_probability=selection.selected_log_probability,
                        selection_rng_seed=self.config.seed,
                        selected_metrics=evaluation.selected_metrics(valid_index),
                        metric_vectors={
                            name: values.detach().clone() for name, values in evaluation.metric_vectors.items()
                        },
                        selected_point_cloud_world=(
                            None
                            if evaluation.selected_point_cloud(valid_index) is None
                            else evaluation.selected_point_cloud(valid_index).detach().clone()
                        ),
                        target_eval_current_points_world=(
                            None
                            if evaluation.target_eval_current_points_world is None
                            else evaluation.target_eval_current_points_world.detach().clone()
                        ),
                        target_eval_candidate_points_world=(
                            None
                            if evaluation.target_eval_candidate_points_world is None
                            else evaluation.target_eval_candidate_points_world.detach().clone()
                        ),
                        target_eval_candidate_point_lengths=(
                            None
                            if evaluation.target_eval_candidate_point_lengths is None
                            else evaluation.target_eval_candidate_point_lengths.detach().clone()
                        ),
                        target_eval_crop_policy=evaluation.target_eval_crop_policy,
                        target_eval_voxel_size_m=evaluation.target_eval_voxel_size_m,
                        target_eval_max_points=evaluation.target_eval_max_points,
                    )
                    next_frontier.append(trajectory.with_appended_step(step))

            frontier = self._apply_beam_width(next_frontier)
            if not frontier:
                frontier = [
                    CounterfactualTrajectory(
                        root_pose_world=root_pose_world,
                        root_time_ns=root_time_ns,
                        root_trajectory_index=root_trajectory_index,
                        root_frame_index=root_frame_index,
                        terminated_early=True,
                    )
                ]
                break

        self._log_timing(
            "Rollout timing summary "
            f"expanded_nodes={expanded_nodes} scored_valid_candidates={scored_valid_candidates} "
            f"candidate_s={candidate_total_s:.3f} evaluate_s={evaluate_total_s:.3f} "
            f"select_s={select_total_s:.3f}",
        )
        return CounterfactualRolloutResult(
            root_pose_world=root_pose_world,
            trajectories=frontier,
            horizon=self.config.horizon,
            branch_factor=self.config.branch_factor,
            beam_width=self.config.beam_width,
            selection_policy=self.config.selection_policy,
            score_label=score_label,
            root_time_ns=root_time_ns,
            root_trajectory_index=root_trajectory_index,
            root_frame_index=root_frame_index,
        )

    def _evaluate_valid_candidates(
        self,
        *,
        result: CandidateSamplingResult,
        trajectory: CounterfactualTrajectory,
        step_index: int,
        score_candidates: CounterfactualEvaluatorFn | None,
    ) -> CounterfactualCandidateEvaluation:
        valid_poses = result.poses_world_cam()
        num_valid = _pose_batch_len(valid_poses)
        device = valid_poses.t.device
        dtype = valid_poses.t.dtype

        if score_candidates is not None:
            raw_eval = score_candidates(result, trajectory, step_index)
            if isinstance(raw_eval, CounterfactualCandidateEvaluation):
                return raw_eval.validate(num_valid=num_valid, device=device, dtype=dtype)
            if isinstance(raw_eval, SceneRriEvaluation):
                return CounterfactualCandidateEvaluation(
                    scores=raw_eval.scores,
                    score_label=raw_eval.score_label,
                    metric_vectors=raw_eval.metric_vectors,
                    candidate_point_clouds_world=raw_eval.candidate_point_clouds_world,
                    candidate_point_cloud_lengths=raw_eval.candidate_point_cloud_lengths,
                ).validate(num_valid=num_valid, device=device, dtype=dtype)
            return CounterfactualCandidateEvaluation(
                scores=torch.as_tensor(raw_eval, device=device, dtype=dtype),
                score_label="score",
            ).validate(num_valid=num_valid, device=device, dtype=dtype)

        scores = self._builtin_scores(valid_poses=valid_poses, trajectory=trajectory)
        return CounterfactualCandidateEvaluation(
            scores=scores,
            score_label=self.config.selection_policy.value,
        )

    def _builtin_scores(
        self,
        *,
        valid_poses: PoseTW,
        trajectory: CounterfactualTrajectory,
    ) -> torch.Tensor:
        centers = valid_poses.t.reshape(-1, 3)
        if self.config.selection_policy in (
            CounterfactualSelectionPolicy.RANDOM,
            CounterfactualSelectionPolicy.RANDOM_VALID,
        ):
            return torch.rand(centers.shape[0], generator=self._selection_generator, device="cpu").to(
                device=centers.device,
                dtype=centers.dtype,
            )

        if self.config.selection_policy is CounterfactualSelectionPolicy.FARTHEST_FROM_REFERENCE:
            reference_center = ensure_unbatched_pose(trajectory.final_pose_world()).t.reshape(1, 3)
            return torch.linalg.norm(centers - reference_center, dim=1)

        history = trajectory.history_centers_world().to(device=centers.device, dtype=centers.dtype)
        distances = torch.cdist(centers, history)
        return distances.min(dim=1).values

    def _select_valid_candidates(
        self,
        *,
        scores: torch.Tensor,
        candidates: CandidateSamplingResult,
        valid_poses: PoseTW,
        trajectory: CounterfactualTrajectory,
        branch_count: int,
    ) -> list[CounterfactualSelectionRecord]:
        if self.config.selection_policy in (
            CounterfactualSelectionPolicy.RANDOM,
            CounterfactualSelectionPolicy.RANDOM_VALID,
            CounterfactualSelectionPolicy.TEMPERATURE_SOFTMAX,
        ):
            return self._sample_valid_candidates(
                scores=scores,
                candidates=candidates,
                valid_poses=valid_poses,
                trajectory=trajectory,
                branch_count=branch_count,
            )
        return self._greedy_valid_candidates(
            scores=scores,
            candidates=candidates,
            valid_poses=valid_poses,
            trajectory=trajectory,
            branch_count=branch_count,
        )

    def _greedy_valid_candidates(
        self,
        *,
        scores: torch.Tensor,
        candidates: CandidateSamplingResult,
        valid_poses: PoseTW,
        trajectory: CounterfactualTrajectory,
        branch_count: int,
    ) -> list[CounterfactualSelectionRecord]:
        finite_scores = torch.isfinite(scores)
        if not bool(finite_scores.any().item()):
            return []
        ranked_scores = torch.where(finite_scores, scores, torch.full_like(scores, float("-inf")))
        order = torch.argsort(ranked_scores, descending=True)
        centers = valid_poses.t.reshape(-1, 3)
        history = trajectory.history_centers_world().to(device=centers.device, dtype=centers.dtype)
        metadata = _valid_diversity_metadata(candidates=candidates, valid_poses=valid_poses)

        selected: list[int] = []
        selected_centers: list[torch.Tensor] = []
        selected_yaws: list[torch.Tensor] = []
        selected_strategies: list[int] = []
        selected_target_bearings: list[torch.Tensor] = []
        for index_tensor in order:
            index = int(index_tensor.item())
            if not bool(finite_scores[index].item()):
                continue
            center = centers[index]
            if not self._passes_diversity_guards(
                index=index,
                center=center,
                history=history,
                selected_centers=selected_centers,
                metadata=metadata,
                selected_yaws=selected_yaws,
                selected_strategies=selected_strategies,
                selected_target_bearings=selected_target_bearings,
            ):
                continue
            selected.append(index)
            selected_centers.append(center)
            _append_diversity_selection(
                index=index,
                metadata=metadata,
                selected_yaws=selected_yaws,
                selected_strategies=selected_strategies,
                selected_target_bearings=selected_target_bearings,
            )
            if len(selected) >= branch_count:
                break

        if not selected:
            selected.append(int(torch.nonzero(finite_scores, as_tuple=False).reshape(-1)[0].item()))
        return [self._one_hot_selection_record(scores=ranked_scores, valid_index=index) for index in selected]

    def _sample_valid_candidates(
        self,
        *,
        scores: torch.Tensor,
        candidates: CandidateSamplingResult,
        valid_poses: PoseTW,
        trajectory: CounterfactualTrajectory,
        branch_count: int,
    ) -> list[CounterfactualSelectionRecord]:
        centers = valid_poses.t.reshape(-1, 3)
        history = trajectory.history_centers_world().to(device=centers.device, dtype=centers.dtype)
        remaining = torch.isfinite(scores).to(device=scores.device, dtype=torch.bool)
        metadata = _valid_diversity_metadata(candidates=candidates, valid_poses=valid_poses)
        selected_centers: list[torch.Tensor] = []
        selected_yaws: list[torch.Tensor] = []
        selected_strategies: list[int] = []
        selected_target_bearings: list[torch.Tensor] = []
        records: list[CounterfactualSelectionRecord] = []

        for _draw_index in range(branch_count):
            if not bool(remaining.any().item()):
                break
            eligible = remaining & self._distance_guard_mask(
                centers=centers,
                history=history,
                selected_centers=selected_centers,
            )
            eligible &= self._metadata_guard_mask(
                metadata=metadata,
                selected_yaws=selected_yaws,
                selected_strategies=selected_strategies,
                selected_target_bearings=selected_target_bearings,
            )
            if not bool(eligible.any().item()):
                eligible = remaining.clone()
            if not bool(eligible.any().item()):
                break

            if self.config.selection_policy in (
                CounterfactualSelectionPolicy.RANDOM,
                CounterfactualSelectionPolicy.RANDOM_VALID,
            ):
                logits = torch.zeros_like(scores)
                distribution = self._masked_softmax(logits=logits, mask=eligible)
            else:
                logits = self._temperature_logits(scores)
                distribution = self._masked_softmax(logits=logits, mask=eligible)

            selected_tensor = torch.multinomial(
                distribution.probabilities.detach().cpu(),
                num_samples=1,
                replacement=False,
                generator=self._selection_generator,
            )
            selected_index = int(selected_tensor.item())
            records.append(
                replace(
                    distribution,
                    valid_index=selected_index,
                    selected_log_probability=float(
                        distribution.log_probabilities[selected_index].detach().cpu().item()
                    ),
                )
            )
            remaining[selected_index] = False
            selected_centers.append(centers[selected_index])
            _append_diversity_selection(
                index=selected_index,
                metadata=metadata,
                selected_yaws=selected_yaws,
                selected_strategies=selected_strategies,
                selected_target_bearings=selected_target_bearings,
            )

        return records

    def _temperature_logits(self, scores: torch.Tensor) -> torch.Tensor:
        if not self.config.robust_temperature_logits:
            return scores / float(self.config.selection_temperature)
        return _robust_temperature_logits(scores=scores, temperature=float(self.config.selection_temperature))

    def _one_hot_selection_record(
        self,
        *,
        scores: torch.Tensor,
        valid_index: int,
    ) -> CounterfactualSelectionRecord:
        probabilities = torch.zeros_like(scores)
        probabilities[valid_index] = 1.0
        log_probabilities = torch.full_like(scores, float("-inf"))
        log_probabilities[valid_index] = 0.0
        return CounterfactualSelectionRecord(
            valid_index=int(valid_index),
            logits=scores.detach().clone(),
            probabilities=probabilities,
            log_probabilities=log_probabilities,
            entropy=0.0,
            selected_log_probability=0.0,
        )

    def _branch_factor_for_step(self, step_index: int) -> int:
        if self.config.stochastic_branch_factors is not None:
            choices = torch.tensor(self.config.stochastic_branch_factors, dtype=torch.long)
            if self.config.stochastic_branch_probabilities is None:
                probabilities = torch.ones(len(choices), dtype=torch.float32) / float(len(choices))
            else:
                probabilities = torch.tensor(self.config.stochastic_branch_probabilities, dtype=torch.float32)
                probabilities = probabilities / probabilities.sum()
            sampled = torch.multinomial(
                probabilities,
                num_samples=1,
                replacement=True,
                generator=self._selection_generator,
            )
            return int(choices[int(sampled.item())].item())
        if self.config.branch_factor_schedule is not None:
            schedule_index = min(step_index, len(self.config.branch_factor_schedule) - 1)
            return int(self.config.branch_factor_schedule[schedule_index])
        return int(self.config.branch_factor)

    def _log_timing(self, message: str) -> None:
        if self.config.log_timing:
            self.console.log(message)

    def _masked_softmax(
        self,
        *,
        logits: torch.Tensor,
        mask: torch.Tensor,
    ) -> CounterfactualSelectionRecord:
        if logits.ndim != 1:
            raise ValueError("Selection logits must be a 1-D tensor aligned with valid candidates.")
        mask = mask.to(device=logits.device, dtype=torch.bool).reshape(-1)
        if mask.shape != logits.shape:
            raise ValueError(f"Selection mask shape {tuple(mask.shape)} must match logits {tuple(logits.shape)}.")
        mask &= torch.isfinite(logits)
        if not bool(mask.any().item()):
            raise ValueError("Cannot sample from an empty valid-candidate mask.")

        masked_logits = torch.where(mask, logits, torch.full_like(logits, float("-inf")))
        probabilities = torch.softmax(masked_logits, dim=0)
        log_probabilities = torch.log(probabilities.clamp_min(torch.finfo(probabilities.dtype).tiny))
        log_probabilities = torch.where(mask, log_probabilities, torch.full_like(logits, float("-inf")))
        entropy = -(probabilities[mask] * log_probabilities[mask]).sum()
        return CounterfactualSelectionRecord(
            valid_index=-1,
            logits=masked_logits,
            probabilities=probabilities,
            log_probabilities=log_probabilities,
            entropy=float(entropy.detach().cpu().item()),
            selected_log_probability=float("nan"),
        )

    def _distance_guard_mask(
        self,
        *,
        centers: torch.Tensor,
        history: torch.Tensor,
        selected_centers: list[torch.Tensor],
    ) -> torch.Tensor:
        mask = torch.ones(centers.shape[0], device=centers.device, dtype=torch.bool)
        if self.config.min_history_distance_m > 0.0 and history.numel() > 0:
            history_dists = torch.cdist(centers, history)
            mask &= ~(history_dists < self.config.min_history_distance_m).any(dim=1)

        if self.config.min_sibling_distance_m > 0.0 and selected_centers:
            sibling = torch.stack(selected_centers, dim=0)
            sibling_dists = torch.cdist(centers, sibling)
            mask &= ~(sibling_dists < self.config.min_sibling_distance_m).any(dim=1)

        return mask

    def _metadata_guard_mask(
        self,
        *,
        metadata: _CandidateDiversityMetadata,
        selected_yaws: list[torch.Tensor],
        selected_strategies: list[int],
        selected_target_bearings: list[torch.Tensor],
    ) -> torch.Tensor:
        mask = torch.ones(metadata.yaw_rad.shape[0], device=metadata.yaw_rad.device, dtype=torch.bool)
        if self.config.min_sibling_yaw_deg > 0.0 and selected_yaws:
            min_delta = radians(float(self.config.min_sibling_yaw_deg))
            yaw_deltas = _circular_min_delta(metadata.yaw_rad, selected_yaws)
            mask &= yaw_deltas >= min_delta
        if self.config.require_sibling_strategy_diversity and selected_strategies and metadata.strategy_id is not None:
            selected = torch.tensor(
                selected_strategies, device=metadata.strategy_id.device, dtype=metadata.strategy_id.dtype
            )
            mask &= ~(metadata.strategy_id.reshape(-1, 1) == selected.reshape(1, -1)).any(dim=1)
        if (
            self.config.min_sibling_target_bearing_deg > 0.0
            and selected_target_bearings
            and metadata.target_bearing_yaw_rad is not None
        ):
            min_delta = radians(float(self.config.min_sibling_target_bearing_deg))
            bearing_deltas = _circular_min_delta(metadata.target_bearing_yaw_rad, selected_target_bearings)
            mask &= bearing_deltas >= min_delta
        return mask

    def _passes_diversity_guards(
        self,
        *,
        index: int,
        center: torch.Tensor,
        history: torch.Tensor,
        selected_centers: list[torch.Tensor],
        metadata: _CandidateDiversityMetadata,
        selected_yaws: list[torch.Tensor],
        selected_strategies: list[int],
        selected_target_bearings: list[torch.Tensor],
    ) -> bool:
        if self.config.min_history_distance_m > 0.0 and history.numel() > 0:
            history_dists = torch.linalg.norm(history - center.reshape(1, 3), dim=1)
            if bool((history_dists < self.config.min_history_distance_m).any().item()):
                return False

        if self.config.min_sibling_distance_m > 0.0 and selected_centers:
            sibling = torch.stack(selected_centers, dim=0)
            sibling_dists = torch.linalg.norm(sibling - center.reshape(1, 3), dim=1)
            if bool((sibling_dists < self.config.min_sibling_distance_m).any().item()):
                return False

        if self.config.min_sibling_yaw_deg > 0.0 and selected_yaws:
            yaw_delta = _angular_separation(metadata.yaw_rad[index], selected_yaws)
            if bool((yaw_delta < radians(float(self.config.min_sibling_yaw_deg))).item()):
                return False

        if self.config.require_sibling_strategy_diversity and selected_strategies and metadata.strategy_id is not None:
            strategy = int(metadata.strategy_id[index].detach().cpu().item())
            if strategy in selected_strategies:
                return False

        if (
            self.config.min_sibling_target_bearing_deg > 0.0
            and selected_target_bearings
            and metadata.target_bearing_yaw_rad is not None
        ):
            bearing_delta = _angular_separation(metadata.target_bearing_yaw_rad[index], selected_target_bearings)
            if bool((bearing_delta < radians(float(self.config.min_sibling_target_bearing_deg))).item()):
                return False

        return True

    def _apply_beam_width(self, trajectories: list[CounterfactualTrajectory]) -> list[CounterfactualTrajectory]:
        if self.config.beam_width is None or len(trajectories) <= self.config.beam_width:
            return trajectories
        return sorted(trajectories, key=lambda trajectory: trajectory.cumulative_score, reverse=True)[
            : self.config.beam_width
        ]


__all__ = [
    "CounterfactualCandidateEvaluation",
    "CounterfactualEvaluatorFn",
    "CounterfactualMetricBundle",
    "CounterfactualPoseGenerator",
    "CounterfactualPoseGeneratorConfig",
    "CounterfactualRolloutResult",
    "CounterfactualSelectionRecord",
    "CounterfactualSelectionPolicy",
    "CounterfactualStepResult",
    "CounterfactualTrajectory",
]
