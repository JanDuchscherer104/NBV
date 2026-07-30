"""Top-level VIN model namespace for runnable scorer implementations.

`aria_nbv.vin.models.scene_myopic` owns the preserved seminar-era
`VinModelV3`. The target-conditioned myopic family remains leaf-only; the
non-runnable finite-horizon scaffold was removed because scorer-independent
``Q_H`` training infrastructure does not imply a production scorer.
"""

from __future__ import annotations

from .scene_myopic import VinModelV3, VinModelV3Config

__all__ = [
    "VinModelV3",
    "VinModelV3Config",
]
