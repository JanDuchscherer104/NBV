"""Build candidate-aligned Plotly figures for RRI and distance diagnostics.

This module visualizes :class:`RriResult` labels, squared point--mesh
components, and selected candidate geometry. It owns presentation only:
candidate order, validity, actor-visible inputs, and oracle-label construction
remain with their source payloads and callers. Distance chart values are in
square metres when the underlying geometry is metric world-frame data.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import plotly.express as px  # type: ignore[import-untyped]
import plotly.graph_objects as go  # type: ignore[import-untyped]
import torch

from .rri import RriResult


def rri_color_map(
    labels: Sequence[str],
    *,
    palette: Sequence[str] | None = None,
) -> dict[str, str]:
    """Assign colors deterministically in input-label order, cycling the palette when needed."""
    colors = list(palette) if palette is not None else px.colors.qualitative.Plotly
    if not colors:
        colors = ["#1f77b4"]
    return {label: colors[i % len(colors)] for i, label in enumerate(labels)}


def plot_rri_scores(
    rri: RriResult,
    labels: Sequence[str],
    color_map: Mapping[str, str],
    *,
    title: str,
) -> go.Figure:
    """Build one dimensionless oracle-RRI bar per candidate label.

    Args:
        rri: Candidate-aligned oracle result.
        labels: Display labels in the same order as ``rri.rri``.
        color_map: Color lookup containing every display label.
        title: Figure title.

    Returns:
        Plotly bar figure whose x-axis is candidate identity and whose y-axis
        is dimensionless RRI. Negative bars are valid low-utility labels, not
        invalid-candidate markers.
    """
    fig = go.Figure(
        data=go.Bar(
            x=list(labels),
            y=_as_list(rri.rri),
            marker_color=[color_map[label] for label in labels],
        )
    )
    fig.update_layout(title_text=title)
    return fig


def plot_pm_distances(
    rri: RriResult,
    labels: Sequence[str],
    color_map: Mapping[str, str],
    *,
    baseline_label: str = "-1",
    title: str,
) -> go.Figure:
    """Plot broadcast pre-view and per-candidate post-view bidirectional errors in square metres."""
    baseline = float(rri.pm_dist_before[0].item())
    fig = go.Figure(
        data=[
            go.Bar(
                x=[baseline_label],
                y=[baseline],
                name="before (semi-dense, -1)",
                marker_color="lightgray",
            ),
            go.Bar(
                x=list(labels),
                y=_as_list(rri.pm_dist_after),
                name="after",
                marker_color=[color_map[label] for label in labels],
            ),
        ],
    )
    fig.update_layout(
        title_text=title,
        xaxis={"categoryorder": "array", "categoryarray": [baseline_label, *labels]},
    )
    return fig


def plot_pm_accuracy(
    rri: RriResult,
    labels: Sequence[str],
    color_map: Mapping[str, str],
    *,
    baseline_label: str = "-1",
    title: str,
) -> go.Figure:
    """Plot pre/post mean-squared point-to-mesh accuracy errors in square metres."""
    baseline = float(rri.pm_acc_before[0].item())
    fig = go.Figure(
        data=[
            go.Bar(
                x=[baseline_label],
                y=[baseline],
                name="point→mesh (before, -1)",
                marker_color="lightgray",
            ),
            go.Bar(
                x=list(labels),
                y=_as_list(rri.pm_acc_after),
                name="point→mesh (after)",
                marker_color=[color_map[label] for label in labels],
            ),
        ],
    )
    fig.update_layout(
        title_text=title,
        xaxis={"categoryorder": "array", "categoryarray": [baseline_label, *labels]},
    )
    return fig


def plot_pm_completeness(
    rri: RriResult,
    labels: Sequence[str],
    color_map: Mapping[str, str],
    *,
    baseline_label: str = "-1",
    title: str,
) -> go.Figure:
    """Plot pre/post mean-squared mesh-to-point completeness errors in square metres."""
    baseline = float(rri.pm_comp_before[0].item())
    fig = go.Figure(
        data=[
            go.Bar(
                x=[baseline_label],
                y=[baseline],
                name="mesh→point (before, -1)",
                marker_color="lightgray",
            ),
            go.Bar(
                x=list(labels),
                y=_as_list(rri.pm_comp_after),
                name="mesh→point (after)",
                marker_color=[color_map[label] for label in labels],
            ),
        ],
    )
    fig.update_layout(
        title_text=title,
        xaxis={"categoryorder": "array", "categoryarray": [baseline_label, *labels]},
    )
    return fig


def _as_list(values: Sequence[float] | torch.Tensor) -> list[float]:
    if isinstance(values, torch.Tensor):
        return values.detach().cpu().flatten().tolist()
    return [float(v) for v in values]


__all__ = [
    "plot_pm_accuracy",
    "plot_pm_completeness",
    "plot_pm_distances",
    "plot_rri_scores",
    "rri_color_map",
]
