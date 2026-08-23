"""CORAL ordinal-output and calibration diagnostics for VIN.

The tab provides threshold logits, class probabilities, monotonicity checks,
entropy and loss views, comparing actor-facing predictions with separately
labeled oracle RRI targets when available.
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st
import torch

from ....utils.plotting import _histogram_overlay
from ....vin.ordinal import coral_loss, coral_monotonicity_violation_rate
from ..common import _info_popover, _pretty_label, current_scientific_label
from .context import VinDiagContext


def render_coral_tab(ctx: VinDiagContext) -> None:
    """Render the CORAL / Ordinal tab.

    Args:
        ctx: Shared VIN diagnostics context.
    """
    pred = ctx.pred
    batch = ctx.batch
    state = ctx.state

    _info_popover(
        "coral diagnostics",
        "CORAL models cumulative probabilities P(y > k) for ordinal bins. "
        "This panel visualizes threshold probabilities, marginal class "
        "probabilities, bin representatives, and per-candidate loss/entropy. "
        "Use it to validate bin calibration and monotonicity.",
    )
    binner = getattr(state.module, "_binner", None)
    head_coral = getattr(state.module.vin, "head_coral", None) if state.module is not None else None

    logits_full = pred.logits
    probs_full = pred.prob
    num_classes = int(probs_full.shape[-1])

    batch_index = 0
    if logits_full.ndim == 3 and logits_full.shape[0] > 1:
        batch_index = int(
            st.slider(
                "Batch index",
                min_value=0,
                max_value=max(0, int(logits_full.shape[0]) - 1),
                value=0,
                step=1,
                key="vin_coral_batch",
            ),
        )

    logits = logits_full[batch_index] if logits_full.ndim == 3 else logits_full
    probs = probs_full[batch_index] if probs_full.ndim == 3 else probs_full

    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader(f"{current_scientific_label('rri')} distribution + bin edges")
        if batch.rri is None:
            st.info("Oracle RRI values unavailable in this batch.")
        elif binner is None:
            st.info("RRI binner unavailable; cannot overlay bin edges.")
        else:
            rri_flat = batch.rri.reshape(-1).detach().cpu().numpy()
            edges = binner.edges.detach().cpu().numpy()
            fig_hist = go.Figure()
            fig_hist.add_trace(
                go.Histogram(
                    x=rri_flat,
                    nbinsx=60,
                    name=current_scientific_label("rri"),
                    marker_color="#5da5da",
                    opacity=0.75,
                ),
            )
            for edge in edges.tolist():
                fig_hist.add_vline(
                    x=edge,
                    line_dash="dot",
                    line_width=1,
                    line_color="gray",
                )
            fig_hist.update_layout(
                title=f"Oracle {current_scientific_label('rri')} with bin edges",
                xaxis_title=current_scientific_label("rri"),
                yaxis_title=_pretty_label("count"),
                barmode="overlay",
            )
            st.plotly_chart(fig_hist, width="stretch")

    with col_right:
        st.subheader("Bin representatives")
        if binner is None:
            st.info("RRI binner unavailable.")
        else:
            bin_means = binner.bin_means
            midpoints = binner.class_midpoints()
            learned = None
            if head_coral is not None and getattr(head_coral, "has_bin_values", False):
                learned = head_coral.bin_values.values().detach().cpu()

            fig_bins = go.Figure()
            if bin_means is not None:
                fig_bins.add_trace(
                    go.Scatter(
                        x=list(range(num_classes)),
                        y=bin_means.detach().cpu().numpy(),
                        mode="lines+markers",
                        name="bin_mean",
                    ),
                )
            if midpoints is not None:
                fig_bins.add_trace(
                    go.Scatter(
                        x=list(range(num_classes)),
                        y=midpoints.detach().cpu().numpy(),
                        mode="lines+markers",
                        name="midpoint",
                    ),
                )
            if learned is not None:
                fig_bins.add_trace(
                    go.Scatter(
                        x=list(range(num_classes)),
                        y=learned.numpy(),
                        mode="lines+markers",
                        name="learned_u",
                    ),
                )
            fig_bins.update_layout(
                title=_pretty_label("Bin representatives (u_k)"),
                xaxis_title=_pretty_label("bin index"),
                yaxis_title=current_scientific_label("rri"),
            )
            st.plotly_chart(fig_bins, width="stretch")

    st.subheader("Candidate-level CORAL outputs")
    cand_idx = st.slider(
        "Candidate index",
        min_value=0,
        max_value=max(0, ctx.num_candidates - 1),
        value=0,
        key="vin_coral_candidate",
    )
    cand_logits = logits[cand_idx]
    cand_probs = probs[cand_idx]
    cand_p_gt = torch.sigmoid(cand_logits).detach().cpu().numpy()
    cand_probs_np = cand_probs.detach().cpu().numpy()

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        fig_pgt = go.Figure()
        fig_pgt.add_trace(
            go.Scatter(
                x=list(range(num_classes - 1)),
                y=cand_p_gt,
                mode="lines+markers",
                name="P(y>k)",
            ),
        )
        fig_pgt.update_layout(
            title=_pretty_label("Cumulative probabilities"),
            xaxis_title=_pretty_label("threshold k"),
            yaxis_title=_pretty_label("P(y>k)"),
            yaxis_range=[0, 1],
        )
        st.plotly_chart(fig_pgt, width="stretch")

    with col_b:
        fig_pi = go.Figure()
        fig_pi.add_trace(
            go.Bar(
                x=list(range(num_classes)),
                y=cand_probs_np,
                name="P(y=k)",
            ),
        )
        fig_pi.update_layout(
            title=_pretty_label("Marginal class probabilities"),
            xaxis_title=_pretty_label("class k"),
            yaxis_title=_pretty_label("P(y=k)"),
            yaxis_range=[0, 1],
        )
        st.plotly_chart(fig_pi, width="stretch")

    with col_c:
        st.subheader("Expected values")
        ordinal_expected = cand_p_gt.sum()
        st.metric("E[y] (ordinal)", f"{float(ordinal_expected):.3f}")
        if head_coral is not None and getattr(head_coral, "has_bin_values", False):
            pred_rri = float(head_coral.expected_from_probs(cand_probs).item())
            st.metric(f"E[{current_scientific_label('rri')}] (learned u_k)", f"{pred_rri:.4f}")
        elif binner is not None:
            pred_rri = float(binner.expected_from_probs(cand_probs).item())
            st.metric(f"E[{current_scientific_label('rri')}] (bin means)", f"{pred_rri:.4f}")
        else:
            st.info("No bin representatives available.")

    st.subheader("CORAL diagnostics across candidates")
    monotonicity = coral_monotonicity_violation_rate(logits_full).reshape(-1).detach().cpu().numpy()
    fig_mono = _histogram_overlay(
        [("monotonicity_violation_rate", monotonicity)],
        bins=60,
        title=_pretty_label("Monotonicity violation rate"),
        xaxis_title=_pretty_label("fraction of violations"),
        log1p_counts=False,
    )
    st.plotly_chart(fig_mono, width="stretch")

    if batch.rri is not None and binner is not None:
        rri_flat = batch.rri.reshape(-1)
        logits_flat = logits_full.reshape(-1, logits_full.shape[-1])
        mask = torch.isfinite(rri_flat)
        if mask.any():
            labels = binner.transform(rri_flat)
            loss_per = coral_loss(
                logits_flat[mask],
                labels[mask],
                num_classes=int(binner.num_classes),
                reduction="none",
            )
            fig_loss = _histogram_overlay(
                [("coral_loss", loss_per.detach().cpu().numpy())],
                bins=60,
                title=_pretty_label("CORAL loss per candidate"),
                xaxis_title=_pretty_label("loss"),
                log1p_counts=False,
            )
            st.plotly_chart(fig_loss, width="stretch")
        else:
            st.info("No finite RRI labels available for loss diagnostics.")
    else:
        st.info("Loss diagnostics require oracle RRIs and a fitted binner.")


__all__ = ["render_coral_tab"]
