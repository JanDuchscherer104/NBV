"""Prepared relative reconstruction improvement payloads and computation.

This module centralizes the numerical guard, candidate-aligned result payload,
and pure RRI formula shared by Oracle scorers. Evidence preparation and
point--mesh distance evaluation remain in their owning modules.

`RriResult` stores both the scalar improvement label and the directional
point-mesh diagnostics needed to audit target-vs-scene behavior. Downstream
datasets should carry these diagnostics when feasible so improvements in RRI
can be decomposed into accuracy and completeness changes.
"""

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
    r"""Batch of oracle RRI labels and directional distance diagnostics.

    ``C`` is the finite-candidate axis. Reference-only distances are broadcast
    to that axis so every diagnostic stays aligned with its candidate row. For
    the bidirectional squared point--mesh error $D$, the label is

    $$
    \mathrm{RRI}(q)=\frac{D(P_t,M)-D(P_t\cup P_q,M)}
                           {\max(D(P_t,M),\epsilon)}.
    $$

    RRI is dimensionless and can be negative when candidate evidence worsens
    the reconstruction. A low or negative value is still a valid oracle label;
    candidate invalidity is an upstream hard-mask/reason-code contract and is
    not encoded in this payload. In the thesis pipeline, the matched target
    mesh and rendered candidate geometry are oracle-only supervision, not
    actor-visible VIN inputs.
    """

    rri: Tensor
    """``Tensor["C", float32]`` dimensionless relative reconstruction improvement."""
    pm_dist_before: Tensor
    """``Tensor["C", float32]`` broadcast pre-view bidirectional error, in square metres."""
    pm_dist_after: Tensor
    """``Tensor["C", float32]`` post-view bidirectional error per candidate, in square metres."""
    pm_acc_before: Tensor
    """``Tensor["C", float32]`` broadcast pre-view point-to-mesh error, in square metres."""
    pm_comp_before: Tensor
    """``Tensor["C", float32]`` broadcast pre-view mesh-to-point error, in square metres."""
    pm_acc_after: Tensor
    """``Tensor["C", float32]`` post-view point-to-mesh error, in square metres."""
    pm_comp_after: Tensor
    """``Tensor["C", float32]`` post-view mesh-to-point error, in square metres."""
    fscore_tau: Tensor | None = None
    """Optional ``Tensor["C ...", float32]`` per-candidate F-scores at configured thresholds."""

    def to_serializable(self) -> dict[str, Any]:
        """Serialize tensors into a cache-friendly CPU payload without changing candidate order."""

        return to_serializable(self)

    @classmethod
    def from_serializable(
        cls,
        payload: dict[str, Any],
        *,
        device: torch.device,
    ) -> "RriResult":
        """Reconstruct one candidate-aligned result on a requested device.

        Args:
            payload: Serialized payload produced by :meth:`to_serializable`.
            device: Destination device for tensors.

        Returns:
            Reconstructed RRI result.
        """

        return from_serializable(cls, payload, device=device)

    def to(self, device: torch.device) -> RriResult:
        """Return a copy with every present tensor moved to ``device``."""
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
