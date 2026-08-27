"""Render immutable report results without acquiring or recomputing evidence."""

from __future__ import annotations

import json

import pandas as pd
import plotly.io as pio
import streamlit as st

from ...reporting import ReportSnapshot
from .common import render_scientific_notation


def render_report_snapshot(
    snapshot: ReportSnapshot,
    *,
    key_prefix: str,
    show_quantities: bool = True,
    show_plotly_specifications: bool = False,
) -> None:
    """Render a sealed report transaction through a presentation-only adapter.

    This function performs no source reads, scientific reductions, or figure
    construction. Figures are reconstructed from the canonical Plotly JSON in
    ``snapshot``; tables and quantities are rendered from their immutable rows.
    """

    if show_quantities:
        for quantity in snapshot.quantities:
            label = quantity.symbol_id or quantity.id
            st.metric(label, quantity.value if quantity.value is not None else "—")
    for figure in snapshot.figures:
        st.subheader(figure.id)
        st.plotly_chart(
            pio.from_json(figure.plotly_json.decode("utf-8")),
            width="stretch",
            key=f"{key_prefix}:figure:{figure.id}",
        )
        render_scientific_notation(*figure.symbol_ids)
        if show_plotly_specifications:
            specification = st.expander(
                "Canonical Plotly specification",
                on_change="rerun",
                key=f"{key_prefix}:spec:{figure.id}",
            )
            if specification.open:
                with specification:
                    st.json(json.loads(figure.plotly_json))
    for table in snapshot.tables:
        expander = st.expander(table.id, on_change="rerun", key=f"{key_prefix}:table:{table.id}")
        if expander.open:
            with expander:
                st.dataframe(
                    pd.DataFrame(table.rows, columns=[column.id for column in table.columns]),
                    hide_index=True,
                    width="stretch",
                )


__all__ = ["render_report_snapshot"]
