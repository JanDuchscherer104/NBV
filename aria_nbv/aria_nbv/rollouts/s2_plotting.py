"""Canonical Plotly construction for target-frame spherical rollout evidence.

The factual reducer remains in :mod:`aria_nbv.rollouts.inspection`, while
:mod:`aria_nbv.rollouts.s2_analysis` owns configured store acquisition. This
module owns only deterministic visual encoding. Streamlit and immutable thesis
reporting consume its Plotly specifications through the shared report snapshot
instead of defining plots in either presentation adapter.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

import numpy as np
import plotly.graph_objects as go

S2Channel = Literal["movement", "view_direction", "frustum"]

_STEP_SYMBOLS = ("circle", "square", "diamond", "cross", "x", "circle-open", "square-open", "diamond-open")


def s2_direction_figure(
    payload: Mapping[str, Any],
    *,
    channel: S2Channel,
    template: str = "plotly_white",
    font_family: str = "Arial",
    surface_colorscale: str = "Cividis",
    rollout_colorscale: str = "Turbo",
    title_suffix: str = "",
) -> go.Figure:
    r"""Build one canonical target-frame :math:`S^2` evidence figure.

    Surface colour encodes the complete equal-solid-angle histogram. The
    bounded incidence overlay preserves factual rollout index :math:`j` and
    persisted step index :math:`t`: continuous colour identifies rollout-chain
    heritage and marker symbol identifies acquisition time. The overlay is a
    display reservoir and never replaces the complete counts.

    Args:
        payload: Serialized
            :class:`~aria_nbv.rollouts.inspection.S2DirectionHistogram`,
            including synchronized projection-provenance arrays.
        channel: ``"movement"`` for
            :math:`\widehat{\boldsymbol{\delta}}_{j,t}^{e}`,
            ``"view_direction"`` for
            :math:`\widehat{\boldsymbol{v}}_{j,t}^{e}`, or ``"frustum"`` for
            calibrated proxy-surface support
            :math:`\mathcal{F}_{j,t}^{e}`.
        template: Plotly template shared by interactive and static reporting.
        font_family: Font family recorded in the canonical Plotly layout.
        surface_colorscale: Sequential scale for complete per-cell counts.
        rollout_colorscale: Continuous scale for rollout-chain incidence.
        title_suffix: Optional provenance label appended to the scientific
            channel title.

    Returns:
        A WebGL Plotly figure over the target-object basis
        :math:`(x^e,y^e,z^e)`.

    Raises:
        ValueError: If the channel is unknown or projection/count arrays violate
            their synchronized shape contract.
    """

    if channel == "movement":
        counts = np.asarray(payload["movement_counts"], dtype=np.int64)
        projection = np.asarray(payload["movement_projection"], dtype=np.float32).reshape(-1, 3)
        lengths = np.asarray(payload["movement_projection_normalized_lengths"], dtype=np.float32).reshape(-1)
        rollout_ids = np.asarray(payload["movement_projection_rollout_row_ids"], dtype=np.int64).reshape(-1)
        step_indices = np.asarray(payload["movement_projection_step_indices"], dtype=np.int64).reshape(-1)
        title = "δ̂ᵉ[j,t] — target-frame movement direction"
        colorbar_title = "selected<br>transitions"
        overlay_name = "movement incidence"
    elif channel == "view_direction":
        counts = np.asarray(payload["view_direction_counts"], dtype=np.int64)
        projection = np.asarray(payload["view_direction_projection"], dtype=np.float32).reshape(-1, 3)
        lengths = None
        rollout_ids = np.asarray(payload["view_direction_projection_rollout_row_ids"], dtype=np.int64).reshape(-1)
        step_indices = np.asarray(payload["view_direction_projection_step_indices"], dtype=np.int64).reshape(-1)
        title = "v̂ᵉ[j,t] — target-frame camera +Z direction"
        colorbar_title = "selected<br>views"
        overlay_name = "view incidence"
    elif channel == "frustum":
        counts = np.asarray(payload["frustum_counts"], dtype=np.int64)
        projection = np.asarray(payload["frustum_projection"], dtype=np.float32).reshape(-1, 3)
        lengths = None
        rollout_ids = np.asarray(payload["frustum_projection_rollout_row_ids"], dtype=np.int64).reshape(-1)
        step_indices = np.asarray(payload["frustum_projection_step_indices"], dtype=np.int64).reshape(-1)
        title = "ℱᵉ[j,t] — calibrated target-proxy surface support"
        colorbar_title = "frusta covering<br>surface cell"
        overlay_name = "frustum-footprint centroid"
    else:
        raise ValueError(f"Unsupported S² channel: {channel!r}.")
    if counts.ndim != 2 or not counts.size:
        raise ValueError("S² histogram counts must be a nonempty two-dimensional grid.")
    if not (projection.shape[0] == rollout_ids.size == step_indices.size):
        raise ValueError("S² projection and provenance arrays must have equal row counts.")
    if lengths is not None and lengths.size != projection.shape[0]:
        raise ValueError("S² movement magnitudes must align with movement projections.")

    elevation_bins, azimuth_bins = counts.shape
    z_centers = -1.0 + (np.arange(elevation_bins, dtype=np.float64) + 0.5) * 2.0 / elevation_bins
    azimuth_centers = -np.pi + (np.arange(azimuth_bins, dtype=np.float64) + 0.5) * 2.0 * np.pi / azimuth_bins
    grid_shape = (elevation_bins, azimuth_bins)
    azimuth = np.broadcast_to(azimuth_centers[None, :], grid_shape).copy()
    z = np.broadcast_to(z_centers[:, None], grid_shape).copy()
    radial = np.sqrt(np.maximum(0.0, 1.0 - z**2))
    x = radial * np.cos(azimuth)
    y = radial * np.sin(azimuth)
    figure = go.Figure(
        go.Surface(
            x=x,
            y=y,
            z=z,
            surfacecolor=counts,
            cmin=0,
            cmax=max(int(counts.max(initial=0)), 1),
            colorscale=surface_colorscale,
            colorbar={"title": colorbar_title, "x": 1.02},
            opacity=0.82,
            customdata=counts,
            hovertemplate=(
                "target-frame S² cell"
                "<br>(xᵉ,yᵉ,zᵉ)=(%{x:.3f}, %{y:.3f}, %{z:.3f})"
                "<br>complete count=%{customdata}<extra></extra>"
            ),
            showscale=True,
            name="complete equal-solid-angle histogram",
        )
    )
    _add_incidence_traces(
        figure,
        projection=projection,
        rollout_ids=rollout_ids,
        step_indices=step_indices,
        normalized_lengths=lengths,
        overlay_name=overlay_name,
        rollout_colorscale=rollout_colorscale,
    )
    suffix = f" · {title_suffix}" if title_suffix else ""
    figure.update_layout(
        template=template,
        font={"family": font_family},
        title=title + suffix,
        margin={"l": 0, "r": 0, "b": 0, "t": 58},
        legend={"orientation": "h", "y": -0.08, "title": "Persisted acquisition step"},
        scene={
            "aspectmode": "cube",
            "xaxis": {"title": "target xᵉ", "range": [-1.05, 1.05]},
            "yaxis": {"title": "target yᵉ", "range": [-1.05, 1.05]},
            "zaxis": {"title": "target zᵉ", "range": [-1.05, 1.05]},
            "camera": {"eye": {"x": 1.5, "y": 1.5, "z": 1.15}},
        },
    )
    return figure


def _add_incidence_traces(
    figure: go.Figure,
    *,
    projection: np.ndarray,
    rollout_ids: np.ndarray,
    step_indices: np.ndarray,
    normalized_lengths: np.ndarray | None,
    overlay_name: str,
    rollout_colorscale: str,
) -> None:
    """Add step-styled, rollout-coloured factual incidence points."""

    if projection.size == 0:
        return
    rollout_min = int(rollout_ids.min())
    rollout_max = int(rollout_ids.max())
    single_rollout = rollout_max == rollout_min
    color_min = rollout_min - 0.5 if single_rollout else rollout_min
    color_max = rollout_max + 0.5 if single_rollout else rollout_max
    colorbar: dict[str, Any] = {"title": "rollout<br>index j", "x": 0.88, "len": 0.65}
    if single_rollout:
        colorbar.update(tickvals=[rollout_min], ticktext=[str(rollout_min)])
    for trace_index, step_index in enumerate(sorted({int(value) for value in step_indices.tolist()})):
        selected = step_indices == step_index
        selected_rollouts = rollout_ids[selected]
        acquisition_number = step_index + 1
        custom_columns = [
            selected_rollouts.astype(np.float64),
            np.full(int(selected.sum()), step_index, dtype=np.float64),
            np.full(int(selected.sum()), acquisition_number, dtype=np.float64),
        ]
        hover = (
            f"{overlay_name}"
            "<br>rollout j=%{customdata[0]:.0f}"
            "<br>step t=%{customdata[1]:.0f} · acquisition=%{customdata[2]:.0f}"
            "<br>(xᵉ,yᵉ,zᵉ)=(%{x:.3f}, %{y:.3f}, %{z:.3f})"
        )
        if normalized_lengths is not None:
            custom_columns.append(normalized_lengths[selected].astype(np.float64))
            hover += "<br>‖δᵉ‖₂ / rₑ=%{customdata[3]:.3f}"
        figure.add_trace(
            go.Scatter3d(
                x=projection[selected, 0],
                y=projection[selected, 1],
                z=projection[selected, 2],
                mode="markers",
                name=f"acquisition {acquisition_number} (t={step_index})",
                marker={
                    "size": 3.5,
                    "color": selected_rollouts,
                    "cmin": color_min,
                    "cmax": color_max,
                    "colorscale": rollout_colorscale,
                    "symbol": _STEP_SYMBOLS[step_index % len(_STEP_SYMBOLS)],
                    "opacity": 0.78,
                    "showscale": trace_index == 0,
                    "colorbar": colorbar,
                },
                customdata=np.column_stack(custom_columns),
                hovertemplate=hover + "<extra></extra>",
            )
        )


__all__ = ["S2Channel", "s2_direction_figure"]
