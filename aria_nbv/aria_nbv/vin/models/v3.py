"""Stable import surface for the preserved VIN v3 scorer.

`aria_nbv.vin.model_v3` remains the implementation owner for now. This module
exists so future model families can live under `aria_nbv.vin.models` without
forcing a broad import migration in the same commit.
"""

from __future__ import annotations

from ..model_v3 import FIELD_CHANNELS_V3, SEMIDENSE_PROJ_DIM, VinModelV3, VinModelV3Config

__all__ = [
    "FIELD_CHANNELS_V3",
    "SEMIDENSE_PROJ_DIM",
    "VinModelV3",
    "VinModelV3Config",
]
