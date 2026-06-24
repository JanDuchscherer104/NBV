"""Transforms tab for VIN diagnostics."""

from __future__ import annotations

import streamlit as st

from ....utils.plotting import _to_numpy
from ....vin.diagnostics import build_prediction_alignment_figure
from ....vin.diagnostics.plotting import (
    build_pos_grid_linearity_figure,
    build_se3_closure_figure,
    build_voxel_inbounds_figure,
    build_voxel_roundtrip_figure,
)
from ....vin.geometry import pos_grid_from_pts_world
from ..common import _info_popover
from .context import VinDiagContext


def render_transforms_tab(ctx: VinDiagContext) -> None:
    """Render the Transforms tab.

    Args:
        ctx: Shared VIN diagnostics context.
    """
    debug = ctx.debug
    pred = ctx.pred
    batch = ctx.batch

    _info_popover(
        "transforms",
        "Roundtrip plots validate world-to-voxel transforms used to align "
        "candidate poses with the EVL grid. Large residuals indicate frame "
        "mismatch or incorrect voxel extents.",
    )
    log1p_roundtrip = st.checkbox(
        "Log1p roundtrip histogram counts",
        value=False,
        key="vin_roundtrip_log1p",
    )
    st.plotly_chart(
        build_voxel_roundtrip_figure(debug, log1p_counts=log1p_roundtrip),
        width="stretch",
    )
    _info_popover(
        "se3 closure",
        "Checks chain consistency of SE(3): "
        "T_world_cam vs T_world_rig_ref * T_rig_ref_cam. "
        "Near-zero translation/rotation residuals indicate that pose "
        "composition and inversion are consistent.",
    )
    st.plotly_chart(
        build_se3_closure_figure(
            batch.candidate_poses_world_cam,
            batch.reference_pose_world_rig,
        ),
        width="stretch",
    )
    _info_popover(
        "voxel in-bounds",
        "Transforms candidate centers into the voxel frame and reports "
        "the fraction inside the voxel extent. Normalized coordinate "
        "histograms show whether per-axis scaling stays within [-1, 1].",
    )
    st.plotly_chart(
        build_voxel_inbounds_figure(
            batch.candidate_poses_world_cam,
            debug.backbone_out.t_world_voxel,
            debug.backbone_out.voxel_extent,
        ),
        width="stretch",
    )
    pos_grid = getattr(debug, "pos_grid", None)
    if pos_grid is not None or getattr(debug, "backbone_out", None) is not None:
        try:
            if pos_grid is None:
                field_in = debug.field_in
                grid_shape = (
                    int(field_in.shape[-3]),
                    int(field_in.shape[-2]),
                    int(field_in.shape[-1]),
                )
                pos_grid = pos_grid_from_pts_world(
                    debug.backbone_out.pts_world,
                    t_world_voxel=debug.backbone_out.t_world_voxel,
                    pose_world_rig_ref=batch.reference_pose_world_rig,
                    voxel_extent=debug.backbone_out.voxel_extent,
                    grid_shape=grid_shape,
                )
            _info_popover(
                "pos grid linearity",
                "Fits an affine map from voxel coordinates to pos_grid values "
                "and reports R² per rig axis. High R² indicates that the "
                "positional grid is a linear transform of voxel coords.",
            )
            st.plotly_chart(
                build_pos_grid_linearity_figure(
                    pos_grid,  # type: ignore[arg-type]
                    debug.backbone_out.voxel_extent,
                ),
                width="stretch",
            )
        except Exception as exc:  # pragma: no cover - optional diagnostics
            st.info(
                f"Pos-grid linearity unavailable: {type(exc).__name__}: {exc}",
            )
    if ctx.has_tokens:
        pred_norm = _to_numpy(pred.expected_normalized.reshape(-1))
        st.plotly_chart(
            build_prediction_alignment_figure(debug, expected_normalized=pred_norm),
            width="stretch",
        )
    else:
        st.info("Prediction alignment plot is only available for VIN v1.")


__all__ = ["render_transforms_tab"]
