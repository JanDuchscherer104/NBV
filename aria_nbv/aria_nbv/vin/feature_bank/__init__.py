"""Feature-bank containers and pooling helpers for VIN readers.

This package owns actor-visible point-descriptor payloads, multiview sampling,
permutation-invariant reductions, compression labels, and source-role checks.
"""

from __future__ import annotations

from .compression import compress_point_features
from .feature_pooling_result import FeaturePoolingResult
from .point_feature_bank import PointFeatureBank
from .point_query_pool import PointQueryPool
from .pooling import pool_multiview_point_features, pool_point_query
from .provenance import validate_actor_feature_provenance
from .sampling import sample_logged_image_features_at_world_points

__all__ = [
    "FeaturePoolingResult",
    "PointFeatureBank",
    "PointQueryPool",
    "compress_point_features",
    "pool_multiview_point_features",
    "pool_point_query",
    "sample_logged_image_features_at_world_points",
    "validate_actor_feature_provenance",
]
