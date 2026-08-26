"""Target-frame S² evidence shared by rollout and campaign admission pages."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ...scientific_labels import TheoryReferences
from .shared import ExplanationSection, ScientificExplanation
from .shared import render_plot as _render_plot

_STEP_SYMBOLS = ("circle", "square", "diamond", "cross", "x", "circle-open", "square-open", "diamond-open")


def s2_direction_figure(payload: dict[str, Any], *, channel: str) -> go.Figure:
    r"""Render a complete target-frame S² count field with factual provenance.

    Surface colour encodes the complete equal-solid-angle histogram.  The
    bounded incidence-point overlay preserves the factual rollout index ``j``
    and persisted step index ``t``: a continuous colour scale identifies a
    rollout chain, while marker symbol identifies the acquisition step.  The
    two encodings are redundant enough to compare common heritage and common
    time without treating the bounded point overlay as the scientific count.

    Args:
        payload: Serialized `S2DirectionHistogram` from the rollout inspection
            owner, including synchronized projection provenance arrays.
        channel: ``"movement"`` for
            :math:`\widehat{\boldsymbol{\delta}}_{j,t}^{e}` or
            ``"view_direction"`` for
            :math:`\widehat{\boldsymbol{v}}_{j,t}^{e}`, or ``"frustum"`` for
            the calibrated target-proxy surface footprint
            :math:`\mathcal{F}_{j,t}^{e}`.

    Returns:
        Plotly figure whose surface is the complete histogram and whose point
        traces are a bounded, provenance-preserving display sample.
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
            colorscale="Cividis",
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
    )
    figure.update_layout(
        title=title,
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
                    "colorscale": "Turbo",
                    "symbol": _STEP_SYMBOLS[step_index % len(_STEP_SYMBOLS)],
                    "opacity": 0.78,
                    "showscale": trace_index == 0,
                    "colorbar": colorbar,
                },
                customdata=np.column_stack(custom_columns),
                hovertemplate=hover + "<extra></extra>",
            )
        )


