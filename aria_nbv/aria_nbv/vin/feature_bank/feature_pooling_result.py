"""Point-feature pooling result container."""

from __future__ import annotations

from dataclasses import dataclass

from torch import Tensor


@dataclass(slots=True)
class FeaturePoolingResult:
    """Weighted point descriptors pooled over logged observations.

    Attributes:
        features: ``Tensor["B N C"]`` weighted mean descriptor per point.
        valid_mask: ``Tensor["B N", bool]`` indicating at least one valid sample.
        valid_frame_count: ``Tensor["B N", int64]`` number of valid logged frames.
        weight_sum: ``Tensor["B N"]`` sum of pooling weights before epsilon.
    """

    features: Tensor
    valid_mask: Tensor
    valid_frame_count: Tensor
    weight_sum: Tensor


__all__ = ["FeaturePoolingResult"]
