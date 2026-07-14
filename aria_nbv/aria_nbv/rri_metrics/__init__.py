"""Stable public API for oracle RRI scoring and VIN ordinal supervision.

The package root exposes point--mesh distance containers, the oracle
:class:`OracleRRI` facade, empirical :class:`RriOrdinalBinner` targets, and the
CORAL helpers consumed by VIN. Rollout reducers, plotting, and stateful
diagnostics remain in their owning submodules so importing
:mod:`aria_nbv.rri_metrics` does not imply those secondary APIs are stable.

Oracle geometry and RRI values are label/evaluation data. CORAL logits,
decoded ranks, and expected bin values are learned actor-side predictions;
candidate hard-validity masks remain separate from both surfaces.
"""

from .coral import (
    CoralLayer,
    coral_expected_from_logits,
    coral_logits_to_prob,
    coral_loss,
    coral_random_loss,
)
from .metrics import chamfer_point_mesh, chamfer_point_mesh_batched
from .oracle_rri import OracleRRI, OracleRRIConfig
from .rri_binning import RriOrdinalBinner, ordinal_labels_to_levels
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
