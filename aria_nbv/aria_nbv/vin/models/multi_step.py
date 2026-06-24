"""Scaffold for finite-horizon candidate-value VIN scorers.

The planned multi-step architecture predicts masked finite-candidate values
over rollout state, target context, history, and candidate tokens. It is not the
same training contract as `aria_nbv.vin.models.v3.VinModelV3`: selected-transition
returns, endpoint gains, and hard valid-action masks come from
`aria_nbv.rollouts` stores and should not be folded into one-step RRI labels.
"""

from __future__ import annotations

from pydantic import Field
from torch import nn

from ...utils import TargetConfig


class MultiStepCandidateScorerConfig(TargetConfig["MultiStepCandidateScorer"]):
    """Config-as-factory placeholder for the planned finite-horizon scorer.

    Attributes:
        horizon: Number of selected future steps represented by the Q_H target.
        discount: Discount factor applied to selected root-normalized target
            gains in finite-horizon backups.
        candidate_token_dim: Internal token width reserved for candidate-query
            Transformer or set-attention implementations.
    """

    @property
    def target_type(self) -> type["MultiStepCandidateScorer"]:
        """Factory target for `BaseConfig.setup_target` once implemented."""

        return MultiStepCandidateScorer

    horizon: int = Field(default=2, ge=1)
    """Finite planning horizon ``H`` for rollout-value targets."""

    discount: float = Field(default=1.0, ge=0.0)
    """Discount factor for finite-horizon target-root-gain returns."""

    candidate_token_dim: int = Field(default=128, gt=0)
    """Reserved hidden width for candidate-query tokens."""


class MultiStepCandidateScorer(nn.Module):
    """Non-runnable scaffold for the planned Q_H scorer.

    The future implementation should own a dedicated objective over rollout
    arrays such as target-root gain, selected-transition return, and hard valid
    masks. Construction fails explicitly so users cannot accidentally train a
    model that has no finite-horizon semantics.
    """

    def __init__(self, config: MultiStepCandidateScorerConfig) -> None:
        """Reject construction until the finite-horizon scorer is implemented."""

        super().__init__()
        self.config = config
        raise NotImplementedError(
            "MultiStepCandidateScorer is a scaffold only. Implement the rollout "
            "Q_H target contract before using this config in training.",
        )


__all__ = [
    "MultiStepCandidateScorer",
    "MultiStepCandidateScorerConfig",
]
