"""Oracle candidate-depth and backprojected-hit diagnostics.

This panel provides metric camera-z depth grids, hit statistics, and optional
world-frame point-cloud overlays derived from the ASE mesh; these rendered
values are evaluation evidence and never actor observations.
"""

from __future__ import annotations

import streamlit as st
import torch

from ...data_handling import EfmSnippetView
from ...rendering.candidate_depth_renderer import CandidateDepths
from ...rendering.candidate_pointclouds import CandidatePointClouds
from ...rendering.plotting import RenderingPlotBuilder, depth_grid, depth_histogram
from .common import _info_popover, _pretty_label


def render_depth_page(
    sample: EfmSnippetView | None,
    depth_batch: CandidateDepths,
    *,
    pcs: CandidatePointClouds | None,
) -> None:
    """Render oracle depth maps and optional world-frame depth-hit clouds.

    Args:
        sample: Optional source snippet needed for 3D scene context.
        depth_batch: Mesh-rendered depths ``Tensor[\"C H W\", float]`` in metres.
        pcs: Optional backprojections ``Tensor[\"C P 3\", float]`` in world metres.
    """

    st.header("Candidate Renders")

    depths = depth_batch.depths
    indices = depth_batch.candidate_indices.tolist()
    titles = [f"cand {i} (id {cid})" for i, cid in enumerate(indices)]
    st.caption(
        "Local indices (cand 0..N-1) refer to the rendered batch order; "
        "`id` is the original candidate index (pre-render filtering).",
    )

    cam = depth_batch.camera
    if hasattr(cam, "valid_radius") and cam.valid_radius.numel() > 0:
        zfar_stat = float(cam.valid_radius.max().item())
    else:
        zfar_stat = float(depths.max().item()) * 1.05

    st.subheader("Depth grid")
    _info_popover(
        "depth grid",
        "Each tile is a rendered depth map for a candidate pose. Depth is in "
        "camera coordinates with +Z forward. Invalid hits are masked in the "
        "renderer and can appear at the far plane if not filtered.",
    )
    fig = depth_grid(depths, titles=titles, zmax=float(depths.max().item()))
    st.plotly_chart(fig, width="stretch")

    with st.expander("Diagnostics", expanded=False):
        tab_hist, tab_hits = st.tabs(["Histograms", "Depth-hit point cloud (3D)"])

        with tab_hist:
            _info_popover(
                "depth hist",
                "Depth histograms summarize per-candidate depth distributions. "
                "A spike near the far plane often indicates many miss pixels; "
                "a bimodal shape can reveal multiple surfaces along the frustum.",
            )
            bins = st.slider(
                "Histogram bins",
                10,
                200,
                50,
                step=10,
                key="depth_hist_bins",
            )
            fig_hist = depth_histogram(depths, bins=int(bins), zfar=zfar_stat)
            st.plotly_chart(fig_hist, width="stretch")

        with tab_hits:
            _info_popover(
                "depth hits",
                "Back-projects valid depth pixels into world space using the "
                "candidate pose and camera intrinsics. The resulting points "
                "approximate the candidate view point cloud used for RRI.",
            )
            if sample is None:
                st.info("Load data first to back-project depth hits.")
                return
            if pcs is None:
                st.info(
                    "Run / refresh renders to compute backprojected CandidatePointClouds.",
                )
                return

            max_points = st.number_input(
                "Max points to display",
                min_value=1,
                max_value=200000,
                value=20000,
                step=1000,
                key="depth_hit_max_points",
            )

            cand_options = depth_batch.candidate_indices.tolist()
            selected_global = st.multiselect(
                "Select candidates to back-project",
                options=cand_options,
                default=cand_options,
                key="depth_hit_cands",
            )
            cand_to_local = {int(g): idx for idx, g in enumerate(depth_batch.candidate_indices.tolist())}
            selected = [cand_to_local[g] for g in selected_global if g in cand_to_local]
            num_frustums = int(depth_batch.poses.tensor().shape[0])

            points_selected = []
            for idx in selected:
                n_valid = int(pcs.lengths[idx].item())
                if n_valid == 0:
                    continue
                pts = pcs.points[idx, :n_valid]
                points_selected.append(pts)

            if points_selected:
                pts_cat = torch.cat(points_selected, dim=0)
                if pts_cat.shape[0] > max_points:
                    rand_idx = torch.randperm(pts_cat.shape[0], device=pts_cat.device)[: int(max_points)]
                    pts_cat = pts_cat[rand_idx]

                builder = (
                    RenderingPlotBuilder.from_snippet(
                        sample,
                        title=_pretty_label("Depth hit back-projection"),
                    )
                    .add_mesh()
                    .add_points(
                        pts_cat,
                        name="Depth hits",
                        color="teal",
                        size=3,
                        opacity=0.8,
                    )
                    .add_frusta_selection(
                        poses=depth_batch.poses,
                        camera=depth_batch.camera,
                        max_frustums=min(16, num_frustums),
                        candidate_indices=selected,
                    )
                )
                st.plotly_chart(builder.finalize(), width="stretch")
            else:
                st.info("No valid depth hits to display for the selected candidates.")


__all__ = ["render_depth_page"]
