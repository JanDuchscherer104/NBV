"""Shared presentation and error-reporting helpers for Streamlit panels."""

from __future__ import annotations

import re
import traceback
from dataclasses import asdict

import streamlit as st

from ...data_handling.vin_store.diagnostics import VinOfflineDatasetStats
from ...utils.reporting import _pretty_label

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _info_popover(label: str, text: str) -> None:
    with st.popover(f"Info: {label.title()}", icon="ℹ️"):
        st.markdown(text, unsafe_allow_html=True)


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
    "_pretty_label",
    "_report_exception",
    "_strip_ansi",
]
