"""Shared presentation and error-reporting helpers for Streamlit panels."""

from __future__ import annotations

import hashlib
import html
import json
import re
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ...data_handling.vin_store.diagnostics import VinOfflineDatasetStats
from ...utils.reporting import _pretty_label
from ..scientific_labels import (
    LabelSurface,
    TheoryReferences,
    TheoryResolutionError,
    format_identifier,
    format_scientific_label,
    resolve_theory,
    scientific_label,
)
from ..state import get_label_display_mode

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

EvidenceRole = Literal["actor-visible", "oracle/evaluation", "derived training data", "provenance"]

_ROLE_COLORS: dict[EvidenceRole, str] = {
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

    def __post_init__(self) -> None:
        if not self.title.strip() or not self.body.strip():
            raise ValueError("Explanation sections require nonempty titles and bodies.")


@dataclass(frozen=True, slots=True)
class ScientificExplanation:
    """Narrative interpretation contract shown beside one primary visualization."""

    question: str
    answer: str
    sections: tuple[ExplanationSection, ...]
    evidence_role: EvidenceRole
    source_fields: tuple[str, ...]
    theory: TheoryReferences | None = None
    external_references: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.question.strip() or not self.answer.strip() or not self.source_fields:
            raise ValueError("Scientific explanations require a question, answer, and source fields.")
        if any(not field.strip() for field in self.source_fields):
            raise ValueError("Scientific explanations require nonempty source fields.")
        if any(not label.strip() or not url.strip() for label, url in self.external_references):
            raise ValueError("External theory references require nonempty labels and URLs.")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _info_popover(label: str, text: str) -> None:
    with st.popover(f"Info: {label.title()}", icon="ℹ️"):
        st.markdown(text, unsafe_allow_html=True)


def _plot_with_y_axis_control(fig: go.Figure, *, key: str) -> tuple[go.Figure, bool]:
    """Copy a figure and apply one independently keyed linear/log y-axis control.

    Logarithmic Plotly axes do not display zero or negative observations. The
    control therefore keeps linear scale as the default and emits this caveat
    beside every opted-in plot.
    """

    logarithmic = st.toggle(
        "Logarithmic y-axis",
        value=False,
        key=key,
        help="Useful for positive values spanning orders of magnitude. Zero and negative values are not visible.",
    )
    rendered = go.Figure(fig)
    rendered.update_yaxes(type="log" if logarithmic else "linear")
    if logarithmic:
        st.caption("Logarithmic y-axis: zero and negative observations are not visible in this plot.")
    return rendered, logarithmic


def plot_control_key(plot_name: str, *identity: Any) -> str:
    """Return a stable widget key for one independently controlled plot."""

    payload = "\x1f".join((plot_name, *(str(value) for value in identity)))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"stored-rollout-plot:{plot_name}:{digest}"


def render_plot(
    fig: go.Figure,
    explanation: ScientificExplanation,
    *,
    log_y_key: str | None = None,
    selection_key: str | None = None,
) -> Any:
    """Render one explained Plotly figure with optional axis and point controls."""

    badge_color = _ROLE_COLORS[explanation.evidence_role]
    columns = st.columns([4, 1, 1]) if log_y_key is not None else st.columns([5, 1])
    col_title, col_info = columns[:2]
    col_title.markdown(
        f'<span style="padding:.15rem .45rem;border-radius:.35rem;background:{badge_color};color:white">'
        f"{html.escape(explanation.evidence_role)}</span>",
        unsafe_allow_html=True,
    )
    render_explanation_popover("Interpret this plot", explanation, log_y_key=log_y_key, container=col_info)
    rendered = fig
    if log_y_key is not None:
        with columns[2]:
            rendered, _ = _plot_with_y_axis_control(fig, key=log_y_key)
    return st.plotly_chart(
        rendered,
        width="stretch",
        key=selection_key,
        on_select="rerun" if selection_key is not None else "ignore",
        selection_mode="points",
    )


def render_explanation_popover(
    label: str,
    explanation: ScientificExplanation,
    *,
    log_y_key: str | None = None,
    container: Any | None = None,
) -> None:
    """Render one reusable scientific explanation popover in a Streamlit container."""

    owner = st if container is None else container
    with owner.popover(label, icon="ℹ️"):
        _render_scientific_guide(explanation, log_y_key=log_y_key)


def _render_scientific_guide(explanation: ScientificExplanation, *, log_y_key: str | None) -> None:
    st.markdown("### Core idea")
    explanation_item("Question", explanation.question)
    explanation_item("Answer", explanation.answer)
    _render_theory(explanation.theory)
    for section in explanation.sections:
        st.markdown(f"### {section.title}")
        st.markdown(section.body)
    if log_y_key is not None:
        explanation_item(
            "Axis scale",
            "Linear by default. Logarithmic scale is independently selectable for this plot and hides zero or negative observations.",
        )
    if explanation.external_references:
        st.markdown("### External sources")
        for label, url in explanation.external_references:
            st.markdown(f"- [{label}]({url})")
    explanation_item("Provenance", ", ".join(explanation.source_fields), code=True)


def _render_theory(theory: TheoryReferences | None) -> None:
    if theory is None:
        return
    try:
        resolved = resolve_theory(theory)
    except TheoryResolutionError as exc:
        st.warning(f"Canonical theory unavailable: {type(exc).__name__}: {exc}")
        return
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


def download_json(label: str, file_name: str, payload: Any) -> None:
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


def serialize_json(payload: Any) -> bytes:
    return json.dumps(payload, indent=2, sort_keys=True, default=json_default).encode("utf-8") + b"\n"


def json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, np.generic):
        return value.item()
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return str(value)


