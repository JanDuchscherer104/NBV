"""Shared target-selection tables and plots for actor/oracle boundary audits.

The helpers provide actor-visible score decomposition and hard invalidity
reasons alongside separately labeled GT-match fields used only for oracle
labels and evaluation.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd
import plotly.express as px
import streamlit as st

from ...data_handling import TARGET_INVALID_REASON_CODES, TargetCandidateRow

_TARGET_REASON_NAMES = {int(code): name for name, code in TARGET_INVALID_REASON_CODES.items()}


def decode_target_invalid_reason(reason: int) -> str:
    """Return the stable target-invalidity reason name for one code."""

    return _TARGET_REASON_NAMES.get(int(reason), f"target_reason_{int(reason)}")


def target_selection_audit_rows(rows: Iterable[TargetCandidateRow]) -> list[dict[str, object]]:
    """Return target-selection rows with score decomposition fields."""

    output: list[dict[str, object]] = []
    for row in rows:
        output.append(
            {
                "target_row_id": int(row.target_row_id),
                "selected_rank": row.selected_rank,
                "class": row.class_name,
                "sem_id": int(row.sem_id),
                "inst_id": int(row.inst_id),
                "confidence": float(row.confidence),
                "projected_area_px": float(row.projected_area_pixels),
                "projected_fraction": float(row.projected_area_fraction),
                "visibility_score": float(row.visibility_score),
                "semidense_support": int(row.semidense_support_count),
                "evl_support": int(row.evl_support_count),
                "effective_support": float(row.effective_support_count),
                "support_score": float(row.support_score),
                "deficit_score": float(row.deficit_score),
                "selection_score": None if not pd.notna(row.score) else float(row.score),
                "eligible": bool(row.eligible),
                "invalid_reason": decode_target_invalid_reason(row.primary_invalid_reason),
                "selection_probability": row.selection_probability,
                "gt_label_valid": bool(row.gt_label_valid),
                "gt_match_status": row.gt_match_status,
                "gt_iou": row.gt_match_iou,
                "gt_match_score": row.gt_match_score,
            }
        )
    return output


def render_target_selection_audit(rows: Iterable[TargetCandidateRow], *, title: str = "Target Selection Audit") -> None:
    """Render target-selection score decomposition and GT-match audit fields."""

    table_rows = target_selection_audit_rows(rows)
    if not table_rows:
        st.info("No target rows are available for target-selection audit.")
        return
    st.subheader(title)
    df = pd.DataFrame(table_rows)
    missing_projection = df["projected_area_px"].fillna(0.0) <= 0.0
    if bool(missing_projection.any()):
        fallback_values = sorted(
            {
                float(value)
                for value in df.loc[missing_projection, "visibility_score"].dropna().tolist()
                if float(value) > 0.0
            }
        )
        fallback_text = ", ".join(f"{value:.2f}" for value in fallback_values) if fallback_values else "0.00"
        st.warning(
            "Some actor-visible target rows have `projected_area_px=0` because the selected OBB source does not "
            "carry valid EFM 2D boxes (`bb2_rgb`, `bb2_slaml`, or `bb2_slamr`) for those targets. The selector keeps "
            f"otherwise supported targets by applying the configured missing-projection visibility fallback ({fallback_text}) "
            "unless projected visibility is required."
        )
    st.dataframe(df, width="stretch", hide_index=True)

    chart_rows = df.copy()
    chart_rows["target"] = chart_rows["target_row_id"].astype(str) + " · " + chart_rows["class"].astype(str)
    chart_cols = st.columns(2)
    with chart_cols[0]:
        st.plotly_chart(
            px.bar(
                chart_rows,
                x="target",
                y=["confidence", "visibility_score", "support_score", "deficit_score"],
                barmode="group",
                title="Target Score Factors",
            ),
            width="stretch",
        )
    with chart_cols[1]:
        st.plotly_chart(
            px.scatter(
                chart_rows,
                x="effective_support",
                y="selection_score",
                color="gt_match_status",
                symbol="eligible",
                hover_data=["target_row_id", "class", "projected_area_px", "invalid_reason"],
                title="Selection Score vs Actor-Visible Support",
            ),
            width="stretch",
        )


__all__ = [
    "decode_target_invalid_reason",
    "render_target_selection_audit",
    "target_selection_audit_rows",
]
