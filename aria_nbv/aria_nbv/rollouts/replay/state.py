"""In-memory replay transitions and trajectories.

This module contains DTOs for selected finite-candidate transitions. Persisted Zarr rows
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
    """Selected compact-valid row and the distribution used to draw it.

    ``V`` is the number of hard-valid actions in the step-local candidate
    shell. Every tensor in this record is aligned to ``V`` rather than the
    full shell axis ``N``.
    """

    valid_index: int
    """Selected zero-based row on the compact valid-candidate axis ``V``."""

    logits: torch.Tensor
    """Selection logits as ``Tensor["V", float32]`` before softmax."""

    probabilities: torch.Tensor
    """Normalized action probabilities as ``Tensor["V", float32]``."""

    log_probabilities: torch.Tensor
    """Natural-log action probabilities as ``Tensor["V", float32]``."""

    entropy: float
    """Categorical entropy of `probabilities`, in nats."""

    selected_log_probability: float
    """Log probability assigned to `valid_index`, in nats."""


@dataclass(slots=True)
class CounterfactualStepResult:
    """One selected transition and its finite-candidate decision context.

    ``N`` is the generated shell width and ``V`` its compact hard-valid
    subset. Candidate generation owns ``N`` and its validity mask; selection
    vectors use ``V`` and map back through `selected_shell_index`.
    """

    step_index: int
    """Zero-based rollout depth on the horizon axis ``H``."""

    candidates: CandidateSamplingResult
    """Full ``N``-row shell, validity masks, valid views, and provenance."""

    selected_valid_index: int
    """Selected zero-based row on the compact valid axis ``V``."""

    selected_shell_index: int
    """Corresponding zero-based row on the full shell axis ``N``."""

    selection_score: float
    """Policy score of the selected action; never a validity sentinel."""

    selection_score_label: str = "score"
    """Stable semantic name for the selection-score channel."""

    selection_scores: torch.Tensor | None = None
    """Optional scores as ``Tensor["V", float32]`` in compact-valid order."""

    selection_policy: str = "unknown"
    """Policy identifier used to choose the action."""

    selection_temperature: float | None = None
    """Softmax temperature when sampling from a score distribution."""

    selection_logits: torch.Tensor | None = None
    """Optional selection logits as ``Tensor["V", float32]``."""

    selection_probabilities: torch.Tensor | None = None
    """Optional action probabilities as ``Tensor["V", float32]``."""

    selection_log_probabilities: torch.Tensor | None = None
    """Optional log action probabilities as ``Tensor["V", float32]``."""

    selection_entropy: float | None = None
    """Categorical selection entropy in nats."""

    selected_log_probability: float | None = None
    """Log probability of the selected compact-valid row, in nats."""

    selection_rng_seed: int | None = None
    """Deterministic per-node seed used for stochastic selection."""

    @property
    def selected_pose_world(self) -> PoseTW:
        """Return the selected valid pose in world coordinates."""

        return _pose_at(self.candidates.poses_world_cam(), self.selected_valid_index)

    @property
    def selected_view(self) -> CameraTW:
        """Return the selected candidate camera from the compact valid table."""

        views = self.candidates.views
        if getattr(views, "ndim", 1) > 1:
            return views[self.selected_valid_index]
        return views


@dataclass(slots=True)
class CounterfactualTrajectory:
    """One retained root-to-leaf path through the replay tree.

    A trajectory has at most ``H`` transitions and
    ``T = len(steps) + 1`` physical camera poses including its root. Update
    helpers return new records so sibling branches do not share step lists.
    """

    root_pose_world: PoseTW
    """Physical world-from-camera pose at rollout depth zero."""

    root_time_ns: int | None = None
    """Source capture timestamp in nanoseconds, when available."""

    root_trajectory_index: int | None = None
    """Source trajectory-sample index used to reconstruct root evidence."""

    root_frame_index: int | None = None
    """Source frame index associated with the root camera pose."""

    steps: list[CounterfactualStepResult] = field(default_factory=list)
    """Selected transitions in increasing zero-based horizon order."""

    cumulative_score: float = 0.0
    """Sum of policy selection scores along this retained path."""

    terminated_early: bool = False
    """Whether expansion stopped before the configured horizon."""

    def final_pose_world(self) -> PoseTW:
        """Return the root pose or final selected pose."""

        if not self.steps:
            return self.root_pose_world
        return self.steps[-1].selected_pose_world

    def pose_chain_world(self) -> PoseTW:
        """Return root and selected poses in trajectory order.

        Returns:
            Batched `PoseTW` backed by ``Tensor["T 12", float32]``, where
            ``T = len(steps) + 1``.
        """

        rows = [_pose_row(self.root_pose_world)]
        rows.extend(_pose_row(step.selected_pose_world) for step in self.steps)
        return PoseTW(torch.cat(rows, dim=0))

    def history_centers_world(self) -> torch.Tensor:
        """Return camera centres as ``Tensor["T 3", float32]`` in world metres."""

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
        """Return an immutable-style copy marked as terminated before the horizon."""

        return replace(self, terminated_early=True)


@dataclass(slots=True)
class CounterfactualRolloutResult:
    """Retained replay leaves and tree controls for one physical root pose.

    ``H`` is maximum depth, ``B`` is base sibling expansion count, and
    ``L = len(trajectories)`` is the retained branch/beam axis after pruning.
    Each step retains its own variable-width candidate shell.
    """

    root_pose_world: PoseTW
    """Physical world-from-camera pose shared by all retained trajectories."""

    trajectories: list[CounterfactualTrajectory]
    """Retained root-to-leaf paths on the branch/beam axis ``L``."""

    horizon: int
    """Maximum number of selected transitions ``H`` per path."""

    branch_factor: int
    """Base sibling expansion count ``B`` before beam pruning."""

    beam_width: int | None
    """Maximum retained partial paths per depth, or ``None`` for no cap."""

    selection_policy: str | CounterfactualSelectionPolicy
    """Action-selection policy shared by the replay call."""

    score_label: str = "score"
    """Stable semantic name for per-action selection scores."""

    root_time_ns: int | None = None
    """Source capture timestamp in nanoseconds, when available."""

    root_trajectory_index: int | None = None
    """Source trajectory index used to reconstruct root evidence."""

    root_frame_index: int | None = None
    """Source frame index associated with the root pose."""


__all__ = [
    "CounterfactualRolloutResult",
    "CounterfactualSelectionRecord",
    "CounterfactualStepResult",
    "CounterfactualTrajectory",
]
