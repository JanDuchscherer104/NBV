"""Failure triage presentation for the active rollout store."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from .shared import ExplanationSection, ScientificExplanation
from .shared import download_frame as _download_frame
from .shared import render_plot as _render_plot

_SECTION_KEY = "stored_rollouts_section"


def _render_failure_triage(session_handle: Any) -> None:
    st.subheader("Active-store failure detail")
    with st.expander("Advanced thresholds"):
        min_valid = int(st.number_input("Minimum valid fanout", min_value=0, value=3, step=1))
        dominant = float(st.slider("Dominant invalidity fraction", min_value=0.0, max_value=1.0, value=0.8))
        max_step = float(st.slider("Maximum selected step (m)", min_value=0.1, max_value=5.0, value=1.25))
    failures = pd.DataFrame(session_handle.failures(min_valid, dominant, max_step))
    if failures.empty:
        st.success("No failure rows match the active thresholds.")
        return
    severity = failures.groupby(["severity", "kind"], dropna=False).size().reset_index(name="count")
    fig = px.bar(severity, x="kind", y="count", color="severity", title="Failure evidence by kind and severity")
    _render_plot(
        fig,
        ScientificExplanation(
            question="Which contract or data-quality failures dominate this store, and where should inspection begin?",
            answer="Failure counts prioritize traceable debugging evidence; they are not independent scientific samples or policy estimates.",
            sections=(
                ExplanationSection(
                    "Population and metric",
                    "Each row is one emitted finding over a rollout, step, candidate, target, or store condition. Counts are grouped by severity and predicate.",
                ),
                ExplanationSection(
                    "Denominator and comparison",
                    "All rows checked by the active thresholds are retained. Compare stores only when thresholds and schema match.",
                ),
                ExplanationSection(
                    "Expected pattern and warning",
                    "Hard mask or linkage failures should be sparse and traceable. Concentrated warnings identify where to inspect next.",
                ),
            ),
            evidence_role="provenance",
            source_fields=(
                "inspection.suspicious_rollout_rows",
                "selected depth",
                "candidate diagnostics",
                "target audit",
            ),
        ),
    )
    st.dataframe(failures, hide_index=True, width="stretch")
    _download_frame("Download failure triage CSV", "failure-triage.csv", failures)
    choices = failures.to_dict("records")
    chosen = st.selectbox(
        "Failure to inspect",
        choices,
        format_func=lambda row: f"{row.get('severity', '?')} · {row.get('kind', '?')} · {row.get('message', '')}",
    )
    st.button(
        "Inspect selected failure",
        on_click=_carry_failure_to_inspect,
        args=(chosen,),
        type="primary",
    )


def _carry_failure_to_inspect(row: dict[str, Any]) -> None:
    """Carry stable rollout/step identifiers into the inspection workspace."""

    if row.get("rollout_row_id") is not None:
        st.session_state["stored_rollout_id"] = int(row["rollout_row_id"])
    if row.get("step_row_id") is not None:
        st.session_state["stored_step_id"] = int(row["step_row_id"])
    st.session_state[_SECTION_KEY] = "Drill-down"
