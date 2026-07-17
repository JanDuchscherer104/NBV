"""Point-feature pooling result container for logged multiview evidence.

This module owns the structured tensors emitted after reducing the frame axis
for each actor-visible world point.
"""

from __future__ import annotations

from dataclasses import dataclass

from torch import Tensor


@dataclass(slots=True)
class FeaturePoolingResult:
    """Weighted point descriptors pooled over logged observations."""

    features: Tensor
    """``Tensor["B N_p C", float32]`` weighted descriptor mean per point."""

    valid_mask: Tensor
    """``Tensor["B N_p", bool]`` points supported by at least one frame."""

    valid_frame_count: Tensor
    """``Tensor["B N_p", int64]`` valid logged frames per point."""

    weight_sum: Tensor
    """``Tensor["B N_p", float32]`` pooling-weight sum before epsilon."""


__all__ = ["FeaturePoolingResult"]
