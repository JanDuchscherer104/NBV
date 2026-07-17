"""Join replay transitions with pipeline-local Oracle outputs.

This module provides adapters from Oracle candidate evaluations to replay policy scores while
retaining typed evidence sidecars for later Zarr materialization.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import torch

from ...rollouts.replay.state import CounterfactualRolloutResult, CounterfactualStepResult, CounterfactualTrajectory
from ...rollouts.replay.types import CandidateScores
from ...rollouts.trace import RolloutLineage
from ..evidence import OracleRriState
from ..labels import OracleCandidateEvaluation

if TYPE_CHECKING:
    from efm3d.aria.pose import PoseTW

    from ...pose_generation.types import CandidateSamplingResult


@runtime_checkable
class OracleInvalidity(Protocol):
    """Expected scorer invalidity accepted by the pipeline adapter."""

    @property
    def reason(self) -> Enum:
        """Return the stable domain reason code for hard-invalid control flow."""

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
    """A replay transition joined to its compact Oracle evaluation."""

    transition: CounterfactualStepResult
    evaluation: OracleCandidateEvaluation


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
                    evaluation=replace(
                        evaluation,
                        evidence=evaluation.evidence.compact_for_selection(
                            step.selected_valid_index,
                            retain_target_crops=retain_target_crops,
                        ),
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
