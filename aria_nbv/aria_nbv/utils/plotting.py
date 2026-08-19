"""Shared scalar-field, histogram, and image plotting for diagnostics.

Tensor inputs are detached and transferred to CPU before NumPy/Plotly use;
this module owns presentation transforms, never training-frame semantics.
"""

from __future__ import annotations

from typing import Any

import matplotlib
import numpy as np
import plotly.graph_objects as go
import torch
from matplotlib import colormaps

from .data_plotting import FrameGridBuilder

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _to_numpy(tensor: torch.Tensor) -> np.ndarray:
    return tensor.detach().cpu().numpy()


def _scalar_to_rgb(
    values: np.ndarray,
    *,
    percentile: float,
    symmetric: bool,
    cmap_name: str = "viridis",
) -> np.ndarray:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return np.zeros(values.shape + (3,), dtype=np.uint8)
    if symmetric:
        vmax = float(np.nanpercentile(np.abs(finite), percentile))
        vmin = -vmax
    else:
        lower = max(0.0, 100.0 - percentile)
        vmin = float(np.nanpercentile(finite, lower))
        vmax = float(np.nanpercentile(finite, percentile))
    if vmax <= vmin:
        vmax = vmin + 1e-6
    norm = (values - vmin) / (vmax - vmin)
    norm = np.clip(norm, 0.0, 1.0)
    cmap = colormaps.get_cmap(cmap_name)
    rgb = (cmap(norm)[..., :3] * 255).astype(np.uint8)
    return rgb


def _plot_slice_grid(
    slices: list[np.ndarray],
    *,
    titles: list[str],
    title: str,
    cols: int = 4,
    percentile: float = 99.0,
    symmetric: bool = False,
    cmap_name: str = "viridis",
) -> go.Figure:
    if not slices:
        return go.Figure()
    num = len(slices)
    cols = max(1, min(cols, num))
    rows = int(np.ceil(num / cols))
    builder = FrameGridBuilder(
        rows=rows,
        cols=cols,
        titles=titles,
        height=320 * rows,
        width=320 * cols,
        title=title,
    )
    for idx, arr in enumerate(slices):
        r = idx // cols + 1
        c = idx % cols + 1
        rgb = _scalar_to_rgb(
            arr,
            percentile=percentile,
            symmetric=symmetric,
            cmap_name=cmap_name,
        )
        builder.add_image(rgb, row=r, col=c)
    return builder.finalize()


def _histogram_overlay(
    series: list[tuple[str, np.ndarray]],
    *,
    bins: int,
    title: str,
    xaxis_title: str,
    log1p_counts: bool,
    log_x: bool = False,
    log_x_epsilon: float = 1e-12,
    pretty_label: callable | None = None,
) -> go.Figure:
    all_vals: list[np.ndarray] = []
    for _, values in series:
        vals = np.asarray(values, dtype=float).reshape(-1)
        vals = vals[np.isfinite(vals)]
        if vals.size:
            all_vals.append(vals)
    if not all_vals:
        return go.Figure()

    merged = np.concatenate(all_vals, axis=0)
    if log_x:
        merged = merged[np.isfinite(merged)]
        merged_pos = merged[merged > 0.0]
        if merged_pos.size == 0:
            return go.Figure()
        vmin = float(np.nanmin(merged_pos))
        vmax = float(np.nanmax(merged_pos))
        eps = float(max(log_x_epsilon, vmin * 0.5))
        vmin = max(vmin, eps)
        vmax = max(vmax, vmin * (1.0 + 1e-6))
        edges = np.logspace(np.log10(vmin), np.log10(vmax), num=int(bins) + 1)
        centers = np.sqrt(edges[:-1] * edges[1:])
        widths = np.diff(edges)
    else:
        edges = np.histogram_bin_edges(merged, bins=int(bins))
        centers = 0.5 * (edges[:-1] + edges[1:])
        widths = None

    label_fn = pretty_label if callable(pretty_label) else (lambda x: x)
    fig = go.Figure()
    for name, values in series:
        vals = np.asarray(values, dtype=float).reshape(-1)
        vals = vals[np.isfinite(vals)]
        if log_x:
            vals = np.clip(vals, eps, None)
        counts, _ = np.histogram(vals, bins=edges)
        y = np.log1p(counts) if log1p_counts else counts
        bar_kwargs: dict[str, Any] = {"x": centers, "y": y, "name": label_fn(name), "opacity": 0.6}
        if widths is not None:
            bar_kwargs["width"] = widths
        fig.add_trace(
            go.Bar(**bar_kwargs),
        )
    fig.update_layout(
        barmode="overlay",
        title=label_fn(title),
        xaxis_title=label_fn(xaxis_title),
        yaxis_title=label_fn("log1p(count)" if log1p_counts else "count"),
    )
    if log_x:
        fig.update_xaxes(type="log")
    return fig


def _plot_hist_counts_mpl(
    values: list[float] | np.ndarray,
    *,
    bins: int,
    log_y: bool,
    ax: plt.Axes,
    color: str | None = None,
) -> None:
    vals = np.asarray(values, dtype=float).reshape(-1)
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return
    counts, edges = np.histogram(vals, bins=int(bins))
    centers = 0.5 * (edges[:-1] + edges[1:])
    widths = np.diff(edges)
    y = counts.astype(float)
    if log_y:
        y[y <= 0] = np.nan
    ax.bar(centers, y, width=widths, align="center", color=color, alpha=0.7)
    if log_y:
        ax.set_yscale("log")


__all__ = [
    "_histogram_overlay",
    "_plot_hist_counts_mpl",
    "_plot_slice_grid",
    "_scalar_to_rgb",
    "_to_numpy",
]
