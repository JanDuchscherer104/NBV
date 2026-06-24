"""Backbone evidence tab for VIN diagnostics."""

from __future__ import annotations

import streamlit as st

from ....vin.diagnostics.plotting import build_backbone_evidence_figures, build_scene_field_evidence_figures
from ..common import _info_popover
from .context import VinDiagContext


def render_evidence_tab(ctx: VinDiagContext) -> None:
    """Render the Backbone Evidence tab.

    Args:
        ctx: Shared VIN diagnostics context.
    """
    debug = ctx.debug
    cfg = ctx.cfg

    _info_popover(
        "evidence",
        "Visualizes voxel evidence (occupancy, centerness, or scene-field "
        "channels) above a threshold. This exposes where the backbone sees "
        "occupied space versus free or unknown space.",
    )
    channel_labels = cfg.module_config.vin.scene_field_channels
    occ_threshold = float(
        st.slider(
            "Evidence threshold",
            min_value=0.0,
            max_value=1.0,
            value=0.5,
            step=0.01,
        ),
    )
    evidence_figs = build_scene_field_evidence_figures(
        debug,
        channel_names=channel_labels,
        occ_threshold=occ_threshold,
        max_points=20000,
    )
    if not evidence_figs:
        evidence_figs = build_backbone_evidence_figures(
            debug,
            occ_threshold=occ_threshold,
            max_points=20000,
        )
    if not evidence_figs:
        st.info("No backbone evidence tensors found for plotting.")
    for key, fig in evidence_figs.items():
        st.plotly_chart(fig, width="stretch", key=f"vin_evidence_{key}")


__all__ = ["render_evidence_tab"]
