"""Independent reconstruction endpoints and collapsed descriptive diagnostics."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from .session import StoredRolloutSession
from .shared import _download_frame, _info_popover, _render_plot

_RECONSTRUCTION_INFO = r"""
The audited endpoint is (J=(\Delta_0-\Delta_H)/(\Delta_0+\epsilon)), where
the target-cropped reconstruction errors are independently re-evaluated from
raw lineage and the selected pose chain. The rollout is the sampling unit;
scene-macro summaries give scenes equal weight. Fixed-budget early termination
is absorbing and reports achieved/unused acquisitions, termination, path
length in metres, and evaluator cost in seconds. Missing or blocked endpoint
rows remain missing and cannot support a confirmatory claim.

Persisted cumulative root gain is a comparator/trajectory diagnostic. Horizon
curves are descriptive without a predeclared simultaneous band. Target RRI,
selection probability, and entropy diagnose state-relative gain and decision
concentration; they are not independent endpoint evidence.
"""


def render(session: StoredRolloutSession) -> None:
    """Render audited endpoints first and persisted diagnostics on demand."""

    st.subheader("Reconstruction & Return")
    _info_popover("Endpoint, budget, and missingness theory", _RECONSTRUCTION_INFO)
    audit = session.audit_state()
    endpoints = pd.DataFrame(session.audited_endpoints())
    if endpoints.empty:
        st.warning(
            "Independent endpoint evidence is unavailable; persisted rollout quantities below are characterization only. "
            + ("; ".join(audit.blockers) if audit.blockers else f"audit status={audit.artifact_status}")
        )
    else:
        st.markdown("#### Audited endpoint and fixed-budget outcomes")
        columns = [
            name
            for name in (
                "scene_id",
                "semantic_role",
                "delta_0",
                "delta_h",
                "endpoint_gain",
                "budget",
                "achieved_steps",
                "unused_budget",
                "termination_reason",
                "path_length_m",
                "evaluation_cost_s",
                "equivalence_verdict",
            )
            if name in endpoints
        ]
        st.dataframe(endpoints[columns], hide_index=True, width="stretch")
        _download_frame("Download audited endpoint CSV", "audited-reconstruction-endpoints.csv", endpoints)

    with st.expander("Descriptive persisted gain, horizon, RRI, probability, and entropy", expanded=False):
        steps = pd.DataFrame(session.steps())
        if steps.empty:
            st.info("No factual rollout steps are available.")
            return
        metrics = [
            name
            for name in (
                "cumulative_target_root_gain",
                "selected_target_root_gain",
                "selected_target_rri",
                "selected_probability",
                "selected_entropy",
            )
            if name in steps and pd.to_numeric(steps[name], errors="coerce").notna().any()
        ]
        if not metrics:
            st.info("Persisted descriptive reconstruction diagnostics are unavailable.")
            return
        metric = st.selectbox("Descriptive metric", metrics, format_func=lambda value: value.replace("_", " ").title())
        summary = pd.DataFrame(session.temporal_summary(metric=metric, group_fields=("policy", "horizon")))
        if not summary.empty:
            summary["series"] = summary.apply(
                lambda row: f"{row.get('policy', 'unknown')} · H={row.get('horizon', '?')}", axis=1
            )
            _render_plot(
                px.line(
                    summary,
                    x="step_index",
                    y="median",
                    color="series",
                    markers=True,
                    hover_data=("q25", "q75", "finite_count", "total_count"),
                    title="Descriptive state-depth trajectory (median; IQR in table)",
                )
            )
            st.dataframe(summary, hide_index=True, width="stretch")
            _download_frame("Download descriptive horizon CSV", "descriptive-reconstruction-horizon.csv", summary)


__all__ = ["render"]
