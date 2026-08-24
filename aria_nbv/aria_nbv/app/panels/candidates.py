"""Candidate-shell inspection and provenance plots for the NBV app.

The panel provides world-frame pose, validity, motion-rule, and sampling-family
diagnostics for actor-visible finite candidates without treating invalid rows
as low-value oracle labels.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import torch

from ...pose_generation.plotting import (
    CandidatePlotBuilder,
    _euler_histogram,
    plot_candidate_centers_simple,
    plot_candidate_frusta_simple,
    plot_direction_marginals,
    plot_direction_polar,
    plot_direction_sphere,
    plot_euler_reference,
    plot_euler_world,
    plot_min_distance_to_mesh,
    plot_path_collision_segments,
    plot_position_polar,
    plot_position_sphere,
    plot_radius_hist,
    plot_rule_masks,
    plot_rule_rejection_bar,
    plot_view_jitter_support,
)
from ...pose_generation.utils import (
    rejected_pose_tensor,
    stats_to_markdown_table,
    summarise_dirs_ref,
    summarise_offsets_ref,
)
from ...rollouts.inspection import decode_position_id, decode_strategy_id
from ...rollouts.trace import _candidate_invalid_reasons
from ...utils.frames import world_up_tensor

if TYPE_CHECKING:
    from efm3d.aria.pose import PoseTW

    from ...data_handling import EfmSnippetView
    from ...pose_generation import CandidateViewGeneratorConfig
    from ...pose_generation.types import CandidateSamplingResult
from .common import _info_popover, _pretty_label, current_scientific_label


def _pose_tensor(pose: PoseTW) -> torch.Tensor:
    """Cross the untyped EFM pose accessor with a typed tensor result."""

    tensor: Callable[[], Any] = pose.tensor
    return cast(torch.Tensor, tensor())


def _target_point_from_config(cand_cfg: CandidateViewGeneratorConfig | None) -> torch.Tensor | None:
    """Return configured actor-visible target point for display overlays."""

    if cand_cfg is None:
        return None
    target = cand_cfg.position_target_point_world
    if target is None:
        target = cand_cfg.view_target_point_world
    if target is None:
        return None
    return torch.as_tensor(target, dtype=torch.float32).reshape(3)


def _add_target_context_overlay(
    builder: CandidatePlotBuilder,
    candidates: CandidateSamplingResult,
    target_world: torch.Tensor | None,
) -> CandidatePlotBuilder:
    """Overlay target center and reference-to-target bearing when available."""

    if target_world is None:
        return builder
    target_np = target_world.detach().cpu().numpy().reshape(3)
    ref_np = candidates.reference_pose.t.detach().cpu().numpy().reshape(3)
    builder.add_points(
        target_np.reshape(1, 3),
        name="Actor-visible target center",
        color="gold",
        size=8,
        opacity=0.95,
        symbol="diamond",
    )
    builder.fig.add_trace(
        go.Scatter3d(
            x=[ref_np[0], target_np[0]],
            y=[ref_np[1], target_np[1]],
            z=[ref_np[2], target_np[2]],
            mode="lines",
            line={"color": "gold", "width": 5},
            name="Target bearing",
        )
    )
    return builder


def _full_shell_color_payload(candidates: CandidateSamplingResult, mode: str) -> tuple[torch.Tensor | None, str | None]:
    """Return full-shell candidate color values and colorbar label."""

    mask_valid = candidates.mask_valid.detach().cpu().reshape(-1)
    if mode == "validity":
        return mask_valid.to(dtype=torch.float32), current_scientific_label("validity_mask")
    if mode == "position_family" and candidates.position_id is not None:
        return candidates.position_id.detach().cpu().to(dtype=torch.float32).reshape(-1), "position_id"
    if mode == "strategy" and candidates.strategy_id is not None:
        return candidates.strategy_id.detach().cpu().to(dtype=torch.float32).reshape(-1), "strategy_id"
    if mode == "invalid_reason":
        _bitset, primary = _candidate_invalid_reasons(candidates)
        return primary.detach().cpu().to(dtype=torch.float32).reshape(-1), "invalid_reason_id"
    extras = candidates.extras if hasattr(candidates, "extras") else {}
    target_distance = extras.get("target_distance_m")
    if mode == "target_distance" and isinstance(target_distance, torch.Tensor):
        return target_distance.detach().cpu().to(dtype=torch.float32).reshape(-1), "target_distance_m"
    target_bearing = extras.get("target_bearing_yaw_rad")
    if mode == "target_bearing_yaw" and isinstance(target_bearing, torch.Tensor):
        return torch.rad2deg(target_bearing.detach().cpu().to(dtype=torch.float32).reshape(-1)), (
            "target_bearing_yaw_deg"
        )
    return None, None


def _color_payload_np(candidates: CandidateSamplingResult, mode: str) -> tuple[np.ndarray | None, str | None]:
    """Return NumPy color values aligned with the full candidate shell."""

    values, label = _full_shell_color_payload(candidates, mode)
    if values is None:
        return None, None
    return values.detach().cpu().numpy().reshape(-1), label


def _candidate_provenance_preview(candidates: CandidateSamplingResult) -> list[dict[str, Any]]:
    """Return decoded provenance counts for target-aware candidate mixtures."""

    rows: list[dict[str, Any]] = []
    mask_valid = candidates.mask_valid.detach().cpu().numpy().reshape(-1).astype(bool, copy=False)
    if candidates.position_id is not None:
        position = candidates.position_id.detach().cpu().numpy().reshape(-1)
        for value in sorted({int(item) for item in position.tolist()}):
            mask = position == value
            rows.append(
                {
                    "kind": "position",
                    "name": decode_position_id(value),
                    "total": int(mask.sum()),
                    "valid": int((mask & mask_valid).sum()),
                }
            )
    if candidates.strategy_id is not None:
        strategy = candidates.strategy_id.detach().cpu().numpy().reshape(-1)
        for value in sorted({int(item) for item in strategy.tolist()}):
            mask = strategy == value
            rows.append(
                {
                    "kind": "strategy",
                    "name": decode_strategy_id(value),
                    "total": int(mask.sum()),
                    "valid": int((mask & mask_valid).sum()),
                }
            )
    return rows


def _motion_threshold_rows(
    candidates: CandidateSamplingResult,
    cand_cfg: CandidateViewGeneratorConfig | None,
) -> list[dict[str, Any]]:
    """Return configured rule thresholds with observed diagnostic ranges."""

    if cand_cfg is None:
        return []
    extras = candidates.extras if hasattr(candidates, "extras") else {}
    specs = [
        ("min_distance_to_mesh", "min", "m", cand_cfg.min_distance_to_mesh, "min_distance_to_mesh"),
        ("path_clearance", "min", "m", cand_cfg.step_clearance, "path_min_clearance_m"),
        ("step_length", "max", "m", cand_cfg.max_step_distance_m, "motion_step_length_m"),
        ("height_delta", "max_abs", "m", cand_cfg.max_height_delta_m, "motion_height_delta_m"),
        ("backward_step", "max", "m", cand_cfg.max_backward_step_m, "motion_backward_step_m"),
        ("yaw_delta", "max_abs", "deg", cand_cfg.max_yaw_delta_deg, "motion_yaw_delta_rad"),
    ]
    rows: list[dict[str, Any]] = []
    for name, comparator, unit, threshold, debug_key in specs:
        if threshold is None:
            continue
        observed_min: float | None = None
        observed_max: float | None = None
        values = extras.get(debug_key)
        if isinstance(values, torch.Tensor):
            flat = values.detach().cpu().to(dtype=torch.float32).reshape(-1)
            if debug_key == "motion_yaw_delta_rad":
                flat = torch.rad2deg(flat)
            finite = flat[torch.isfinite(flat)]
            if finite.numel() > 0:
                observed_min = float(finite.min().item())
                observed_max = float(finite.max().item())
        rows.append(
            {
                "rule": name,
                "comparator": comparator,
                "threshold": float(threshold),
                "unit": unit,
                "observed_min": observed_min,
                "observed_max": observed_max,
            }
        )
    return rows


def _shell_offsets_dirs_ref(
    candidates: CandidateSamplingResult,
) -> tuple[torch.Tensor, torch.Tensor] | None:
    """Offsets and forward directions for the full sampling shell in reference frame."""

    shell = candidates.shell_poses
    if shell is None or shell._data is None or shell._data.numel() == 0:
        return None
    ref_inv = candidates.reference_pose.inverse().to(shell.t.device)
    poses_ref_cam = ref_inv.compose(shell)
    offsets = poses_ref_cam.t.view(-1, 3)
    z_cam = (
        torch.tensor([0.0, 0.0, 1.0], device=offsets.device, dtype=offsets.dtype).view(1, 3).expand(offsets.shape[0], 3)
    )
    dirs = poses_ref_cam.rotate(z_cam).view(-1, 3)
    dirs = dirs / dirs.norm(dim=-1, keepdim=True).clamp_min(1e-8)
    return offsets, dirs


def _pose_orthonormality_stats(pose: PoseTW) -> dict[str, float]:
    """Summarize orthonormality statistics for a pose rotation matrix.

    Args:
        pose: PoseTW with rotation matrices in ``pose.R``.

    Returns:
        Aggregated orthonormality statistics across all poses in the batch.
    """

    r = pose.R.detach()
    if r.ndim == 2:
        r = r.unsqueeze(0)
    eye = torch.eye(3, device=r.device, dtype=r.dtype).unsqueeze(0)
    resid = r.transpose(-1, -2) @ r - eye
    resid_abs = resid.abs()
    ortho_max = resid_abs.amax(dim=(-1, -2))
    ortho_mean = resid_abs.mean(dim=(-1, -2))

    axis_norms = torch.linalg.norm(r, dim=-2)
    axis_norm_err = (axis_norms - 1.0).abs()
    axis_norm_max = axis_norm_err.amax(dim=-1)
    axis_norm_mean = axis_norm_err.mean(dim=-1)

    det = torch.linalg.det(r)

    return {
        "orth_max": float(ortho_max.max().item()),
        "orth_mean": float(ortho_mean.mean().item()),
        "axis_norm_max": float(axis_norm_max.max().item()),
        "axis_norm_mean": float(axis_norm_mean.mean().item()),
        "det_min": float(det.min().item()),
        "det_max": float(det.max().item()),
        "det_mean": float(det.mean().item()),
    }


def _render_pose_orthonormality(label: str, pose: PoseTW | None) -> None:
    """Render orthonormality metrics for a pose in Streamlit."""

    if pose is None:
        st.info(f"{label}: pose not available.")
        return

    stats = _pose_orthonormality_stats(pose)
    st.markdown(f"**{label}**")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("max |R^T R - I|", f"{stats['orth_max']:.2e}")
    with col2:
        st.metric("mean |R^T R - I|", f"{stats['orth_mean']:.2e}")
    with col3:
        st.metric("max |axis_norm - 1|", f"{stats['axis_norm_max']:.2e}")
    with col4:
        st.metric("det(R) mean", f"{stats['det_mean']:.6f}")
    st.caption(
        "det(R) range: "
        f"[{stats['det_min']:.6f}, {stats['det_max']:.6f}] · "
        f"mean |axis_norm - 1|: {stats['axis_norm_mean']:.2e}",
    )


def _render_live_candidates_page(
    sample: EfmSnippetView | None,
    candidates: CandidateSamplingResult,
    cand_cfg: CandidateViewGeneratorConfig | None,
    *,
    source_caption: str | None = None,
    source_note: str | None = None,
) -> None:
    st.header("Candidate Proposals")

    if source_caption:
        st.caption(source_caption)
    if source_note:
        st.caption(source_note)

    shell_poses = candidates.shell_poses
    mask_valid = candidates.mask_valid

    cam_label = cand_cfg.camera_label if cand_cfg is not None else "cached"
    has_snippet = sample is not None
    target_world = _target_point_from_config(cand_cfg)

    mode_options = ["raw candidate generator", "target-conditioned mixture / provenance"]
    inspection_mode = st.radio(
        "Inspection mode",
        options=mode_options,
        horizontal=True,
        key="cand_inspection_mode",
    )
    if inspection_mode == mode_options[1] and candidates.position_id is None and target_world is None:
        st.info(
            "This candidate result does not carry target-conditioned mixture provenance or a configured target point."
        )

    with st.container(border=True):
        st.subheader("Sampling behavior: view jitter")
        st.caption(
            "Each marker is one generated full-shell candidate. The dotted box is the resolved yaw/pitch "
            "sampling contract; crosses are proposals rejected by downstream hard rules."
        )
        st.plotly_chart(plot_view_jitter_support(candidates), width="stretch")

    with st.expander("Frame orthonormality", expanded=False):
        _info_popover(
            "frame orthonormality",
            "Reports orthonormality errors for the reference and sampling poses "
            "(R^T R should be close to I, det(R) near +1). These stats are "
            "computed before any display-only rotations.",
        )
        _render_pose_orthonormality("Reference pose (world <- rig)", candidates.reference_pose)
        sampling_pose = candidates.sampling_pose
        if sampling_pose is None:
            st.info("Sampling pose not available (cached data or gravity alignment disabled).")
        else:
            if sampling_pose is candidates.reference_pose:
                st.caption("Sampling pose matches reference pose.")
            _render_pose_orthonormality("Sampling pose (world <- sampling)", sampling_pose)

    tab_pos, tab_frusta = st.tabs(["Positions (3D)", "Frusta (3D)"])

    with tab_pos:
        _info_popover(
            "candidate positions",
            "Candidate centers are sampled around the reference pose according "
            "to the sampling shell (radius, azimuth, elevation). Only valid "
            "candidates (after rule filtering) are shown in blue. The reference "
            "axes show the sampling frame (gravity-aligned when enabled) to "
            "stay symmetric with the candidate cloud.",
        )
        color_mode = st.selectbox(
            "Color candidates by",
            options=[
                "validity",
                "position_family",
                "strategy",
                "invalid_reason",
                "target_distance",
                "target_bearing_yaw",
            ],
            index=0,
            key="cand_position_color_mode",
        )
        color_values, color_title = _color_payload_np(candidates, color_mode)
        if sample is not None:
            builder = CandidatePlotBuilder.from_candidates(
                sample,
                candidates,
                title=_pretty_label(f"Candidate positions ({cam_label})"),
            ).add_mesh()
            if color_values is None:
                builder.add_candidate_cloud(use_valid=True, color="royalblue", size=4, opacity=0.7)
            else:
                builder.add_candidate_points(
                    use_valid=False,
                    color=color_values,
                    colorbar_title=color_title,
                    name="Full candidate shell",
                    size=4,
                    opacity=0.72,
                    mark_reference=True,
                )
            cand_fig = (
                _add_target_context_overlay(builder, candidates, target_world)
                .add_reference_axes(display_rotate=True)
                .finalize()
            )
            st.plotly_chart(cand_fig, width="stretch")
        else:
            st.warning("EFM snippet not attached; rendering candidates without mesh.")
            st.plotly_chart(
                plot_candidate_centers_simple(
                    candidates,
                    title=_pretty_label("Candidate positions (cached)"),
                ),
                width="stretch",
            )
        provenance_rows = _candidate_provenance_preview(candidates)
        if provenance_rows:
            with st.expander("Position / strategy provenance", expanded=False):
                st.dataframe(provenance_rows, width="stretch", hide_index=True)

    offsets_ref, dirs_ref = candidates.get_offsets_and_dirs_ref(display_rotate=False)
    shell_data = _shell_offsets_dirs_ref(candidates)
    dirs_shell_ref = shell_data[1] if shell_data is not None else None

    with tab_frusta:
        if mask_valid is None or mask_valid.sum() == 0:
            st.warning("All candidates were rejected; frustum plot omitted.")
        else:
            _info_popover(
                "candidate frusta",
                "Frusta visualize the candidate camera extrinsics with the "
                "selected camera intrinsics. Scale is a display-only factor "
                "and does not change rendering or scoring.",
            )
            opt_col1, opt_col2 = st.columns(2)
            with opt_col1:
                frustum_scale = st.slider(
                    "Frustum scale",
                    min_value=0.1,
                    max_value=1.0,
                    value=0.5,
                    step=0.05,
                    key="cand_frustum_scale",
                )
            with opt_col2:
                max_frustums = st.slider(
                    "Max frustums",
                    min_value=1,
                    max_value=24,
                    value=6,
                    step=1,
                    key="cand_max_frustums",
                )

            if sample is not None:
                frust_builder = (
                    CandidatePlotBuilder.from_candidates(
                        sample,
                        candidates,
                        title=_pretty_label(f"Candidate frusta ({cam_label})"),
                    )
                    .add_mesh()
                    .add_candidate_cloud(
                        use_valid=True,
                        color="royalblue",
                        size=3,
                        opacity=0.35,
                    )
                    .add_candidate_frusta(
                        scale=float(frustum_scale),
                        color="crimson",
                        name="Frustum",
                        max_frustums=int(max_frustums),
                        include_axes=False,
                        include_center=False,
                        display_rotate=False,
                    )
                )
                frust_fig = (
                    _add_target_context_overlay(frust_builder, candidates, target_world)
                    .add_reference_axes(display_rotate=True)
                    .finalize()
                )
                st.plotly_chart(frust_fig, width="stretch")
            else:
                st.warning("EFM snippet not attached; rendering frusta without mesh.")
                st.plotly_chart(
                    plot_candidate_frusta_simple(
                        candidates,
                        scale=float(frustum_scale),
                        max_frustums=int(max_frustums),
                    ),
                    width="stretch",
                )

    with st.expander("Distributions & Diagnostics", expanded=False):
        _info_popover(
            "candidate diagnostics",
            "Offsets and directions are expressed in the reference rig frame. "
            "These plots diagnose sampling coverage, symmetry, and any bias "
            "introduced by constraints or collision rules.",
        )
        fixed_ranges = st.checkbox(
            "Clamp axes to standard ranges",
            value=True,
            key="cand_angles_fixed_ranges",
        )
        diag_offsets, diag_dirs, diag_rules, diag_rejected = st.tabs(
            ["Offsets", "Directions", "Rules", "Rejected"],
        )

        with diag_offsets:
            _info_popover(
                "offsets",
                "Offsets are candidate translations relative to the reference pose. "
                "Polar plots show azimuth/elevation of the offset direction; the "
                "radius histogram shows the sampled distance distribution.",
            )
            show_view_dirs = st.checkbox(
                "Show view directions (rig frame)",
                value=False,
                key="cand_offsets_show_view_dirs",
            )
            st.markdown(
                stats_to_markdown_table(
                    summarise_offsets_ref(offsets_ref),
                    header=None,
                ),
            )
            offsets_np = offsets_ref.cpu().numpy()
            dirs_overlay = None
            if show_view_dirs:
                dirs_overlay = dirs_ref
                if dirs_shell_ref is not None and mask_valid.shape[0] == dirs_shell_ref.shape[0]:
                    dirs_overlay = dirs_shell_ref[mask_valid]
            dirs_overlay_np = dirs_overlay.cpu().numpy() if dirs_overlay is not None else None
            colp1, colp2 = st.columns(2)
            with colp1:
                st.plotly_chart(
                    plot_position_polar(
                        offsets_np,
                        title=_pretty_label("Offsets from reference pose (az/elev)"),
                        fixed_ranges=fixed_ranges,
                    ),
                    width="stretch",
                )
            with colp2:
                st.plotly_chart(
                    plot_position_sphere(
                        offsets_np,
                        show_axes=True,
                        dirs=dirs_overlay_np,
                    ),
                    width="stretch",
                )
            st.plotly_chart(plot_radius_hist(offsets_np), width="stretch")

        with diag_dirs:
            _info_popover(
                "directions",
                "View directions are unit forward vectors in the reference frame. "
                "Marginals expose angular coverage; sphere plots reveal anisotropy. "
                "Euler plots are shown in both world and reference frames to "
                "highlight frame-dependent interpretations.",
            )
            dirs_plot = dirs_shell_ref if dirs_shell_ref is not None else dirs_ref
            st.markdown(
                stats_to_markdown_table(summarise_dirs_ref(dirs_plot), header=None),
            )
            dirs_np = dirs_plot.cpu().numpy()

            col1, col2 = st.columns(2)
            with col1:
                st.plotly_chart(
                    plot_direction_polar(
                        dirs_np,
                        title=_pretty_label("View directions (reference frame)"),
                        fixed_ranges=fixed_ranges,
                    ),
                    width="stretch",
                )
            with col2:
                st.plotly_chart(
                    plot_direction_sphere(
                        dirs_np,
                        title=_pretty_label("View dirs on unit sphere"),
                        show_axes=True,
                    ),
                    width="stretch",
                )
            st.plotly_chart(
                plot_direction_marginals(
                    torch.as_tensor(dirs_np),
                    fixed_ranges=fixed_ranges,
                ),
                width="stretch",
            )

            r_wr = candidates.reference_pose.R
            if r_wr.ndim == 3:
                r_wr = r_wr[0]
            fwd_w = r_wr[:, 2].view(1, 3)
            up_w = r_wr[:, 1].view(1, 3)
            wup = world_up_tensor(device=fwd_w.device, dtype=fwd_w.dtype).view(1, 3)
            left0 = torch.cross(wup, fwd_w, dim=-1)
            left0_norm = left0.norm(dim=-1, keepdim=True)
            if float(left0_norm.item()) < 1e-6:
                alt = torch.tensor(
                    [1.0, 0.0, 0.0],
                    device=fwd_w.device,
                    dtype=fwd_w.dtype,
                ).view(1, 3)
                left0 = torch.cross(alt, fwd_w, dim=-1)
                left0_norm = left0.norm(dim=-1, keepdim=True)
                if float(left0_norm.item()) < 1e-6:
                    alt2 = torch.tensor(
                        [0.0, 1.0, 0.0],
                        device=fwd_w.device,
                        dtype=fwd_w.dtype,
                    ).view(1, 3)
                    left0 = torch.cross(alt2, fwd_w, dim=-1)
                    left0_norm = left0.norm(dim=-1, keepdim=True)
            left0 = left0 / left0_norm.clamp_min(1e-6)
            up0 = torch.cross(fwd_w, left0, dim=-1)
            sin_roll = (fwd_w * torch.cross(up0, up_w, dim=-1)).sum(dim=-1)
            cos_roll = (up0 * up_w).sum(dim=-1)
            roll = torch.rad2deg(torch.atan2(sin_roll, cos_roll)).item()
            yaw = torch.rad2deg(torch.atan2(fwd_w[:, 0], fwd_w[:, 1])).item()
            pitch = torch.rad2deg(torch.asin(fwd_w[:, 2].clamp(-1.0, 1.0))).item()
            st.markdown(
                f"Reference pose view angles (world): yaw={yaw:.2f}°, pitch={pitch:.2f}°, roll={roll:.2f}°",
            )
            st.plotly_chart(
                plot_euler_world(candidates, fixed_ranges=fixed_ranges),
                width="stretch",
            )
            st.plotly_chart(
                plot_euler_reference(candidates, fixed_ranges=fixed_ranges),
                width="stretch",
            )
            delta = candidates.extras.get("view_dirs_delta") if hasattr(candidates, "extras") else None
            if delta is not None:
                r_delta = delta.R
                fwd = r_delta[:, :, 2]
                yaw_d = torch.rad2deg(torch.atan2(fwd[:, 0], fwd[:, 2])).cpu()
                pitch_d = torch.rad2deg(torch.asin(fwd[:, 1].clamp(-1.0, 1.0))).cpu()
                roll_d = torch.rad2deg(
                    torch.atan2(r_delta[:, 1, 0], r_delta[:, 1, 1]),
                ).cpu()
                st.markdown(
                    stats_to_markdown_table(
                        {
                            "yaw_delta_deg": {
                                "min": float(yaw_d.min()),
                                "max": float(yaw_d.max()),
                                "mean": float(yaw_d.mean()),
                                "std": float(yaw_d.std(unbiased=False)),
                            },
                            "pitch_delta_deg": {
                                "min": float(pitch_d.min()),
                                "max": float(pitch_d.max()),
                                "mean": float(pitch_d.mean()),
                                "std": float(pitch_d.std(unbiased=False)),
                            },
                            "roll_delta_deg": {
                                "min": float(roll_d.min()),
                                "max": float(roll_d.max()),
                                "mean": float(roll_d.mean()),
                                "std": float(roll_d.std(unbiased=False)),
                            },
                        },
                        header="Orientation jitter stats (delta, LUF yaw/pitch/roll)",
                    ),
                )
                st.plotly_chart(
                    _euler_histogram(
                        yaw_d,
                        pitch_d,
                        roll_d,
                        bins=90,
                        title=_pretty_label("Orientation jitter (delta, deg)"),
                        fixed_ranges=fixed_ranges,
                    ),
                    width="stretch",
                )

        with diag_rules:
            _info_popover(
                "rules",
                "Rule masks mark which candidates were rejected by each constraint "
                "(collision, distance-to-mesh, visibility, etc.). The bar plot "
                "summarizes rejection counts per rule to reveal dominant filters.",
            )
            masks = candidates.masks
            if sample is not None and isinstance(masks, dict) and len(masks) > 0 and shell_poses is not None:
                masks_tensor = torch.stack(list(masks.values()))
                mask_fig = plot_rule_masks(
                    snippet=sample,
                    shell_poses=_pose_tensor(shell_poses),
                    masks=masks_tensor,
                    rule_names=list(masks.keys()),
                )
                st.plotly_chart(mask_fig, width="stretch")
            elif not has_snippet:
                st.info("Attach an EFM snippet to visualize rule masks in 3D.")

            extras = candidates.extras if hasattr(candidates, "extras") else {}
            dist_min = extras.get("min_distance_to_mesh")
            path_collide = extras.get("path_collision_mask")

            if sample is not None and dist_min is not None:
                st.plotly_chart(
                    cast(
                        go.Figure,
                        plot_min_distance_to_mesh(
                            snippet=sample,
                            candidates=candidates,
                            distances=dist_min,
                        ),
                    ),
                    width="stretch",
                )
            if sample is not None and path_collide is not None:
                st.plotly_chart(
                    cast(
                        go.Figure,
                        plot_path_collision_segments(
                            snippet=sample,
                            candidates=candidates,
                            collision_mask=path_collide,
                        ),
                    ),
                    width="stretch",
                )

            st.plotly_chart(plot_rule_rejection_bar(candidates), width="stretch")
            threshold_rows = _motion_threshold_rows(candidates, cand_cfg)
            if threshold_rows:
                st.markdown("**Motion and clearance thresholds**")
                st.dataframe(threshold_rows, width="stretch", hide_index=True)

        with diag_rejected:
            _info_popover(
                "rejected",
                "Rejected poses are candidates that failed at least one rule. "
                "Plotting them can reveal systematic failures (e.g., walls, "
                "occlusions, or sampling bias).",
            )
            plot_rejected_only = st.checkbox(
                "Plot rejected poses only (if any)",
                value=False,
                key="cand_plot_rejected_only",
            )
            if plot_rejected_only:
                rejected_poses = rejected_pose_tensor(candidates)
                if rejected_poses is None:
                    st.info(
                        "No rejected poses to plot; all sampled candidates survived rule filtering.",
                    )
                elif sample is not None:
                    rej_fig = (
                        CandidatePlotBuilder.from_candidates(
                            sample,
                            candidates,
                            title=_pretty_label(
                                f"Rejected candidate positions ({rejected_poses.shape[0]})",
                            ),
                        )
                        .add_mesh()
                        .add_rejected_cloud()
                        .add_reference_axes()
                    ).finalize()
                    st.plotly_chart(rej_fig, width="stretch")
                else:
                    st.info("Attach an EFM snippet to render rejected poses in 3D.")


def render_candidates_page(
    sample: EfmSnippetView | None,
    candidates: CandidateSamplingResult,
    cand_cfg: CandidateViewGeneratorConfig | None,
    *,
    source_caption: str | None = None,
    source_note: str | None = None,
) -> None:
    """Render the candidate shell and its actor-action diagnostics.

    Args:
        sample: Optional EFM snippet used for observed-scene context and explicit
            oracle mesh overlays.
        candidates: Finite candidate shell, validity masks, and provenance.
        cand_cfg: Optional generator config used to display rule thresholds.
        source_caption: Optional short source label shown above the panel.
        source_note: Optional longer provenance note shown with the source.
    """

    _render_live_candidates_page(
        sample,
        candidates,
        cand_cfg,
        source_caption=source_caption,
        source_note=source_note,
    )


__all__ = ["render_candidates_page"]
