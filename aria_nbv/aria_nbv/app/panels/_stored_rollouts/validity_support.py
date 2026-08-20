"""Target-admission and support presentation."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from ....rollouts import RolloutZarrStoreReader
from .candidate_generation import (
    _render_candidate_aggregate_breakdowns,
    _render_candidate_geometry_diagnostics,
    _render_candidate_population_evidence,
    _render_candidate_provenance_flow,
    _render_target_score_diagnostics,
)
from .session import _cached_projection
from .shared import ScientificExplanation
from .shared import download_frame as _download_frame
from .shared import render_plot as _render_plot


def _render_targets_and_support(reader: RolloutZarrStoreReader) -> None:
    st.subheader("Targets and action support")
    store_path = reader.store_dir.as_posix()
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
    targets = pd.DataFrame(_cached_projection(store_path, "targets"))
    if not targets.empty:
        protocol = (
            targets.groupby(["target_valid", "gt_label_valid", "gt_match_status"], dropna=False)
            .size()
            .reset_index(name="count")
        )
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
                population="One persisted target row grouped by actor task validity, GT-label validity, and match status.",
                metric="Target count; no scientific effect units.",
                denominator_masks="All target rows; neither invalid population is silently removed.",
                comparability="Compare target protocols only when target selection and GT matching configuration agree.",
                expected_pattern="Actor-valid targets may lack GT labels, but such rows remain masked from oracle-label training.",
                failure_interpretation="Actor-valid/GT-invalid concentration signals evaluation coverage gaps, not low RRI.",
                evidence_role="oracle/evaluation",
                answer="The admission bars show whether actor-valid targets also have an unambiguous privileged label; they do not turn rejected targets into low-reward examples.",
                intuition="Actor validity answers whether the action can be executed, while GT-label validity answers whether privileged evaluation is available; these are distinct masks.",
                visual_encoding="Bar height is the persisted target count; color and pattern separate actor validity and GT-label validity within each match-status category.",
                uncertainty="All target rows remain in the denominator, including ambiguous, unmatched, and invalid rows; counts describe protocol coverage rather than effect size.",
                external_references=(
                    (
                        "Canonical ARIA-NBV RRI definition",
                        "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/docs/typst/shared/equations/rri.typ",
                    ),
                ),
                source_fields=(
                    "targets/target_valid_mask",
                    "targets/gt_label_valid_mask",
                    "targets/gt_match_status_id",
                ),
            ),
        )
        _download_frame("Download target protocol CSV", "target-protocol.csv", targets)
        _render_target_score_diagnostics(targets)

    _render_candidate_provenance_flow(store_path)

    masks = pd.DataFrame(_cached_projection(store_path, "masks"))
    if not masks.empty:
        label_cols = [c for c in ("actor_action", "oracle_label", "q_train", "selected") if c in masks]
        masks["combination"] = masks[label_cols].astype(str).agg(" · ".join, axis=1)
        fig = px.bar(masks, x="combination", y="count", title="Observed candidate-mask combinations")
        _render_plot(
            fig,
            ScientificExplanation(
                question="Which actor, oracle, training, and selection mask combinations actually occur?",
                population="One candidate row summarized by its exact four-mask bit pattern.",
                metric="Candidate count and fraction of the full sampled shell.",
                denominator_masks="All persisted candidate rows; selected must imply actor_action, while q_train is not a selection stage.",
                comparability="Compare stores only under the same candidate-shell generation and label-availability protocol.",
                expected_pattern="No selected/actor_action violation; selected-but-not-q_train may legitimately occur.",
                failure_interpretation="A selected actor-invalid row is a hard contract failure; missing q_train is a label/cache issue, not invalid action support.",
                evidence_role="derived training data",
                source_fields=("candidates/actor_action_mask", "oracle_label_mask", "q_train_mask", "selected_mask"),
            ),
        )
        st.dataframe(masks.drop(columns="combination"), hide_index=True, width="stretch")
        _download_frame(
            "Download mask combinations CSV", "candidate-mask-combinations.csv", masks.drop(columns="combination")
        )

    if st.toggle(
        "Load complete candidate aggregate breakdowns",
        value=False,
        help="Builds the heavyweight candidate audit used by the restored family, mask-population, and invalid-reason tables.",
    ):
        _render_candidate_aggregate_breakdowns(store_path)

    if st.toggle(
        "Load cohort composition, proposal calibration, and collision support",
        value=False,
        help="Materializes the complete candidate audit only after this explicit request and reuses its cached rows.",
    ):
        _render_candidate_population_evidence(store_path)

    candidate_rows = _cached_projection(store_path, "candidates", limit=candidate_plot_limit)
    _render_candidate_geometry_diagnostics(
        pd.DataFrame(candidate_rows),
        pd.DataFrame(candidate_rows),
        total_candidates=int(reader.array("candidates/candidate_row_id").size),
    )
