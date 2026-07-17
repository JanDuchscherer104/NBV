"""Reference-rig candidate pose descriptor diagnostics for VIN.

The tab provides centre radii and directions, camera-forward alignment, and
6D-rotation validity checks for actor-visible world-from-camera candidate poses.
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import torch
from plotly.subplots import make_subplots
from pytorch3d.transforms import rotation_6d_to_matrix

from ....pose_generation.plotting import (
    plot_direction_polar,
    plot_direction_sphere,
    plot_radius_hist,
)
from ....utils.plotting import _histogram_overlay, _to_numpy
from ..common import _info_popover, _pretty_label
from .context import VinDiagContext


def render_pose_tab(ctx: VinDiagContext) -> None:
    """Render the Pose Descriptor tab.

    Args:
        ctx: Shared VIN diagnostics context.
    """
    debug = ctx.debug
    has_tokens = ctx.has_tokens

    _info_popover(
        "pose descriptor",
        "Candidate centers are translations of `T_rig_ref_cam` "
        "(reference rig frame). Radii are `||t||` in meters. "
        "For VIN v1, direction plots show unit vectors for center "
        "directions and forward axes; view alignment is `dot(f, -u)`, "
        "measuring how much the camera looks back toward the rig. "
        "VIN v2 does not compute frustum tokens.",
    )
    centers = _to_numpy(debug.candidate_center_rig_m.reshape(-1, 3))
    st.plotly_chart(
        plot_radius_hist(
            centers,
            title=_pretty_label("Candidate radii (reference rig)"),
        ),
        width="stretch",
    )

    pose_vec = getattr(debug, "pose_vec", None)
    if torch.is_tensor(pose_vec) and pose_vec.shape[-1] >= 9:
        pose_flat = pose_vec.reshape(-1, pose_vec.shape[-1])
        r6d = pose_flat[:, 3:9]
        try:
            r6d_rot = rotation_6d_to_matrix(r6d.to(dtype=torch.float32))
            eye = torch.eye(3, device=r6d_rot.device, dtype=r6d_rot.dtype).unsqueeze(0)
            resid = r6d_rot.transpose(1, 2) @ r6d_rot - eye
            ortho_err = torch.linalg.norm(resid, dim=(1, 2))
            det = torch.det(r6d_rot)

            _info_popover(
                "r6d orthonormality",
                "Orthonormality error (||R^T R - I||_F) and determinant for rotations "
                "reconstructed from the 6D representation (Zhou et al., 2019). "
                "These should cluster near 0 error and det≈1.",
            )
            col_err, col_det = st.columns(2)
            with col_err:
                st.plotly_chart(
                    _histogram_overlay(
                        [("orthonormality error", _to_numpy(ortho_err))],
                        bins=60,
                        title=_pretty_label("R6D orthonormality error"),
                        xaxis_title=_pretty_label("||R^T R - I||_F"),
                        log1p_counts=False,
                    ),
                    width="stretch",
                )
            with col_det:
                st.plotly_chart(
                    _histogram_overlay(
                        [("det(R)", _to_numpy(det))],
                        bins=60,
                        title=_pretty_label("R6D determinant"),
                        xaxis_title=_pretty_label("det(R)"),
                        log1p_counts=False,
                    ),
                    width="stretch",
                )
        except Exception:  # pragma: no cover - diagnostic-only
            st.info("R6D orthonormality plot unavailable for this batch.")

        _info_popover(
            "r6d circles",
            "R6D component circle plots (Zhou et al., 2019). Each 3D vector in the 6D "
            "representation is projected to XY/XZ/YZ planes after normalization.",
        )
        r6d_cols = r6d.reshape(-1, 2, 3)
        norms = torch.linalg.norm(r6d_cols, dim=-1, keepdim=True).clamp_min(1e-6)
        r6d_norm = (r6d_cols / norms).detach().cpu().numpy()
        colors = np.linspace(0.0, 1.0, r6d_norm.shape[0])
        fig = make_subplots(
            rows=2,
            cols=3,
            subplot_titles=(
                "col1: (x, y)",
                "col1: (x, z)",
                "col1: (y, z)",
                "col2: (x, y)",
                "col2: (x, z)",
                "col2: (y, z)",
            ),
        )
        for row in range(2):
            vec = r6d_norm[:, row, :]
            pairs = [(0, 1), (0, 2), (1, 2)]
            for col, (i, j) in enumerate(pairs, start=1):
                fig.add_trace(
                    go.Scatter(
                        x=vec[:, i],
                        y=vec[:, j],
                        mode="markers",
                        marker={
                            "size": 3,
                            "color": colors,
                            "colorscale": "Turbo",
                            "showscale": False,
                            "opacity": 0.6,
                        },
                        name=f"col{row + 1}",
                    ),
                    row=row + 1,
                    col=col,
                )
        fig.update_layout(
            title=_pretty_label("R6D component circle plots"),
            height=520,
            showlegend=False,
        )
        st.plotly_chart(fig, width="stretch")

    if has_tokens:
        center_dirs = _to_numpy(debug.candidate_center_dir_rig.reshape(-1, 3))
        forward_dirs = _to_numpy(debug.candidate_forward_dir_rig.reshape(-1, 3))
        view_align = _to_numpy(debug.view_alignment.reshape(-1))

        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(
                plot_direction_polar(
                    center_dirs,
                    title=_pretty_label("Candidate center directions (rig frame)"),
                ),
                width="stretch",
            )
        with col2:
            st.plotly_chart(
                plot_direction_sphere(
                    center_dirs,
                    title=_pretty_label("Center directions on unit sphere"),
                ),
                width="stretch",
            )

        col3, col4 = st.columns(2)
        with col3:
            st.plotly_chart(
                plot_direction_polar(
                    forward_dirs,
                    title=_pretty_label("Candidate forward directions (rig frame)"),
                ),
                width="stretch",
            )
        with col4:
            st.plotly_chart(
                plot_direction_sphere(
                    forward_dirs,
                    title=_pretty_label("Forward directions on unit sphere"),
                ),
                width="stretch",
            )

        log1p_pose_counts = st.checkbox(
            "Log1p alignment histogram counts",
            value=False,
            key="vin_pose_align_log1p",
        )
        fig_align = _histogram_overlay(
            [("alignment", view_align)],
            bins=60,
            title=_pretty_label("View alignment dot(f, -u)"),
            xaxis_title=_pretty_label("dot(f, -u)"),
            log1p_counts=log1p_pose_counts,
        )
        st.plotly_chart(fig_align, width="stretch")
    else:
        st.info("Pose-direction plots are only available for VIN v1 diagnostics.")


__all__ = ["render_pose_tab"]
