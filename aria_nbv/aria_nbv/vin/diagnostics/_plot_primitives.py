"""Generic Plotly primitives shared by VIN diagnostic figures.

This module owns reusable NumPy and Plotly helpers that are independent of
VIN pose, voxel, or semidense projection contracts. VIN-specific diagnostic
adapters remain in :mod:`aria_nbv.vin.diagnostics.plotting_common`, while
callers that need canonical labeling or edge flattening should import
:func:`aria_nbv.utils.reporting._pretty_label` and
:func:`aria_nbv.utils.data_plotting._flatten_edges_for_plotly` directly.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import plotly.graph_objects as go  # type: ignore[import-untyped]

from ...utils.data_plotting import _flatten_edges_for_plotly
from ...utils.reporting import _pretty_label


def _pca_2d(values: np.ndarray) -> np.ndarray:
    """Project a two-dimensional feature matrix onto its first two PCs."""
    values = np.asarray(values, dtype=float)
    if values.ndim != 2:
        raise ValueError(f"Expected values with ndim=2, got {values.ndim}.")
    values = values - values.mean(axis=0, keepdims=True)
    _, _, vt = np.linalg.svd(values, full_matrices=False)
    return values @ vt[:2].T


def _pca_2d_with_components(
    values: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return a 2-D PCA projection together with mean and component matrix."""
    values = np.asarray(values, dtype=float)
    if values.ndim != 2:
        raise ValueError(f"Expected values with ndim=2, got {values.ndim}.")
    mean = values.mean(axis=0, keepdims=True)
    centered = values - mean
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    components = vt[:2].T
    proj = centered @ components
    return proj, mean, components


def _histogram_edges(values_list: Iterable[np.ndarray], *, bins: int) -> np.ndarray:
    """Compute shared histogram bin edges over finite values from many arrays."""
    arrays: list[np.ndarray] = []
    for arr in values_list:
        vals = np.asarray(arr, dtype=float).reshape(-1)
        vals = vals[np.isfinite(vals)]
        if vals.size:
            arrays.append(vals)
    if not arrays:
        return np.array([0.0, 1.0], dtype=float)
    return np.histogram_bin_edges(np.concatenate(arrays, axis=0), bins=int(bins))


def _histogram_bar(
    values: np.ndarray,
    *,
    edges: np.ndarray,
    name: str,
    color: str | None = None,
    opacity: float = 0.6,
    log1p_counts: bool = False,
) -> go.Bar:
    """Create a Plotly bar trace for values binned by precomputed edges."""
    vals = np.asarray(values, dtype=float).reshape(-1)
    vals = vals[np.isfinite(vals)]
    counts, _ = np.histogram(vals, bins=edges)
    centers = 0.5 * (edges[:-1] + edges[1:])
    y = np.log1p(counts) if log1p_counts else counts
    marker: dict[str, Any] = {"opacity": opacity}
    if color is not None:
        marker["color"] = color
    return go.Bar(x=centers, y=y, name=_pretty_label(name), marker=marker)


def _segment_trace(
    starts: np.ndarray,
    ends: np.ndarray,
    *,
    color: str,
    name: str,
    width: int = 4,
) -> go.Scatter3d:
    """Create a 3-D line trace from paired start and end points."""
    starts = np.asarray(starts, dtype=float).reshape(-1, 3)
    ends = np.asarray(ends, dtype=float).reshape(-1, 3)
    segments = np.stack([starts, ends], axis=1)
    x, y, z = _flatten_edges_for_plotly(segments)
    return go.Scatter3d(
        x=x,
        y=y,
        z=z,
        mode="lines",
        line={"color": color, "width": width},
        name=name,
        showlegend=True,
    )


def _line_trace(
    start: np.ndarray,
    end: np.ndarray,
    *,
    color: str,
    name: str,
    width: int = 3,
) -> go.Scatter3d:
    """Create a single-segment 3-D line trace."""
    starts = np.asarray(start, dtype=float).reshape(1, 3)
    ends = np.asarray(end, dtype=float).reshape(1, 3)
    return _segment_trace(starts, ends, color=color, name=name, width=width)


def _scatter3d(
    points: np.ndarray,
    *,
    name: str,
    color: str | None = None,
    values: np.ndarray | None = None,
    colorscale: str | None = None,
    size: int = 3,
    opacity: float = 0.7,
    prettify_name: bool = True,
) -> go.Scatter3d:
    """Create a 3-D point trace with either a fixed color or scalar values."""
    pts = np.asarray(points, dtype=float).reshape(-1, 3)
    label = _pretty_label(name) if prettify_name else name
    marker: dict[str, Any] = {"size": size, "opacity": opacity}
    if values is not None:
        marker["color"] = np.asarray(values, dtype=float)
        if colorscale is not None:
            marker["colorscale"] = colorscale
        marker["colorbar"] = {"title": label}
    elif color is not None:
        marker["color"] = color

    return go.Scatter3d(
        x=pts[:, 0],
        y=pts[:, 1],
        z=pts[:, 2],
        mode="markers",
        marker=marker,
        name=label,
        showlegend=True,
    )


__all__ = [
    "_histogram_bar",
    "_histogram_edges",
    "_line_trace",
    "_pca_2d",
    "_pca_2d_with_components",
    "_scatter3d",
    "_segment_trace",
]
