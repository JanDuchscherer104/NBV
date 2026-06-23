"""Top-level VIN model namespace.

This package is the intended home for trainable VIN scorer architectures:

- `aria_nbv.vin.models.v3` exposes the preserved seminar-era `VinModelV3`.
- `aria_nbv.vin.models.target_conditioned_myopic` reserves the one-step,
  target-conditioned scorer family.
- `aria_nbv.vin.models.multi_step` reserves the finite-horizon candidate-value
  scorer family planned for Q_H rollout learning.

The active implementation still lives at `aria_nbv.vin.model_v3` to keep
historical imports, diagnostics, and checkpoint key paths stable. New code may
import v3 from this package, but no existing scorer semantics change here.
"""

from __future__ import annotations

from .multi_step import MultiStepCandidateScorer, MultiStepCandidateScorerConfig
from .target_conditioned_myopic import TargetConditionedMyopicScorer, TargetConditionedMyopicScorerConfig
from .v3 import VinModelV3, VinModelV3Config

__all__ = [
    "MultiStepCandidateScorer",
    "MultiStepCandidateScorerConfig",
    "TargetConditionedMyopicScorer",
    "TargetConditionedMyopicScorerConfig",
    "VinModelV3",
    "VinModelV3Config",
]
