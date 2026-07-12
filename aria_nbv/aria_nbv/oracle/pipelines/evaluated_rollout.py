"""Pipeline-local join between replay transitions and Oracle outputs."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import torch

from ...rollouts.replay.state import CounterfactualRolloutResult, CounterfactualStepResult, CounterfactualTrajectory
from ...rollouts.replay.types import CandidateScores
from ...rollouts.trace import RolloutLineage
from ..evidence import OracleRriState
from ..labels import OracleCandidateEvaluation, OracleCandidateLabels, RetainedOracleEvidence

if TYPE_CHECKING:
    from efm3d.aria.camera import CameraTW
    from efm3d.aria.pose import PoseTW

    from ...pose_generation.types import CandidateSamplingResult


@runtime_checkable
class OracleInvalidity(Protocol):
    """Expected scorer invalidity accepted by the pipeline adapter."""

    @property
    def reason(self) -> Enum:
        """Return the stable domain reason code."""

    @property
    def message(self) -> str:
        """Return an actionable explanation of the invalid outcome."""


class OracleCandidateScorer(Protocol):
    """Oracle scorer accepted by the evaluated-rollout adapter."""

    def __call__(
        self,
        candidates: CandidateSamplingResult,
        state: OracleRriState,
        step_index: int,
    ) -> OracleCandidateEvaluation | OracleInvalidity: ...


@dataclass(frozen=True, slots=True)
class EvaluatedRolloutStep:
    """Oracle labels and retained evidence for one replay step."""

    transition: CounterfactualStepResult
    labels: OracleCandidateLabels
    evidence: RetainedOracleEvidence

    @property
    def selected_metrics(self) -> dict[str, float]:
        """Return scalar Oracle metrics for the selected action."""

        return self.labels.selected(self.transition.selected_valid_index)

    @property
    def metric_vectors(self) -> dict[str, torch.Tensor]:
        """Return compact candidate-wise Oracle metric vectors."""

        return self.labels.metrics

    @property
    def candidates(self) -> CandidateSamplingResult:
        """Return the replay-owned candidate table."""

        return self.transition.candidates

    @property
    def selected_pose_world(self) -> PoseTW:
        """Return the selected camera pose in world coordinates."""

        return self.transition.selected_pose_world

    @property
    def selected_view(self) -> CameraTW:
        """Return the selected candidate camera."""

        return self.transition.selected_view

    @property
    def step_index(self) -> int:
        """Return the zero-based replay step index."""

        return self.transition.step_index

    @property
    def selected_valid_index(self) -> int:
        """Return the selected row in compact valid-candidate order."""

        return self.transition.selected_valid_index

    @property
    def selected_shell_index(self) -> int:
        """Return the selected row in full candidate-shell order."""

        return self.transition.selected_shell_index

    @property
    def selection_score_label(self) -> str:
        """Return the semantic name of replay selection scores."""

        return self.transition.selection_score_label

    @property
    def selection_scores(self) -> torch.Tensor | None:
        """Return replay scores aligned with the full candidate shell."""

        return self.transition.selection_scores

    @property
    def selection_probabilities(self) -> torch.Tensor | None:
        """Return full-shell action probabilities when retained."""

        return self.transition.selection_probabilities

    @property
    def selection_logits(self) -> torch.Tensor | None:
        """Return full-shell action logits when retained."""

        return self.transition.selection_logits

    @property
    def selected_depth_m(self) -> torch.Tensor | None:
        return self.evidence.selected_depth_m

    @property
    def selected_depth_valid_mask(self) -> torch.Tensor | None:
        return self.evidence.selected_depth_valid_mask

    @property
    def selected_depth_focal_px(self) -> tuple[float, float] | None:
        return self.evidence.selected_depth_focal_px

    @property
    def selected_depth_principal_point_px(self) -> tuple[float, float] | None:
        return self.evidence.selected_depth_principal_point_px

    @property
    def selected_depth_image_size_hw(self) -> tuple[int, int] | None:
        return self.evidence.selected_depth_image_size_hw


@dataclass(slots=True)
class EvaluatedRollout:
    """Replay result joined to Oracle outputs by chain and step index."""

    result: CounterfactualRolloutResult
    steps: dict[tuple[int, int], EvaluatedRolloutStep] = field(default_factory=dict)

    def step(self, chain_id: int, step_index: int) -> EvaluatedRolloutStep | None:
        """Return the evaluated step for one retained chain position."""

        return self.steps.get((int(chain_id), int(step_index)))


@dataclass(slots=True)
class EvaluatedRolloutRecord:
    """Evaluated rollout plus lineage consumed by the Zarr writer."""

    evaluated: EvaluatedRollout
    lineage: RolloutLineage
    rollout_id_prefix: str

    @property
    def result(self) -> CounterfactualRolloutResult:
        """Return the replay result for writer compatibility."""

        return self.evaluated.result

    def lineage_for_chain(self, chain_id: int) -> RolloutLineage:
        """Return composed persisted lineage for one retained chain."""

        return self.lineage.for_chain(
            chain_id,
            rollout_id=f"{self.rollout_id_prefix}-{chain_id:06d}",
            rollout_policy=str(self.result.selection_policy),
        )

    def step(self, chain_id: int, step_index: int) -> EvaluatedRolloutStep | None:
        """Return Oracle outputs for one retained replay step."""

        return self.evaluated.step(chain_id, step_index)

    def with_lineage(self, lineage: RolloutLineage) -> "EvaluatedRolloutRecord":
        """Return a copy carrying writer-normalized lineage."""

        return replace(self, lineage=lineage)


class OracleReplayAdapter:
    """Project Oracle evaluations to replay scores and retain sidecar outputs."""

    def __init__(self, scorer: OracleCandidateScorer) -> None:
        self.scorer: OracleCandidateScorer = scorer
        self._evaluations: dict[int, tuple[CandidateSamplingResult, OracleCandidateEvaluation]] = {}

    def __call__(
        self,
        candidates: CandidateSamplingResult,
        trajectory: CounterfactualTrajectory,
        step_index: int,
    ) -> CandidateScores:
        """Score one candidate table and return only the replay policy input."""

        outcome = self.scorer(candidates, self._state_for(trajectory), step_index)
        if isinstance(outcome, OracleInvalidity):
            raise OracleReplayInvalidityError(outcome)
        if not isinstance(outcome, OracleCandidateEvaluation):
            raise TypeError(f"Oracle scorer returned unsupported outcome {type(outcome).__name__}.")
        evaluation = outcome.validate(
            candidates,
            device=candidates.poses_world_cam().t.device,
            dtype=candidates.poses_world_cam().t.dtype,
        )
        self._evaluations[id(candidates)] = (candidates, evaluation)
        return CandidateScores.from_valid_values(
            evaluation.labels.scores,
            name=evaluation.labels.score_label,
            candidates=candidates,
            device=candidates.poses_world_cam().t.device,
            dtype=candidates.poses_world_cam().t.dtype,
        )

    def materialize(
        self,
        result: CounterfactualRolloutResult,
        *,
        retain_target_crops: bool,
    ) -> EvaluatedRollout:
        """Join cached Oracle outputs to retained replay chains."""

        steps: dict[tuple[int, int], EvaluatedRolloutStep] = {}
        for chain_id, trajectory in enumerate(result.trajectories):
            for step in trajectory.steps:
                evaluation = self._evaluation_for(step.candidates)
                steps[(chain_id, step.step_index)] = EvaluatedRolloutStep(
                    transition=step,
                    labels=evaluation.labels,
                    evidence=evaluation.evidence.compact_for_selection(
                        step.selected_valid_index,
                        retain_target_crops=retain_target_crops,
                    ),
                )
        self._evaluations.clear()
        return EvaluatedRollout(result=result, steps=steps)

    def _state_for(self, trajectory: CounterfactualTrajectory) -> OracleRriState:
        return _PipelineOracleState(trajectory=trajectory, evaluations=self._evaluations)

    def _evaluation_for(self, candidates: CandidateSamplingResult) -> OracleCandidateEvaluation:
        try:
            cached_candidates, evaluation = self._evaluations[id(candidates)]
        except KeyError as exc:
            raise KeyError("Missing Oracle evaluation for retained replay candidate table.") from exc
        if cached_candidates is not candidates:
            raise KeyError("Oracle evaluation cache identity collision for retained candidate table.")
        return evaluation


class OracleReplayInvalidityError(ValueError):
    """Pipeline control flow carrying a typed Oracle invalidity outcome."""

    def __init__(self, invalidity: OracleInvalidity) -> None:
        reason = getattr(getattr(invalidity, "reason", None), "value", "oracle_invalid")
        message = str(getattr(invalidity, "message", invalidity))
        super().__init__(f"{reason}: {message}")
        self.invalidity: OracleInvalidity = invalidity


@dataclass(frozen=True, slots=True)
class _PipelineOracleState:
    trajectory: CounterfactualTrajectory
    evaluations: dict[int, tuple[CandidateSamplingResult, OracleCandidateEvaluation]]

    @property
    def root_pose_world(self) -> PoseTW:
        return self.trajectory.root_pose_world

    @property
    def root_time_ns(self) -> int | None:
        return self.trajectory.root_time_ns

    @property
    def root_trajectory_index(self) -> int | None:
        return self.trajectory.root_trajectory_index

    @property
    def root_frame_index(self) -> int | None:
        return self.trajectory.root_frame_index

    def root_metric(self, name: str) -> float | None:
        for step in self.trajectory.steps:
            cached = self.evaluations.get(id(step.candidates))
            if cached is None or cached[0] is not step.candidates:
                continue
            evaluation = cached[1]
            value = evaluation.labels.selected(step.selected_valid_index).get(name)
            if value is not None and torch.isfinite(torch.tensor(value)):
                return float(value)
        return None

    def accumulated_points_world(self) -> torch.Tensor:
        clouds: list[torch.Tensor] = []
        for step in self.trajectory.steps:
            cached = self.evaluations.get(id(step.candidates))
            if cached is None or cached[0] is not step.candidates:
                continue
            evaluation = cached[1]
            cloud = evaluation.evidence.selected_point_cloud(step.selected_valid_index)
            if cloud is not None:
                clouds.append(cloud)
        if clouds:
            return torch.cat(clouds, dim=0)
        root = self.trajectory.root_pose_world
        return torch.empty((0, 3), device=root.t.device, dtype=root.t.dtype)


__all__ = [
    "EvaluatedRollout",
    "EvaluatedRolloutRecord",
    "EvaluatedRolloutStep",
    "OracleReplayAdapter",
    "OracleReplayInvalidityError",
]
