"""RRI inspection panel."""

from __future__ import annotations

import streamlit as st

import aria_nbv.rri_metrics.plotting as rri_plotting

from ...data_handling import EfmSnippetView
from ...rendering.candidate_depth_renderer import CandidateDepths
from ...rendering.candidate_pointclouds import CandidatePointClouds
from ...rri_metrics.types import RriResult
from .common import _info_popover, _pretty_label


def render_rri_page(
    sample: EfmSnippetView,
    depth_batch: CandidateDepths,
    pcs: CandidatePointClouds,
    rri: RriResult,
) -> None:
    st.header("RRI Preview: Point Clouds vs Mesh")

    candidate_ids = depth_batch.candidate_indices.cpu().tolist()
    if len(candidate_ids) == 0:
        st.warning("No candidate renders available for RRI scoring.")
        return

    labels = [str(int(cid)) for cid in candidate_ids]
    baseline_label = "-1"

    bar_color_map = rri_plotting.rri_color_map(labels)

    _info_popover(
        "rri",
        "RRI measures relative improvement in mesh distance after adding the "
        "candidate point cloud: (d_before - d_after) / d_before. Higher is better. "
        "Scores are computed against the GT mesh with semidense points as baseline.",
    )
    st.plotly_chart(
        rri_plotting.plot_rri_scores(
            rri,
            labels,
            bar_color_map,
            title=_pretty_label("Oracle RRI per candidate"),
        ),
        width="stretch",
    )

    _info_popover(
        "pm dist",
        "Bidirectional point-mesh distance (Chamfer-style). "
        "Before uses semidense points only; after includes the candidate "
        "point cloud. Lower is better.",
    )
    st.plotly_chart(
        rri_plotting.plot_pm_distances(
            rri,
            labels,
            bar_color_map,
            baseline_label=baseline_label,
            title=_pretty_label("Chamfer-like (bidirectional)"),
        ),
        width="stretch",
    )

    _info_popover(
        "pm acc",
        "Point-to-mesh accuracy: distance from reconstruction points to GT mesh. "
        "Captures how well points lie on the surface. Lower is better.",
    )
    st.plotly_chart(
        rri_plotting.plot_pm_accuracy(
            rri,
            labels,
            bar_color_map,
            baseline_label=baseline_label,
            title=_pretty_label("Point→Mesh (accuracy)"),
        ),
        width="stretch",
    )

    _info_popover(
        "pm comp",
        "Mesh-to-point completeness: distance from GT mesh to reconstruction points. "
        "Captures coverage of the surface. Lower is better.",
    )
    st.plotly_chart(
        rri_plotting.plot_pm_completeness(
            rri,
            labels,
            bar_color_map,
            baseline_label=baseline_label,
            title=_pretty_label("Mesh→Point (completeness)"),
        ),
        width="stretch",
    )

    col1, col2 = st.columns(2)
    with col1:
        default_selection = candidate_ids[: min(6, len(candidate_ids))]
        selected_ids = st.multiselect(
            "Candidates to display",
            options=candidate_ids,
            default=default_selection,
            key="rri_cands",
        )
    with col2:
        show_frusta = st.checkbox("Show frusta", value=True, key="rri_show_frusta")

    max_sem_pts = st.number_input(
        "Max semi-dense points",
        min_value=1000,
        max_value=200000,
        value=50000,
        step=1000,
        key="rri_max_sem_pts",
    )

    _info_popover(
        "rri scene",
        "3D overlay of GT mesh, semidense points, and selected candidate "
        "point clouds. This helps validate that high-RRI candidates add "
        "new surface coverage rather than noisy points.",
    )
    st.plotly_chart(
        rri_plotting.plot_rri_scene(
            sample,
            depth_batch.poses,
            depth_batch.camera,
            pcs,
            candidate_ids=candidate_ids,
            selected_ids=selected_ids,
            color_map=bar_color_map,
            title=_pretty_label("Mesh + Semi-dense + Candidate PCs"),
            max_sem_pts=max_sem_pts,
            show_frusta=show_frusta,
        ),
        width="stretch",
    )


__all__ = ["render_rri_page"]