def current_scientific_label(identifier: str, *, surface: LabelSurface = "plain") -> str:
    """Format a canonical scientific label using the app-wide display mode."""

    label = scientific_label(identifier)
    try:
        return cast(str, format_scientific_label(label, mode=get_label_display_mode(), surface=surface))
    except TheoryResolutionError as exc:
        st.warning(f"Canonical notation is unavailable for {identifier!r}: {exc}")
        units = f" ({label.units})" if label.units else ""
        return f"{label.text or format_identifier(label.identifier)}{units}"


def render_scientific_notation(*identifiers: str) -> None:
    """Render canonical notation beside a chart without changing Plotly axes."""

    if get_label_display_mode() == "Text" or not identifiers:
        return
    st.caption(
        "**Notation:** "
        + " · ".join(current_scientific_label(identifier, surface="markdown") for identifier in identifiers)
    )


def _report_exception(exc: Exception, *, context: str) -> None:
    """Render a full traceback in the UI and emit it to stdout."""
    trace = traceback.format_exc()
    print(trace, flush=True)
    st.error(f"{context}: {type(exc).__name__}: {exc}")
    st.exception(exc)
    with st.expander("Full traceback", expanded=False):
        st.code(trace, language="text")


def _offline_summary_rows(stats: VinOfflineDatasetStats) -> list[dict[str, Any]]:
    """Return the shared aggregate rows for VIN offline diagnostics."""

    return [
        {"metric": "candidate_count", **asdict(stats.candidate_count)},
        {"metric": "rri", **asdict(stats.rri)},
        {"metric": "vin_points", **asdict(stats.vin_points)},
    ]


__all__ = [
    "EvidenceRole",
    "ExplanationSection",
    "ScientificExplanation",
    "_info_popover",
    "_offline_summary_rows",
    "_ROLE_COLORS",
    "_plot_with_y_axis_control",
    "_pretty_label",
    "_report_exception",
    "_strip_ansi",
    "current_scientific_label",
    "download_frame",
    "download_json",
    "explanation_item",
    "json_default",
    "plot_control_key",
    "render_explanation_popover",
    "render_plot",
    "render_scientific_notation",
    "serialize_frame_csv",
    "serialize_json",
]
