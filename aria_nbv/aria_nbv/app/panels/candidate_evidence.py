"""Render retained candidate plot models without scientific recomputation."""

from __future__ import annotations

import streamlit as st

from ..candidate_evidence import CandidateEvidenceView


def render_candidate_evidence_view(view: CandidateEvidenceView, *, key: str) -> None:
    """Render only the active retained candidate plot.

    Args:
        view: Immutable snapshots and already-built plot models. The renderer
            never reads a store or invokes a candidate/scientific reducer.
        key: Page-scoped stable widget identity.

    Dynamic Streamlit tabs ensure hidden Plotly payloads are not deserialized
    on each rerun. The visible model is reconstructed only from canonical JSON
    retained in :class:`~aria_nbv.rollouts.candidate_plotting.CandidatePlotModel`.
    """

    tabs = st.tabs(
        [model.title for model in view.plot_models],
        key=f"{key}:plots",
        on_change="rerun",
        width="stretch",
    )
    for tab, model in zip(tabs, view.plot_models, strict=True):
        if not tab.open:
            continue
        with tab:
            st.caption(
                "Retained candidate snapshot · switching plots does not reread the store or regenerate candidates."
            )
            st.plotly_chart(
                model.build_figure(),
                width="stretch",
                key=f"{key}:{model.key}",
            )


__all__ = ["render_candidate_evidence_view"]
