"""Finite-candidate rollout policy specification.

This module owns action-selection names and the complete immutable policy
configuration. Candidate generation remains in :mod:`aria_nbv.pose_generation`;
the replay engine consumes one policy spec without duplicating its fields in
pipeline recipes.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator
from pydantic_settings import SettingsConfigDict

from ...utils import BaseConfig


class CounterfactualSelectionPolicy(StrEnum):
    """Built-in policies used to rank valid candidates during rollout expansion."""

    FARTHEST_FROM_HISTORY = "farthest_from_history"
    FARTHEST_FROM_REFERENCE = "farthest_from_reference"
    RANDOM = "random"
    RANDOM_VALID = "random_valid"
    ORACLE_GREEDY = "oracle_greedy"
    TEMPERATURE_SOFTMAX = "temperature_softmax"


class RolloutPolicySpec(BaseConfig):
    """Immutable branching and action-selection policy for one rollout recipe."""

    model_config = SettingsConfigDict(frozen=True, validate_assignment=False)

    horizon: int = Field(default=3, ge=1)
    """Maximum number of selected transitions."""

    branch_factor: int = Field(default=2, ge=1)
    """Default number of child actions expanded per non-terminal state."""

    beam_width: int | None = Field(default=None, ge=1)
    """Maximum retained partial trajectories; ``None`` keeps every branch."""

    branch_factor_schedule: tuple[int, ...] | None = None
    """Optional deterministic per-step branch counts; the final value repeats."""

    stochastic_branch_factors: tuple[int, ...] | None = None
    """Optional seeded branch-count choices sampled per expanded state."""

    stochastic_branch_probabilities: tuple[float, ...] | None = None
    """Optional probabilities aligned with ``stochastic_branch_factors``."""

    selection_policy: CounterfactualSelectionPolicy = CounterfactualSelectionPolicy.FARTHEST_FROM_HISTORY
    """Policy used to rank or sample admitted candidate actions."""

    selection_temperature: float = Field(default=1.0, gt=0.0)
    """Temperature used by stochastic score-based selection."""

    robust_temperature_logits: bool = True
    """Normalize finite scores by median and IQR before temperature scaling."""

    min_history_distance_m: float = Field(default=0.0, ge=0.0)
    """Minimum distance from poses already selected in the current trajectory."""

    min_sibling_distance_m: float = Field(default=0.0, ge=0.0)
    """Minimum translation separation between sibling branches, in metres."""

    min_sibling_yaw_deg: float = Field(default=0.0, ge=0.0)
    """Minimum yaw separation between sibling branches, in degrees."""

    min_sibling_target_bearing_deg: float = Field(default=0.0, ge=0.0)
    """Minimum target-bearing separation between sibling branches, in degrees."""

    require_sibling_strategy_diversity: bool = False
    """Prefer distinct candidate strategy families among sibling branches."""

    seed: int | None = Field(default=0, ge=0)
    """Seed used once for deterministic policy sampling; ``None`` is unseeded."""

    @model_validator(mode="after")
    def _validate_branch_controls(self) -> "RolloutPolicySpec":
        if self.branch_factor_schedule is not None and self.stochastic_branch_factors is not None:
            raise ValueError("Use either branch_factor_schedule or stochastic_branch_factors, not both.")
        if self.branch_factor_schedule is not None:
            if not self.branch_factor_schedule:
                raise ValueError("branch_factor_schedule must be non-empty when set.")
            if any(value < 1 for value in self.branch_factor_schedule):
                raise ValueError("branch_factor_schedule entries must be >= 1.")
        if self.stochastic_branch_factors is not None:
            if not self.stochastic_branch_factors:
                raise ValueError("stochastic_branch_factors must be non-empty when set.")
            if any(value < 1 for value in self.stochastic_branch_factors):
                raise ValueError("stochastic_branch_factors entries must be >= 1.")
        if self.stochastic_branch_probabilities is not None:
            if self.stochastic_branch_factors is None:
                raise ValueError("stochastic_branch_probabilities require stochastic_branch_factors.")
            if len(self.stochastic_branch_probabilities) != len(self.stochastic_branch_factors):
                raise ValueError("stochastic_branch_probabilities must match stochastic_branch_factors length.")
            if any(value < 0.0 for value in self.stochastic_branch_probabilities):
                raise ValueError("stochastic_branch_probabilities entries must be >= 0.")
            if sum(self.stochastic_branch_probabilities) <= 0.0:
                raise ValueError("stochastic_branch_probabilities must have positive total mass.")
        return self


__all__ = ["CounterfactualSelectionPolicy", "RolloutPolicySpec"]
