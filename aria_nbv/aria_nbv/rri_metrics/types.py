"""Typed distance and oracle-label payloads for RRI computation.

This module centralises small, self-contained data structures that are shared
between the RRI metrics utilities and the high-level ``OracleRRI`` facade.
Keeping the types separate avoids circular imports between :mod:`metrics` and
:mod:`aria_nbv.rri_metrics.oracle_rri` while providing one source of truth for
candidate axes, squared-distance units, and semantic meaning.

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
    """Directional mean-squared components of a point--mesh distance.

    Leading dimensions are preserved: the unbatched primitive returns scalar
    tensors, while the batched primitive returns one value per candidate.
    Metric-frame inputs therefore produce values in square metres.
    """

    accuracy: Tensor
    """``Tensor["...", float32]`` mean squared point-to-triangle distance, in square metres."""
    completeness: Tensor
    """``Tensor["...", float32]`` mean squared triangle-to-point distance, in square metres."""
    bidirectional: Tensor
    """``Tensor["...", float32]`` sum of accuracy and completeness, in square metres."""


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


__all__ = [
    "DistanceAggregation",
    "DistanceBreakdown",
    "RriResult",
]
