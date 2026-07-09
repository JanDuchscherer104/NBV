"""Stable root API for RRI metrics and VIN ordinal helpers."""

from .metrics.point_mesh import chamfer_point_mesh, chamfer_point_mesh_batched
from .objectives.coral import (
    CoralLayer,
    coral_expected_from_logits,
    coral_logits_to_prob,
    coral_loss,
    coral_random_loss,
)
from .objectives.ordinal_binning import RriOrdinalBinner, ordinal_labels_to_levels
from .oracle.scorer import OracleRRI, OracleRRIConfig
from .types import DistanceAggregation, DistanceBreakdown, RriResult

__all__ = [
    "CoralLayer",
    "DistanceAggregation",
    "DistanceBreakdown",
    "OracleRRI",
    "OracleRRIConfig",
    "RriOrdinalBinner",
    "RriResult",
    "chamfer_point_mesh",
    "chamfer_point_mesh_batched",
    "coral_expected_from_logits",
    "coral_logits_to_prob",
    "coral_loss",
    "coral_random_loss",
    "ordinal_labels_to_levels",
]
