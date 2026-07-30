"""Audited exact-pair oracle headroom and learned-planner effects."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .session import StoredRolloutSession
from .shared import _download_frame, _info_popover

_HEADROOM_INFO = r"""
Exact pre-treatment pairs estimate
(\Delta_{\mathrm{look}}=J(\pi_{oracle-look})-J(\pi_{oracle-1})) and
(\Delta_Q=J(\pi_Q)-J(\pi_{learned-1})). Scenes are the top-level sampling
unit; every exact within-scene pair is retained and cluster intervals are
eligible only at the frozen scene gate.

Recovered headroom is
(\eta_Q=\Delta_Q/[J(\pi_{oracle-look})-J(\pi_{learned-1})]). There is no
epsilon in this denominator. The ratio is emitted only above the frozen
positive-headroom threshold; weak/nonpositive denominators remain explicit
exclusions. Missing roles, mismatched context/checkpoints, failed audit rows,
and wrong-store artifacts block inference. Selected rank/regret describes the
same valid action table and never establishes generator causality.
"""


def render(session: StoredRolloutSession) -> None:
    """Render only independently audited exact-pair policy evidence."""

    st.subheader("Oracle Headroom & Policies")
    _info_popover("Exact pairing, scene gate, and headroom theory", _HEADROOM_INFO)
    audit = session.audit_state()
    evidence = session.audited_policy_effects()
    if not bool(evidence.get("available")):
        st.warning(
            "Δlook is blocked and ηQ is blocked: audited policy effects are unavailable; "
            "no persisted pooled headroom estimate is substituted."
        )
        blockers = pd.DataFrame(evidence.get("blocker_rows", [{"reason": value} for value in audit.blockers]))
        if not blockers.empty:
            st.dataframe(blockers, hide_index=True, width="stretch")
        return

    summaries = pd.DataFrame(evidence.get("summary_rows", []))
    pairs = pd.DataFrame(evidence.get("pair_rows", []))
    scenes = pd.DataFrame(evidence.get("scene_rows", []))
    exclusions = pd.DataFrame(evidence.get("exclusion_rows", []))
    denominators = pd.DataFrame(evidence.get("headroom_denominator_rows", []))
    st.caption(
        f"Audit {audit.artifact_status}/{audit.readiness}; scene CI gate: "
        f"{evidence.get('min_scenes_for_cluster_ci')} scenes; eta_Q threshold: "
        f"{evidence.get('eta_headroom_threshold')} (epsilon-free)."
    )
    st.markdown("#### ΔQ, Δlook, and ηQ summaries")
    st.dataframe(summaries, hide_index=True, width="stretch")
    st.markdown("#### Headroom denominator and exact exclusions")
    st.dataframe(denominators, hide_index=True, width="stretch")
    if not exclusions.empty:
        st.dataframe(exclusions, hide_index=True, width="stretch")
    with st.expander("Exact pair and scene-macro rows", expanded=False):
        st.dataframe(pairs, hide_index=True, width="stretch")
        st.dataframe(scenes, hide_index=True, width="stretch")
    _download_frame("Download audited policy summary CSV", "audited-policy-effects.csv", summaries)
    _download_frame("Download exact policy pairs CSV", "audited-policy-pairs.csv", pairs)
    rank_key = f"stored_oracle_rank:{session.identity}"
    if st.button("Load selected-action rank and regret evidence", key=f"{rank_key}:load"):
        st.session_state[rank_key] = True
    if st.session_state.get(rank_key, False):
        ranks = pd.DataFrame(session.selected_candidate_ranks())
        with st.expander("Selected-action rank and regret on the same valid action table", expanded=True):
            if ranks.empty:
                st.info("Selected rank/regret evidence is unavailable for this store.")
            else:
                st.dataframe(ranks, hide_index=True, width="stretch")
                _download_frame("Download selected rank/regret CSV", "selected-rank-regret.csv", ranks)


__all__ = ["render"]
