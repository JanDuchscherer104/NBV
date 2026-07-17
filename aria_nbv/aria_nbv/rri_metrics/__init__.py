"""Stable public API for prepared RRI scoring and VIN ordinal supervision.

The package root exposes the prepared RRI payload/formula and empirical
:class:`RriOrdinalBinner` targets consumed by VIN. Oracle evidence preparation,
rollout reducers, plotting, and stateful diagnostics remain in their owning
submodules so importing
:mod:`aria_nbv.rri_metrics` does not imply those secondary APIs are stable.

Oracle geometry and RRI values are label/evaluation data. CORAL logits,
decoded ranks, and expected bin values are learned actor-side predictions;
candidate hard-validity masks remain separate from both surfaces.
"""

from .ordinal import RriOrdinalBinner
from .rri import RriConfig, RriResult, compute_rri

__all__ = ["RriConfig", "RriOrdinalBinner", "RriResult", "compute_rri"]
