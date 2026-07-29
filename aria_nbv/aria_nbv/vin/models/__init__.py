"""Top-level VIN model namespace for runnable scorer implementations.

:mod:`aria_nbv.vin.models.scene_myopic` owns the preserved seminar-era
:class:`aria_nbv.vin.models.scene_myopic.VinModelV3`. Specialized
target-conditioned and finite-horizon families stay
available from their leaf modules so broad imports do not conflate their
different training objectives.
"""

from __future__ import annotations

from .scene_myopic import VinModelV3, VinModelV3Config

__all__ = [
    "VinModelV3",
    "VinModelV3Config",
]
