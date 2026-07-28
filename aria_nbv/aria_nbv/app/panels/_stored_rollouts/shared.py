"""Shared immutable-store caches and rendering primitives for rollout sections."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

_ROLE_COLORS = {
    "actor-visible": "#1f77b4",
    "oracle/evaluation": "#d62728",
    "derived training data": "#9467bd",
    "provenance": "#6b7280",
}
_SECTION_KEY = "stored_rollouts_section"
_LAUNCH_HANDLE_KEY = "stored_rollouts_rerun_handle"
_PLOT_LABEL_OVERRIDES = {
    "eta_q": "ηQ",
    "q_h": "QH",
    "q25": "25th Percentile",
    "q75": "75th Percentile",
    "rri": "RRI",
    "step_index": "Rollout Step",
    "xy": "XY",
}


def _format_plot_label(value: object) -> str:
    """Convert persisted field names and categorical values into compact display labels."""

    text = str(value).strip()
    if not text:
        return text
    if text in _PLOT_LABEL_OVERRIDES:
        return _PLOT_LABEL_OVERRIDES[text]
    words = re.sub(r"[_-]+", " ", text).split()
    formatted = " ".join(word if word.isupper() or word.isdigit() else word.capitalize() for word in words)
    return formatted.replace("Q H", "QH").replace("Rri", "RRI")


def _apply_plot_style(fig: go.Figure) -> None:
    """Apply the stored-rollout visual vocabulary without altering plotted data."""

    fig.update_layout(font={"size": 18}, title_font={"size": 26}, legend_font={"size": 16})
    if fig.layout.title.text:
        fig.layout.title.text = _format_plot_label(fig.layout.title.text)
    if fig.layout.legend.title.text:
        fig.layout.legend.title.text = _format_plot_label(fig.layout.legend.title.text)
    for annotation in fig.layout.annotations:
        text = str(annotation.text)
        annotation.text = _format_plot_label(text.partition("=")[2] if "=" in text else text)
        annotation.font = {"size": 18}
    for trace in fig.data:
        if trace.name:
            trace.name = _format_plot_label(trace.name)
    for axis in (*fig.select_xaxes(), *fig.select_yaxes()):
        axis.tickfont = {"size": 16}
        if axis.title.text:
            axis.title.text = _format_plot_label(axis.title.text)
            axis.title.font = {"size": 20}


def _render_stale_store_boundary(
    validation: Any, *, inventory_row: dict[str, object] | None, manifest_payload: dict[str, Any]
) -> None:
    st.warning(
        "Scientific evidence and Rerun are disabled because this store does not pass the current schema contract."
    )
    for error in getattr(validation, "errors", ()):
        st.error(str(error))
    payload = {
        "inventory": inventory_row,
        **manifest_payload,
        "validation_errors": list(getattr(validation, "errors", ())),
    }
    _download_json("Download stale-store diagnostics JSON", "stale-rollout-store.json", payload)


def _render_plot(fig: go.Figure) -> None:
    """Render one consistently styled Plotly figure without changing its evidence."""

    _apply_plot_style(fig)
    st.plotly_chart(fig, width="stretch")


def _info_popover(label: str, content: str) -> None:
    """Render free-form conceptual context for one coherent page section."""

    with st.popover(label, icon="ℹ️"):
        st.markdown(content)


def _download_frame(label: str, file_name: str, frame: pd.DataFrame) -> None:
    """Offer a complete filtered CSV without registering eager media URLs."""

    st.download_button(
        label,
        data=lambda: _serialize_frame_csv(frame),
        file_name=file_name,
        mime="text/csv",
        on_click="ignore",
        help="Materialized lazily on click so tab reruns do not retain stale media URLs.",
    )
    st.caption(f"Export rows: {len(frame):,} (complete filtered dataset).")


def _download_json(label: str, file_name: str, payload: object) -> None:
    """Offer deterministic JSON without registering eager media URLs."""

    st.download_button(
        label,
        data=lambda: _serialize_json(payload),
        file_name=file_name,
        mime="application/json",
        on_click="ignore",
        help="Materialized lazily on click so tab reruns do not retain stale media URLs.",
    )


def _serialize_frame_csv(frame: pd.DataFrame) -> bytes:
    """Serialize every dataframe row in deterministic displayed column order."""

    csv_text = frame.to_csv(index=False)
    if not isinstance(csv_text, str):
        raise TypeError("DataFrame CSV serialization did not return text.")
    return csv_text.encode("utf-8")


def _serialize_json(payload: object) -> bytes:
    """Serialize one payload as stable, indented UTF-8 JSON."""

    return json.dumps(payload, indent=2, sort_keys=True, default=_json_default).encode("utf-8") + b"\n"


def _json_default(value: object) -> object:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, np.generic):
        return value.item()
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return str(value)


__all__ = [
    "_LAUNCH_HANDLE_KEY",
    "_ROLE_COLORS",
    "_SECTION_KEY",
    "_apply_plot_style",
    "_download_frame",
    "_download_json",
    "_format_plot_label",
    "_info_popover",
    "_render_plot",
    "_render_stale_store_boundary",
]
