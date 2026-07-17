"""Small deterministic statistics helpers for app, plots, and exports.

The functions return plain labels, slopes, and index slices so presentation
layers can share calculations without importing one another.
"""

from __future__ import annotations

import numpy as np


def _pretty_label(text: str) -> str:
    """Format labels by replacing underscores and title-casing words."""
    if not text:
        return text
    return text.replace("_", " ").title()


def _linear_slope(x: np.ndarray, y: np.ndarray) -> float:
    """Estimate a linear slope for one x/y series."""
    if x.size < 2 or np.allclose(x, x[0]):
        return float("nan")
    try:
        return float(np.polyfit(x, y, 1)[0])
    except Exception:  # pragma: no cover - numerical guard
        return float("nan")


def _segment_indices(num: int, frac: float) -> tuple[slice, slice, slice]:
    """Compute early/mid/late segment slices for a series."""
    size = max(2, int(num * frac))
    early = slice(0, size)
    late = slice(max(num - size, 0), num)
    mid_start = size
    mid_end = max(num - size, mid_start)
    mid = slice(mid_start, mid_end)
    return early, mid, late


__all__ = ["_linear_slope", "_pretty_label", "_segment_indices"]
