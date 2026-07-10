"""Stable root API for reconstruction-improvement metrics."""

from .oracle_rri import OracleRRI, OracleRRIConfig
from .ordinal import RriOrdinalBinner, ordinal_labels_to_levels
from .point_mesh import chamfer_point_mesh, chamfer_point_mesh_batched
from .types import DistanceAggregation, DistanceBreakdown, RriResult

__all__ = [
    "DistanceAggregation",
    "DistanceBreakdown",
    "OracleRRI",
    "OracleRRIConfig",
    "RriOrdinalBinner",
    "RriResult",
    "chamfer_point_mesh",
    "chamfer_point_mesh_batched",
    "ordinal_labels_to_levels",
]
