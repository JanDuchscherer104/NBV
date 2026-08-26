"""Read-only W&B presentation for immutable performance-goal evidence."""

from __future__ import annotations

from collections.abc import Iterable

import streamlit as st

from ...utils.wandb_utils import WandbRun, build_autoresearch_run_dataframe


def render_autoresearch_panel(runs: Iterable[WandbRun]) -> None:
    """Render bridge-produced evidence without fetching mutable run histories."""
    evidence = build_autoresearch_run_dataframe(runs)
    if evidence.empty:
        return
    st.subheader("Autoresearch")
    st.caption("Immutable evaluator evidence mirrored from performance-goal checkpoints.")
    st.dataframe(evidence, hide_index=True, width="stretch")
