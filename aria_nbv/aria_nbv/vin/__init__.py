"""VIN one-step scoring models and typed prediction contracts.

The active public surface is `VinModelV3`: a target-agnostic one-step scorer for
candidate RRI rows that uses EVL voxel evidence, candidate pose encodings,
semidense projection features, and a CORAL ordinal head. It is the implemented
seminar substrate and the myopic control for the thesis target-conditioned
rollout work; it is not a full multi-step NBV policy.

Inputs must preserve actor/oracle separation. EVL fields, candidate poses, and
semidense observations are actor-visible features. Oracle RRI labels, GT meshes,
and target crops are supervision/evaluation assets.
"""

from __future__ import annotations

from .backbones import EvlBackbone, EvlBackboneConfig
from .candidate_scorer import (
    CandidateScorer,
    CandidateScorerConfig,
    CandidateScorerPrediction,
)
from .encoders import (
    LearnableFourierFeatures,
    LearnableFourierFeaturesConfig,
    PoseEncoder,
    PoseEncodingOutput,
    R6dLffPoseEncoder,
    R6dLffPoseEncoderConfig,
    TrajectoryEncoder,
    TrajectoryEncoderConfig,
    TrajectoryEncodingOutput,
)
from .feature_bank import (
    FeaturePoolingResult,
    PointFeatureBank,
    PointQueryPool,
    compress_point_features,
    pool_multiview_point_features,
    pool_point_query,
    sample_logged_image_features_at_world_points,
    validate_actor_feature_provenance,
)
from .models import (
    MultiStepCandidateScorer,
    MultiStepCandidateScorerConfig,
    TargetConditionedMyopicScorer,
    TargetConditionedMyopicScorerConfig,
    VinModelV3,
    VinModelV3Config,
)
from .types import EvlBackboneOutput, VinPrediction, VinV3ForwardDiagnostics

__all__ = [
    "EvlBackbone",
    "EvlBackboneConfig",
    "EvlBackboneOutput",
    "CandidateScorer",
    "CandidateScorerConfig",
    "CandidateScorerPrediction",
    "FeaturePoolingResult",
    "LearnableFourierFeatures",
    "LearnableFourierFeaturesConfig",
    "MultiStepCandidateScorer",
    "MultiStepCandidateScorerConfig",
    "PointFeatureBank",
    "PointQueryPool",
    "PoseEncoder",
    "PoseEncodingOutput",
    "R6dLffPoseEncoder",
    "R6dLffPoseEncoderConfig",
    "TargetConditionedMyopicScorer",
    "TargetConditionedMyopicScorerConfig",
    "TrajectoryEncoder",
    "TrajectoryEncoderConfig",
    "TrajectoryEncodingOutput",
    "VinModelV3",
    "VinModelV3Config",
    "VinPrediction",
    "VinV3ForwardDiagnostics",
    "compress_point_features",
    "pool_multiview_point_features",
    "pool_point_query",
    "sample_logged_image_features_at_world_points",
    "validate_actor_feature_provenance",
]
