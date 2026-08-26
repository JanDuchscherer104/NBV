"""Store-local Q_H evidence presentation.

Corpus construction remains on the Training Dataset page.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go  # type: ignore[import-untyped]
import streamlit as st

from .shared import ExplanationSection, ScientificExplanation
from .shared import download_frame as _download_frame
from .shared import render_plot as _render_plot


def _s2_direction_figure(payload: dict[str, Any], *, channel: str) -> go.Figure:
    r"""Render one target-frame equal-solid-angle S² histogram.

    The sphere coordinates are target object coordinates: its ``+x``, ``+y``,
    and ``+z`` axes rotate with the target OBB rather than the world or root
    rig.  Histogram cells are uniform in azimuth and ``z``.  Since
    ``dΩ=dφ dz``, this avoids the polar over-counting of a latitude-longitude
    grid.  The translucent point layer is a bounded reservoir sample projected
    to the unit sphere; surface colours always represent the complete factual
    selected-action count.

    Args:
        payload: Serialized `S2DirectionHistogram` from the store-owned
            inspection reducer.
        channel: Either ``"movement"`` for root-to-selected and subsequent
            selected-to-selected translations, or ``"view_direction"`` for
            selected camera local ``+Z`` axes.
    """

    if channel == "movement":
        counts = np.asarray(payload["movement_counts"], dtype=np.int64)
        projection = np.asarray(payload["movement_projection"], dtype=np.float32).reshape(-1, 3)
        normalized_lengths = np.asarray(payload["movement_projection_normalized_lengths"], dtype=np.float32).reshape(-1)
        title = "Root-target-normalized movement on target-frame S²"
        colorbar_title = "selected<br>transitions"
        overlay_name = "movement projection"
        overlay_customdata: np.ndarray | None = normalized_lengths[:, None]
        overlay_hovertemplate = (
            "target-frame movement projection"
            "<br>(x,y,z)=(%{x:.3f}, %{y:.3f}, %{z:.3f})"
            "<br>||Δp|| / r=%{customdata[0]:.3f}<extra></extra>"
        )
    elif channel == "view_direction":
        counts = np.asarray(payload["view_direction_counts"], dtype=np.int64)
        projection = np.asarray(payload["view_direction_projection"], dtype=np.float32).reshape(-1, 3)
        title = "Selected camera view directions on target-frame S²"
        colorbar_title = "selected<br>views"
        overlay_name = "camera +Z projection"
        overlay_customdata = None
        overlay_hovertemplate = (
            "target-frame camera +Z projection<br>(x,y,z)=(%{x:.3f}, %{y:.3f}, %{z:.3f})<extra></extra>"
        )
    else:
        raise ValueError(f"Unsupported S² channel: {channel!r}.")
    if counts.ndim != 2 or not counts.size:
        raise ValueError("S² histogram counts must be a nonempty two-dimensional grid.")

    elevation_bins, azimuth_bins = counts.shape
    z_centers = -1.0 + (np.arange(elevation_bins, dtype=np.float64) + 0.5) * 2.0 / elevation_bins
    azimuth_centers = -np.pi + (np.arange(azimuth_bins, dtype=np.float64) + 0.5) * 2.0 * np.pi / azimuth_bins
    azimuth, z = np.meshgrid(azimuth_centers, z_centers)
    radial = np.sqrt(np.maximum(0.0, 1.0 - z**2))
    x = radial * np.cos(azimuth)
    y = radial * np.sin(azimuth)
    max_count = max(int(counts.max(initial=0)), 1)

    figure = go.Figure(
        go.Surface(
            x=x,
            y=y,
            z=z,
            surfacecolor=counts,
            cmin=0,
            cmax=max_count,
            colorscale="Cividis",
            colorbar={"title": colorbar_title},
            opacity=0.9,
            customdata=counts,
            hovertemplate=(
                "target-frame S² cell"
                "<br>(x,y,z)=(%{x:.3f}, %{y:.3f}, %{z:.3f})"
                "<br>selected count=%{customdata}<extra></extra>"
            ),
            showscale=True,
            name="complete histogram",
        )
    )
    if projection.size:
        figure.add_trace(
            go.Scatter3d(
                x=projection[:, 0],
                y=projection[:, 1],
                z=projection[:, 2],
                mode="markers",
                name=overlay_name,
                marker={"size": 2.5, "color": "#111827", "opacity": 0.35},
                customdata=overlay_customdata,
                hovertemplate=overlay_hovertemplate,
            )
        )
    figure.update_layout(
        title=title,
        margin={"l": 0, "r": 0, "b": 0, "t": 48},
        legend={"orientation": "h", "y": -0.08},
        scene={
            "aspectmode": "cube",
            "xaxis": {"title": "target x", "range": [-1.05, 1.05]},
            "yaxis": {"title": "target y", "range": [-1.05, 1.05]},
            "zaxis": {"title": "target z", "range": [-1.05, 1.05]},
            "camera": {"eye": {"x": 1.5, "y": 1.5, "z": 1.15}},
        },
    )
    return figure


def _render_s2_direction_histograms(session_handle: Any) -> None:
    """Gate complete factual target-frame S² directional evidence behind an explicit action."""

    st.markdown("#### Target-frame S² movement and view-direction histograms")
    st.caption(
        "Both spheres use target-object coordinates. Movement uses the geometric-mean OBB scale "
        "r=(aₓaᵧa_z)^(1/3) before unit-sphere projection; camera views use their local +Z optical axes."
    )
    controls = st.columns(2)
    azimuth_bins = int(
        controls[0].number_input(
            "S² azimuth bins",
            min_value=8,
            max_value=144,
            value=36,
            step=4,
            help="Uniform azimuth bins. Together with uniform target-frame z bins, cells have equal solid angle.",
        )
    )
    elevation_bins = int(
        controls[1].number_input(
            "S² elevation bins",
            min_value=4,
            max_value=72,
            value=18,
            step=2,
            help="Uniform target-frame z bins, not uniform polar angles, to avoid polar over-counting.",
        )
    )
    if not st.toggle(
        "Load complete target-frame S² distributions",
        value=False,
        help="Reads every factual selected path in the selected immutable store; it does not scan full candidate shells.",
    ):
        return

    payload = session_handle.s2_direction_histogram(
        azimuth_bins=azimuth_bins,
        elevation_bins=elevation_bins,
    )
    movement_count = int(payload["movement_count"])
    view_count = int(payload["view_direction_count"])
    if movement_count == 0 and view_count == 0:
        st.info("No finite factual selected-action directions were available in the selected store.")
        return
    st.caption(
        f"Complete factual paths: {int(payload['rollout_count']):,} rollouts · "
        f"{movement_count:,} movement directions · {view_count:,} view directions · "
        f"{int(payload['movement_skipped_zero_count']):,} zero-length movements omitted."
    )
    movement_column, view_column = st.columns(2)
    with movement_column:
        _render_plot(
            _s2_direction_figure(payload, channel="movement"),
            ScientificExplanation(
                question="Which target-relative movement directions occur along factual selected paths?",
                answer="Surface colour is the complete selected-transition count in equal-solid-angle target-frame S² cells.",
                sections=(
                    ExplanationSection(
                        "Coordinate and scale",
                        "The translation is rotated into the target object frame and divided by the target OBB geometric-mean extent before projection. "
                        "The unit-sphere direction is scale invariant; the overlay hover reports its retained normalized length.",
                    ),
                    ExplanationSection(
                        "Population and warning",
                        "Only factual root-to-selected and selected-to-selected transitions contribute. Zero-length movements have no direction and are reported separately; missing or invalid target geometry excludes only the affected rollout.",
                    ),
                ),
                evidence_role="actor-visible",
                source_fields=(
                    "rollouts/root_pose_world",
                    "candidates/pose_world_cam (selected_mask)",
                    "targets/target_pose_world_object",
                    "targets/target_extents",
                ),
            ),
        )
    with view_column:
        _render_plot(
            _s2_direction_figure(payload, channel="view_direction"),
            ScientificExplanation(
                question="Which camera optical-axis directions occur relative to target coordinates?",
                answer="Surface colour is the complete selected-camera +Z direction count in equal-solid-angle target-frame S² cells.",
                sections=(
                    ExplanationSection(
                        "Coordinate convention",
                        "Each selected camera local +Z forward axis is rotated into the target object frame. This is an optical-axis distribution, not a camera-to-target bearing distribution.",
                    ),
                    ExplanationSection(
                        "Population and warning",
                        "Only selected factual camera poses contribute. The points are bounded display-only reservoir samples; the heat map retains the full selected-path count.",
                    ),
                ),
                evidence_role="actor-visible",
                source_fields=(
                    "candidates/pose_world_cam (selected_mask)",
                    "targets/target_pose_world_object",
                ),
            ),
        )
    issues = pd.DataFrame(payload["issues"])
    if not issues.empty:
        st.warning(
            "Some rollout paths were excluded from the S² reducer because their target frame or factual path was invalid."
        )
        st.dataframe(issues, hide_index=True, width="stretch")


def _render_q_h_evidence(session_handle: Any) -> None:
    """Render metadata-only Q_H facts and gate mask counts behind an explicit toggle."""

    st.markdown("#### Store-local Q_H evidence")
    deep_count = st.toggle(
        "Count current-store Q_H masks",
        value=False,
        help="Off reads metadata only. On performs the bounded current-store mask projection.",
    )
    chunk_size = int(
        st.number_input(
            "Q_H state chunk size",
            min_value=1,
            value=1024,
            step=256,
            disabled=not deep_count,
            help="Bounded Zarr read size used by the optional Q_H mask count.",
        )
    )
    state_limit_value = st.number_input(
        "Q_H state-row limit (0 = full store)",
        min_value=0,
        value=0,
        step=1024,
        disabled=not deep_count,
        help="Optional bounded prefix for diagnostics; 0 counts all persisted Q_H states.",
    )
    state_limit = None if int(state_limit_value) == 0 else int(state_limit_value)
    if not deep_count:
        evidence_rows = session_handle.q_h(deep_count=False)
    else:
        cancel_key = f"q_h_cancel:{session_handle.canonical_path.as_posix()}"
        stop_requested = bool(
            st.checkbox(
                "Stop after the current Q_H chunk",
                value=bool(st.session_state.get(cancel_key, False)),
                key=cancel_key,
                help="Cancellation is observed at the next bounded chunk boundary.",
            )
        )
        progress = st.progress(0.0, text="Preparing bounded Q_H count…")
        status = st.empty()

        def update_progress(completed: int, total: int) -> bool:
            fraction = 1.0 if total <= 0 else min(1.0, float(completed) / float(total))
            progress.progress(fraction, text=f"Q_H count: {completed:,}/{total:,} state rows")
            status.caption(
                "Stop requested; finishing the current chunk." if stop_requested else "Reading bounded Q_H slices…"
            )
            return not stop_requested

        evidence_rows = session_handle.q_h_progressive(
            chunk_size=chunk_size,
            state_row_limit=state_limit,
            progress_callback=update_progress,
        )
        evidence = evidence_rows[0] if evidence_rows else {}
        if str(evidence.get("count_reason", "")).startswith("cancelled"):
            status.caption("Q_H count stopped at a chunk boundary.")
        elif bool(evidence.get("truncated")):
            status.caption("Q_H bounded-prefix count complete.")
        else:
            status.caption("Q_H full-store count complete.")
    rows = pd.DataFrame(evidence_rows)
    st.dataframe(rows, hide_index=True, width="stretch")
    if not rows.empty and not bool(rows.iloc[0].get("available", False)):
        st.info(f"Q_H evidence unavailable: {rows.iloc[0].get('blocking_reason', 'unknown reason')}")
    _download_frame("Download Q_H evidence CSV", "q-h-evidence.csv", rows)
    _render_s2_direction_histograms(session_handle)
