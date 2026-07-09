"""Typed containers and enums for oracle RRI computation.

This module centralises small, self-contained data structures that are shared
between the RRI metrics utilities and the high-level ``OracleRRI`` facade.
Keeping the types separate avoids circular imports between ``metrics`` and
``aria_nbv.rri_metrics.oracle.scorer`` while providing a single source of truth for shapes, units, and
semantic meaning.

`RriResult` stores both the scalar improvement label and the directional
point-mesh diagnostics needed to audit target-vs-scene behavior. Downstream
datasets should carry these diagnostics when feasible so improvements in RRI
can be decomposed into accuracy and completeness changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import torch

from ..utils.typed_payloads import from_serializable, to_serializable

Tensor = torch.Tensor


class DistanceAggregation(StrEnum):
    """Supported reduction modes for distance tensors.

    - ``mean``: Average over the last dimension (preferred for Chamfer style).
    - ``sum``: Sum over the last dimension.
    - ``none``: Return per-point distances without reducing.
    """

    MEAN = "mean"
    SUM = "sum"
    NONE = "none"


@dataclass(slots=True)
class DistanceBreakdown:
    """Directional distance components used to form Chamfer-style metrics."""

    accuracy: Tensor
    """Point→mesh (prediction to GT) distances."""
    completeness: Tensor
    """Mesh→point (GT to prediction) distances."""
    bidirectional: Tensor
    """Sum of accuracy and completeness (Chamfer when using L2 distances with mean reduction)."""


@dataclass(slots=True)
class RriResult:
    """Batch of per-candidate RRI outcomes and distance diagnostics.

    Shapes follow the candidate batch dimension ``C`` produced by the caller.
    Scalars such as the reference-only distances are broadcast to ``(C,)`` so
    downstream code can remain shape-agnostic.
    """

    rri: Tensor
    """Tensor["C"] Relative reconstruction improvement ``(d_before - d_after) / d_before``."""
    pm_dist_before: Tensor
    """Tensor["C"] Bidirectional Chamfer-style distance between ``P_t`` and the GT mesh."""
    pm_dist_after: Tensor
    """Tensor["C"] Bidirectional distance between ``P_t ∪ P_q`` and the GT mesh."""
    pm_acc_before: Tensor
    """Tensor["C"] Point→mesh (accuracy) distance for ``P_t`` (broadcast)."""
    pm_comp_before: Tensor
    """Tensor["C"] Mesh→point (completeness) distance for ``P_t`` (broadcast)."""
    pm_acc_after: Tensor
    """Tensor["C"] Point→mesh distance for ``P_t ∪ P_q``."""
    pm_comp_after: Tensor
    """Tensor["C"] Mesh→point distance for ``P_t ∪ P_q``."""
    fscore_tau: Tensor | None = None
    """Optional F-score values at configured distance thresholds."""

    def to_serializable(self) -> dict[str, Any]:
        """Serialize this result into a cache-friendly CPU payload."""

        return to_serializable(self)

    @classmethod
    def from_serializable(
        cls,
        payload: dict[str, Any],
        *,
        device: torch.device,
    ) -> "RriResult":
        """Reconstruct one result from a serialized payload.

        Args:
            payload: Serialized payload produced by `to_serializable`.
            device: Destination device for tensors.

        Returns:
            Reconstructed RRI result.
        """

        return from_serializable(cls, payload, device=device)

    def to(self, device: torch.device) -> RriResult:
        """Move all tensors in this result to the specified device."""
        return RriResult(
            rri=self.rri.to(device=device),
            pm_dist_before=self.pm_dist_before.to(device=device),
            pm_dist_after=self.pm_dist_after.to(device=device),
            pm_acc_before=self.pm_acc_before.to(device=device),
            pm_comp_before=self.pm_comp_before.to(device=device),
            pm_acc_after=self.pm_acc_after.to(device=device),
            pm_comp_after=self.pm_comp_after.to(device=device),
            fscore_tau=self.fscore_tau.to(device=device) if self.fscore_tau is not None else None,
        )


__all__ = [
    "DistanceAggregation",
    "DistanceBreakdown",
    "RriResult",
]
