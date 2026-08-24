"""Reusable neural building blocks for VIN scorer architectures.

The package owns `torch.nn.Module` components that are shared across active
and planned VIN scorers, while top-level architecture orchestration remains in
`aria_nbv.vin.models`.
"""

from __future__ import annotations

from .heads import VinScorerHead, VinScorerHeadConfig
from .normalization import largest_divisor_leq
from .pooling import PoseConditionedGlobalPool
from .qh_value_decoders import (
    QhCoralAuxiliary,
    QhCoralValueDecoder,
    QhCoralValueDecoderConfig,
    QhDecodedValue,
    QhRegressionValueDecoder,
    QhRegressionValueDecoderConfig,
    QhValueDecoderConfig,
)
from .scene_field import SceneFieldProjection, SceneFieldProjectionConfig
from .semidense_grid import SemidenseGridEncoder, SemidenseGridEncoderConfig

__all__ = [
    "PoseConditionedGlobalPool",
    "QhCoralAuxiliary",
    "QhCoralValueDecoder",
    "QhCoralValueDecoderConfig",
    "QhDecodedValue",
    "QhRegressionValueDecoder",
    "QhRegressionValueDecoderConfig",
    "QhValueDecoderConfig",
    "SceneFieldProjection",
    "SceneFieldProjectionConfig",
    "SemidenseGridEncoder",
    "SemidenseGridEncoderConfig",
    "VinScorerHead",
    "VinScorerHeadConfig",
    "largest_divisor_leq",
]
