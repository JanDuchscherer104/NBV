"""Scene field tab for VIN diagnostics."""

from __future__ import annotations

import streamlit as st

from ....vin.diagnostics.plotting import build_field_slice_figures
from ....vin.experimental.plotting import build_field_token_histograms
from ..common import _info_popover
from .context import VinDiagContext


def render_field_tab(ctx: VinDiagContext) -> None:
    """Render the Field Slices tab.

    Args:
        ctx: Shared VIN diagnostics context.
    """
    debug = ctx.debug
    cfg = ctx.cfg

    _info_popover(
        "scene field",
        "`field_in` is the raw concatenated EVL channels. `field` is the "
        "projected version after 1x1x1 Conv3d + GroupNorm + GELU "
        "(VIN v2/v3), which compresses the channels for attention pooling.",
    )
    channel_labels = cfg.module_config.vin.scene_field_channels
    field_in = debug.field_in
    field = debug.field
    if field_in.cpu().ndim == 5:
        field_in = field_in[0]
    if field.cpu().ndim == 5:
        field = field[0]

    if field_in.cpu().ndim == 4:
        st.subheader("field_in slices (raw)")
        figs_in = build_field_slice_figures(
            field_in,
            channel_names=channel_labels,
            max_channels=4,
            title_prefix="field_in",
        )
        for key, fig in figs_in.items():
            st.plotly_chart(fig, width="stretch", key=f"vin_field_in_{key}")

    if field.cpu().ndim == 4:
        st.subheader("field slices (projected)")
        figs_out = build_field_slice_figures(
            field,
            channel_names=[f"proj_{i}" for i in range(field.shape[0])],
            max_channels=4,
            title_prefix="field",
        )
        for key, fig in figs_out.items():
            st.plotly_chart(fig, width="stretch", key=f"vin_field_{key}")

    if ctx.has_tokens:
        log1p_field_counts = st.checkbox(
            "Log1p token histogram counts",
            value=False,
            key="vin_field_token_log1p",
        )
        token_figs = build_field_token_histograms(
            debug,
            channel_names=channel_labels,
            max_channels=4,
            log1p_counts=log1p_field_counts,
        )
        for key, fig in token_figs.items():
            st.plotly_chart(fig, width="stretch", key=f"vin_field_token_{key}")


__all__ = ["render_field_tab"]
