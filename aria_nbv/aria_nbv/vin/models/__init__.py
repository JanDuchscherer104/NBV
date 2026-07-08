"""Top-level VIN model namespace for runnable scorer implementations.

`aria_nbv.vin.models.scene_myopic` owns the preserved seminar-era
`VinModelV3`. Scaffold-only target-conditioned and finite-horizon families stay
available from their leaf modules so broad imports do not imply runnable target
scoring or Q_H support.
"""

from __future__ import annotations

from .scene_myopic import VinModelV3, VinModelV3Config

__all__ = [
    "VinModelV3",
    "VinModelV3Config",
]
