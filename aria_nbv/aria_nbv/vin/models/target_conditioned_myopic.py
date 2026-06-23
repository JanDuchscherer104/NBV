"""Scaffold for a target-conditioned myopic VIN scorer.

This module names the one-step architecture family that should score each
candidate from actor-visible scene evidence plus an actor-visible target
descriptor. It is intentionally not wired into Lightning yet: the concrete
target descriptor contract and feature ownership still need implementation
tests before this can replace or extend `aria_nbv.vin.model_v3.VinModelV3`.
"""

from __future__ import annotations

from pydantic import Field
from torch import nn

from ...utils import TargetConfig


class TargetConditionedMyopicScorerConfig(TargetConfig["TargetConditionedMyopicScorer"]):
    """Config-as-factory placeholder for the planned one-step target scorer.

    Attributes:
        num_classes: Number of ordinal output classes for CORAL-style row
            scoring if the scorer uses the current VIN Lightning objective.
        target_descriptor_dim: Dimension of the actor-visible target token or
            descriptor that conditions candidate scoring.
        candidate_token_dim: Internal candidate token width reserved for the
            first target-conditioned implementation.
    """

    @property
    def target_type(self) -> type["TargetConditionedMyopicScorer"]:
        """Factory target for `BaseConfig.setup_target` once implemented."""

        return TargetConditionedMyopicScorer

    num_classes: int = Field(default=15, ge=2)
    """Number of ordinal classes for candidate-row scoring."""

    target_descriptor_dim: int = Field(default=0, ge=0)
    """Actor-visible target descriptor width; ``0`` means not implemented."""

    candidate_token_dim: int = Field(default=128, gt=0)
    """Reserved hidden width for target-conditioned candidate tokens."""


class TargetConditionedMyopicScorer(nn.Module):
    """Non-runnable scaffold for the planned myopic target scorer.

    The future implementation should satisfy
    `aria_nbv.vin.candidate_scorer.CandidateScorer` when it produces
    per-candidate ordinal logits compatible with the current Lightning loss.
    Until then, construction fails explicitly so experiments cannot silently run
    a placeholder model.
    """

    def __init__(self, config: TargetConditionedMyopicScorerConfig) -> None:
        """Reject construction until the target-conditioned scorer is implemented."""

        super().__init__()
        self.config = config
        raise NotImplementedError(
            "TargetConditionedMyopicScorer is a scaffold only. Implement the "
            "actor-visible target descriptor path before using this config in training.",
        )


__all__ = [
    "TargetConditionedMyopicScorer",
    "TargetConditionedMyopicScorerConfig",
]
