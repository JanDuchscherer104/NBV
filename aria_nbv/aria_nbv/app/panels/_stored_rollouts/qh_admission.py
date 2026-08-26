"""Store-local Q_H evidence presentation.

Corpus construction remains on the Training Dataset page.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from .s2_directions import render_s2_direction_histograms as _render_s2_direction_histograms
from .shared import download_frame as _download_frame


def _render_q_h_evidence(session_handle: Any) -> None:
    """Render metadata-only Q_H facts and gate mask counts behind an explicit toggle."""

    st.markdown("#### Store-local Q_H evidence")
    deep_count = st.toggle(
        "Count current-store Q_H masks",
        value=False,
        help="Off reads metadata only. On performs the bounded current-store mask projection.",
    )
    chunk_size = int(
        st.number_input(
            "Q_H state chunk size",
            min_value=1,
            value=1024,
            step=256,
            disabled=not deep_count,
            help="Bounded Zarr read size used by the optional Q_H mask count.",
        )
    )
    state_limit_value = st.number_input(
        "Q_H state-row limit (0 = full store)",
        min_value=0,
        value=0,
        step=1024,
        disabled=not deep_count,
        help="Optional bounded prefix for diagnostics; 0 counts all persisted Q_H states.",
    )
    state_limit = None if int(state_limit_value) == 0 else int(state_limit_value)
    if not deep_count:
        evidence_rows = session_handle.q_h(deep_count=False)
    else:
        cancel_key = f"q_h_cancel:{session_handle.canonical_path.as_posix()}"
        stop_requested = bool(
            st.checkbox(
                "Stop after the current Q_H chunk",
                value=bool(st.session_state.get(cancel_key, False)),
                key=cancel_key,
                help="Cancellation is observed at the next bounded chunk boundary.",
            )
        )
        progress = st.progress(0.0, text="Preparing bounded Q_H count…")
        status = st.empty()

        def update_progress(completed: int, total: int) -> bool:
            fraction = 1.0 if total <= 0 else min(1.0, float(completed) / float(total))
            progress.progress(fraction, text=f"Q_H count: {completed:,}/{total:,} state rows")
            status.caption(
                "Stop requested; finishing the current chunk." if stop_requested else "Reading bounded Q_H slices…"
            )
            return not stop_requested

        evidence_rows = session_handle.q_h_progressive(
            chunk_size=chunk_size,
            state_row_limit=state_limit,
            progress_callback=update_progress,
        )
        evidence = evidence_rows[0] if evidence_rows else {}
        if str(evidence.get("count_reason", "")).startswith("cancelled"):
            status.caption("Q_H count stopped at a chunk boundary.")
        elif bool(evidence.get("truncated")):
            status.caption("Q_H bounded-prefix count complete.")
        else:
            status.caption("Q_H full-store count complete.")
    rows = pd.DataFrame(evidence_rows)
    st.dataframe(rows, hide_index=True, width="stretch")
    if not rows.empty and not bool(rows.iloc[0].get("available", False)):
        st.info(f"Q_H evidence unavailable: {rows.iloc[0].get('blocking_reason', 'unknown reason')}")
    _download_frame("Download Q_H evidence CSV", "q-h-evidence.csv", rows)
    _render_s2_direction_histograms(session_handle, key_prefix="stored_rollouts_qh")
