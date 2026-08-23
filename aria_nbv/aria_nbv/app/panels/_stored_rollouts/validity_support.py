"""Target-admission and support presentation."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from ...scientific_labels import TheoryReferences
from .candidate_generation import (
    _render_candidate_aggregate_breakdowns,
    _render_candidate_geometry_diagnostics,
    _render_candidate_population_evidence,
    _render_candidate_provenance_flow,
    _render_target_score_diagnostics,
)
from .shared import ExplanationSection, ScientificExplanation
from .shared import download_frame as _download_frame
from .shared import render_plot as _render_plot


def _render_bounded_candidate_geometry(session_handle: object, *, limit: int) -> None:
    """Render geometry from one identity-bound, bounded candidate read."""

    candidates = pd.DataFrame(session_handle.candidates(limit=limit))
    proposal = session_handle.proposal_geometry(limit=limit)
    _render_candidate_geometry_diagnostics(
        candidates,
        proposal,
        session_handle.trajectory_geometry(),
        total_candidates=int(session_handle.validation.num_candidates),
    )


def _render_targets_and_support(session_handle: object) -> None:
    st.subheader("Targets and action support")
    candidate_plot_limit = int(
        st.number_input(
            "Candidate plot row limit",
            min_value=1_000,
            max_value=500_000,
            value=50_000,
            step=10_000,
            help="Bounds interactive geometry traces only; aggregate masks and family counts still use the full store.",
        )
    )
    targets = pd.DataFrame(session_handle.targets())
    if not targets.empty:
        required_protocol_fields = {"target_valid", "gt_label_valid", "gt_match_status"}
        missing_protocol_fields = sorted(required_protocol_fields.difference(targets.columns))
        if missing_protocol_fields:
            st.warning(
                "Target-admission plot unavailable: the selected store does not expose the current target audit "
                f"fields ({', '.join(missing_protocol_fields)}). Raw target evidence remains available below."
            )
            protocol = pd.DataFrame()
        else:
            protocol = targets.groupby(sorted(required_protocol_fields), dropna=False).size().reset_index(name="count")
        if not protocol.empty:
            fig = px.bar(
                protocol,
                x="gt_match_status",
                y="count",
                color="target_valid",
                pattern_shape="gt_label_valid",
                title="Target protocol: actor validity × GT-label validity",
            )
            _render_plot(
                fig,
                ScientificExplanation(
                    question="Are actor target choices and privileged GT evaluation labels being kept distinct?",
                    answer="Actor task validity and privileged GT-label validity are separate masks, so an actor-valid target is not silently treated as trainable.",
                    sections=(
                        ExplanationSection(
                            "Population and metric",
                            "Rows are grouped by actor validity, GT-label validity, and match status; the metric is a count, not an effect size.",
                        ),
                        ExplanationSection(
                            "Denominator and comparison",
                            "All target rows remain in the denominator. Compare protocols only when target selection and GT matching agree.",
                        ),
                        ExplanationSection(
                            "Expected pattern and warning",
                            "Actor-valid targets may lack GT labels and remain masked from oracle training; concentration of such rows indicates evaluation coverage gaps.",
                        ),
                    ),
                    evidence_role="oracle/evaluation",
                    source_fields=(
                        "targets/target_valid_mask",
                        "targets/gt_label_valid_mask",
                        "targets/gt_match_status_id",
                    ),
                ),
            )
        _download_frame("Download target protocol CSV", "target-protocol.csv", targets)
        _render_target_score_diagnostics(targets)

    _render_candidate_provenance_flow(session_handle)

    masks = pd.DataFrame(session_handle.masks())
    if not masks.empty:
        label_cols = [c for c in ("actor_action", "oracle_label", "q_train", "selected") if c in masks]
        if "count" not in masks.columns or not label_cols:
            st.warning(
                "Candidate mask-combination plot unavailable: the selected store exposes no grouped mask counts. "
                "The validated store summary remains available in the raw evidence export."
            )
        else:
            masks["combination"] = masks[label_cols].astype(str).agg(" · ".join, axis=1)
            fig = px.bar(masks, x="combination", y="count", title="Observed candidate-mask combinations")
            _render_plot(
                fig,
                ScientificExplanation(
                    question="Which actor, oracle, training, and selection mask combinations actually occur?",
                    answer="The mask combinations expose the boundary between actor admissibility, oracle labels, trainability, and realized selection.",
                    sections=(
                        ExplanationSection(
                            "Population and metric",
                            "Each candidate row contributes its exact four-mask pattern and count within the complete sampled shell.",
                        ),
                        ExplanationSection(
                            "Denominator and comparison",
                            "All persisted rows are retained; selection must imply actor action validity, while q_train is not a selection stage. Compare only matched shell and label protocols.",
                        ),
                        ExplanationSection(
                            "Expected pattern and warning",
                            "Selected actor-invalid rows are hard contract failures. Selected-but-not-q_train rows can be valid when labels are unavailable.",
                        ),
                    ),
                    evidence_role="derived training data",
                    source_fields=(
                        "candidates/actor_action_mask",
                        "oracle_label_mask",
                        "q_train_mask",
                        "selected_mask",
                    ),
                    theory=TheoryReferences(
                        equation_ids=("rl.masked_candidate_selection",),
                        symbol_ids=("rl.validity_mask",),
                        term_ids=("validity-mask",),
                    ),
                ),
            )
        st.dataframe(masks.drop(columns="combination", errors="ignore"), hide_index=True, width="stretch")
        _download_frame(
            "Download mask combinations CSV",
            "candidate-mask-combinations.csv",
            masks.drop(columns="combination", errors="ignore"),
        )

    if st.toggle(
        "Load complete candidate aggregate breakdowns",
        value=False,
        help="Builds the heavyweight candidate audit used by the restored family, mask-population, and invalid-reason tables.",
    ):
        _render_candidate_aggregate_breakdowns(session_handle)

    if st.toggle(
        "Load complete candidate-family lineage and choice evidence",
        value=False,
        help=(
            "Materializes the complete candidate audit only after this explicit request. "
            "The resulting surface exposes allocation share, valid share, policy mass, realized selection, "
            "and expected-versus-realized family transitions with exact contract controls and pooled temperatures."
        ),
    ):
        _render_candidate_population_evidence(session_handle)

    with st.expander(
        "Bounded candidate geometry and reward plots",
        expanded=True,
    ):
        st.caption(
            "Bounded preview is loaded automatically from the validated candidate shell; "
            "the explicit heavy population audit above remains opt-in."
        )
        _render_bounded_candidate_geometry(session_handle, limit=candidate_plot_limit)
