"""Observed snippet inspection with optional oracle scene overlays.

The panel provides trajectory, camera, image, and semidense evidence views;
ASE meshes and GT boxes remain explicitly labeled evaluation-only overlays.
"""

from __future__ import annotations

import streamlit as st
import torch
from efm3d.aria.pose import PoseTW

from ...data_handling import EfmSnippetView
from ...utils.data_plotting import (
    SnippetPlotBuilder,
    collect_frame_modalities,
    plot_first_last_frames,
    pose_world_cam,
    project_pointcloud_on_frame,
    semidense_points_for_frame,
)
from ..scene_view import DATA_SCENE_DEFAULTS, apply_scene_plot_options, scene_plot_options_ui
from .common import _info_popover, _pretty_label


def render_data_page(
    sample: EfmSnippetView,
) -> None:
    """Render modalities, poses, projections, and 3D context for one snippet.

    Args:
        sample: Selected EFM snippet whose source poses are world-from-rig and
            whose observed camera/semidense evidence is actor-visible.
    """

    st.header("Observed Snippet")
    st.write(f"Scene: **{sample.scene_id}**, snippet: **{sample.snippet_id}**")

    first_pose = sample.trajectory.t_world_rig[0]
    last_pose = sample.trajectory.t_world_rig[-1]

    def _pose_summary(pose: torch.Tensor | PoseTW):
        pt = (
            pose
            if isinstance(pose, PoseTW)
            else PoseTW.from_matrix3x4(
                pose.view(3, 4) if pose.shape[-1] == 12 else pose,
            )
        )
        r, p, y = pt.to_ypr(rad=True)
        rpy = torch.rad2deg(torch.stack([r, p, y])).tolist()
        euler = torch.rad2deg(pt.to_euler(rad=True)).tolist()
        t = pt.t.tolist()
        return t, rpy, euler

    t_first, rpy_first, eul_first = _pose_summary(first_pose)
    t_last, rpy_last, eul_last = _pose_summary(last_pose)
    st.markdown(
        "- **First frame**: "
        f"t=({t_first[0]:.3f},{t_first[1]:.3f},{t_first[2]:.3f}) m, "
        f"RPY=({rpy_first[0]:.2f},{rpy_first[1]:.2f},{rpy_first[2]:.2f})°, "
        f"Euler ZYX=({eul_first[0]:.2f},{eul_first[1]:.2f},{eul_first[2]:.2f})°",
    )
    st.markdown(
        "- **Last frame**: "
        f"t=({t_last[0]:.3f},{t_last[1]:.3f},{t_last[2]:.3f}) m, "
        f"RPY=({rpy_last[0]:.2f},{rpy_last[1]:.2f},{rpy_last[2]:.2f})°, "
        f"Euler ZYX=({eul_last[0]:.2f},{eul_last[1]:.2f},{eul_last[2]:.2f})°",
    )

    modalities, missing = collect_frame_modalities(sample, include_depth=True)
    st.plotly_chart(plot_first_last_frames(sample), width="stretch")

    missing_depth = [m for m in missing if m.startswith("Depth")]
    if modalities and not missing_depth:
        st.caption("Depth maps available for rendering and overlays.")
    elif missing_depth:
        st.info(f"Depth maps missing for: {', '.join(missing_depth)}")

    st.subheader("Point cloud overlay")
    _info_popover(
        "overlay",
        "Projects world-space points into the selected camera image using the "
        "camera intrinsics and the per-frame pose. Use this to verify that "
        "the semidense SLAM points align with RGB/SLAM frames and to spot "
        "pose or calibration mismatches.",
    )
    overlay_cam = st.selectbox(
        "Overlay camera",
        ["rgb", "slam-l", "slam-r"],
        index=0,
        key="overlay_cam",
    )
    overlay_frame = st.slider(
        "Frame index for overlay",
        0,
        int(sample.camera_rgb.images.shape[0] - 1),
        0,
    )
    overlay_source = st.selectbox(
        "Point cloud source",
        [
            "Semidense (all frames)",
            "Semidense (selected frame)",
            "Semidense (last with points)",
        ],
        index=0,
    )

    if overlay_source == "Semidense (all frames)":
        points_world = semidense_points_for_frame(sample, None, all_frames=True)
    elif overlay_source == "Semidense (selected frame)":
        points_world = semidense_points_for_frame(
            sample,
            overlay_frame,
            all_frames=False,
        )
    else:
        lengths = sample.semidense.lengths if sample.semidense is not None else None
        last_idx = (
            int(torch.nonzero(lengths > 0, as_tuple=False).max().item())
            if lengths is not None and torch.any(lengths > 0)
            else 0
        )
        points_world = semidense_points_for_frame(sample, last_idx, all_frames=False)

    if points_world is None or points_world.numel() == 0:
        st.info("No points available for overlay with current selection.")
    else:
        cam_view = sample.get_camera(overlay_cam.replace("-", ""))
        pose_wc, cam_tw = pose_world_cam(sample, cam_view, overlay_frame)
        fig_overlay = project_pointcloud_on_frame(
            img=cam_view.images[overlay_frame],
            cam=cam_tw,
            pose_world_cam=pose_wc,
            points_world=points_world,
            title=_pretty_label(
                f"Overlay on {overlay_cam.upper()} frame {overlay_frame} ({points_world.shape[0]} pts)",
            ),
            max_points=20000,
        )
        st.plotly_chart(fig_overlay, width="stretch")

    cam_choice, plot_opts = scene_plot_options_ui(
        sample,
        key_prefix="data_scene",
        defaults=DATA_SCENE_DEFAULTS,
    )
    _info_popover(
        "scene overview",
        "3D scene view combines GT mesh, semidense points, and the trajectory. "
        "Frusta are drawn from camera intrinsics/extrinsics. Bounds boxes show "
        "scene extents and any crop applied during RRI computation.",
    )

    builder = SnippetPlotBuilder.from_snippet(
        sample,
        title=_pretty_label("Mesh + semidense + trajectory + camera frustum"),
    )
    apply_scene_plot_options(builder, sample, camera=cam_choice, options=plot_opts)

    st.plotly_chart(builder.finalize(), width="stretch")


__all__ = ["render_data_page"]
