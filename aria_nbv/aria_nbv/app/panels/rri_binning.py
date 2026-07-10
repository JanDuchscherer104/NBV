"""RRI binning diagnostics panel."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import torch

from ...configs import PathConfig
from ...data_handling import VinOfflineDatasetConfig, VinOfflineStoreConfig
from ...rri_metrics.ordinal import RriOrdinalBinner
from ...rri_metrics.plotting import _histogram_overlay
from .common import _info_popover, _pretty_label, _report_exception


def render_rri_binning_page() -> None:
    """Render RRI binning diagnostics from saved fit data."""
    st.header("RRI Binning")
    st.caption(
        "Inspect the RRI distribution and quantile edges used for CORAL binning, "
        "loaded directly from saved binner artifacts.",
    )
    _info_popover(
        "rri binning",
        "The binner is fit on cached oracle RRIs stored in "
        "`rri_binner_fit_data.pt` (raw RRI samples) and "
        "`rri_binner.json` (quantile edges + optional per-bin stats). "
        "When created via `nbv-fit-binner`, the fit data is collected from the training dataloader. "
        "This view uses only those artifacts—no dataset reloading—to verify "
        "binning quality and the empirical bin means/stds used for expected-value "
        "computations."
        "\nTo refit the binner on updated data, run "
        "`uv run nbv-fit-binner [--config-path .configs/offline_only.toml]`.",
    )

    default_fit_path = Path(".logs") / "vin" / "rri_binner_fit_data.pt"
    default_edges_path = Path(".logs") / "vin" / "rri_binner.json"

    col_a, col_b = st.columns(2)
    with col_a:
        fit_path_str = st.text_input(
            "Fit data (.pt)",
            value=str(default_fit_path),
            key="rri_binner_fit_path",
        )
    with col_b:
        edges_path_str = st.text_input(
            "Binner edges (.json)",
            value=str(default_edges_path),
            key="rri_binner_edges_path",
        )

    log_y = st.checkbox(
        "Log-scale y-axis",
        value=False,
        help="Use a log scale on the y-axis across plots; non-positive values are hidden.",
        key="rri_binner_log_y",
    )
    show_edges = st.checkbox(
        "Show quantile edges",
        value=True,
        key="rri_binner_show_edges",
    )
    show_midpoints = st.checkbox(
        "Show bin midpoints",
        value=False,
        key="rri_binner_show_midpoints",
    )
    normalize_x = st.checkbox(
        "Quantile-normalized x-axis",
        value=False,
        help="Map RRI to its empirical CDF so quantile edges appear equidistant.",
        key="rri_binner_normalize_x",
    )
    bins = int(
        st.slider(
            "Histogram bins",
            min_value=20,
            max_value=200,
            value=80,
            step=10,
            key="rri_binner_bins",
        ),
    )

    def _resolve_path(path_str: str, *, expected_suffix: str) -> Path:
        if not path_str.strip():
            raise ValueError("Path is empty.")
        return PathConfig().resolve_artifact_path(
            path_str,
            expected_suffix=expected_suffix,
            create_parent=False,
        )

    try:
        fit_path = _resolve_path(fit_path_str, expected_suffix=".pt")
        edges_path = _resolve_path(edges_path_str, expected_suffix=".json")
        if not fit_path.exists():
            st.warning(f"Fit data not found: {fit_path}")
            return
        if not edges_path.exists():
            st.warning(f"Binner JSON not found: {edges_path}")
            return

        rri = RriOrdinalBinner.load_fit_data(fit_path)
        binner = RriOrdinalBinner.load(edges_path)
    except Exception as exc:  # pragma: no cover - UI guard
        _report_exception(exc, context="Failed to load RRI binning data")
        return

    if rri.numel() == 0:
        st.info("Fit data contains no finite RRI values.")
        return

    edges = binner.edges
    num_classes = int(binner.num_classes or (edges.numel() + 1))
    rri_stats = {
        "samples": int(rri.numel()),
        "min": float(rri.min().item()),
        "max": float(rri.max().item()),
        "mean": float(rri.mean().item()),
        "median": float(rri.median().item()),
    }

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Samples", rri_stats["samples"])
    col2.metric("Mean RRI", f"{rri_stats['mean']:.4f}")
    col3.metric("Median RRI", f"{rri_stats['median']:.4f}")
    col4.metric("Min RRI", f"{rri_stats['min']:.4f}")
    col5.metric("Max RRI", f"{rri_stats['max']:.4f}")

    random_coral_loss = float(max(1, num_classes - 1) * math.log(2.0))
    col_a, col_b = st.columns(2)
    col_a.metric(
        "Random-guess CORAL loss",
        f"{random_coral_loss:.4f}",
        help="Assumes logits=0 (p=0.5) for each threshold; loss = (K-1)*log(2).",
    )
    random_probs = torch.full((num_classes,), 1.0 / float(num_classes), dtype=torch.float32)
    random_expected = float(binner.expected_from_probs(random_probs).item())
    col_b.metric(
        "Uniform-guess expected RRI",
        f"{random_expected:.4f}",
        help="Expected RRI from uniform class probabilities using bin means (or midpoints if means missing).",
    )

    rri_np = rri.cpu().numpy()
    x_title = "rri"
    edge_values = edges.detach().cpu().numpy()
    midpoint_values = binner.class_midpoints().detach().cpu().numpy()
    cdf_sorter: np.ndarray | None = None
    cdf_values: np.ndarray | None = None
    if normalize_x:
        finite = rri_np[np.isfinite(rri_np)]
        if finite.size > 1:
            sorter = np.sort(finite)
            cdf = np.linspace(0.0, 1.0, sorter.size, endpoint=True)
            cdf_sorter = sorter
            cdf_values = cdf

            def _to_quantile(vals: np.ndarray) -> np.ndarray:
                return np.interp(vals, sorter, cdf, left=0.0, right=1.0)

            rri_np = _to_quantile(rri_np)
            edge_values = _to_quantile(edge_values)
            midpoint_values = _to_quantile(midpoint_values)
        else:
            rri_np = np.zeros_like(rri_np)
            edge_values = np.zeros_like(edge_values)
            midpoint_values = np.zeros_like(midpoint_values)
        x_title = "rri (quantile)"

    series = [("rri", rri_np)]
    fig_hist = _histogram_overlay(
        series,
        bins=bins,
        title="Raw oracle RRI distribution",
        xaxis_title=x_title,
        log1p_counts=False,
    )
    if log_y:
        for trace in fig_hist.data:
            if getattr(trace, "y", None) is None:
                continue
            y_vals = np.asarray(trace.y, dtype=float)
            y_vals[y_vals <= 0] = np.nan
            trace.y = y_vals
        fig_hist.update_yaxes(type="log", title_text="count (log)")
    if normalize_x and cdf_sorter is not None and cdf_values is not None:
        tick_levels = np.linspace(0.0, 1.0, num=11, endpoint=True)
        tick_labels = np.interp(tick_levels, cdf_values, cdf_sorter)

        def _format_tick_label(value: float) -> str:
            return f"{value:.2e}"

        fig_hist.update_xaxes(
            tickmode="array",
            tickvals=tick_levels.tolist(),
            ticktext=[_format_tick_label(float(val)) for val in tick_labels],
            range=[0.0, 1.0],
        )
    if show_edges:
        for edge in edge_values.tolist():
            fig_hist.add_vline(
                x=float(edge),
                line_width=2,
                line_dash="solid",
                line_color="rgba(255, 215, 0, 0.7)",
            )
    if show_midpoints:
        for midpoint in midpoint_values.tolist():
            fig_hist.add_vline(
                x=float(midpoint),
                line_width=1,
                line_dash="dot",
                line_color="rgba(0, 200, 255, 0.6)",
            )
    st.plotly_chart(fig_hist, width="stretch")

    labels = binner.transform(rri)
    counts = torch.bincount(labels.to(dtype=torch.int64), minlength=int(num_classes)).cpu().numpy()
    bin_means = binner.bin_means
    bin_stds = binner.bin_stds
    if bin_means is None or bin_stds is None:
        means = torch.empty(int(num_classes), dtype=rri.dtype)
        stds = torch.empty_like(means)
        midpoints = binner.class_midpoints().to(device=rri.device, dtype=rri.dtype)
        for idx in range(int(num_classes)):
            vals = rri[labels == idx]
            if vals.numel() == 0:
                means[idx] = midpoints[idx]
                stds[idx] = 0.0
            else:
                means[idx] = vals.mean()
                stds[idx] = vals.std(unbiased=False)
        bin_means = means.cpu()
        bin_stds = stds.cpu()

    midpoints = binner.class_midpoints().cpu()
    bin_widths = torch.full((int(num_classes),), float("nan"), dtype=torch.float32)
    uniform_stds = torch.full_like(bin_widths, float("nan"))
    edges_f = edges.detach().cpu().reshape(-1).to(dtype=torch.float32)
    if edges_f.numel() >= 2 and int(num_classes) == int(edges_f.numel() + 1):
        step_lo = edges_f[1] - edges_f[0]
        step_hi = edges_f[-1] - edges_f[-2]
        lo = edges_f[0] - 0.5 * step_lo
        hi = edges_f[-1] + 0.5 * step_hi
        boundaries = torch.cat([lo.unsqueeze(0), edges_f, hi.unsqueeze(0)], dim=0)
        bin_widths = boundaries[1:] - boundaries[:-1]
        uniform_stds = bin_widths / math.sqrt(12.0)
    stats_df = pd.DataFrame(
        {
            "class": np.arange(int(num_classes)),
            "count": counts,
            "midpoint": midpoints.numpy(),
            "bin_width": bin_widths.numpy(),
            "bin_mean": bin_means.numpy() if bin_means is not None else midpoints.numpy(),
            "bin_std": bin_stds.numpy() if bin_stds is not None else np.zeros_like(midpoints.numpy()),
            "uniform_std": uniform_stds.numpy(),
        },
    )
    st.subheader("Per-bin statistics")
    st.dataframe(stats_df, width="stretch", height=260)

    fig_means = go.Figure()
    fig_means.add_trace(
        go.Bar(
            x=stats_df["class"],
            y=stats_df["bin_mean"],
            error_y={"type": "data", "array": stats_df["bin_std"], "visible": True},
            name="bin mean",
        ),
    )
    fig_means.add_trace(
        go.Scatter(
            x=stats_df["class"],
            y=stats_df["midpoint"],
            mode="lines+markers",
            name="midpoint",
        ),
    )
    fig_means.update_layout(
        title=_pretty_label("Bin means (±1 std) vs midpoints"),
        xaxis_title="class",
        yaxis_title="rri",
    )
    if log_y:
        for trace in fig_means.data:
            if getattr(trace, "y", None) is None:
                continue
            y_vals = np.asarray(trace.y, dtype=float)
            y_vals[y_vals <= 0] = np.nan
            trace.y = y_vals
        fig_means.update_yaxes(type="log", title_text="rri (log)")
    st.plotly_chart(fig_means, width="stretch")

    fig_stds = go.Figure()
    fig_stds.add_trace(
        go.Bar(
            x=stats_df["class"],
            y=stats_df["bin_std"],
            name="bin std",
        ),
    )
    fig_stds.add_trace(
        go.Scatter(
            x=stats_df["class"],
            y=stats_df["uniform_std"],
            mode="lines+markers",
            name="uniform std (width/√12)",
        ),
    )
    fig_stds.update_layout(
        title=_pretty_label("Bin stds vs uniform baseline"),
        xaxis_title="class",
        yaxis_title="rri std",
    )
    if log_y:
        for trace in fig_stds.data:
            if getattr(trace, "y", None) is None:
                continue
            y_vals = np.asarray(trace.y, dtype=float)
            y_vals[y_vals <= 0] = np.nan
            trace.y = y_vals
        fig_stds.update_yaxes(type="log", title_text="rri std (log)")
    st.plotly_chart(fig_stds, width="stretch")
    counts_plot = counts.astype(float)
    if log_y:
        counts_plot[counts_plot <= 0] = np.nan
        y_title = "count (log)"
    else:
        y_title = "count"
    fig_labels = px.bar(
        x=np.arange(int(num_classes)),
        y=counts_plot,
        labels={"x": "label", "y": y_title},
        title=_pretty_label("Ordinal labels (fit data)"),
    )
    if log_y:
        fig_labels.update_yaxes(type="log")
    st.plotly_chart(fig_labels, width="stretch")

    st.subheader("Ordinal labels by split")
    st.caption(
        "Compute label distributions for the VIN offline store train/val splits. "
        "This loads offline samples from disk and may take a while.",
    )
    default_cache_dir = PathConfig().offline_cache_dir
    cache_col_a, cache_col_b, cache_col_c = st.columns([2.5, 1.0, 1.2])
    with cache_col_a:
        cache_dir_str = st.text_input(
            "VIN offline store dir",
            value=str((default_cache_dir / "vin_offline") if default_cache_dir is not None else "vin_offline"),
            key="rri_binner_cache_dir",
        )
    with cache_col_b:
        max_snippets = int(
            st.number_input(
                "Max snippets / split",
                min_value=0,
                value=0,
                step=50,
                help="0 scans all snippets in the split index.",
                key="rri_binner_cache_max_snippets",
            ),
        )
    with cache_col_c:
        compute_split = st.button(
            "Compute train/val",
            key="rri_binner_cache_compute",
        )

    cache_dir = Path(cache_dir_str).expanduser()
    if not cache_dir.is_absolute():
        cache_dir = PathConfig().resolve_under_root(cache_dir)
    manifest_path = cache_dir / "manifest.json"
    sample_index_path = cache_dir / "sample_index.jsonl"

    if not manifest_path.exists() or not sample_index_path.exists():
        st.info("Missing `manifest.json` / `sample_index.jsonl` under the VIN offline store dir.")
        return

    split_cache_key = (
        str(cache_dir),
        float(manifest_path.stat().st_mtime),
        float(sample_index_path.stat().st_mtime),
        str(edges_path),
        int(max_snippets),
        int(num_classes),
    )

    if compute_split or st.session_state.get("rri_binner_split_cache_key") == split_cache_key:
        if compute_split or st.session_state.get("rri_binner_split_cache_key") != split_cache_key:
            edges_cpu = edges.detach().cpu().reshape(-1).to(dtype=torch.float32)

            def _count_labels(split_name: str) -> tuple[np.ndarray, int, int]:
                dataset = VinOfflineDatasetConfig(
                    store=VinOfflineStoreConfig(store_dir=cache_dir),
                    split=split_name,
                    limit=max_snippets or None,
                    return_format="sample",
                    map_location="cpu",
                    load_backbone=False,
                    load_candidates=False,
                    load_depths=False,
                    load_candidate_pcs=False,
                ).setup_target()
                total = len(dataset)
                if total == 0:
                    return np.zeros((int(num_classes),), dtype=np.int64), 0, 0

                counts_t = torch.zeros((int(num_classes),), dtype=torch.int64)
                total_candidates = 0
                progress = st.progress(0.0, text=f"Scanning {split_name} split…")
                for idx in range(total):
                    sample = dataset[idx]
                    rri_t = sample.oracle.rri.to(dtype=torch.float32).reshape(-1)
                    rri_t = rri_t[torch.isfinite(rri_t)]
                    if rri_t.numel() == 0:
                        continue

                    labels_t = torch.bucketize(rri_t, edges_cpu, right=False).to(dtype=torch.int64)
                    counts_t += torch.bincount(labels_t, minlength=int(num_classes))
                    total_candidates += int(rri_t.numel())

                    progress.progress((idx + 1) / total, text=f"Scanning {split_name}: {idx + 1}/{total} snippets")
                progress.empty()
                return counts_t.cpu().numpy(), total, total_candidates

            train_counts, train_snippets, train_candidates = _count_labels("train")
            val_counts, val_snippets, val_candidates = _count_labels("val")

            st.session_state["rri_binner_split_cache_key"] = split_cache_key
            st.session_state["rri_binner_split_train_counts"] = train_counts
            st.session_state["rri_binner_split_val_counts"] = val_counts
            st.session_state["rri_binner_split_train_snippets"] = train_snippets
            st.session_state["rri_binner_split_val_snippets"] = val_snippets
            st.session_state["rri_binner_split_train_candidates"] = train_candidates
            st.session_state["rri_binner_split_val_candidates"] = val_candidates

    train_counts = st.session_state.get("rri_binner_split_train_counts")
    val_counts = st.session_state.get("rri_binner_split_val_counts")
    if train_counts is None or val_counts is None:
        st.info("Click `Compute train/val` to render the split histograms.")
        return

    col_train, col_val = st.columns(2)
    col_train.metric(
        "Train (snippets / candidates)",
        f"{int(st.session_state.get('rri_binner_split_train_snippets', 0))} / {int(st.session_state.get('rri_binner_split_train_candidates', 0))}",
    )
    col_val.metric(
        "Val (snippets / candidates)",
        f"{int(st.session_state.get('rri_binner_split_val_snippets', 0))} / {int(st.session_state.get('rri_binner_split_val_candidates', 0))}",
    )

    split_df = pd.DataFrame(
        {
            "label": np.tile(np.arange(int(num_classes)), 2),
            "count": np.concatenate([train_counts, val_counts]).astype(float),
            "split": np.repeat(["train", "val"], int(num_classes)),
        },
    )
    if log_y:
        split_df.loc[split_df["count"] <= 0, "count"] = np.nan
        split_y_title = "count (log)"
    else:
        split_y_title = "count"
    fig_split = px.bar(
        split_df,
        x="label",
        y="count",
        color="split",
        barmode="group",
        labels={"label": "label", "count": split_y_title},
        title=_pretty_label("Ordinal labels (train vs val)"),
    )
    if log_y:
        fig_split.update_yaxes(type="log")
    st.plotly_chart(fig_split, width="stretch")
