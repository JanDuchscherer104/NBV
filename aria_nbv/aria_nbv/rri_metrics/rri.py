"""Prepared relative reconstruction improvement computation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch
from torch import Tensor

from ..utils.typed_payloads import from_serializable, to_serializable
from .point_mesh import DistanceBreakdown


@dataclass(frozen=True, slots=True)
class RriConfig:
    """Numerical contract for prepared RRI computation."""

    epsilon: float = 1e-12
    """Positive denominator guard for zero-error roots."""

    def __post_init__(self) -> None:
        if self.epsilon <= 0.0:
            raise ValueError("epsilon must be positive.")


_DEFAULT_RRI_CONFIG = RriConfig()


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


def compute_rri(
    before: DistanceBreakdown,
    after: DistanceBreakdown,
    *,
    config: RriConfig = _DEFAULT_RRI_CONFIG,
) -> RriResult:
    """Compute RRI from prepared before/after point-mesh distances.

    The caller owns evidence preparation, cropping, and fusion. This function
    owns only the differentiable reconstruction-improvement formula.
    """

    denominator = before.bidirectional.clamp_min(config.epsilon)
    rri = (before.bidirectional - after.bidirectional) / denominator
    return RriResult(
        rri=rri,
        pm_dist_before=before.bidirectional.expand_as(rri),
        pm_dist_after=after.bidirectional,
        pm_acc_before=before.accuracy.expand_as(rri),
        pm_comp_before=before.completeness.expand_as(rri),
        pm_acc_after=after.accuracy,
        pm_comp_after=after.completeness,
    )


__all__ = ["RriConfig", "RriResult", "compute_rri"]
