"""Failure triage presentation for the active rollout store."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from ....rollouts import RolloutZarrStoreReader
from .session import _cached_failures
from .shared import (
    STORED_ROLLOUTS_DIAGNOSE_MODE_KEY,
    STORED_ROLLOUTS_DIAGNOSE_MODES,
    STORED_ROLLOUTS_DIAGNOSE_SECTION,
    STORED_ROLLOUTS_SECTION_KEY,
    ExplanationSection,
    ScientificExplanation,
)
from .shared import download_frame as _download_frame
from .shared import render_plot as _render_plot


def _render_failure_triage(reader: RolloutZarrStoreReader) -> None:
    st.subheader("Active-store failure detail")
    with st.expander("Advanced thresholds"):
        min_valid = int(st.number_input("Minimum valid fanout", min_value=0, value=3, step=1))
        dominant = float(st.slider("Dominant invalidity fraction", min_value=0.0, max_value=1.0, value=0.8))
        max_step = float(st.slider("Maximum selected step (m)", min_value=0.1, max_value=5.0, value=1.25))
    failures = pd.DataFrame(_cached_failures(reader.store_dir.as_posix(), min_valid, dominant, max_step))
    if failures.empty:
        st.success("No failure rows match the active thresholds.")
        return
    severity = failures.groupby(["severity", "kind"], dropna=False).size().reset_index(name="count")
    fig = px.bar(severity, x="kind", y="count", color="severity", title="Failure evidence by kind and severity")
    _render_plot(
        fig,
        ScientificExplanation(
            question="Which contract or data-quality failures dominate this store, and where should inspection begin?",
            sections=(
                ExplanationSection(
                    "Reading the bars",
                    "Each bar counts emitted triage findings by severity and predicate. A finding may be attached to a rollout, step, candidate, target, or store-level condition, so counts are not independent scientific samples.",
                ),
                ExplanationSection(
                    "Scope and comparison",
                    "The denominator is every row checked by the active threshold configuration. Compare stores only when thresholds and schema contracts match.",
                ),
                ExplanationSection(
                    "Investigate next",
                    "Use concentration to prioritize operator inspection. Counts are descriptive debugging evidence and do not estimate policy performance.",
                ),
            ),
            evidence_role="provenance",
            answer="The bars rank the persisted failure predicates that deserve operator inspection first; they do not summarize rollout quality.",
            external_references=(
                (
                    "NIST Engineering Statistics Handbook: counts and nonconformities",
                    "https://www.itl.nist.gov/div898/handbook/toolaids/pff/pmc.pdf",
                ),
            ),
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


def _carry_failure_to_inspect(row: dict[str, object]) -> None:
    """Carry stable rollout/step identifiers into the inspection workspace."""

    if row.get("rollout_row_id") is not None:
        st.session_state["stored_rollout_id"] = int(row["rollout_row_id"])
    if row.get("step_row_id") is not None:
        st.session_state["stored_step_id"] = int(row["step_row_id"])
    st.session_state[STORED_ROLLOUTS_SECTION_KEY] = STORED_ROLLOUTS_DIAGNOSE_SECTION
    st.session_state[STORED_ROLLOUTS_DIAGNOSE_MODE_KEY] = STORED_ROLLOUTS_DIAGNOSE_MODES[1]
