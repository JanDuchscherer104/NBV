"""Ordinal-bin value diagnostics for fitted and learned VIN quantities.

The tab provides fitted edges, midpoints or empirical oracle-bin means, learned
CORAL representatives, and monotonic spacing comparisons without changing the
binner or model.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import torch

from ....rri_metrics.ordinal import RriOrdinalBinner
from ...scientific_labels import format_scientific_label, scientific_label
from ...state import get_label_display_mode
from ..common import _info_popover, _pretty_label, render_scientific_notation
from .context import VinDiagContext


def _rri_label() -> str:
    return format_scientific_label(
        scientific_label("rri"),
        mode=get_label_display_mode(),
        surface="plain",
    )


@dataclass(slots=True)
class _BinValuePayload:
    """Tabular fitted-bin data and scalar comparisons prepared for rendering."""

    edges_df: pd.DataFrame
    """Threshold rows indexed over the ``K - 1`` fitted ordinal edges."""

    centers_df: pd.DataFrame
    """Per-class rows over ``K`` midpoints, fit targets, and learned values."""

    stats: dict[str, float]
    """Scalar learned-versus-fitted delta and spacing diagnostics."""


def _build_bin_value_payload(
    *,
    binner: RriOrdinalBinner,
    learned_u: torch.Tensor | None,
) -> _BinValuePayload:
    if not binner.is_fitted:
        raise RuntimeError("Binner is not fitted.")

    edges = binner.edges.detach().reshape(-1).to(dtype=torch.float32).cpu()
    midpoints = binner.class_midpoints().detach().reshape(-1).to(dtype=torch.float32).cpu()
    bin_means = (
        binner.bin_means.detach().reshape(-1).to(dtype=torch.float32).cpu() if binner.bin_means is not None else None
    )

    num_classes = int(midpoints.numel())
    if edges.numel() != max(0, num_classes - 1):
        raise ValueError(
            f"Edge count mismatch: got {int(edges.numel())} edges but {num_classes} classes.",
        )

    baseline = bin_means if bin_means is not None else midpoints
    baseline_name = "bin_mean" if bin_means is not None else "midpoint"

    edges_df = pd.DataFrame(
        {
            "threshold_k": np.arange(int(edges.numel()), dtype=int),
            "edge": edges.numpy(),
        },
    )

    data: dict[str, np.ndarray] = {
        "class_k": np.arange(num_classes, dtype=int),
        "midpoint": midpoints.numpy(),
        "init_target": baseline.numpy(),
    }
    if bin_means is not None:
        data["bin_mean"] = bin_means.numpy()

    stats: dict[str, float] = {}
    if learned_u is not None:
        learned_u = learned_u.detach().reshape(-1).to(dtype=torch.float32).cpu()
        if learned_u.numel() != num_classes:
            raise ValueError(
                f"learned_u must have shape (K,), got {tuple(learned_u.shape)} for K={num_classes}.",
            )
        learned_np = learned_u.numpy()
        data["learned_u"] = learned_np
        diff = learned_u - baseline
        data[f"learned_u_minus_{baseline_name}"] = diff.numpy()
        stats["mean_abs_delta"] = float(diff.abs().mean().item())
        stats["max_abs_delta"] = float(diff.abs().max().item())

        learned_d = torch.diff(learned_u)
        baseline_d = torch.diff(baseline)
        if learned_d.numel() > 0:
            stats["min_learned_delta"] = float(learned_d.min().item())
            stats["min_baseline_delta"] = float(baseline_d.min().item())
            stats["mean_learned_delta"] = float(learned_d.mean().item())
            stats["mean_baseline_delta"] = float(baseline_d.mean().item())

    centers_df = pd.DataFrame(data)
    centers_df.attrs["baseline_name"] = baseline_name
    return _BinValuePayload(edges_df=edges_df, centers_df=centers_df, stats=stats)


def render_bin_values_tab(ctx: VinDiagContext) -> None:
    """Render binner-vs-learned CORAL bin values.

    Args:
        ctx: Shared VIN diagnostics context.
    """
    state = ctx.state
    module = state.module
    if module is None:
        st.info("VIN module not available.")
        return

    binner = getattr(module, "_binner", None)
    if not isinstance(binner, RriOrdinalBinner):
        st.info("RRI binner unavailable; cannot compare edges/centers to learned values.")
        return

    vin = getattr(module, "vin", None)
    head_coral = getattr(vin, "head_coral", None) if vin is not None else None
    learned_u = None
    if head_coral is not None and getattr(head_coral, "has_bin_values", False):
        learned_u = head_coral.bin_values.values()

    _info_popover(
        "bin values",
        "CORAL predicts a class distribution P(y=k). To map this to a continuous RRI "
        "estimate, we multiply by per-class representatives u_k and sum. "
        "These u_k are initialized from the fitted RRI binner (bin means or midpoints) "
        "and then trained as a monotone parameterization (MonotoneBinValues). "
        "This tab compares the fitted binner edges/centers against the learned u_k.",
    )
    render_scientific_notation("rri")

    try:
        payload = _build_bin_value_payload(binner=binner, learned_u=learned_u)
    except Exception as exc:  # pragma: no cover - UI guard
        st.error(f"{type(exc).__name__}: {exc}")
        return
    baseline_name = str(payload.centers_df.attrs.get("baseline_name", "baseline"))

    st.subheader(_pretty_label("Binner edges"))
    st.dataframe(payload.edges_df, width="stretch")

    st.subheader(_pretty_label("Bin centers"))
    st.caption(
        f"Baseline used for initialization: `{baseline_name}` (see Lightning `prepare_for_inference`).",
    )
    st.dataframe(payload.centers_df, width="stretch")

    col_a, col_b = st.columns(2)
    with col_a:
        fig_edges = go.Figure()
        fig_edges.add_trace(
            go.Scatter(
                x=payload.edges_df["threshold_k"],
                y=payload.edges_df["edge"],
                mode="lines+markers",
                name="edge",
            ),
        )
        fig_edges.update_layout(
            title=_pretty_label("Binner edges (quantile thresholds)"),
            xaxis_title=_pretty_label("threshold k"),
            yaxis_title=_rri_label(),
        )
        st.plotly_chart(fig_edges, width="stretch")

    with col_b:
        fig_centers = go.Figure()
        fig_centers.add_trace(
            go.Scatter(
                x=payload.centers_df["class_k"],
                y=payload.centers_df["midpoint"],
                mode="lines+markers",
                name="midpoint",
            ),
        )
        if "bin_mean" in payload.centers_df.columns:
            fig_centers.add_trace(
                go.Scatter(
                    x=payload.centers_df["class_k"],
                    y=payload.centers_df["bin_mean"],
                    mode="lines+markers",
                    name="bin_mean",
                ),
            )
        if learned_u is not None and "learned_u" in payload.centers_df.columns:
            fig_centers.add_trace(
                go.Scatter(
                    x=payload.centers_df["class_k"],
                    y=payload.centers_df["learned_u"],
                    mode="lines+markers",
                    name="learned_u",
                ),
            )
        fig_centers.update_layout(
            title=_pretty_label("Bin centers vs learned u_k"),
            xaxis_title=_pretty_label("class k"),
            yaxis_title=_rri_label(),
        )
        st.plotly_chart(fig_centers, width="stretch")

    if learned_u is None:
        st.info("Learnable bin values (u_k) are not initialized for this model.")
        return

    diff_col = f"learned_u_minus_{baseline_name}"
    if diff_col not in payload.centers_df.columns:
        st.info("Learned u_k values are available but diffs could not be computed.")
        return

    st.subheader(_pretty_label("Learned - baseline deltas"))
    fig_delta = go.Figure(
        go.Bar(
            x=payload.centers_df["class_k"],
            y=payload.centers_df[diff_col],
            name=diff_col,
        ),
    )
    fig_delta.update_layout(
        title=_pretty_label(f"learned_u - {baseline_name}"),
        xaxis_title=_pretty_label("class k"),
        yaxis_title=_pretty_label("delta"),
    )
    st.plotly_chart(fig_delta, width="stretch")

    st.subheader(_pretty_label("Delta summary"))
    if payload.stats:
        cols = st.columns(4)
        cols[0].metric("Mean |Δ|", f"{payload.stats.get('mean_abs_delta', float('nan')):.6f}")
        cols[1].metric("Max |Δ|", f"{payload.stats.get('max_abs_delta', float('nan')):.6f}")
        cols[2].metric("Min learned Δu", f"{payload.stats.get('min_learned_delta', float('nan')):.6f}")
        cols[3].metric("Min baseline Δ", f"{payload.stats.get('min_baseline_delta', float('nan')):.6f}")


__all__ = ["render_bin_values_tab"]
