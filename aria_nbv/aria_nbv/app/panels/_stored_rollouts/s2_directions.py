"""Target-frame S² evidence shared by rollout and campaign admission pages."""

from __future__ import annotations

from typing import Protocol, TypedDict

import numpy as np
import pandas as pd
import streamlit as st
from numpy.typing import NDArray

from ....rollouts.s2_reporting import s2_direction_figure
from ...scientific_labels import TheoryReferences
from .shared import ExplanationSection, ScientificExplanation
from .shared import render_plot as _render_plot


class _S2PanelPayload(TypedDict):
    """Serialized reducer fields consumed by the interactive panel."""

    movement_count: int
    view_direction_count: int
    frustum_count: int
    source_sample_count: int
    source_snippet_count: int
    source_scene_count: int
    target_count: int
    rollout_count: int
    store_rollout_count: int
    selected_step_count: int
    movement_skipped_zero_count: int
    frustum_missing_calibration_count: int
    movement_projection: NDArray[np.float32]
    view_direction_projection: NDArray[np.float32]
    frustum_projection: NDArray[np.float32]
    frustum_mean_fov_solid_angle_sr: float
    frustum_mean_target_surface_fraction_approx: float
    frustum_union_target_surface_fraction_approx: float
    issues: tuple[dict[str, object], ...]


class _S2DirectionSession(Protocol):
    """Minimal read-only session required by the shared S² panel."""

    def s2_direction_histogram(self, *, azimuth_bins: int, elevation_bins: int) -> _S2PanelPayload:
        """Return one presentation-ready complete spherical projection."""


def render_s2_direction_histograms(session_handle: _S2DirectionSession, *, key_prefix: str) -> None:
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
    issues = pd.DataFrame(payload["issues"])
    if movement_count == 0 and view_count == 0:
        if not issues.empty:
            st.warning("All rollout paths were excluded because their target frame or factual path was invalid.")
            st.dataframe(issues, hide_index=True, width="stretch")
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
            "spatial.target_frame_obb_scale",
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
                        "For each selected view, focal length, principal point, image size, camera pose, target centre, and geometric-mean OBB semi-axis scale define a target-proxy footprint. The intrinsic frustum solid angle Ω is reported separately in steradians.",
                    ),
                    ExplanationSection(
                        "interpretation limit",
                        "This is geometric potential visibility on a scale-normalized target-proxy sphere. It does not claim measured target-mesh visibility: true object shape and scene occlusion require mesh/depth intersection evidence.",
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
    if not issues.empty:
        st.warning("Some rollout paths were excluded because their target frame or factual path was invalid.")
        st.dataframe(issues, hide_index=True, width="stretch")


__all__ = ["render_s2_direction_histograms", "s2_direction_figure"]
