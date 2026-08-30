"""Top-level VIN model namespace for runnable scorer implementations.

`aria_nbv.vin.models.scene_myopic` owns the preserved seminar-era
`VinModelV3`. `aria_nbv.vin.models.target_finite_horizon` owns the production
actor-only ``Q_H`` scorer over persisted chain views.
"""

from __future__ import annotations

from .scene_myopic import VinModelV3, VinModelV3Config
from .target_finite_horizon import (
    QhScoreOutput,
    TargetFiniteHorizonScorer,
    TargetFiniteHorizonScorerConfig,
)

__all__ = [
    "QhScoreOutput",
    "TargetFiniteHorizonScorer",
    "TargetFiniteHorizonScorerConfig",
    "VinModelV3",
    "VinModelV3Config",
]
