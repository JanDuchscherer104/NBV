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

from ...scientific_labels import TheoryReferences, TheoryResolutionError, resolve_theory
from ..common import _plot_with_y_axis_control

_ROLE_COLORS = {
    "actor-visible": "#1f77b4",
    "oracle/evaluation": "#d62728",
    "derived training data": "#9467bd",
    "provenance": "#6b7280",
}


@dataclass(frozen=True, slots=True)
class ExplanationSection:
    """One concise narrative section in a scientific plot explanation."""

    title: str
    body: str


@dataclass(frozen=True, slots=True)
class ScientificExplanation:
    """Narrative interpretation contract shown beside one primary visualization."""

    question: str
    answer: str
    sections: tuple[ExplanationSection, ...]
    evidence_role: Literal["actor-visible", "oracle/evaluation", "derived training data", "provenance"]
    source_fields: tuple[str, ...]
    theory: TheoryReferences | None = None
    external_references: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.question.strip() or not self.answer.strip() or not self.source_fields:
            raise ValueError("Scientific explanations require a question, answer, and source fields.")
        if not self.sections or any(not section.title.strip() or not section.body.strip() for section in self.sections):
            raise ValueError("Scientific explanations require ordered nonempty narrative sections.")


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
    with col_info.popover("Interpret this plot", icon="ℹ️"):
        if explanation.answer:
            explanation_item("Answer", explanation.answer)
            for section in explanation.sections:
                explanation_item(section.title, section.body)
        explanation_item("Question", explanation.question)
        if log_y_key is not None:
            explanation_item(
                "Axis scale",
                "Linear by default. Logarithmic scale is independently selectable for this plot and hides zero or negative observations.",
            )
        if explanation.theory is not None:
            try:
                resolved = resolve_theory(explanation.theory)
                if resolved.equations:
                    st.markdown("**Canonical equations**")
                    for item in resolved.equations:
                        st.caption(item.identifier)
                        st.latex(item.tex)
                        if item.description:
                            st.markdown(item.description)
                        st.markdown(f"[Notation source]({item.source_url})")
                if resolved.symbols:
                    st.markdown("**Symbols**")
                    for item in resolved.symbols:
                        description = f" — {item.description}" if item.description else ""
                        st.markdown(f"`${item.identifier}`: ${item.tex}${description}")
                        st.markdown(f"[Symbol source]({item.source_url})")
                if resolved.terms:
                    st.markdown("**Glossary**")
                    for item in resolved.terms:
                        st.markdown(f"**{item.label}** — {item.definition}")
                        st.markdown(f"[Glossary source]({item.source_url})")
            except TheoryResolutionError as exc:
                st.warning(f"Canonical theory unavailable: {type(exc).__name__}: {exc}")
        if explanation.external_references:
            explanation_item(
                "External sources", "\n\n".join(f"[{label}]({url})" for label, url in explanation.external_references)
            )
        if explanation.source_fields:
            explanation_item("Sources", ", ".join(explanation.source_fields), code=True)
    rendered = fig
    if log_y_key is not None:
        with columns[2]:
            rendered, _ = _plot_with_y_axis_control(fig, key=log_y_key)
    st.plotly_chart(rendered, width="stretch")


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
