"""Shared presentation and error-reporting helpers for Streamlit panels."""

from __future__ import annotations

import re
import traceback
from dataclasses import asdict

import plotly.graph_objects as go
import streamlit as st

from ...data_handling.vin_store.diagnostics import VinOfflineDatasetStats
from ...utils.reporting import _pretty_label
from ..scientific_labels import (
    LabelSurface,
    TheoryResolutionError,
    format_identifier,
    format_scientific_label,
    scientific_label,
)
from ..state import get_label_display_mode

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


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


def current_scientific_label(identifier: str, *, surface: LabelSurface = "plain") -> str:
    """Format a canonical scientific label using the app-wide display mode."""

    label = scientific_label(identifier)
    try:
        return format_scientific_label(label, mode=get_label_display_mode(), surface=surface)
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


def _offline_summary_rows(stats: VinOfflineDatasetStats) -> list[dict[str, object]]:
    """Return the shared aggregate rows for VIN offline diagnostics."""

    return [
        {"metric": "candidate_count", **asdict(stats.candidate_count)},
        {"metric": "rri", **asdict(stats.rri)},
        {"metric": "vin_points", **asdict(stats.vin_points)},
    ]


__all__ = [
    "_info_popover",
    "_offline_summary_rows",
    "_plot_with_y_axis_control",
    "_pretty_label",
    "_report_exception",
    "_strip_ansi",
    "current_scientific_label",
    "render_scientific_notation",
]
