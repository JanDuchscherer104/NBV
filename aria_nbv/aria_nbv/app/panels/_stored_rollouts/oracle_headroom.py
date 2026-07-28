"""Exact-cohort oracle headroom and policy evidence."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from .session import StoredRolloutSession
from .shared import _download_frame, _info_popover, _render_plot

_HEADROOM_INFO = r"""
For root-normalized target reconstruction error, endpoint gain and discounted
selected-chain return are

$$
J(\pi)=\frac{\Delta_0-\Delta_H}{\Delta_0+\varepsilon},
\qquad
G(\pi)=\sum_{t=0}^{H-1}\gamma^t r_{t,\mathrm{root}}.
$$

Oracle lookahead headroom and the fraction recovered by a QH policy are

$$
\Delta_{\mathrm{look}}=J(\pi_{\mathrm{oracle-look}})-J(\pi_{\mathrm{oracle-1}}),
$$

$$
\eta_Q=\frac{J(\pi_Q)-J(\pi_{\mathrm{learned-1}})}
{J(\pi_{\mathrm{oracle-look}})-J(\pi_{\mathrm{learned-1}})+\varepsilon}.
$$

The primary endpoint is root-normalized target gain; target RRI is diagnostic.
Rows are paired only when source, target/protocol, horizon and acquisition
budget, candidate and oracle configuration, and branch/beam schedule match
exactly. Actor policies consume actor-visible observations. Oracle roles use
privileged evaluation labels and define ceilings, not deployable inputs.
"""


def _return_contract(session: StoredRolloutSession) -> None:
    semantics = session.header_summary.get("q_h_return_semantics")
    gamma = session.header_summary.get("discount_gamma")
    columns = st.columns(2)
    columns[0].metric("Persisted return semantics", "unavailable" if semantics is None else str(semantics))
    gamma_label = f"{float(gamma):.6g}" if isinstance(gamma, (int, float)) else "unavailable"
    columns[1].metric("Discount γ", gamma_label)
    evidence = session.discounted_returns()
    if not evidence.get("available"):
        st.info(f"Discounted return is unavailable: {evidence.get('reason', 'store contract is insufficient')}.")
        return
    returns = pd.DataFrame(evidence.get("rows", []))
    finite = pd.to_numeric(returns.get("discounted_return"), errors="coerce").dropna()
    if finite.empty:
        st.info(
            "Discounted return is derivable under the store contract, but no rollout has a complete finite reward chain."
        )
        return
    st.caption(str(evidence.get("reason")))
    st.metric(
        "Median discounted return G",
        f"{float(finite.median()):.4g}",
        delta=f"{len(finite):,} finite rollouts",
        delta_color="off",
    )
    _download_frame("Download discounted returns CSV", "discounted-rollout-returns.csv", returns)


def _endpoint_and_horizon_views(role_rows: pd.DataFrame) -> None:
    if role_rows.empty:
        return
    exact = role_rows.dropna(subset=["final_cumulative_target_root_gain"])
    if exact.empty:
        return
    figure = px.histogram(
        exact,
        x="final_cumulative_target_root_gain",
        color="semantic_role",
        marginal="box",
        barmode="overlay",
        opacity=0.55,
        title="Exact-cohort endpoint gain distributions",
    )
    _render_plot(figure)
    horizon = (
        exact.groupby(["semantic_role", "horizon"], dropna=False)["final_cumulative_target_root_gain"]
        .agg(endpoint_median="median", endpoint_mean="mean", cohort_count="count")
        .reset_index()
    )
    figure = px.line(
        horizon,
        x="horizon",
        y="endpoint_median",
        color="semantic_role",
        markers=True,
        hover_data=("endpoint_mean", "cohort_count"),
        title="Exact-cohort endpoint gain by horizon",
    )
    _render_plot(figure)


def _oracle_evidence(rows: pd.DataFrame) -> None:
    finite = pd.to_numeric(rows["delta_look"], errors="coerce").dropna()
    columns = st.columns(3)
    columns[0].metric("Exact oracle pairs", f"{len(finite):,}")
    columns[1].metric("Median Δlook", f"{float(finite.median()):.4g}")
    columns[2].metric("Mean Δlook", f"{float(finite.mean()):.4g}")
    figure = px.histogram(
        rows,
        x="delta_look",
        marginal="box",
        title="Paired oracle lookahead headroom (root-normalized endpoint gain)",
    )
    _render_plot(figure)
    horizon = (
        rows.groupby("horizon", dropna=False)["delta_look"]
        .agg(delta_median="median", delta_mean="mean", matched_cohorts="count")
        .reset_index()
    )
    _render_plot(
        px.line(
            horizon,
            x="horizon",
            y="delta_median",
            markers=True,
            hover_data=("delta_mean", "matched_cohorts"),
            title="Oracle lookahead headroom by horizon",
        )
    )
    st.caption("Target RRI deltas below are diagnostic; root-normalized endpoint gain is the headroom definition.")
    st.dataframe(rows, hide_index=True, width="stretch")
    _download_frame("Download exact oracle headroom CSV", "oracle-headroom.csv", rows)


def _qh_evidence(rows: pd.DataFrame) -> None:
    finite = pd.to_numeric(rows["eta_q"], errors="coerce").dropna()
    st.metric(
        "Median recovered headroom ηQ",
        f"{float(finite.median()):.4g}",
        delta=f"{len(finite):,} exact cohorts",
        delta_color="off",
    )
    _render_plot(px.histogram(rows, x="eta_q", marginal="box", title="Recovered QH headroom over exact cohorts"))
    st.dataframe(rows, hide_index=True, width="stretch")
    _download_frame("Download recovered headroom CSV", "qh-recovered-headroom.csv", rows)


def render(session: StoredRolloutSession) -> None:
    """Render exact semantic-role evidence and fail-closed blockers."""

    st.subheader("Oracle Headroom & Policies")
    _info_popover("Endpoint return and headroom theory", _HEADROOM_INFO)
    _return_contract(session)

    evidence = session.oracle_headroom()
    blockers = pd.DataFrame(evidence.get("blocker_rows", []))
    st.markdown("#### Prerequisites")
    st.dataframe(blockers, hide_index=True, width="stretch")
    st.caption(
        "Semantic roles are assigned only to exact persisted policy/recipe identifiers. Similar names, prefixes, and free-text labels are never inferred."
    )

    role_rows = pd.DataFrame(evidence.get("role_rows", []))
    _endpoint_and_horizon_views(role_rows)
    oracle_rows = pd.DataFrame(evidence.get("oracle_rows", []))
    if oracle_rows.empty:
        st.warning(
            "Δlook is blocked: the store has no finite one-step-oracle/lookahead-oracle pair in the same exact cohort."
        )
    else:
        _oracle_evidence(oracle_rows)
    qh_rows = pd.DataFrame(evidence.get("qh_rows", []))
    if qh_rows.empty:
        st.info(
            "ηQ is blocked: exact QH, learned-one-step, and oracle-lookahead rows do not coexist in a finite matched cohort."
        )
    else:
        _qh_evidence(qh_rows)

    if oracle_rows.empty or qh_rows.empty:
        mismatch = pd.DataFrame(session.comparable_cohorts().get("mismatch_rows", []))
        if not mismatch.empty:
            with st.expander("Nearest unmatched cohorts", expanded=False):
                st.dataframe(mismatch, hide_index=True, width="stretch")
                _download_frame("Download mismatch evidence CSV", "policy-cohort-mismatches.csv", mismatch)


__all__ = ["render"]
