"""Geometry tab for VIN diagnostics."""

from __future__ import annotations

import plotly.graph_objects as go  # type: ignore[import-untyped]
import streamlit as st
import torch

from ....data_handling import VinSnippetView
from ....rri_metrics.coral import coral_loss
from ....vin.diagnostics import build_alignment_figures
from ....vin.diagnostics.plotting import build_geometry_overview_figure, build_semidense_projection_figure
from ..common import _info_popover
from ..data import scene_plot_options_ui
from .context import VinDiagContext


def render_geometry_tab(ctx: VinDiagContext) -> None:
    """Render the Geometry tab.

    Args:
        ctx: Shared VIN diagnostics context.
    """
    state = ctx.state
    debug = ctx.debug
    pred = ctx.pred
    batch = ctx.batch

    _info_popover(
        "geometry overview",
        "Combines candidate centers, trajectory, semidense points, and GT mesh "
        "in the same world frame. Frusta and GT OBBs help verify that the "
        "candidate poses align with scene geometry and annotations.",
    )
    snippet_view = batch.efm_snippet_view
    if snippet_view is None:
        st.info(
            "Geometry plots require EFM or VIN snippets from the configured diagnostics source.",
        )
        return
    if isinstance(snippet_view, VinSnippetView) or not hasattr(snippet_view, "camera_rgb"):
        st.info(
            "VIN offline snippets provide minimal geometry. Showing semidense-only views "
            "and candidate visibility instead of the full scene overview.",
        )
        points_world = snippet_view.points_world
        if not torch.is_tensor(points_world) or points_world.numel() == 0:
            st.info("VIN offline snippet points are empty.")
        else:
            batch_idx = 0
            if points_world.ndim == 3:
                batch_size = int(points_world.shape[0])
                batch_idx = int(
                    st.number_input(
                        "Batch index",
                        min_value=0,
                        max_value=max(0, batch_size - 1),
                        value=0,
                        step=1,
                        key="vin_geom_vin_snippet_batch_idx",
                    ),
                )
                points_world = points_world[batch_idx]
            points_world = points_world[..., :3]
            finite = torch.isfinite(points_world).all(dim=-1)
            points_world = points_world[finite]

            max_points = int(
                st.slider(
                    "Max semidense points",
                    min_value=1000,
                    max_value=200000,
                    value=40000,
                    step=1000,
                    key="vin_geom_vin_snippet_max_points",
                ),
            )
            if points_world.shape[0] > max_points:
                idx = torch.randperm(points_world.shape[0], device=points_world.device)[:max_points]
                points_world = points_world[idx]

            pts_np = points_world.detach().cpu().numpy()
            fig_points = go.Figure()
            if pts_np.shape[0] > 0:
                fig_points.add_trace(
                    go.Scatter3d(
                        x=pts_np[:, 0],
                        y=pts_np[:, 1],
                        z=pts_np[:, 2],
                        mode="markers",
                        marker={"size": 2, "opacity": 0.6, "color": "#4c78a8"},
                        name="semidense",
                        showlegend=False,
                    ),
                )
            fig_points.update_layout(
                title="VIN snippet semidense point cloud",
                scene={"aspectmode": "data"},
                margin={"l": 0, "r": 0, "t": 40, "b": 0},
            )
            st.plotly_chart(fig_points, width="stretch")

            poses = batch.candidate_poses_world_cam.tensor()
            if poses.ndim == 3:
                cand_batch = int(poses.shape[0])
                num_candidates = int(poses.shape[1])
            else:
                cand_batch = 1
                num_candidates = int(poses.shape[0])
            if num_candidates > 0:
                cand_idx = int(
                    st.slider(
                        "Candidate index",
                        min_value=0,
                        max_value=max(0, num_candidates - 1),
                        value=0,
                        step=1,
                        key="vin_geom_vin_snippet_candidate_idx",
                    ),
                )
                show_frustum = st.checkbox(
                    "Show candidate frustum",
                    value=True,
                    key="vin_geom_vin_snippet_show_frustum",
                )
                frustum_scale = float(
                    st.slider(
                        "Frustum scale",
                        min_value=0.1,
                        max_value=10.0,
                        value=1.0,
                        step=0.1,
                        key="vin_geom_vin_snippet_frustum_scale",
                    ),
                )
                frustum_color = st.color_picker(
                    "Frustum color",
                    value="#ff4d4d",
                    key="vin_geom_vin_snippet_frustum_color",
                )
                cam_count = int(batch.p3d_cameras.R.shape[0])
                proj_batch = batch_idx if batch_idx < cand_batch else 0
                global_idx = cand_idx
                if cam_count == cand_batch * num_candidates:
                    global_idx = proj_batch * num_candidates + cand_idx
                elif cam_count <= global_idx:
                    global_idx = max(0, cam_count - 1)
                st.plotly_chart(
                    build_semidense_projection_figure(
                        points_world,
                        p3d_cameras=batch.p3d_cameras,
                        candidate_index=global_idx,
                        max_points=max_points,
                        show_frustum=show_frustum,
                        frustum_scale=frustum_scale,
                        frustum_color=frustum_color,
                    ),
                    width="stretch",
                )
            else:
                st.info("No candidates available for projection.")

        if ctx.has_tokens:
            log1p_align_counts = st.checkbox(
                "Log1p alignment histogram counts",
                value=False,
                key="vin_geom_align_log1p",
            )
            alignment_figs = build_alignment_figures(
                debug,
                log1p_counts=log1p_align_counts,
            )
            for key, fig in alignment_figs.items():
                st.plotly_chart(fig, width="stretch", key=f"vin_align_{key}")
        return

    cam_choice, plot_opts = scene_plot_options_ui(
        snippet_view,
        key_prefix="vin_geom",
    )
    frustum_indices = plot_opts.frustum_frame_indices[-1:] if plot_opts.frustum_frame_indices else []
    axis_expander = st.expander("Axes & candidate settings", expanded=False)
    with axis_expander:
        show_reference_axes = st.checkbox(
            "Show reference axes",
            value=True,
            key="vin_geom_ref_axes",
        )
        show_voxel_axes = st.checkbox(
            "Show voxel axes",
            value=True,
            key="vin_geom_voxel_axes",
        )
        candidate_pose_mode = st.selectbox(
            "Candidate coordinates",
            options=["ref rig", "world cam", "rig (raw)"],
            index=0,
            key="vin_geom_candidate_pose_mode",
        )
        candidate_color_mode_ui = st.selectbox(
            "Candidate color mode",
            options=[
                "valid fraction",
                "solid",
                "loss",
                "predicted score",
                "oracle rri",
                "voxel_valid_frac",
                "semidense_candidate_vis_frac",
            ],
            index=0,
            key="vin_geom_candidate_color_mode",
        )
        candidate_color = "#ffd966"
        candidate_colorscale = "Viridis"
        if candidate_color_mode_ui == "solid":
            candidate_color = st.color_picker(
                "Candidate color",
                value="#ffd966",
                key="vin_geom_candidate_color",
            )
        else:
            candidate_colorscale = st.selectbox(
                "Candidate colorscale",
                options=["Viridis", "Cividis", "Plasma", "Turbo", "Magma"],
                index=0,
                key="vin_geom_candidate_colorscale",
            )

    candidate_frusta_indices: list[int] = []
    candidate_frusta_scale = 0.5
    candidate_frusta_color = "#ff4d4d"
    candidate_frusta_show_axes = False
    candidate_frusta_show_center = False
    candidate_frusta_camera = cam_choice
    candidate_frusta_frame_index = frustum_indices[0] if frustum_indices else 0
    with st.expander("Candidate frusta", expanded=False):
        show_candidate_frusta = st.checkbox(
            "Show candidate frusta",
            value=False,
            key="vin_geom_candidate_frusta",
        )
        if show_candidate_frusta:
            options = list(range(ctx.num_candidates))
            default = options[: min(4, len(options))] if options else []
            candidate_frusta_indices = st.multiselect(
                "Candidate indices",
                options=options,
                default=default,
                key="vin_geom_candidate_frusta_indices",
            )
            candidate_frusta_camera = st.selectbox(
                "Candidate frusta camera",
                options=["rgb", "slam-l", "slam-r"],
                index=0,
                key="vin_geom_candidate_frusta_camera",
            )
            candidate_frusta_scale = float(
                st.slider(
                    "Candidate frusta scale",
                    min_value=0.1,
                    max_value=2.0,
                    value=0.5,
                    step=0.05,
                    key="vin_geom_candidate_frusta_scale",
                ),
            )
            candidate_frusta_color = st.color_picker(
                "Candidate frusta color",
                value="#ff4d4d",
                key="vin_geom_candidate_frusta_color",
            )
            candidate_frusta_show_axes = st.checkbox(
                "Show candidate axes",
                value=False,
                key="vin_geom_candidate_frusta_axes",
            )
            candidate_frusta_show_center = st.checkbox(
                "Show candidate center",
                value=False,
                key="vin_geom_candidate_frusta_center",
            )
    backbone_fields: list[str] = []
    backbone_threshold = 0.5
    backbone_max_points = 40_000
    backbone_colorscale = "Viridis"
    available_fields: list[str] = []
    if debug.backbone_out is not None:
        available_fields = [
            name for name in ("occ_pr", "occ_input", "counts") if getattr(debug.backbone_out, name, None) is not None
        ]
    with st.expander("Backbone evidence overlay", expanded=False):
        show_backbone = st.checkbox(
            "Overlay backbone evidence",
            value=False,
            key="vin_geom_backbone_enable",
        )
        if not available_fields:
            st.info("Backbone evidence not available in debug outputs.")
        elif show_backbone:
            backbone_fields = st.multiselect(
                "Backbone fields",
                options=available_fields,
                default=available_fields,
                key="vin_geom_backbone_fields",
            )
            backbone_colorscale = st.selectbox(
                "Evidence colorscale",
                options=["Viridis", "Cividis", "Plasma", "Turbo", "Magma"],
                index=0,
                key="vin_geom_backbone_colorscale",
            )
            backbone_threshold = float(
                st.slider(
                    "Evidence threshold",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.5,
                    step=0.01,
                    key="vin_geom_backbone_threshold",
                ),
            )
            backbone_max_points = int(
                st.slider(
                    "Max evidence points",
                    min_value=1000,
                    max_value=200000,
                    value=40000,
                    step=1000,
                    key="vin_geom_backbone_max_points",
                ),
            )
    candidate_plot_mode = "valid_fraction"
    candidate_color_values: torch.Tensor | None = None
    candidate_color_title = "value"
    match candidate_color_mode_ui:
        case "solid":
            candidate_plot_mode = "solid"
        case "valid fraction":
            candidate_plot_mode = "valid_fraction"
        case "predicted score":
            candidate_plot_mode = "scalar"
            candidate_color_values = pred.expected_normalized
            candidate_color_title = "expected_norm"
        case "oracle rri":
            if batch.rri is None:
                st.info("Oracle RRI unavailable; falling back to valid fraction.")
            else:
                candidate_plot_mode = "scalar"
                candidate_color_values = batch.rri
                candidate_color_title = "oracle_rri"
        case "voxel_valid_frac":
            values = pred.voxel_valid_frac
            if values is None:
                values = getattr(debug, "voxel_valid_frac", None)
            if values is None:
                st.info("voxel_valid_frac unavailable; falling back to valid fraction.")
            else:
                candidate_plot_mode = "scalar"
                candidate_color_values = values
                candidate_color_title = "voxel_valid_frac"
        case "semidense_candidate_vis_frac":
            values = pred.semidense_candidate_vis_frac
            if values is None:
                values = getattr(debug, "semidense_candidate_vis_frac", None)
            if values is None:
                st.info("semidense_candidate_vis_frac unavailable; falling back to valid fraction.")
            else:
                candidate_plot_mode = "scalar"
                candidate_color_values = values
                candidate_color_title = "semidense_candidate_vis_frac"
        case "loss":
            loss_error = None
            binner = getattr(state.module, "_binner", None)
            if binner is None:
                loss_error = "RRI binner unavailable; cannot compute loss hue."
            elif batch.rri is None:
                loss_error = "Loss hue requires oracle RRI labels."
            else:
                try:
                    with torch.no_grad():
                        logits = pred.logits
                        rri = batch.rri.to(device=logits.device)
                        rri_flat = rri.reshape(-1)
                        mask = torch.isfinite(rri_flat)
                        if mask.any():
                            labels = binner.transform(rri_flat)
                            loss_per = coral_loss(
                                logits.reshape(-1, logits.shape[-1])[mask],
                                labels[mask],
                                num_classes=int(binner.num_classes),
                                reduction="none",
                            )
                            loss_flat = torch.full(
                                (rri_flat.numel(),),
                                float("nan"),
                                device=logits.device,
                                dtype=torch.float32,
                            )
                            loss_flat[mask] = loss_per
                            candidate_plot_mode = "scalar"
                            candidate_color_values = loss_flat.reshape(rri.shape)
                            candidate_color_title = "loss"
                        else:
                            loss_error = "Loss hue requires finite RRI labels."
                except Exception as exc:  # pragma: no cover - UI guard
                    loss_error = f"{type(exc).__name__}: {exc}"
            if loss_error:
                st.info(loss_error)
        case _:
            st.info("Unknown candidate color mode; falling back to valid fraction.")
    apply_cw90_correction = False
    if state.module is not None and hasattr(state.module, "vin"):
        apply_cw90_correction = bool(
            getattr(getattr(state.module.vin, "config", None), "apply_cw90_correction", False),
        )

    reference_pose_world_rig = batch.reference_pose_world_rig
    candidate_poses_world_cam = batch.candidate_poses_world_cam
    display_rotate_yaw_cw90 = False
    if not apply_cw90_correction:
        st.caption(
            "Note: VIN apply_cw90_correction is disabled; geometry plots assume corrected poses.",
        )

    st.plotly_chart(
        build_geometry_overview_figure(
            debug,
            snippet=snippet_view,
            reference_pose_world_rig=reference_pose_world_rig,
            max_candidates=512,
            show_scene_bounds=plot_opts.show_scene_bounds,
            show_crop_bounds=plot_opts.show_crop_bounds,
            show_frustum=plot_opts.show_frustum,
            frustum_camera=cam_choice,
            frustum_frame_indices=frustum_indices,
            frustum_scale=plot_opts.frustum_scale,
            show_gt_obbs=plot_opts.show_gt_obbs,
            gt_timestamp=plot_opts.gt_timestamp,
            semidense_mode=plot_opts.semidense_mode,
            max_sem_points=plot_opts.max_sem_points,
            show_trajectory=plot_opts.mark_first_last,
            mark_first_last=plot_opts.mark_first_last,
            show_reference_axes=show_reference_axes,
            show_voxel_axes=show_voxel_axes,
            display_rotate_yaw_cw90=display_rotate_yaw_cw90,
            candidate_pose_mode="ref_rig"
            if candidate_pose_mode == "ref rig"
            else "world_cam"
            if candidate_pose_mode == "world cam"
            else "rig",
            candidate_poses_world_cam=candidate_poses_world_cam,
            candidate_color_mode=candidate_plot_mode,
            candidate_color=candidate_color,
            candidate_colorscale=candidate_colorscale,
            candidate_color_values=candidate_color_values,
            candidate_color_title=candidate_color_title,
            candidate_frusta_indices=candidate_frusta_indices,
            candidate_frusta_camera=candidate_frusta_camera,
            candidate_frusta_frame_index=candidate_frusta_frame_index,
            candidate_frusta_scale=candidate_frusta_scale,
            candidate_frusta_color=candidate_frusta_color,
            candidate_frusta_show_axes=candidate_frusta_show_axes,
            candidate_frusta_show_center=candidate_frusta_show_center,
            backbone_fields=backbone_fields,
            backbone_occ_threshold=backbone_threshold,
            backbone_max_points=backbone_max_points,
            backbone_colorscale=backbone_colorscale,
        ),
        width="stretch",
        key="vin_geometry_overview",
    )

    if ctx.has_tokens:
        log1p_align_counts = st.checkbox(
            "Log1p alignment histogram counts",
            value=False,
            key="vin_geom_align_log1p",
        )
        alignment_figs = build_alignment_figures(
            debug,
            log1p_counts=log1p_align_counts,
        )
        for key, fig in alignment_figs.items():
            st.plotly_chart(fig, width="stretch", key=f"vin_align_{key}")


__all__ = ["render_geometry_tab"]
