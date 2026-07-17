"""Shared target-selection tables and plots for actor/oracle boundary audits.

The helpers provide actor-visible score decomposition and hard invalidity
reasons alongside separately labeled GT-match fields used only for oracle
labels and evaluation.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd
import streamlit as st

from ...oracle.target_selection import OracleTargetTask, TargetTaskIdentityStatus


def target_selection_audit_rows(rows: Iterable[OracleTargetTask]) -> list[dict[str, object]]:
    """Return compact Oracle target-task audit rows."""

    output: list[dict[str, object]] = []
    for row in rows:
        output.append(
            {
                "target_row_id": int(row.target_row_id),
                "selected_rank": row.selected_rank,
                "class": row.descriptor.class_name,
                "sem_id": int(row.descriptor.sem_id),
                "inst_id": int(row.inst_id),
                "confidence": float(row.confidence),
                "admitted": row.identity_status == TargetTaskIdentityStatus.MATCHED.value,
                "identity_status": row.identity_status,
                "selection_probability": row.selection_probability,
            }
        )
    return output


def render_target_selection_audit(rows: Iterable[OracleTargetTask], *, title: str = "Target Selection Audit") -> None:
    """Render Oracle task admission and sampling fields."""

    table_rows = target_selection_audit_rows(rows)
    if not table_rows:
        st.info("No target rows are available for target-selection audit.")
        return
    st.subheader(title)
    df = pd.DataFrame(table_rows)
    st.dataframe(df, width="stretch", hide_index=True)


__all__ = [
    "render_target_selection_audit",
    "target_selection_audit_rows",
]
