"""Shared presentation and error-reporting helpers for Streamlit panels.

The module provides ANSI cleanup, explanatory popovers, traceback rendering,
and selected reporting utilities re-exported for consistent page behavior.
"""

from __future__ import annotations

import re
import traceback

import streamlit as st

from ...utils.reporting import _linear_slope, _pretty_label, _segment_indices

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


__all__ = [
    "_info_popover",
    "_linear_slope",
    "_pretty_label",
    "_report_exception",
    "_segment_indices",
    "_strip_ansi",
]
