"""VIN frustum-token and semidense-projection diagnostics.

The tab provides per-candidate token validity, depth-plane features, observed
semidense projection grids, and optional CNN activations derived from
actor-visible evidence.
"""

from __future__ import annotations

import streamlit as st
import torch

from ....utils.plotting import _histogram_overlay, _plot_slice_grid, _to_numpy
from ....vin.diagnostics import build_frustum_samples_figure
from ....vin.diagnostics.plotting import (
    build_semidense_cnn_grid_figure,
    build_semidense_projection_feature_figure,
    build_semidense_projection_figure,
)
from ..common import _info_popover, _pretty_label
from .context import VinDiagContext

SEMIDENSE_PROJ_FEATURES_INFO = (
    "Counts: number of projected semidense points per grid cell. "
    "Weights: reliability-weighted counts using obs_count and inv_dist_std (1/σ_d). "
    "Depth_mean: weighted mean depth (z) of valid projections per cell. "
    "Depth_std: weighted depth standard deviation per cell (depth spread)."
)


def render_tokens_tab(ctx: VinDiagContext) -> None:
    """Render the Frustum Tokens tab.

    Args:
        ctx: Shared VIN diagnostics context.
    """
    debug = ctx.debug
    batch = ctx.batch
    cfg = ctx.cfg

    has_semidense_proj = getattr(debug, "semidense_proj", None) is not None
    has_semidense_cnn = getattr(cfg.module_config.vin, "semidense_cnn_enabled", False)
    if not ctx.has_tokens and not ctx.has_semidense_frustum and not has_semidense_proj:
        st.info("No token/projection diagnostics available for this VIN variant.")
        return

    batch_size = 1
    try:
        pose_enc = getattr(debug, "pose_enc", None)
        if torch.is_tensor(pose_enc) and pose_enc.ndim >= 2:
            batch_size = int(pose_enc.shape[0])
    except Exception:  # pragma: no cover - UI guard
        batch_size = 1
    batch_idx = 0
    if batch_size > 1:
        batch_idx = int(
            st.slider(
                "Batch index",
                0,
                max(0, batch_size - 1),
                0,
                key="vin_token_batch_idx",
            )
        )

    cand_idx = st.slider(
        "Candidate index",
        0,
        max(0, ctx.num_candidates - 1),
        0,
        key="vin_token_cand_idx",
    )

    if ctx.has_tokens:
        _info_popover(
            "frustum tokens",
            "VIN v1 samples the scene field along a frustum grid of size "
            "grid_size x grid_size x num_depths. Token norms show feature "
            "strength per sample; token_valid marks whether a sample lies "
            "inside the voxel field.",
        )
        grid_size = int(cfg.module_config.vin.frustum_grid_size)
        depth_values = list(cfg.module_config.vin.frustum_depths_m)
        num_depths = len(depth_values)

        max_depths = st.slider(
            "Max depth planes",
            1,
            max(1, num_depths),
            min(4, num_depths),
            key="vin_token_depths",
        )

        tokens = debug.tokens[batch_idx, cand_idx]
        token_valid = debug.token_valid[batch_idx, cand_idx]
        token_norm = torch.linalg.vector_norm(tokens, dim=-1)

        expected_k = grid_size * grid_size * num_depths
        if int(token_norm.numel()) != expected_k:
            st.warning(
                "Token count does not match grid_size² x num_depths; skipping grid view.",
            )
        else:
            token_norm = token_norm.view(num_depths, grid_size, grid_size)
            token_valid = token_valid.view(num_depths, grid_size, grid_size).float()

            depth_labels = [f"d={d:g}m" for d in depth_values[:max_depths]]
            norm_slices = [_to_numpy(token_norm[i]) for i in range(max_depths)]
            valid_slices = [_to_numpy(token_valid[i]) for i in range(max_depths)]

            fig_norm = _plot_slice_grid(
                norm_slices,
                titles=depth_labels,
                title=_pretty_label("Token feature norm per depth plane"),
                percentile=99.0,
                symmetric=False,
                cmap_name="viridis",
            )
            st.plotly_chart(fig_norm, width="stretch")

            fig_valid = _plot_slice_grid(
                valid_slices,
                titles=depth_labels,
                title=_pretty_label("Token validity per depth plane"),
                percentile=100.0,
                symmetric=False,
                cmap_name="gray",
            )
            st.plotly_chart(fig_valid, width="stretch")

        st.subheader("Frustum samples in world")
        st.plotly_chart(
            build_frustum_samples_figure(
                debug,
                p3d_cameras=batch.p3d_cameras,
                candidate_index=int(batch_idx * ctx.num_candidates + int(cand_idx)),
                grid_size=int(grid_size),
                depths_m=depth_values,
            ),
            width="stretch",
        )

    if ctx.has_semidense_frustum and batch.efm_snippet_view is not None:
        st.subheader("Semidense projection (candidate visibility)")
        try:
            semidense = batch.efm_snippet_view.semidense
        except Exception:  # pragma: no cover - UI guard
            semidense = None
        if semidense is None:
            st.info("Semidense points unavailable for this snippet.")
        else:
            points_world = semidense.collapse_points(
                max_points=int(cfg.module_config.vin.semidense_proj_max_points),
                include_inv_dist_std=True,
            )
            if points_world.numel() == 0:
                st.info("Semidense points are empty for this snippet.")
            else:
                st.plotly_chart(
                    build_semidense_projection_figure(
                        points_world,
                        p3d_cameras=batch.p3d_cameras,
                        candidate_index=int(batch_idx * ctx.num_candidates + int(cand_idx)),
                        show_frustum=True,
                    ),
                    width="stretch",
                )
    elif ctx.has_semidense_frustum:
        st.info("Attach the EFM snippet to visualize semidense frustum projections.")

    if has_semidense_proj:
        st.subheader(_pretty_label("VIN v3 projection scalars"))
        semidense_proj = getattr(debug, "semidense_proj", None)
        voxel_proj = getattr(debug, "voxel_proj", None)

        def _named_features(values: torch.Tensor | None) -> dict[str, float] | None:
            if not torch.is_tensor(values):
                return None
            vec = values
            if vec.ndim == 3:
                vec = vec[batch_idx, cand_idx]
            vec = vec.detach().reshape(-1)
            names = [f"f{i}" for i in range(int(vec.numel()))]
            if int(vec.numel()) == 5:
                names = [
                    "coverage",
                    "empty_frac",
                    "semidense_candidate_vis_frac",
                    "depth_mean",
                    "depth_std",
                ]
            return {name: float(vec[i].item()) for i, name in enumerate(names)}

        col_a, col_b = st.columns(2)
        with col_a:
            _info_popover(
                "semidense_proj scalars",
                "Scalar features used by VIN v3 from semidense point projections. "
                "These are concatenated into the scorer head.",
            )
            sem_features = _named_features(semidense_proj)
            if sem_features is None:
                st.info("semidense_proj unavailable.")
            else:
                st.json(sem_features)
        with col_b:
            _info_popover(
                "voxel_proj scalars",
                "Scalar features from projecting pooled voxel centers into the candidate view. "
                "VIN v3 uses these for a light FiLM modulation of the global feature.",
            )
            vox_features = _named_features(voxel_proj)
            if vox_features is None:
                st.info("voxel_proj unavailable.")
            else:
                st.json(vox_features)

        grid_feat = getattr(debug, "semidense_grid_feat", None)
        if torch.is_tensor(grid_feat):
            _info_popover(
                "semidense_grid_feat",
                "Feature vector produced by the tiny CNN over the semidense projection grid. "
                "A collapsed norm distribution can indicate a dead CNN branch.",
            )
            norms = torch.linalg.vector_norm(grid_feat[batch_idx], dim=-1).reshape(-1)
            fig = _histogram_overlay(
                [("||semidense_grid_feat||", _to_numpy(norms))],
                bins=60,
                title=_pretty_label("Semidense CNN feature norms"),
                xaxis_title=_pretty_label("norm"),
                log1p_counts=False,
            )
            st.plotly_chart(fig, width="stretch")

        st.subheader("Semidense projection feature maps (v3)")
        _info_popover("semidense projection features", SEMIDENSE_PROJ_FEATURES_INFO)
        num_candidates = ctx.num_candidates
        if torch.is_tensor(semidense_proj) and semidense_proj.ndim >= 2:
            num_candidates = int(semidense_proj.shape[1])
        multi_candidates = st.checkbox(
            "Plot multiple candidates",
            value=False,
            key="vin_semidense_multi",
        )
        candidate_count = 1
        if multi_candidates:
            candidate_count = int(
                st.number_input(
                    "# candidates",
                    min_value=1,
                    max_value=max(1, num_candidates),
                    value=min(4, max(1, num_candidates)),
                    step=1,
                    key="vin_semidense_multi_count",
                )
            )
        candidate_count = max(1, min(candidate_count, num_candidates))

        snippet_view = batch.efm_snippet_view
        if snippet_view is None:
            st.info("Semidense projection maps require a VIN or EFM snippet.")
            return

        points_world = None
        if hasattr(snippet_view, "points_world"):
            points_world = snippet_view.points_world
            if torch.is_tensor(points_world) and points_world.ndim == 3:
                if batch_idx < points_world.shape[0]:
                    points_world = points_world[batch_idx]
            if hasattr(snippet_view, "lengths") and torch.is_tensor(snippet_view.lengths):
                length_idx = min(batch_idx, int(snippet_view.lengths.numel()) - 1)
                length = int(snippet_view.lengths[length_idx].item()) if snippet_view.lengths.numel() > 0 else None
                if length is not None and torch.is_tensor(points_world) and points_world.ndim == 2:
                    points_world = points_world[:length]
        else:
            try:
                semidense = snippet_view.semidense  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - UI guard
                semidense = None
            if semidense is not None:
                points_world = semidense.collapse_points(
                    max_points=int(cfg.module_config.vin.semidense_proj_max_points),
                    include_inv_dist_std=True,
                    include_obs_count=True,
                )

        if points_world is None or not torch.is_tensor(points_world) or points_world.numel() == 0:
            st.info("Semidense points are empty for this snippet.")
        else:
            start_idx = int(cand_idx)
            cand_indices = [(start_idx + offset) % num_candidates for offset in range(candidate_count)]
            for idx in cand_indices:
                cam_index = int(batch_idx * num_candidates + int(idx))
                fig = build_semidense_projection_feature_figure(
                    points_world,
                    p3d_cameras=batch.p3d_cameras,
                    candidate_index=cam_index,
                    grid_size=int(cfg.module_config.vin.semidense_proj_grid_size),
                    max_points=int(cfg.module_config.vin.semidense_proj_max_points),
                    semidense_obs_count_max=float(cfg.module_config.vin.semidense_obs_count_max),
                    semidense_inv_dist_std_min=float(cfg.module_config.vin.semidense_inv_dist_std_min),
                    semidense_inv_dist_std_p95=float(cfg.module_config.vin.semidense_inv_dist_std_p95),
                )
                label = f"Candidate {idx}"
                if batch_idx > 0:
                    label = f"Batch {batch_idx} · Candidate {idx}"
                st.markdown(f"**{label}**")
                if fig.data:
                    st.plotly_chart(fig, width="stretch")
                else:
                    st.info("No valid semidense projections for this candidate.")

                if has_semidense_cnn:
                    fig_cnn = build_semidense_cnn_grid_figure(
                        points_world,
                        p3d_cameras=batch.p3d_cameras,
                        candidate_index=cam_index,
                        grid_size=int(cfg.module_config.vin.semidense_proj_grid_size),
                        max_points=int(cfg.module_config.vin.semidense_proj_max_points),
                    )
                    if fig_cnn.data:
                        st.plotly_chart(fig_cnn, width="stretch")


__all__ = ["render_tokens_tab"]
