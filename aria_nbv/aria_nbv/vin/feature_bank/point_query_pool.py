"""Masked query-pooling result container for unordered point selections.

The module owns reduced descriptor statistics and their empty-support mask.
"""

from __future__ import annotations

from dataclasses import dataclass

from torch import Tensor


@dataclass(slots=True)
class PointQueryPool:
    """Permutation-invariant descriptor statistics for a masked point query."""

    mean: Tensor
    """``Tensor["B C", float32]`` selected-point descriptor mean."""

    maximum: Tensor
    """``Tensor["B C", float32]`` selected-point elementwise maximum."""

    std: Tensor
    """``Tensor["B C", float32]`` selected-point population deviation."""

    count: Tensor
    """``Tensor["B", int64]`` selected-point count."""

    valid_mask: Tensor
    """``Tensor["B", bool]`` non-empty query-support mask."""


__all__ = ["PointQueryPool"]
