"""Training objectives and label transforms for RRI-derived targets."""

from .coral import (
    CoralLayer,
    coral_expected_from_logits,
    coral_logits_to_label,
    coral_logits_to_prob,
    coral_loss,
    coral_monotonicity_violation_rate,
    coral_random_loss,
)
from .ordinal_binning import RriOrdinalBinner, ordinal_labels_to_levels

__all__ = [
    "CoralLayer",
    "RriOrdinalBinner",
    "coral_expected_from_logits",
    "coral_logits_to_label",
    "coral_logits_to_prob",
    "coral_loss",
    "coral_monotonicity_violation_rate",
    "coral_random_loss",
    "ordinal_labels_to_levels",
]
