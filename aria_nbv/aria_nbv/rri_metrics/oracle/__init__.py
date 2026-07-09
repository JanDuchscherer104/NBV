"""Oracle evidence preparation and RRI scoring."""

from .evidence import (
    RootEvalPointCloud,
    RriEvaluationPointCloudSource,
    RriRewardMode,
    build_root_eval_pointcloud,
    canonical_fuse_points,
    observed_prefix_frame_indices,
)
from .scorer import OracleRRI, OracleRRIConfig

__all__ = [
    "OracleRRI",
    "OracleRRIConfig",
    "RootEvalPointCloud",
    "RriEvaluationPointCloudSource",
    "RriRewardMode",
    "build_root_eval_pointcloud",
    "canonical_fuse_points",
    "observed_prefix_frame_indices",
]
