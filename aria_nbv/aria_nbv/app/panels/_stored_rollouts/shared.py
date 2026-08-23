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

from ..common import _plot_with_y_axis_control

_ROLE_COLORS = {
    "actor-visible": "#1f77b4",
    "oracle/evaluation": "#d62728",
    "derived training data": "#9467bd",
    "provenance": "#6b7280",
}


@dataclass(frozen=True, slots=True)
class ScientificExplanation:
    """Complete interpretation contract shown beside one primary visualization."""

    question: str
    population: str
    metric: str
    denominator_masks: str
    comparability: str
    expected_pattern: str
    failure_interpretation: str
    evidence_role: Literal["actor-visible", "oracle/evaluation", "derived training data", "provenance"]
    source_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        required = (
            self.question,
            self.population,
            self.metric,
            self.denominator_masks,
            self.comparability,
            self.expected_pattern,
            self.failure_interpretation,
        )
        if any(not value.strip() for value in required) or not self.source_fields:
            raise ValueError("Scientific explanations require every interpretation field and at least one source.")


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
    with col_info.popover("How to read this", icon="ℹ️"):
        for label, value in (
            ("Question", explanation.question),
            ("Population / grain", explanation.population),
            ("Metric / units", explanation.metric),
            ("Denominator / masks", explanation.denominator_masks),
            ("Valid comparison conditions", explanation.comparability),
            ("Expected pattern", explanation.expected_pattern),
            ("Warnings / failure modes", explanation.failure_interpretation),
        ):
            explanation_item(label, value)
        if log_y_key is not None:
            explanation_item(
                "Axis scale",
                "Linear by default. Logarithmic scale is independently selectable for this plot and hides zero or negative observations.",
            )
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
