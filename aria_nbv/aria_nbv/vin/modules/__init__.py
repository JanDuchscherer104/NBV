"""Reusable neural building blocks for VIN scorer architectures.

The package owns `torch.nn.Module` components that are shared across active
and planned VIN scorers, while top-level architecture orchestration remains in
`aria_nbv.vin.models`.
"""

from __future__ import annotations

from .heads import VinScorerHead, VinScorerHeadConfig
from .normalization import largest_divisor_leq
from .pooling import PoseConditionedGlobalPool
from .qh_history_encoders import (
    QhCausalTransformerHistoryEncoder,
    QhCausalTransformerHistoryEncoderConfig,
    QhHistoryEncoderConfig,
    QhMeanPoolHistoryEncoder,
    QhMeanPoolHistoryEncoderConfig,
)
from .qh_scene_encoders import QhRootMomentsSceneEncoder, QhSceneChannel
from .qh_state_fusion import (
    QhCrossAttentionStateFusion,
    QhCrossAttentionStateFusionConfig,
    QhIndependentMlpStateFusion,
    QhIndependentMlpStateFusionConfig,
    QhStateFusionConfig,
)
from .qh_value_decoders import (
    QhCoralAuxiliary,
    QhCoralSupportProvenance,
    QhCoralValueDecoder,
    QhCoralValueDecoderConfig,
    QhDecodedValue,
    QhLegacyFixedCoralSupport,
    QhPredeclaredPhysicalCoralSupport,
    QhRegressionValueDecoder,
    QhRegressionValueDecoderConfig,
    QhTrainFittedCoralSupport,
    QhValueDecoderConfig,
)
from .scene_field import SceneFieldProjection, SceneFieldProjectionConfig
from .semidense_grid import SemidenseGridEncoder, SemidenseGridEncoderConfig

__all__ = [
    "PoseConditionedGlobalPool",
    "QhCausalTransformerHistoryEncoder",
    "QhCausalTransformerHistoryEncoderConfig",
    "QhCoralAuxiliary",
    "QhCoralSupportProvenance",
    "QhCoralValueDecoder",
    "QhCoralValueDecoderConfig",
    "QhDecodedValue",
    "QhLegacyFixedCoralSupport",
    "QhPredeclaredPhysicalCoralSupport",
    "QhRegressionValueDecoder",
    "QhRegressionValueDecoderConfig",
    "QhRootMomentsSceneEncoder",
    "QhSceneChannel",
    "QhTrainFittedCoralSupport",
    "QhValueDecoderConfig",
    "QhCrossAttentionStateFusion",
    "QhCrossAttentionStateFusionConfig",
    "QhIndependentMlpStateFusion",
    "QhIndependentMlpStateFusionConfig",
    "QhHistoryEncoderConfig",
    "QhMeanPoolHistoryEncoder",
    "QhMeanPoolHistoryEncoderConfig",
    "QhStateFusionConfig",
    "SceneFieldProjection",
    "SceneFieldProjectionConfig",
    "SemidenseGridEncoder",
    "SemidenseGridEncoderConfig",
    "VinScorerHead",
    "VinScorerHeadConfig",
    "largest_divisor_leq",
]
