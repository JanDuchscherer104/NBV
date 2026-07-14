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

from collections.abc import Callable
from dataclasses import dataclass, replace
from math import radians
from time import perf_counter
from typing import TYPE_CHECKING

import torch
from efm3d.aria.pose import PoseTW
from pydantic import Field, field_validator

from ...pose_generation.candidate_generation import CandidateViewGenerator, CandidateViewGeneratorConfig
from ...pose_generation.candidate_mixture import (  # noqa: TC001 - Pydantic config field.
    CandidateMixtureViewGeneratorConfig,
)
from ...pose_generation.types import CandidateGenerationRuntimeContext, CandidateSamplingResult
from ...pose_generation.utils import ensure_unbatched_pose
from ...utils import BaseConfig, Console, TargetConfig, Verbosity
from ...utils.frames import rotate_yaw_cw90
from .policy import CounterfactualSelectionPolicy, RolloutPolicySpec
from .state import (
    CounterfactualRolloutResult,
    CounterfactualSelectionRecord,
    CounterfactualStepResult,
    CounterfactualTrajectory,
)
from .types import CandidateScores

if TYPE_CHECKING:
    import trimesh
    from efm3d.aria.camera import CameraTW

    from ...data_handling import EfmSnippetView
    from ...pose_generation.candidate_mixture import CandidateMixtureViewGenerator


_SELECTION_SCORE_ATOL = 1e-5


def _pose_batch_len(poses: PoseTW) -> int:
    tensor = poses.tensor()
    return 1 if tensor.ndim == 1 else int(tensor.shape[0])


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


def _canonical_selection_scores(scores: torch.Tensor) -> torch.Tensor:
    """Make numerically equivalent zero gains deterministic across backends."""

    return torch.where(scores.abs() <= _SELECTION_SCORE_ATOL, torch.zeros_like(scores), scores)


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


@dataclass(frozen=True, slots=True)
class _CandidateDiversityMetadata:
    """Optional valid-candidate metadata used by branch diversity guards."""

    yaw_rad: torch.Tensor
    strategy_id: torch.Tensor | None = None
    target_bearing_yaw_rad: torch.Tensor | None = None


