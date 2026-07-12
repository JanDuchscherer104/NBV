"""In-memory replay transitions and trajectories.

These DTOs describe selected finite-candidate transitions. Persisted Zarr rows
remain separate contracts in :mod:`aria_nbv.rollouts.zarr_store`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import torch
from efm3d.aria import CameraTW
from efm3d.aria.pose import PoseTW

from ...pose_generation.types import CandidateSamplingResult
from ...pose_generation.utils import ensure_unbatched_pose
from .policy import CounterfactualSelectionPolicy


def _pose_row(pose: PoseTW) -> torch.Tensor:
    return pose.tensor().reshape(-1, 12)[:1]


def _pose_at(poses: PoseTW, index: int) -> PoseTW:
    if getattr(poses, "ndim", 1) > 1:
        return ensure_unbatched_pose(poses[index])
    if index != 0:
        raise IndexError(f"Cannot select index {index} from an unbatched PoseTW.")
    return ensure_unbatched_pose(poses)


@dataclass(slots=True)
class CounterfactualSelectionRecord:
    """Selected valid-candidate index plus the distribution used to draw it."""

    valid_index: int
    logits: torch.Tensor
    probabilities: torch.Tensor
    log_probabilities: torch.Tensor
    entropy: float
    selected_log_probability: float


@dataclass(slots=True)
class CounterfactualStepResult:
    """One selected rollout transition."""

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

    @property
    def selected_pose_world(self) -> PoseTW:
        """Return the selected valid pose in world coordinates."""

        return _pose_at(self.candidates.poses_world_cam(), self.selected_valid_index)

    @property
    def selected_view(self) -> CameraTW:
        """Return the selected candidate camera."""

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
    terminated_early: bool = False

    def final_pose_world(self) -> PoseTW:
        """Return the root pose or final selected pose."""

        if not self.steps:
            return self.root_pose_world
        return self.steps[-1].selected_pose_world

    def pose_chain_world(self) -> PoseTW:
        """Return root and selected poses in trajectory order."""

        rows = [_pose_row(self.root_pose_world)]
        rows.extend(_pose_row(step.selected_pose_world) for step in self.steps)
        return PoseTW(torch.cat(rows, dim=0))

    def history_centers_world(self) -> torch.Tensor:
        """Return root and selected camera centres in world coordinates."""

        return self.pose_chain_world().t.reshape(-1, 3)

    def reference_pose_world(self, step_index: int) -> PoseTW:
        """Return the pose from which ``step_index`` expands."""

        if step_index <= 0 or not self.steps:
            return self.root_pose_world
        return self.steps[step_index - 1].selected_pose_world

    def with_appended_step(self, step: CounterfactualStepResult) -> "CounterfactualTrajectory":
        """Return a new trajectory with one selected transition appended."""

        return CounterfactualTrajectory(
            root_pose_world=self.root_pose_world,
            root_time_ns=self.root_time_ns,
            root_trajectory_index=self.root_trajectory_index,
            root_frame_index=self.root_frame_index,
            steps=[*self.steps, step],
            cumulative_score=float(self.cumulative_score + step.selection_score),
            terminated_early=False,
        )

    def mark_terminated(self) -> "CounterfactualTrajectory":
        """Return an early-terminated copy."""

        return replace(self, terminated_early=True)


@dataclass(slots=True)
class CounterfactualRolloutResult:
    """All trajectories produced by one replay-engine call."""

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


__all__ = [
    "CounterfactualRolloutResult",
    "CounterfactualSelectionRecord",
    "CounterfactualStepResult",
    "CounterfactualTrajectory",
]
