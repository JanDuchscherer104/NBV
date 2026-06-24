"""Masked query-pooling result container."""

from __future__ import annotations

from dataclasses import dataclass

from torch import Tensor


@dataclass(slots=True)
class PointQueryPool:
    """Permutation-invariant descriptor statistics for a masked point query.

    Attributes:
        mean: ``Tensor["B C"]`` mean descriptor over selected points.
        maximum: ``Tensor["B C"]`` elementwise maximum over selected points.
        std: ``Tensor["B C"]`` population standard deviation over selected points.
        count: ``Tensor["B", int64]`` selected-point count per batch item.
        valid_mask: ``Tensor["B", bool]`` indicating non-empty query support.
    """

    mean: Tensor
    maximum: Tensor
    std: Tensor
    count: Tensor
    valid_mask: Tensor


__all__ = ["PointQueryPool"]
