"""Reusable neural building blocks for VIN scorer architectures.

The package collects `torch.nn.Module` components that are shared across active
and planned VIN scorers, while top-level architecture orchestration remains in
`aria_nbv.vin.models`.
"""

from __future__ import annotations

from .heads import VinScorerHead, VinScorerHeadConfig
from .normalization import largest_divisor_leq
from .pooling import PoseConditionedGlobalPool

__all__ = ["PoseConditionedGlobalPool", "VinScorerHead", "VinScorerHeadConfig", "largest_divisor_leq"]
