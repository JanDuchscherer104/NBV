"""Top-level VIN batch, prediction, model, and cache summary diagnostics.

The tab provides data-lineage and parameter summaries plus prediction-versus-
oracle comparisons while keeping RRI labels separate from actor-visible model
inputs and outputs.
"""

from __future__ import annotations

import numpy as np
import plotly.express as px
import streamlit as st
import torch

from ....data_handling import VinSnippetView
from ....data_handling.vin_store.diagnostics import collect_vin_offline_dataset_stats
from ....data_handling.vin_store.source import VinOfflineSourceConfig
from ....utils.plotting import _histogram_overlay, _to_numpy
from ....vin.diagnostics.plotting import _parameter_distribution
from ...scientific_labels import format_scientific_label, scientific_label
from ...state import get_label_display_mode
from ..common import _info_popover, _offline_summary_rows, _pretty_label, _strip_ansi, render_scientific_notation
from .context import VinDiagContext


def _rri_label() -> str:
    return format_scientific_label(
        scientific_label("rri"),
        mode=get_label_display_mode(),
        surface="plain",
    )


def render_summary_tab(ctx: VinDiagContext) -> None:
    """Render the Summary tab for VIN diagnostics.

    Args:
        ctx: Shared VIN diagnostics context.
    """
    state = ctx.state
    debug = ctx.debug
    pred = ctx.pred
    batch = ctx.batch
    cfg = ctx.cfg

    cache_label = "online oracle labeler"
    if ctx.use_offline_cache:
        cache_label = "VIN offline store"
        if isinstance(batch.efm_snippet_view, VinSnippetView):
            cache_label = "VIN offline store (minimal snippet)"
        if batch.efm_snippet_view is None:
            cache_label = f"{cache_label} (snippet detached)"
    st.caption(f"Data source: {cache_label}")

    source = ctx.cfg.datamodule_config.source
    if ctx.use_offline_cache and isinstance(source, VinOfflineSourceConfig):
        with st.expander("VIN offline store diagnostics", expanded=False):
            sample_limit = int(
                st.number_input(
                    "Diagnostic sample limit",
                    min_value=1,
                    max_value=10000,
                    value=512,
                    step=128,
                    key="vin_offline_stats_sample_limit",
                )
            )
            try:
                stats = collect_vin_offline_dataset_stats(source.offline.store, max_samples=sample_limit)
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("Samples", stats.num_samples)
                col_b.metric("Scenes", stats.num_scenes)
                col_c.metric("Snippets", stats.num_snippets)
                col_d.metric("Numeric blocks", f"{stats.numeric_bytes / (1024**2):.1f} MiB")
                st.dataframe(
                    _offline_summary_rows(stats),
                    width="stretch",
                    hide_index=True,
                )
                st.json(
                    {
                        "store_dir": stats.store_dir,
                        "version": stats.version,
                        "sampled_samples": stats.sampled_samples,
                        "split_counts": stats.split_counts,
                        "materialized_blocks": stats.materialized_blocks,
                    },
                    expanded=False,
                )
            except Exception as exc:  # pragma: no cover - diagnostics guard
                st.warning(f"Could not inspect VIN offline store: {type(exc).__name__}: {exc}")

    if batch.rri is not None:
        render_scientific_notation("rri")
        _info_popover(
            "scatter",
            "Each point is a candidate view. **X** is the oracle RRI computed from "
            "mesh distances (before vs after adding the candidate point cloud). "
            "**Y** is the VIN expected score from the CORAL ordinal head "
            "(mean of `P(y>k)` across bins, normalized to `[0,1]`). "
            "VIN v2/v3 use pose features from `[t, r6d]` in the reference rig "
            "frame plus global voxel context; VIN v3 additionally concatenates "
            "semidense/voxel projection statistics. VIN v1 may also use local "
            "frustum tokens.",
        )
        rri = _to_numpy(batch.rri.reshape(-1))
        expected = _to_numpy(pred.expected_normalized.reshape(-1))
        use_log_axes = st.checkbox(
            "Log scale axes",
            value=False,
            key="vin_summary_log_axes",
        )
        if use_log_axes:
            pos_mask = (rri > 0) & (expected > 0)
            if not np.all(pos_mask):
                st.info(
                    "Log axes require positive values; non-positive points are omitted.",
                )
                rri = rri[pos_mask]
                expected = expected[pos_mask]
        fig = px.scatter(
            x=rri,
            y=expected,
            labels={
                "x": f"Oracle {_rri_label()}",
                "y": _pretty_label("VIN expected (normalized)"),
            },
            title=_pretty_label("Predicted score vs oracle RRI"),
            log_x=use_log_axes,
            log_y=use_log_axes,
        )
        st.plotly_chart(fig, width="stretch")

    with st.expander("Candidate leaderboard + proxy correlations", expanded=False):
        expected = pred.expected_normalized.reshape(-1)
        candidate_valid = pred.candidate_valid.reshape(-1).to(dtype=torch.bool)
        voxel_valid = pred.voxel_valid_frac.reshape(-1) if pred.voxel_valid_frac is not None else None
        sem_vis = (
            pred.semidense_candidate_vis_frac.reshape(-1) if pred.semidense_candidate_vis_frac is not None else None
        )
        radius_m = torch.linalg.vector_norm(debug.candidate_center_rig_m, dim=-1).reshape(-1)

        vin_model_local = state.module.vin if state.module is not None else None
        expected_rri = None
        if vin_model_local is not None and getattr(vin_model_local, "head_coral", None) is not None:
            head_coral = vin_model_local.head_coral
            if getattr(head_coral, "has_bin_values", False):
                try:
                    expected_rri = head_coral.expected_from_probs(pred.prob).reshape(-1)
                except Exception:  # pragma: no cover - diagnostics only
                    expected_rri = None

        total = int(expected.numel())
        k_default = min(12, total) if total else 1
        k = int(
            st.number_input(
                "Top-k candidates",
                min_value=1,
                max_value=max(1, min(128, total)),
                value=k_default,
                step=1,
                key="vin_summary_topk",
            )
        )
        only_valid = st.checkbox(
            "Only valid candidates",
            value=False,
            key="vin_summary_only_valid",
        )
        mask = torch.isfinite(expected)
        if only_valid:
            mask = mask & candidate_valid

        masked_idx = torch.where(mask)[0]
        if masked_idx.numel() == 0:
            st.info("No candidates available for leaderboard (mask filtered everything).")
        else:
            scores = expected[masked_idx]
            k_eff = int(min(k, int(scores.numel())))
            top_local = torch.topk(scores, k=k_eff, largest=True).indices
            top_idx = masked_idx[top_local]
            rows: list[dict[str, object]] = []
            for flat_idx in top_idx.tolist():
                row: dict[str, object] = {
                    "flat_idx": int(flat_idx),
                    "expected_norm": float(expected[flat_idx].item()),
                    "radius_m": float(radius_m[flat_idx].item()),
                    "candidate_valid": bool(candidate_valid[flat_idx].item()),
                }
                if voxel_valid is not None:
                    row["voxel_valid_frac"] = float(voxel_valid[flat_idx].item())
                if sem_vis is not None:
                    row["semidense_vis_frac"] = float(sem_vis[flat_idx].item())
                if expected_rri is not None:
                    row["expected_rri"] = float(expected_rri[flat_idx].item())
                if batch.rri is not None:
                    try:
                        row["oracle_rri"] = float(batch.rri.reshape(-1)[flat_idx].item())
                    except Exception:  # pragma: no cover - guard
                        pass
                rows.append(row)
            st.dataframe(rows, width="stretch", hide_index=True)

        def _corr(x: torch.Tensor, y: torch.Tensor) -> float | None:
            x_np = _to_numpy(x.reshape(-1))
            y_np = _to_numpy(y.reshape(-1))
            finite = np.isfinite(x_np) & np.isfinite(y_np)
            if finite.sum() < 3:
                return None
            xv = x_np[finite]
            yv = y_np[finite]
            denom = np.std(xv) * np.std(yv)
            if denom < 1e-12:
                return None
            return float(np.mean((xv - xv.mean()) * (yv - yv.mean())) / denom)

        _info_popover(
            "proxy correlations",
            "Quick sanity checks: if expected score correlates almost perfectly with a proxy "
            "(e.g., semidense visibility), the model might be ignoring other cues.",
        )
        corr_rows: list[dict[str, object]] = []
        for name, values in (
            ("radius_m", radius_m),
            ("voxel_valid_frac", voxel_valid),
            ("semidense_candidate_vis_frac", sem_vis),
        ):
            if values is None:
                continue
            corr = _corr(values, expected)
            corr_rows.append({"feature": name, "pearson": corr})
        if corr_rows:
            st.dataframe(corr_rows, width="stretch", hide_index=True)

        semidense_proj = getattr(debug, "semidense_proj", None)
        voxel_proj = getattr(debug, "voxel_proj", None)
        for label, values in (("semidense_proj", semidense_proj), ("voxel_proj", voxel_proj)):
            if not torch.is_tensor(values) or values.ndim != 3:
                continue
            vec = values.reshape(-1, values.shape[-1])
            if int(vec.shape[-1]) != 5:
                continue
            names = [
                "coverage",
                "empty_frac",
                "semidense_candidate_vis_frac",
                "depth_mean",
                "depth_std",
            ]
            corr_vals: list[dict[str, object]] = []
            for idx, name in enumerate(names):
                corr = _corr(vec[:, idx], expected)
                corr_vals.append({"feature": f"{label}.{name}", "pearson": corr})
            fig_corr = px.bar(
                corr_vals,
                x="feature",
                y="pearson",
                title=_pretty_label(f"{label} feature correlations vs expected"),
                labels={"pearson": _pretty_label("pearson")},
            )
            st.plotly_chart(fig_corr, width="stretch")

        if voxel_valid is not None:
            fig = px.scatter(
                x=_to_numpy(voxel_valid),
                y=_to_numpy(expected),
                labels={"x": _pretty_label("voxel_valid_frac"), "y": _pretty_label("expected (normalized)")},
                title=_pretty_label("Expected vs voxel_valid_frac"),
            )
            st.plotly_chart(fig, width="stretch")
        if sem_vis is not None:
            fig = px.scatter(
                x=_to_numpy(sem_vis),
                y=_to_numpy(expected),
                labels={
                    "x": _pretty_label("semidense_candidate_vis_frac"),
                    "y": _pretty_label("expected (normalized)"),
                },
                title=_pretty_label("Expected vs semidense_candidate_vis_frac"),
            )
            st.plotly_chart(fig, width="stretch")

    feature_dims: list[tuple[str, int]] = []
    if hasattr(debug, "pose_enc"):
        feature_dims.append(("pose_enc", int(debug.pose_enc.shape[-1])))
    if getattr(debug, "global_feat", None) is not None:
        feature_dims.append(("global_feat", int(debug.global_feat.shape[-1])))
    if hasattr(debug, "local_feat"):
        feature_dims.append(("local_feat", int(debug.local_feat.shape[-1])))
    if feature_dims:
        _info_popover(
            "feature dims",
            "Feature blocks concatenated before the scorer MLP. "
            "VIN v2/v3 use `pose_enc` (LFF over translation + rotation-6D "
            "with learned scales) and `global_feat` (pose-conditioned "
            "attention pooling over the voxel field). VIN v3 may also append "
            "projection stats (see Tokens tab). VIN v1 can add `local_feat` "
            "from frustum sampling.",
        )
        dims_df = {
            "modality": [name for name, _ in feature_dims],
            "num_features": [count for _, count in feature_dims],
        }
        fig_dims = px.bar(
            dims_df,
            x="modality",
            y="num_features",
            title=_pretty_label("Feature dimensions by modality"),
        )
        st.plotly_chart(fig_dims, width="stretch")

    vin_model = state.module.vin if state.module is not None else None
    if vin_model is not None:
        params_df = _parameter_distribution(vin_model, trainable_only=True)
        if not params_df.empty:
            _info_popover(
                "param counts",
                "Trainable parameter counts grouped by top-level VIN submodule "
                "(frozen backbone params are excluded). This highlights where "
                "capacity is concentrated (pose encoder vs global pool vs head).",
            )
            fig_params = px.bar(
                params_df,
                x="module",
                y="num_params",
                title=_pretty_label("Trainable parameter counts by VIN module"),
                labels={"num_params": _pretty_label("parameters")},
            )
            st.plotly_chart(fig_params, width="stretch")
            total_params = int(params_df["num_params"].sum())
            st.caption(f"Total trainable parameters: {total_params:,}")

    field_in = getattr(debug, "field_in", None)
    if isinstance(field_in, torch.Tensor) and field_in.ndim == 5:
        _info_popover(
            "field hists",
            "Per-channel scene-field distributions **before** projection. "
            "VIN builds channels from EVL heads: `occ_pr` (occupancy prob), "
            "`cent_pr` (centerness), `occ_input` (occupied evidence), "
            "`counts_norm` (log1p-normalized coverage), `observed`=counts_norm, "
            "`unknown`=1-counts_norm, `free_input` (EVL free-space or derived), "
            "`new_surface_prior`=unknown*occ_pr. Values are mostly in `[0,1]` "
            "and plotted as |value|.",
        )
        channel_count = int(field_in.shape[1])
        configured_channels = list(getattr(cfg.module_config.vin, "scene_field_channels", ()))
        if channel_count == len(configured_channels):
            channel_names = configured_channels
        else:
            channel_names = [f"ch_{idx}" for idx in range(channel_count)]
        default_channels = channel_names[: min(len(channel_names), 6)]
        selected_channels = st.multiselect(
            "Scene field channels",
            options=channel_names,
            default=default_channels,
            key="vin_summary_field_hist_channels",
        )
        log1p_counts = st.checkbox(
            "Log1p histogram counts",
            value=False,
            key="vin_summary_field_hist_log1p",
        )
        hist_bins = int(
            st.slider(
                "Histogram bins",
                min_value=10,
                max_value=200,
                value=60,
                key="vin_summary_field_hist_bins",
            ),
        )
        channel_vals = field_in.abs().detach().cpu()
        series: list[tuple[str, np.ndarray]] = []
        for idx, name in enumerate(channel_names):
            if name not in selected_channels:
                continue
            vals = channel_vals[:, idx, ...].reshape(-1).numpy()
            series.append((name, vals))
        fig_hist = _histogram_overlay(
            series,
            bins=hist_bins,
            title=_pretty_label("Scene field channel |value| distributions"),
            xaxis_title=_pretty_label("|value|"),
            log1p_counts=log1p_counts,
        )
        st.plotly_chart(fig_hist, width="stretch")

    _info_popover(
        "feature norms",
        "Per-candidate L2 norms of feature blocks (pose/global/local). "
        "Very low norms suggest weak signal; very high norms can dominate the "
        "MLP. Compare modalities to spot imbalance or saturation.",
    )
    feat_norms: dict[str, torch.Tensor] = {
        "pose_enc": torch.linalg.vector_norm(debug.pose_enc, dim=-1).reshape(-1),
        "feats": torch.linalg.vector_norm(debug.feats, dim=-1).reshape(-1),
    }
    if hasattr(debug, "local_feat"):
        feat_norms["local_feat"] = torch.linalg.vector_norm(
            debug.local_feat,
            dim=-1,
        ).reshape(-1)
    if getattr(debug, "global_feat", None) is not None:
        feat_norms["global_feat"] = torch.linalg.vector_norm(
            debug.global_feat,
            dim=-1,
        ).reshape(-1)

    log1p_norm_counts = st.checkbox(
        "Log1p feature histogram counts",
        value=False,
        key="vin_summary_feat_norm_log1p",
    )
    log_norm_x = st.checkbox(
        "Log x-axis (norm)",
        value=False,
        key="vin_summary_feat_norm_logx",
    )
    norm_bins = int(st.session_state.get("vin_summary_field_hist_bins", 60))
    norm_series = [(name, _to_numpy(vals)) for name, vals in feat_norms.items()]
    fig = _histogram_overlay(
        norm_series,
        bins=norm_bins,
        title=_pretty_label("Feature norms (per-candidate)"),
        xaxis_title=_pretty_label("norm"),
        log1p_counts=log1p_norm_counts,
        log_x=log_norm_x,
    )
    st.plotly_chart(fig, width="stretch")

    with st.expander("VIN summarize_vin output"):
        include_torchsummary = st.checkbox(
            "Include torchsummary modules",
            value=False,
            key="vin_summary_include_ts",
        )
        torchsummary_depth = int(
            st.slider(
                "Torchsummary depth",
                min_value=1,
                max_value=6,
                value=3,
                key="vin_summary_depth",
            ),
        )
        summary_key = f"{state.cfg_sig}|{batch.scene_id}|{batch.snippet_id}|{include_torchsummary}|{torchsummary_depth}"
        if state.summary_key != summary_key:
            state.summary_key = summary_key
            state.summary_text = None
            state.summary_error = None

        auto_run = state.summary_text is None and state.summary_error is None
        if st.button("Generate summary", key="vin_summary_generate") or auto_run:
            try:
                with st.spinner("Generating VIN summary..."):
                    state.summary_text = state.module.summarize_vin(
                        batch,
                        include_torchsummary=include_torchsummary,
                        torchsummary_depth=torchsummary_depth,
                    )
                state.summary_error = None
            except Exception as exc:  # pragma: no cover - UI guard
                state.summary_error = f"{type(exc).__name__}: {exc}"
                state.summary_text = None

        if state.summary_error:
            st.error(state.summary_error)
        elif state.summary_text:
            st.code(_strip_ansi(state.summary_text))
        else:
            st.info("Click 'Generate summary' to render summarize_vin output.")


__all__ = ["render_summary_tab"]
