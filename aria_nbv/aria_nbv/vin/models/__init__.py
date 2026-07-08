"""Top-level VIN model namespace.

This package is the intended home for trainable VIN scorer architectures:

- `aria_nbv.vin.models.scene_myopic` exposes the preserved seminar-era `VinModelV3`.
- `aria_nbv.vin.models.target_myopic` reserves the one-step,
  target-conditioned scorer family.
- `aria_nbv.vin.models.target_finite_horizon` reserves the finite-horizon candidate-value
  scorer family planned for Q_H rollout learning.

The preserved v3 implementation now lives in `aria_nbv.vin.models.scene_myopic`; root
VIN imports re-export it without owning a duplicate implementation.
"""

from __future__ import annotations

from .scene_myopic import VinModelV3, VinModelV3Config
from .target_finite_horizon import MultiStepCandidateScorer, MultiStepCandidateScorerConfig
from .target_myopic import TargetConditionedMyopicScorer, TargetConditionedMyopicScorerConfig

__all__ = [
    "MultiStepCandidateScorer",
    "MultiStepCandidateScorerConfig",
    "TargetConditionedMyopicScorer",
    "TargetConditionedMyopicScorerConfig",
    "VinModelV3",
    "VinModelV3Config",
]