CounterfactualEvaluatorFn = Callable[
    [CandidateSamplingResult, CounterfactualTrajectory, int],
    CandidateScores | torch.Tensor,
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
    policy: RolloutPolicySpec = Field(default_factory=RolloutPolicySpec)
    """Complete immutable branching and action-selection policy."""

    log_timing: bool = False
    verbosity: Verbosity = Field(default=Verbosity.NORMAL)
    is_debug: bool = False

    _coerce_verbosity = field_validator("verbosity", mode="before")(BaseConfig._coerce_verbosity)


class CounterfactualPoseGenerator:
    """Expand a multi-step counterfactual pose tree from the current generator.

    The generator returns in-memory trajectories only. Callers such as
    `RolloutDatasetWriter` provide source samples and oracle evaluators, then
    decide which rollout records and diagnostics are retained in standalone
    replay stores.
    """

    def __init__(self, config: CounterfactualPoseGeneratorConfig) -> None:
        self.config = config
        self.policy = config.policy
        self.console = (
            Console.with_prefix(self.__class__.__name__)
            .set_verbosity(self.config.verbosity)
            .set_debug(self.config.is_debug)
        )
        self._candidate_generator: CandidateViewGenerator | CandidateMixtureViewGenerator = (
            self.config.candidate_config.setup_target()
        )
        self._selection_generator = torch.Generator(device="cpu")
        if self.policy.seed is not None:
            self._selection_generator.manual_seed(int(self.policy.seed))

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
        score_label = self.policy.selection_policy.value
        candidate_total_s = 0.0
        evaluate_total_s = 0.0
        select_total_s = 0.0
        expanded_nodes = 0
        scored_valid_candidates = 0

        for step_index in range(self.policy.horizon):
            self.console.dbg(
                f"Expanding counterfactual rollout step {step_index + 1}/{self.policy.horizon}.",
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
                candidate_scores = self._evaluate_valid_candidates(
                    result=candidates,
                    trajectory=trajectory,
                    step_index=step_index,
                    score_candidates=score_candidates,
                )
                evaluate_s = perf_counter() - evaluate_start_s
                evaluate_total_s += evaluate_s
                score_label = candidate_scores.name
                select_start_s = perf_counter()
                branch_count = self._branch_factor_for_step(step_index)
                selection_records = self._select_valid_candidates(
                    candidate_scores=candidate_scores,
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
                        selection_score=float(candidate_scores.values[valid_index].item()),
                        selection_score_label=candidate_scores.name,
                        selection_scores=candidate_scores.values.detach().clone(),
                        selection_policy=self.policy.selection_policy.value,
                        selection_temperature=(
                            self.policy.selection_temperature
                            if self.policy.selection_policy is CounterfactualSelectionPolicy.TEMPERATURE_SOFTMAX
                            else None
                        ),
                        selection_logits=selection.logits.detach().clone(),
                        selection_probabilities=selection.probabilities.detach().clone(),
                        selection_log_probabilities=selection.log_probabilities.detach().clone(),
                        selection_entropy=selection.entropy,
                        selected_log_probability=selection.selected_log_probability,
                        selection_rng_seed=self.policy.seed,
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
            horizon=self.policy.horizon,
            branch_factor=self.policy.branch_factor,
            beam_width=self.policy.beam_width,
            selection_policy=self.policy.selection_policy,
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
    ) -> CandidateScores:
        valid_poses = result.poses_world_cam()
        device = valid_poses.t.device
        dtype = valid_poses.t.dtype

        if score_candidates is not None:
            raw_eval = score_candidates(result, trajectory, step_index)
            if isinstance(raw_eval, CandidateScores):
                return raw_eval.validate_for(result, device=device, dtype=dtype)
            return CandidateScores.from_valid_values(
                torch.as_tensor(raw_eval, device=device, dtype=dtype),
                name="score",
                candidates=result,
                device=device,
                dtype=dtype,
            )

        scores = self._builtin_scores(valid_poses=valid_poses, trajectory=trajectory)
        return CandidateScores.from_valid_values(
            scores,
            name=self.policy.selection_policy.value,
            candidates=result,
            device=device,
            dtype=dtype,
        )

    def _builtin_scores(
        self,
        *,
        valid_poses: PoseTW,
        trajectory: CounterfactualTrajectory,
    ) -> torch.Tensor:
        centers = valid_poses.t.reshape(-1, 3)
        if self.policy.selection_policy in (
            CounterfactualSelectionPolicy.RANDOM,
            CounterfactualSelectionPolicy.RANDOM_VALID,
        ):
            return torch.rand(centers.shape[0], generator=self._selection_generator, device="cpu").to(
                device=centers.device,
                dtype=centers.dtype,
            )

        if self.policy.selection_policy is CounterfactualSelectionPolicy.FARTHEST_FROM_REFERENCE:
            reference_center = ensure_unbatched_pose(trajectory.final_pose_world()).t.reshape(1, 3)
            return torch.linalg.norm(centers - reference_center, dim=1)

        history = trajectory.history_centers_world().to(device=centers.device, dtype=centers.dtype)
        distances = torch.cdist(centers, history)
        return distances.min(dim=1).values

    def _select_valid_candidates(
        self,
        *,
        candidate_scores: CandidateScores,
        candidates: CandidateSamplingResult,
        valid_poses: PoseTW,
        trajectory: CounterfactualTrajectory,
        branch_count: int,
    ) -> list[CounterfactualSelectionRecord]:
        scores = _canonical_selection_scores(candidate_scores.values)
        if self.policy.selection_policy in (
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
        order = torch.argsort(ranked_scores, descending=True, stable=True)
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

            if self.policy.selection_policy in (
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
        if not self.policy.robust_temperature_logits:
            return scores / float(self.policy.selection_temperature)
        return _robust_temperature_logits(scores=scores, temperature=float(self.policy.selection_temperature))

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
        if self.policy.stochastic_branch_factors is not None:
            choices = torch.tensor(self.policy.stochastic_branch_factors, dtype=torch.long)
            if self.policy.stochastic_branch_probabilities is None:
                probabilities = torch.ones(len(choices), dtype=torch.float32) / float(len(choices))
            else:
                probabilities = torch.tensor(self.policy.stochastic_branch_probabilities, dtype=torch.float32)
                probabilities = probabilities / probabilities.sum()
            sampled = torch.multinomial(
                probabilities,
                num_samples=1,
                replacement=True,
                generator=self._selection_generator,
            )
            return int(choices[int(sampled.item())].item())
        if self.policy.branch_factor_schedule is not None:
            schedule_index = min(step_index, len(self.policy.branch_factor_schedule) - 1)
            return int(self.policy.branch_factor_schedule[schedule_index])
        return int(self.policy.branch_factor)

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
        if self.policy.min_history_distance_m > 0.0 and history.numel() > 0:
            history_dists = torch.cdist(centers, history)
            mask &= ~(history_dists < self.policy.min_history_distance_m).any(dim=1)

        if self.policy.min_sibling_distance_m > 0.0 and selected_centers:
            sibling = torch.stack(selected_centers, dim=0)
            sibling_dists = torch.cdist(centers, sibling)
            mask &= ~(sibling_dists < self.policy.min_sibling_distance_m).any(dim=1)

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
        if self.policy.min_sibling_yaw_deg > 0.0 and selected_yaws:
            min_delta = radians(float(self.policy.min_sibling_yaw_deg))
            yaw_deltas = _circular_min_delta(metadata.yaw_rad, selected_yaws)
            mask &= yaw_deltas >= min_delta
        if self.policy.require_sibling_strategy_diversity and selected_strategies and metadata.strategy_id is not None:
            selected = torch.tensor(
                selected_strategies, device=metadata.strategy_id.device, dtype=metadata.strategy_id.dtype
            )
            mask &= ~(metadata.strategy_id.reshape(-1, 1) == selected.reshape(1, -1)).any(dim=1)
        if (
            self.policy.min_sibling_target_bearing_deg > 0.0
            and selected_target_bearings
            and metadata.target_bearing_yaw_rad is not None
        ):
            min_delta = radians(float(self.policy.min_sibling_target_bearing_deg))
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
        if self.policy.min_history_distance_m > 0.0 and history.numel() > 0:
            history_dists = torch.linalg.norm(history - center.reshape(1, 3), dim=1)
            if bool((history_dists < self.policy.min_history_distance_m).any().item()):
                return False

        if self.policy.min_sibling_distance_m > 0.0 and selected_centers:
            sibling = torch.stack(selected_centers, dim=0)
            sibling_dists = torch.linalg.norm(sibling - center.reshape(1, 3), dim=1)
            if bool((sibling_dists < self.policy.min_sibling_distance_m).any().item()):
                return False

        if self.policy.min_sibling_yaw_deg > 0.0 and selected_yaws:
            yaw_delta = _angular_separation(metadata.yaw_rad[index], selected_yaws)
            if bool((yaw_delta < radians(float(self.policy.min_sibling_yaw_deg))).item()):
                return False

        if self.policy.require_sibling_strategy_diversity and selected_strategies and metadata.strategy_id is not None:
            strategy = int(metadata.strategy_id[index].detach().cpu().item())
            if strategy in selected_strategies:
                return False

        if (
            self.policy.min_sibling_target_bearing_deg > 0.0
            and selected_target_bearings
            and metadata.target_bearing_yaw_rad is not None
        ):
            bearing_delta = _angular_separation(metadata.target_bearing_yaw_rad[index], selected_target_bearings)
            if bool((bearing_delta < radians(float(self.policy.min_sibling_target_bearing_deg))).item()):
                return False

        return True

    def _apply_beam_width(self, trajectories: list[CounterfactualTrajectory]) -> list[CounterfactualTrajectory]:
        if self.policy.beam_width is None or len(trajectories) <= self.policy.beam_width:
            return trajectories
        return sorted(trajectories, key=lambda trajectory: trajectory.cumulative_score, reverse=True)[
            : self.policy.beam_width
        ]


__all__ = [
    "CounterfactualPoseGenerator",
    "CounterfactualPoseGeneratorConfig",
]