def render_s2_direction_histograms(session_handle: Any, *, key_prefix: str) -> None:
    r"""Render full-store directional evidence after explicit user dispatch.

    The scientific population is every factual selected transition in the
    immutable store.  The two heat maps use complete counts.  Incidence points
    use deterministic bounded reservoirs whose rollout and time provenance is
    retained exactly; the UI reports both population and display support.
    """

    st.markdown("#### Target-frame S² movement and view-direction evidence")
    st.caption(
        "Both spheres use target-object coordinates. Movement is normalized by "
        "rₑ=(aₓaᵧa_z)^(1/3), where aₓ,aᵧ,a_z are OBB semi-axes, before unit projection. "
        "Point colour identifies rollout chain j; "
        "point symbol identifies persisted step t (acquisition t+1)."
    )
    controls = st.columns(2)
    azimuth_bins = int(
        controls[0].number_input(
            "S² azimuth bins",
            min_value=8,
            max_value=144,
            value=36,
            step=4,
            key=f"{key_prefix}_s2_azimuth_bins",
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
            key=f"{key_prefix}_s2_elevation_bins",
            help="Uniform target-frame z bins, not uniform polar angles, to avoid polar over-counting.",
        )
    )
    if not st.toggle(
        "Load complete target-frame S² distributions",
        value=False,
        key=f"{key_prefix}_load_s2",
        help="Reads every factual selected path in the selected immutable store; it does not scan full candidate shells.",
    ):
        return

    payload = session_handle.s2_direction_histogram(azimuth_bins=azimuth_bins, elevation_bins=elevation_bins)
    movement_count = int(payload["movement_count"])
    view_count = int(payload["view_direction_count"])
    if movement_count == 0 and view_count == 0:
        st.info("No finite factual selected-action directions were available in the selected store.")
        return
    st.caption(
        f"Evidence support: {int(payload['source_sample_count']):,} source samples · "
        f"{int(payload['source_snippet_count']):,} unique scene/snippet windows · "
        f"{int(payload['source_scene_count']):,} scenes · {int(payload['target_count']):,} targets · "
        f"{int(payload['rollout_count']):,}/{int(payload['store_rollout_count']):,} admissible rollout chains · "
        f"{int(payload['selected_step_count']):,} selected steps."
    )
    support = pd.DataFrame(
        (
            {
                "channel": r"movement δ-hatᵉ[j,t]",
                "complete contributors": movement_count,
                "display incidence points": len(payload["movement_projection"]),
                "zero/undefined omitted": int(payload["movement_skipped_zero_count"]),
            },
            {
                "channel": r"camera-forward v-hatᵉ[j,t]",
                "complete contributors": view_count,
                "display incidence points": len(payload["view_direction_projection"]),
                "zero/undefined omitted": 0,
            },
            {
                "channel": r"calibrated proxy-surface frustum ℱᵉ[j,t]",
                "complete contributors": int(payload["frustum_count"]),
                "display incidence points": len(payload["frustum_projection"]),
                "zero/undefined omitted": int(payload["frustum_missing_calibration_count"]),
            },
        )
    )
    st.dataframe(support, hide_index=True, width="stretch")

    movement_column, view_column = st.columns(2)
    theory = TheoryReferences(
        equation_ids=(
            "spatial.target_frame_obb_radius",
            "spatial.target_frame_motion_direction",
            "spatial.target_frame_view_direction",
            "spatial.target_frame_frustum_geometry",
            "spatial.target_frame_frustum_projection",
            "spatial.target_frame_frustum_membership",
            "spatial.target_frame_frustum_coverage",
            "spatial.spherical_triangle_solid_angle",
            "spatial.pinhole_frustum_solid_angle",
        ),
        symbol_ids=(
            "spatial.target_frame_motion_direction",
            "spatial.target_frame_view_direction",
            "spatial.target_frame_frustum",
            "spatial.target_frame_frustum_fraction",
            "spatial.frustum_solid_angle",
            "spatial.target_obb_scale",
            "rl.rollout_index",
        ),
    )
    with movement_column:
        _render_plot(
            s2_direction_figure(payload, channel="movement"),
            ScientificExplanation(
                question="Which target-frame movement directions occur along factual selected paths?",
                answer="Surface colour is the complete selected-transition count; point colour links a rollout chain and point symbol links acquisition time.",
                sections=(
                    ExplanationSection(
                        "coordinate and scale",
                        "The selected-camera displacement is rotated into target coordinates, divided by the target OBB geometric-mean scale rₑ, and projected to S².",
                    ),
                    ExplanationSection(
                        "population and display support",
                        "Every finite factual root-to-selected or selected-to-selected transition contributes to the heat map. Only the explicitly reported deterministic reservoir is drawn as incidence points.",
                    ),
                ),
                evidence_role="actor-visible",
                source_fields=(
                    "rollouts/root_pose_world",
                    "rollouts/rollout_row_id",
                    "steps/step_index",
                    "candidates/pose_world_cam (selected_mask)",
                    "targets/target_pose_world_object",
                    "targets/target_extents",
                ),
                theory=theory,
            ),
        )
    with view_column:
        _render_plot(
            s2_direction_figure(payload, channel="view_direction"),
            ScientificExplanation(
                question="Which selected-camera optical-axis directions occur in target coordinates?",
                answer="Surface colour is the complete selected-camera +Z count; point colour links a rollout chain and point symbol links acquisition time.",
                sections=(
                    ExplanationSection(
                        "coordinate convention",
                        "The selected camera local +Z forward axis is rotated into the target object frame. This is an optical-axis distribution, not a camera-to-target bearing distribution.",
                    ),
                    ExplanationSection(
                        "population and display support",
                        "Every finite selected-camera direction contributes to the heat map. The displayed incidence points are a bounded provenance-preserving reservoir.",
                    ),
                ),
                evidence_role="actor-visible",
                source_fields=(
                    "rollouts/rollout_row_id",
                    "steps/step_index",
                    "candidates/pose_world_cam (selected_mask)",
                    "targets/target_pose_world_object",
                ),
                theory=theory,
            ),
        )
    if int(payload["frustum_count"]) > 0:
        mean_sr = float(payload["frustum_mean_fov_solid_angle_sr"])
        mean_fraction = float(payload["frustum_mean_target_surface_fraction_approx"])
        union_fraction = float(payload["frustum_union_target_surface_fraction_approx"])
        st.caption(
            f"Calibrated frustum support: mean intrinsic FOV Ω={mean_sr:.4f} sr · "
            f"mean front-facing proxy surface≈{mean_fraction:.2%} per selected view · "
            f"equal-area-bin union≈{union_fraction:.2%} of S². "
            f"Missing calibration: {int(payload['frustum_missing_calibration_count']):,} selected steps."
        )
        _render_plot(
            s2_direction_figure(payload, channel="frustum"),
            ScientificExplanation(
                question="Which parts of the target-centred proxy sphere are geometrically visible inside the calibrated selected-camera frusta?",
                answer="Each heat-map cell counts selected pinhole cameras for which the proxy-surface cell is front-facing, in front of the camera, and inside the continuous image rectangle.",
                sections=(
                    ExplanationSection(
                        "calibrated spherical footprint",
                        "For each selected view, focal length, principal point, image size, camera pose, target centre, and volume-equivalent OBB radius define a target-surface footprint. The intrinsic frustum solid angle Ω is reported separately in steradians.",
                    ),
                    ExplanationSection(
                        "interpretation limit",
                        "This is geometric potential visibility on a volume-equivalent sphere. It does not claim measured target-mesh visibility: true object shape and scene occlusion require mesh/depth intersection evidence.",
                    ),
                    ExplanationSection(
                        "union approximation",
                        "Per-view and union surface fractions count covered equal-solid-angle bin centres. Increase both bin controls for a finer surface approximation; the intrinsic pinhole FOV solid angle remains analytic.",
                    ),
                ),
                evidence_role="actor-visible",
                source_fields=(
                    "selected_depth/focal_px",
                    "selected_depth/principal_point_px",
                    "selected_depth/image_size_hw",
                    "steps/step_index",
                    "candidates/pose_world_cam (selected_mask)",
                    "targets/target_pose_world_object",
                    "targets/target_extents",
                ),
                theory=theory,
            ),
        )
    issues = pd.DataFrame(payload["issues"])
    if not issues.empty:
        st.warning("Some rollout paths were excluded because their target frame or factual path was invalid.")
        st.dataframe(issues, hide_index=True, width="stretch")


__all__ = ["render_s2_direction_histograms", "s2_direction_figure"]
