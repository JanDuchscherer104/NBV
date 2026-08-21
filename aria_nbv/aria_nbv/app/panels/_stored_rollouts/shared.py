"""Shared, presentation-only widgets for stored-rollout inspection."""

from __future__ import annotations

import hashlib
import html
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ...scientific_labels import ResolvedNotation, ResolvedTerm, TheoryReferences, TheoryResolutionError, resolve_theory
from ..common import _plot_with_y_axis_control

_ROLE_COLORS = {
    "actor-visible": "#1f77b4",
    "oracle/evaluation": "#d62728",
    "derived training data": "#9467bd",
    "provenance": "#6b7280",
}

# The coordinator and its triage action share these state identifiers.  Keeping
# them here prevents a failure-to-inspection handoff from depending on copied
# string literals in two presentation modules.
STORED_ROLLOUTS_SECTION_KEY = "stored_rollouts_section"
STORED_ROLLOUTS_DIAGNOSE_MODE_KEY = "stored_rollouts_diagnose_mode"
STORED_ROLLOUTS_DIAGNOSE_SECTION = "Diagnose a store"
STORED_ROLLOUTS_DIAGNOSE_MODES = ("Triage failures", "Inspect, export, and Rerun")


@dataclass(frozen=True, slots=True)
class ExplanationSection:
    """One author-chosen narrative section in a scientific explanation."""

    title: str
    body: str

    def __post_init__(self) -> None:
        if not self.title.strip() or not self.body.strip():
            raise ValueError("Each narrative section requires a title and body.")


@dataclass(frozen=True, slots=True)
class ScientificExplanation:
    """Narrative interpretation and canonical theory references for one plot."""

    question: str
    answer: str
    sections: tuple[ExplanationSection, ...]
    evidence_role: Literal["actor-visible", "oracle/evaluation", "derived training data", "provenance"]
    source_fields: tuple[str, ...]
    theory: TheoryReferences | None = None
    external_references: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.question.strip() or not self.answer.strip() or not self.source_fields:
            raise ValueError("Scientific explanations require a question, answer, and at least one source.")
        if any(not source.strip() for source in self.source_fields):
            raise ValueError("Scientific explanation sources must be non-empty.")
        if any(not label.strip() or not url.strip() for label, url in self.external_references):
            raise ValueError("External references require a label and URL.")


def render_stale_store_boundary(
    validation: Any, *, inventory_row: dict[str, object] | None, manifest_payload: dict[str, Any]
) -> None:
    st.warning(
        "Scientific evidence and Rerun are disabled because this store does not pass the current schema contract."
    )
    for error in getattr(validation, "errors", ()):
        st.error(str(error))
    download_json(
        "Download stale-store diagnostics JSON",
        "stale-rollout-store.json",
        {"inventory": inventory_row, **manifest_payload, "validation_errors": list(getattr(validation, "errors", ()))},
    )


def plot_control_key(plot_name: str, *identity: object) -> str:
    payload = "\x1f".join((plot_name, *(str(value) for value in identity)))
    return f"stored-rollout-plot:{plot_name}:{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def render_plot(fig: go.Figure, explanation: ScientificExplanation, *, log_y_key: str | None = None) -> None:
    badge_color = _ROLE_COLORS[explanation.evidence_role]
    columns = st.columns([4, 1, 1]) if log_y_key is not None else st.columns([5, 1])
    col_title, col_info = columns[:2]
    col_title.markdown(
        f'<span style="padding:.15rem .45rem;border-radius:.35rem;background:{badge_color};color:white">'
        f"{html.escape(explanation.evidence_role)}</span>",
        unsafe_allow_html=True,
    )
    st.markdown(f"**Answer:** {explanation.answer}")
    with col_info.popover("Interpret this plot", icon="ℹ️"):
        _render_scientific_guide(explanation)
        if log_y_key is not None:
            explanation_item(
                "Axis scale",
                "Linear by default. Logarithmic scale is independently selectable for this plot and hides zero or negative observations.",
            )
        explanation_item("Provenance", ", ".join(explanation.source_fields), code=True)
    rendered = fig
    if log_y_key is not None:
        with columns[2]:
            rendered, _ = _plot_with_y_axis_control(fig, key=log_y_key)
    st.plotly_chart(rendered, width="stretch")


def render_explanation_popover(label: str, explanation: ScientificExplanation) -> None:
    """Render canonical scientific context for a metric group without a plot."""

    with st.popover(label, icon="ℹ️"):
        _render_scientific_guide(explanation)
        explanation_item("Provenance", ", ".join(explanation.source_fields), code=True)


def _render_scientific_guide(explanation: ScientificExplanation) -> None:
    """Render an explanation as a compact narrative backed by shared theory."""

    st.markdown("### Core idea")
    explanation_item("Question", explanation.question)
    st.markdown(explanation.answer)
    if explanation.theory is not None:
        _render_theory(explanation.theory)
    for section in explanation.sections:
        st.markdown(f"### {section.title}")
        st.markdown(section.body)
    if explanation.external_references:
        st.markdown("**External sources**")
        for label, url in explanation.external_references:
            st.markdown(f"- [{label}]({url})")


def _render_theory(references: TheoryReferences) -> None:
    """Render canonical equations, symbols, and glossary terms or warn clearly."""

    try:
        resolved = resolve_theory(references)
    except TheoryResolutionError as exc:
        st.warning(f"Canonical theory unavailable: {exc}")
        return

    if resolved.equations:
        st.markdown("### Canonical equations")
        for equation in resolved.equations:
            _render_equation(equation)
    if resolved.symbols or resolved.terms:
        st.markdown("### Symbols and terms")
        for symbol in resolved.symbols:
            _render_symbol(symbol)
        for term in resolved.terms:
            _render_term(term)


def _render_equation(equation: ResolvedNotation) -> None:
    st.latex(equation.tex)
    if equation.description is not None:
        st.markdown(equation.description)
    st.markdown(f"[Shared equation source]({equation.source_url})")


def _render_symbol(symbol: ResolvedNotation) -> None:
    description = symbol.description or symbol.identifier
    st.markdown(f"${symbol.tex}$ — {description} ([shared symbol]({symbol.source_url}))")


def _render_term(term: ResolvedTerm) -> None:
    label = f"{term.label} ({term.short})" if term.short and term.short != term.label else term.label
    st.markdown(f"**{label}.** {term.definition} ([glossary source]({term.source_url}))")


def explanation_item(label: str, value: str, *, code: bool = False) -> None:
    st.markdown(f"**{label}**\n\n{f'`{value}`' if code else value}")


def download_frame(label: str, file_name: str, frame: pd.DataFrame) -> None:
    st.download_button(
        label,
        data=lambda: serialize_frame_csv(frame),
        file_name=file_name,
        mime="text/csv",
        on_click="ignore",
        help="Materialized lazily on click so tab reruns do not retain stale media URLs.",
    )
    st.caption(f"Export rows: {len(frame):,} (complete filtered dataset).")


def download_json(label: str, file_name: str, payload: object) -> None:
    st.download_button(
        label,
        data=lambda: serialize_json(payload),
        file_name=file_name,
        mime="application/json",
        on_click="ignore",
        help="Materialized lazily on click so tab reruns do not retain stale media URLs.",
    )


def serialize_frame_csv(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8")


def serialize_json(payload: object) -> bytes:
    return json.dumps(payload, indent=2, sort_keys=True, default=json_default).encode("utf-8") + b"\n"


def json_default(value: object) -> object:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, np.generic):
        return value.item()
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return str(value)
