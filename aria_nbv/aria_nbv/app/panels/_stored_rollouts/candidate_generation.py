"""Candidate-generation provenance and aggregate evidence presentation."""

from __future__ import annotations

from collections import Counter
from itertools import pairwise
from typing import TypedDict

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ....rollouts.inspection import CANDIDATE_GROUP_FIELDS, GeometryProjection, ProposalAlignment
from ....utils.data_plotting import add_pose_axes_to_figure, configure_3d_scene
from ...scientific_labels import TheoryReferences
from ..common import current_scientific_label, render_scientific_notation
from .session import _cached_projection, _cached_store_bundle
from .shared import ExplanationSection, ScientificExplanation
from .shared import download_frame as _download_frame
from .shared import render_plot as _render_plot

_CORRELATION_REFERENCE = (
    "SciPy Pearson correlation documentation",
    "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.pearsonr.html",
)
_EVIDENCE_REPORTING_REFERENCE = (
    "ARRIVE reporting guidance for individual data and summaries",
    "https://arriveguidelines.org/arrive-guidelines/results/10a/explanation",
)
_PYTORCH3D_RENDERING_REFERENCE = (
    "PyTorch3D renderer concepts",
    "https://pytorch3d.org/docs/renderer_getting_started",
)


_CANDIDATE_POPULATIONS = ("Selected step", "Selected rollout", "Explicit full store")


class _PairwiseCorrelation(TypedDict):
    """Pair-local Pearson estimates and auditable exclusions for one heatmap."""

    correlation: pd.DataFrame
    counts: pd.DataFrame
    reasons: dict[tuple[str, str], str]
    has_finite_off_diagonal: bool


def _render_candidate_population_evidence(store_path: str) -> None:
    """Render complete candidate aggregates and a deterministic display-only sample."""

    group_by = st.selectbox("Candidate evidence grouping", options=list(CANDIDATE_GROUP_FIELDS))
    population = _cached_projection(store_path, "candidate_population", group_by=group_by)
    composition = pd.DataFrame(population["composition"][group_by])
    calibration = pd.DataFrame(population["calibration"][group_by])
    collision = pd.DataFrame(population["collision"])
    sample = population["sample"]

    st.markdown("#### Candidate composition")
    st.caption("Rates use state-then-scene macro aggregation within exact persisted generation cohorts.")
    st.dataframe(composition, hide_index=True, width="stretch")
    _download_frame("Download candidate composition CSV", "candidate-composition.csv", composition)

    st.markdown("#### Proposal calibration")
    st.caption("Empirical frequency, proposal mass, and selection enrichment remain descriptive within cohort.")
    st.dataframe(calibration, hide_index=True, width="stretch")
    _download_frame("Download proposal calibration CSV", "candidate-proposal-calibration.csv", calibration)

    st.markdown("#### Collision support")
    st.dataframe(collision, hide_index=True, width="stretch")
    _download_frame("Download collision support CSV", "candidate-collision-support.csv", collision)

    sample_rows = pd.DataFrame(sample.get("rows", []))
    st.markdown("#### Deterministic display sample")
    st.caption(
        f"Showing {int(sample.get('display_count', 0)):,} of {int(sample.get('population_count', 0)):,} rows. "
        "This bounded, order-invariant sample is display-only; aggregates above use the complete population."
    )
    st.dataframe(sample_rows, hide_index=True, width="stretch")


def _render_candidate_provenance_flow(store_path: str) -> None:
    """Render the lightweight complete-population candidate provenance flow."""

    _, validation, _ = _cached_store_bundle(store_path)
    store_candidate_count = int(validation.num_candidates)
    steps = pd.DataFrame(_cached_projection(store_path, "steps"))
    policy_options = sorted(str(value) for value in steps.get("policy", pd.Series(dtype=str)).dropna().unique())
    depth_options = sorted(int(value) for value in steps.get("step_index", pd.Series(dtype=int)).dropna().unique())
    col_policy, col_depth = st.columns(2)
    selected_policies = col_policy.multiselect("Flow policies", options=policy_options, default=policy_options)
    selected_depths = col_depth.multiselect("Flow rollout depths", options=depth_options, default=depth_options)
    flow = pd.DataFrame(
        _cached_projection(
            store_path,
            "candidate_flow",
            policies=tuple(selected_policies),
            step_indices=tuple(selected_depths),
        )
    )
    if flow.empty:
        st.info(
            "No candidate rows match the active policy and rollout-depth filters. "
            f"The unfiltered store contains {store_candidate_count:,} candidate rows."
        )
        return
    denominator = int(flow["root_denominator"].iloc[0])
    projected_store_count = int(flow["store_candidate_count"].iloc[0])
    if projected_store_count != store_candidate_count:
        raise ValueError("Candidate-flow projection disagrees with validated store candidate count.")
    st.caption(
        f"Active-scope root: {denominator:,} of {store_candidate_count:,} persisted candidate rows, including both "
        "actor-valid and actor-invalid candidates. Policy/depth filters define the scope; validity never filters the root."
    )
    _render_plot(
        _candidate_flow_figure(flow),
        ScientificExplanation(
            question="How does persisted candidate-generation provenance flow into actor-valid support and terminal outcomes?",
            answer="The flow separates what the generator proposed, what the actor could execute, and what the rollout ultimately selected or rejected.",
            sections=(
                ExplanationSection(
                    title="Following the population",
                    body=(
                        "Every candidate row matching the visible policy/depth filters, including actor-valid and actor-invalid rows, aggregated through proposal signature, actor validity, and outcome."
                    )
                    + "\n\n"
                    + ("Candidate count and fraction of the filtered root population; no reward or geometric units.")
                    + "\n\n"
                    + (
                        "The filtered complete candidate population is the root denominator. Actor validity is a hard action constraint; selected actor-invalid rows remain explicit selection_contract_violation evidence."
                    )
                    + "\n\n"
                    + (
                        "Link width is the candidate count and the hover label gives its fraction of the filtered root population; nodes are ordered by provenance stage."
                    ),
                ),
                ExplanationSection(
                    title="Reading the evidence",
                    body=("Candidate proposal signatures, budgets, and active policy/depth filters must match.")
                    + "\n\n"
                    + (
                        "Intended center/view proposal signatures retain actor-valid support, while invalid rows terminate at explicit reasons and selected rows remain actor-valid."
                    )
                    + "\n\n"
                    + (
                        "Following one conserved candidate population through these stages distinguishes lack of support from a later selection or labeling problem."
                    )
                    + "\n\n"
                    + (
                        "This is an exact accounting of the filtered persisted rows, not a sampled estimate; filters change the root population and must be read with the result."
                    ),
                ),
                ExplanationSection(
                    title="What to investigate",
                    body=(
                        "Unknown provenance indicates missing persisted labels; concentrated invalid reasons indicate support loss; selection_contract_violation is a hard invariant failure."
                    )
                    + "\n\n"
                    + (
                        "Actor-valid means the candidate satisfies executable-action constraints; selected rows are the persisted actions actually taken."
                    ),
                ),
            ),
            evidence_role="provenance",
            source_fields=(
                "inspection.candidate_flow_rows",
                "candidates/mixture_id",
                "candidates/position_id",
                "candidates/strategy_id",
                "candidates/actor_action_mask",
                "candidates/selected_mask",
                "candidates/primary_invalid_reason",
            ),
            external_references=(_EVIDENCE_REPORTING_REFERENCE,),
        ),
    )
    st.dataframe(flow, hide_index=True, width="stretch")
    _download_frame("Download candidate provenance flow CSV", "candidate-provenance-flow.csv", flow)

    ranks = pd.DataFrame(
        _cached_projection(
            store_path,
            "ranks",
            policies=tuple(selected_policies),
            step_indices=tuple(selected_depths),
        )
    )
    _render_selected_action_policy_flow(ranks)


def _candidate_flow_figure(flow: pd.DataFrame) -> go.Figure:
    """Build one stage-stable Sankey from normalized candidate-flow links."""

    return _sankey_figure(
        flow,
        stage_order=("root", "proposal", "actor_validity", "candidate_outcome"),
        title="Candidate provenance and support flow",
    )


def _render_selected_action_policy_flow(ranks: pd.DataFrame) -> None:
    """Render policy mechanics and target-RRI rank for selected rollout steps."""

    st.markdown("#### Selected-action policy and rank")
    if ranks.empty or "selected_candidate_row_id" not in ranks:
        st.info("No selected rollout steps match the active policy and rollout-depth filters.")
        return
    selected_ranks = ranks[pd.to_numeric(ranks["selected_candidate_row_id"], errors="coerce").fillna(-1) >= 0].copy()
    if selected_ranks.empty:
        st.info("No selected rollout steps match the active policy and rollout-depth filters.")
        return
    st.caption(
        "Temperature-softmax is the primary behavior-policy view for training-data diversity; random-valid and "
        "oracle policies remain baseline and upper-bound evidence. Target-RRI rank is an oracle diagnostic and is "
        "kept distinct from the persisted selection-score rank."
    )
    selection_flow = pd.DataFrame(_selected_action_flow_rows(selected_ranks))
    if not selection_flow.empty:
        _render_plot(
            _selected_action_flow_figure(selection_flow),
            ScientificExplanation(
                question="Which candidate/action policy selected each persisted action, and where did that action rank by target RRI?",
                answer="The flow shows which policy produced each executed action and how that action ranked among the valid oracle-scored alternatives available at that same step.",
                sections=(
                    ExplanationSection(
                        title="Following the population",
                        body=("One persisted selected rollout step matching the active policy/depth filters.")
                        + "\n\n"
                        + ("Selected-step count and target-RRI competition rank among finite actor-valid candidates.")
                        + "\n\n"
                        + (
                            "The root denominator is selected rollout steps. Target-RRI rank excludes actor-invalid and non-finite alternatives; unavailable ranks remain explicit."
                        )
                        + "\n\n"
                        + (
                            "Link width is selected-step count; policy and temperature label the first stage, while the terminal node is the shell-local target-RRI rank bucket."
                        ),
                    ),
                    ExplanationSection(
                        title="Reading the evidence",
                        body=(
                            "Compare policies only under matched roots, targets, candidate proposals, acquisition budgets, and score semantics."
                        )
                        + "\n\n"
                        + (
                            "Temperature-softmax covers more than rank one without collapsing to uniformly poor target-RRI ranks; greedy policies concentrate near the top."
                        )
                        + "\n\n"
                        + (
                            "A selected action can be diverse without being arbitrary: its target-RRI rank gives a local opportunity-cost diagnostic after action validity has been enforced."
                        )
                        + "\n\n"
                        + (
                            "Ranks are unavailable when oracle evaluation is absent and are shell-local, so the chart is descriptive rather than a cross-scene policy effect estimate."
                        ),
                    ),
                    ExplanationSection(
                        title="What to investigate",
                        body=(
                            "Unavailable ranks indicate missing oracle diagnostics; high-rank concentration can indicate excessive temperature or score/RRI mismatch."
                        )
                        + "\n\n"
                        + (
                            "Target-RRI rank orders finite target-RRI values only among actor-valid candidates in one persisted candidate shell."
                        ),
                    ),
                ),
                evidence_role="oracle/evaluation",
                source_fields=(
                    "inspection.selected_candidate_rank_rows",
                    "rollouts/policy_id",
                    "rollouts/temperature",
                    "candidates/selection_probabilities",
                    "candidates/selection_logits",
                    "candidates/target_rri",
                ),
                external_references=(_EVIDENCE_REPORTING_REFERENCE,),
            ),
        )
        st.dataframe(selection_flow, hide_index=True, width="stretch")
        _download_frame(
            "Download selected-action policy/rank flow CSV",
            "selected-action-policy-rank-flow.csv",
            selection_flow,
        )

    exact_columns = [
        column
        for column in (
            "rollout_row_id",
            "step_row_id",
            "step_index",
            "selected_candidate_row_id",
            "policy",
            "temperature",
            "score_source",
            "selected_probability",
            "selection_entropy",
            "selection_score_rank",
            "selection_score_rank_denominator",
            "target_rri_rank",
            "rank_denominator",
            "target_rri_rank_label",
            "selected_target_rri",
            "selected_target_root_gain",
        )
        if column in selected_ranks
    ]
    exact_table = selected_ranks[exact_columns].rename(
        columns={"target_rri_rank_label": "target-RRI rank / finite actor-valid candidates"}
    )
    st.dataframe(exact_table, hide_index=True, width="stretch")
    _download_frame(
        "Download exact selected-step evidence CSV",
        "selected-step-selection-evidence.csv",
        selected_ranks,
    )


def _selected_action_flow_rows(ranks: pd.DataFrame) -> list[dict[str, object]]:
    """Aggregate selected-step policy and target-RRI ranks for a Sankey."""

    if ranks.empty or "selected_candidate_row_id" not in ranks:
        return []
    selected = ranks[pd.to_numeric(ranks["selected_candidate_row_id"], errors="coerce").fillna(-1) >= 0]
    denominator = len(selected)
    if denominator <= 0:
        return []
    counts: Counter[tuple[str, str, str, str, str, str]] = Counter()
    root = ("selected_root:steps", f"Selected rollout steps ({denominator:,})", "selected_root")
    for _, row in selected.iterrows():
        policy = str(row.get("policy") or "unknown")
        temperature = pd.to_numeric(pd.Series([row.get("temperature")]), errors="coerce").iloc[0]
        policy_label = policy
        if policy == "temperature_softmax" and pd.notna(temperature):
            policy_label = f"{policy} (τ={float(temperature):g})"
        actor_valid = bool(row.get("selected_actor_valid", True))
        rank_label = (
            "selection_contract_violation" if not actor_valid else _target_rri_rank_bucket(row.get("target_rri_rank"))
        )
        nodes = (
            root,
            (f"candidate_action_policy:{policy_label}", policy_label, "candidate_action_policy"),
            (f"target_rri_rank:{rank_label}", rank_label, "target_rri_rank"),
        )
        for source_node, target_node in pairwise(nodes):
            counts[(*source_node, *target_node)] += 1

    stage_order = {stage: index for index, stage in enumerate(("selected_root", "candidate_action_policy"))}
    output: list[dict[str, object]] = []
    for transition, count in sorted(
        counts.items(),
        key=lambda item: (stage_order[item[0][2]], item[0][0], item[0][3]),
    ):
        source_id, source_label, source_stage, target_id, target_label, target_stage = transition
        output.append(
            {
                "source_id": source_id,
                "source_label": source_label,
                "source_stage": source_stage,
                "target_id": target_id,
                "target_label": target_label,
                "target_stage": target_stage,
                "transition": f"{source_stage} -> {target_stage}",
                "count": int(count),
                "root_denominator": denominator,
                "fraction_of_root": float(count) / float(denominator),
            }
        )
    return output


def _target_rri_rank_bucket(value: object) -> str:
    """Return the compact displayed bucket for one exact target-RRI rank."""

    try:
        rank = int(value)
    except (TypeError, ValueError):
        return "unavailable"
    if rank <= 0:
        return "unavailable"
    return str(rank) if rank <= 10 else ">10"


def _selected_action_flow_figure(flow: pd.DataFrame | list[dict[str, object]]) -> go.Figure:
    """Build the selected-step policy-to-target-RRI-rank Sankey."""

    return _sankey_figure(
        pd.DataFrame(flow),
        stage_order=("selected_root", "candidate_action_policy", "target_rri_rank"),
        title="Selected-action policy and target-RRI rank flow",
    )


def _sankey_figure(flow: pd.DataFrame, *, stage_order: tuple[str, ...], title: str) -> go.Figure:
    """Build one stage-stable Sankey from normalized count-conserving links."""

    nodes: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for stage in stage_order:
        candidates = [
            (str(row[f"{side}_id"]), str(row[f"{side}_label"]), stage)
            for _, row in flow.iterrows()
            for side in ("source", "target")
            if str(row[f"{side}_stage"]) == stage
        ]
        for node in sorted(candidates, key=lambda value: (value[1], value[0])):
            if node[0] not in seen:
                seen.add(node[0])
                nodes.append(node)
    node_index = {node_id: index for index, (node_id, _label, _stage) in enumerate(nodes)}
    custom = np.column_stack((flow["root_denominator"], flow["fraction_of_root"]))
    figure = go.Figure(
        go.Sankey(
            arrangement="snap",
            node={
                "label": [label for _node_id, label, _stage in nodes],
                "customdata": [stage for _node_id, _label, stage in nodes],
                "hovertemplate": "%{label}<br>stage=%{customdata}<extra></extra>",
            },
            link={
                "source": [node_index[str(value)] for value in flow["source_id"]],
                "target": [node_index[str(value)] for value in flow["target_id"]],
                "value": flow["count"].astype(int).tolist(),
                "customdata": custom,
                "hovertemplate": (
                    "%{source.label} → %{target.label}<br>count=%{value:,}"
                    "<br>root denominator=%{customdata[0]:,.0f}<br>fraction of root=%{customdata[1]:.2%}<extra></extra>"
                ),
            },
        )
    )
    figure.update_layout(title=title)
    return figure


def _render_candidate_aggregate_breakdowns(store_path: str) -> None:
    """Render restored complete-store candidate audit plots on demand."""

    families = pd.DataFrame(_cached_projection(store_path, "candidate_group", group_by="position"))
    if not families.empty:
        families["selection_rate_given_available"] = np.where(
            families["actor_valid"] > 0,
            families["selected"] / families["actor_valid"],
            np.nan,
        )
        long = families.melt(
            id_vars="position",
            value_vars=["actor_valid_fraction", "selection_rate_given_available"],
            var_name="metric",
            value_name="fraction",
        )
        fig = px.bar(
            long,
            x="position",
            y="fraction",
            color="metric",
            barmode="group",
            title="Candidate-family availability and normalized selection",
        )
        _render_plot(
            fig,
            ScientificExplanation(
                question="Is a candidate family selected because it is useful, or merely because it is frequently available?",
                answer="The paired bars separate a family's opportunity to be chosen from the rate at which it is chosen when that opportunity exists.",
                sections=(
                    ExplanationSection(
                        title="Following the population",
                        body=("Candidate rows grouped by root-relative position family.")
                        + "\n\n"
                        + (
                            "Actor-valid fraction of sampled rows and selected/actor-valid rate; both dimensionless fractions."
                        )
                        + "\n\n"
                        + ("Availability uses the full family shell; selection rate uses actor-valid family rows only.")
                        + "\n\n"
                        + (
                            "For each family, one bar is its actor-valid fraction of the sampled shell and the other is selected divided by actor-valid count."
                        ),
                    ),
                    ExplanationSection(
                        title="Reading the evidence",
                        body=("Family names, mixture weights, and branch budgets must match across stores.")
                        + "\n\n"
                        + (
                            "Useful families retain availability and non-degenerate normalized selection without monopolizing support."
                        )
                        + "\n\n"
                        + (
                            "Raw selections conflate availability and preference, whereas selection divided by actor-valid support asks which usable family the policy favors."
                        )
                        + "\n\n"
                        + (
                            "Both fractions are exact store summaries; a low-support family can have a volatile normalized rate, so read availability before inferring preference."
                        ),
                    ),
                    ExplanationSection(
                        title="What to investigate",
                        body=(
                            "High raw selection with tiny availability can be unstable; zero availability is a generator/mask clue."
                        )
                        + "\n\n"
                        + (
                            "Selection rate given availability = selected candidate rows / actor-valid candidate rows for that family."
                        ),
                    ),
                ),
                evidence_role="actor-visible",
                source_fields=("candidate position_id", "actor_action_mask", "selected_mask"),
                theory=TheoryReferences(equation_ids=("metrics.selection_rate_given_available",)),
                external_references=(_EVIDENCE_REPORTING_REFERENCE,),
            ),
        )
        _download_frame("Download family support CSV", "candidate-family-support.csv", families)

    breakdown_by = st.selectbox(
        "Candidate aggregate breakdown",
        options=list(CANDIDATE_GROUP_FIELDS),
        help="Switches one complete-store aggregate plot without rebuilding the candidate audit.",
    )
    breakdown = pd.DataFrame(_cached_projection(store_path, "candidate_group", group_by=breakdown_by))
    count_fields = [name for name in ("actor_valid", "q_train", "selected") if name in breakdown]
    if not breakdown.empty and count_fields:
        long = breakdown.melt(
            id_vars=breakdown_by,
            value_vars=count_fields,
            var_name="mask_population",
            value_name="count",
        )
        fig = px.bar(
            long,
            x=breakdown_by,
            y="count",
            color="mask_population",
            barmode="group",
            title=f"Candidate support by {breakdown_by}",
        )
        _render_plot(
            fig,
            ScientificExplanation(
                question=f"How do actor-valid, trainable, and selected populations differ across {breakdown_by}?",
                answer="The grouped counts reveal where candidates are executable, label-trainable, or actually selected without pretending those masks form a single pipeline.",
                sections=(
                    ExplanationSection(
                        title="Following the population",
                        body=(f"Complete-store candidate rows grouped by persisted {breakdown_by} provenance.")
                        + "\n\n"
                        + ("Candidate count in each explicitly named mask population.")
                        + "\n\n"
                        + ("Actor-valid, q_train, and selected are overlapping sets, not sequential waterfall stages.")
                        + "\n\n"
                        + (
                            "Each bar is an exact count for one persisted provenance group and mask population; grouped bars permit within-group comparison."
                        ),
                    ),
                    ExplanationSection(
                        title="Reading the evidence",
                        body=("Candidate protocol, group vocabulary, and store schema must match.")
                        + "\n\n"
                        + (
                            "Trainable support is no larger than label availability permits, and selection stays within actor support."
                        )
                        + "\n\n"
                        + (
                            "Actor validity, oracle-label availability, and selection answer different questions; their overlap exposes where supervision or action support is lost."
                        )
                        + "\n\n"
                        + (
                            "Counts are descriptive and mask populations overlap, so bar heights must not be added or read as mutually exclusive stages."
                        ),
                    ),
                    ExplanationSection(
                        title="What to investigate",
                        body=(
                            "Missing groups, selected-only spikes, or large actor/train gaps identify generator, mask, or label-cache issues."
                        )
                        + "\n\n"
                        + (
                            "q_train marks candidates with both actor-action validity and the required oracle-label evidence for Q_H supervision."
                        ),
                    ),
                ),
                evidence_role="derived training data",
                source_fields=(
                    "inspection.candidate_group_summary_rows",
                    f"candidate {breakdown_by}",
                    "candidate masks",
                ),
                theory=TheoryReferences(equation_ids=("metrics.q_train_mask",)),
                external_references=(_EVIDENCE_REPORTING_REFERENCE,),
            ),
        )

    with st.expander("Invalid reasons and valid fanout"):
        invalid = pd.DataFrame(_cached_projection(store_path, "candidate_group", group_by="invalid_reason"))
        fanout = pd.DataFrame(_cached_projection(store_path, "steps"))
        if not invalid.empty:
            st.dataframe(invalid, hide_index=True, width="stretch")
        if not fanout.empty:
            st.dataframe(
                fanout[
                    [
                        c
                        for c in (
                            "rollout_row_id",
                            "step_row_id",
                            "step_index",
                            "num_candidates",
                            "num_valid_candidates",
                            "invalid_fraction",
                        )
                        if c in fanout
                    ]
                ],
                hide_index=True,
                width="stretch",
            )


def _render_target_score_diagnostics(targets: pd.DataFrame) -> None:
    """Restore interpretable target-selection plots and replace the scatter matrix."""

    with st.expander("Target selection score diagnostics", expanded=True):
        rank_rows = targets.dropna(subset=[name for name in ("selection_rank", "selection_score") if name in targets])
        if {"selection_rank", "selection_score"}.issubset(targets.columns) and not rank_rows.empty:
            fig = px.scatter(
                rank_rows,
                x="selection_rank",
                y="selection_score",
                color="gt_match_status" if "gt_match_status" in rank_rows else None,
                symbol="gt_label_valid" if "gt_label_valid" in rank_rows else None,
                hover_data=[
                    name
                    for name in ("target_row_id", "class", "source", "target_valid", "effective_support")
                    if name in rank_rows
                ],
                title="Target selection rank versus score",
            )
            _render_plot(
                fig,
                ScientificExplanation(
                    question="Does persisted target rank agree with the score used to prioritize targets?",
                    answer="The scatter checks whether the persisted ordinal priority is consistent with the configured score while retaining each target's validity status.",
                    sections=(
                        ExplanationSection(
                            title="Following the population",
                            body=("One target proposal with finite rank and selection score.")
                            + "\n\n"
                            + ("Selection rank is ordinal; selection score is a dimensionless configured composite.")
                            + "\n\n"
                            + ("All scored target proposals, including actor-invalid and GT-invalid rows.")
                            + "\n\n"
                            + (
                                "Each mark is one target proposal; horizontal position is its stored rank, vertical position is score, and visual groups retain GT-match status and label validity."
                            ),
                        ),
                        ExplanationSection(
                            title="Reading the evidence",
                            body=("Target-selection weights, proposal source, and GT-matching protocol must match.")
                            + "\n\n"
                            + (
                                "Higher-priority ranks follow higher scores while validity classes remain visibly distinct."
                            )
                            + "\n\n"
                            + (
                                "Rank is an ordering of a score, so inversions, ties, or valid/invalid separation make target-selection behavior inspectable rather than implicit."
                            )
                            + "\n\n"
                            + (
                                "This is a finite proposal audit, not a calibration curve; scores are configuration-dependent and should only be compared under the same target protocol."
                            ),
                        ),
                        ExplanationSection(
                            title="What to investigate",
                            body=(
                                "Rank inversions, score ties, or high-scoring invalid targets indicate selection or matching problems."
                            )
                            + "\n\n"
                            + (
                                "Selection rank is the persisted ordinal priority assigned by the target-selection procedure; smaller ranks denote earlier priority."
                            ),
                        ),
                    ),
                    evidence_role="provenance",
                    source_fields=("targets/selection_rank", "targets/selection_score", "targets/gt_match_status_id"),
                    external_references=(_EVIDENCE_REPORTING_REFERENCE,),
                ),
            )

        support_field = next(
            (
                name
                for name in ("effective_support", "projected_area_fraction", "visibility_score")
                if name in targets and targets[name].notna().any()
            ),
            None,
        )
        if support_field is not None and "selection_score" in targets:
            support_rows = targets.dropna(subset=[support_field, "selection_score"])
            if not support_rows.empty:
                fig = px.scatter(
                    support_rows,
                    x=support_field,
                    y="selection_score",
                    color="gt_match_status" if "gt_match_status" in support_rows else None,
                    symbol="target_valid" if "target_valid" in support_rows else None,
                    hover_data=[name for name in ("target_row_id", "class", "gt_label_valid") if name in support_rows],
                    title=f"Selection score versus {support_field}",
                )
                _render_plot(
                    fig,
                    ScientificExplanation(
                        question="How strongly does visible target support influence the persisted target score?",
                        answer="The scatter shows whether the selected support diagnostic contributes plausibly to the persisted target-selection score.",
                        sections=(
                            ExplanationSection(
                                title="Following the population",
                                body=(f"One target proposal with finite selection score and {support_field}.")
                                + "\n\n"
                                + (f"{support_field} and selection score are dimensionless configured diagnostics.")
                                + "\n\n"
                                + ("Scored target proposals; actor and GT validity remain explicit marks.")
                                + "\n\n"
                                + (
                                    "Each mark is one finite target proposal; x is the chosen support diagnostic, y is selection score, and groups retain validity and GT-match evidence."
                                ),
                            ),
                            ExplanationSection(
                                title="Reading the evidence",
                                body=(
                                    "Support computation, crop geometry, score weights, and target source must match."
                                )
                                + "\n\n"
                                + ("Support contributes monotonically without becoming the only determinant of score.")
                                + "\n\n"
                                + (
                                    "Support should inform confidence that a target is observable, but a composite score should not be explained by one diagnostic alone."
                                )
                                + "\n\n"
                                + (
                                    "The apparent relationship is descriptive and may be shaped by other score terms, target sources, or missing GT labels; it is not a fitted effect."
                                ),
                            ),
                            ExplanationSection(
                                title="What to investigate",
                                body=(
                                    "High scores at negligible support or validity-separated clusters can reveal weighting or GT-association issues."
                                )
                                + "\n\n"
                                + (
                                    "The persisted selection score is a configured target-priority composite; its individual components are diagnostics, not independent outcomes."
                                ),
                            ),
                        ),
                        evidence_role="oracle/evaluation",
                        source_fields=(
                            f"targets/{support_field}",
                            "targets/selection_score",
                            "targets/gt_label_valid_mask",
                        ),
                        external_references=(_EVIDENCE_REPORTING_REFERENCE,),
                    ),
                )

        component_cols = [
            name
            for name in (
                "selection_score",
                "visibility_score",
                "support_score",
                "deficit_score",
                "projected_area_fraction",
                "gt_match_iou",
            )
            if name in targets and targets[name].notna().any()
        ]
        if len(component_cols) >= 2:
            prepared = _prepare_pairwise_correlation(targets[component_cols], component_cols)
            corr = prepared["correlation"]
            counts = prepared["counts"]
            reasons = prepared["reasons"]
            if not prepared["has_finite_off_diagonal"]:
                reason_text = "; ".join(f"{pair}: {reason}" for pair, reason in reasons.items() if pair[0] != pair[1])
                st.info(f"Correlation heatmap unavailable: no estimable finite off-diagonal pair. {reason_text}")
                return
            if any("n=2" in reason for reason in reasons.values()):
                st.warning(
                    "Some correlation cells have n=2; Pearson |r| is algebraically forced to 1 and is not substantive evidence."
                )
            labels = [
                [
                    "n/a"
                    if pd.isna(corr.iloc[row, col])
                    else f"r={corr.iloc[row, col]:.2f}, n={int(counts.iloc[row, col])}"
                    for col in range(len(component_cols))
                ]
                for row in range(len(component_cols))
            ]
            fig = go.Figure(
                go.Heatmap(
                    z=corr.to_numpy(),
                    x=corr.columns.tolist(),
                    y=corr.index.tolist(),
                    zmin=-1,
                    zmax=1,
                    colorscale="RdBu",
                    reversescale=True,
                    text=labels,
                    texttemplate="%{text}",
                    customdata=np.stack([counts.to_numpy(), np.array(labels, dtype=object)], axis=-1),
                    hovertemplate="%{y} × %{x}<br>%{customdata[1]}<extra></extra>",
                )
            )
            fig.update_layout(title="Target score-component correlation (descriptive; pairwise n shown)", height=440)
            _render_plot(
                fig,
                ScientificExplanation(
                    question="Which target-score components are redundant, opposed, or unexpectedly disconnected?",
                    answer="The heatmap is descriptive evidence of linear association between persisted score components, with pair-local support shown for every cell.",
                    sections=(
                        ExplanationSection(
                            title="Following the population",
                            body=("Pairwise-complete target proposals for each component pair.")
                            + "\n\n"
                            + ("Pearson correlation coefficient, dimensionless in [-1, 1].")
                            + "\n\n"
                            + ("Finite pairwise component values; pairwise denominators may differ.")
                            + "\n\n"
                            + (
                                "Cell color encodes r from -1 to 1; each annotation and hover label reports r and the exact pairwise finite n."
                            ),
                        ),
                        ExplanationSection(
                            title="Reading the evidence",
                            body=("Only compare matrices from identical score definitions and target protocols.")
                            + "\n\n"
                            + ("Components reflect their intended roles without perfect accidental duplication.")
                            + "\n\n"
                            + (
                                "Pearson r compares centered component values within the same finite pair; it diagnoses redundancy or opposition but does not establish causality."
                            )
                            + "\n\n"
                            + (
                                "Pairs with n=2 are algebraically forced to |r|=1 and are not substantive evidence; missing or constant pairs are withheld."
                            ),
                        ),
                        ExplanationSection(
                            title="What to investigate",
                            body=(
                                "Near-perfect correlations suggest redundancy; unexpected signs can expose score wiring errors."
                            )
                            + "\n\n"
                            + ("Pearson r is the standardized covariance of the same pair-local finite observations."),
                        ),
                    ),
                    evidence_role="oracle/evaluation",
                    source_fields=tuple(f"targets/{name}" for name in component_cols),
                    theory=TheoryReferences(equation_ids=("metrics.pearson",)),
                    external_references=(_CORRELATION_REFERENCE,),
                ),
            )
        elif len(component_cols) == 1:
            st.info(
                "Correlation heatmap unavailable: one target-score component has finite observations; at least two components are required."
            )
        else:
            st.info("Correlation heatmap unavailable: no target-score components have finite observations.")


def _prepare_pairwise_correlation(frame: pd.DataFrame, columns: list[str]) -> _PairwiseCorrelation:
    """Prepare pair-local Pearson evidence without changing reporting semantics."""

    numeric = frame.loc[:, columns].apply(pd.to_numeric, errors="coerce")
    correlation = pd.DataFrame(np.nan, index=columns, columns=columns, dtype=float)
    counts = pd.DataFrame(0, index=columns, columns=columns, dtype=int)
    reasons: dict[tuple[str, str], str] = {}
    has_finite_off_diagonal = False
    for left in columns:
        for right in columns:
            pair_values = numeric.loc[:, [left, right]].to_numpy(dtype=float)
            finite = np.isfinite(pair_values).all(axis=1)
            finite_values = pair_values[finite]
            n = len(finite_values)
            counts.loc[left, right] = n
            if n < 2:
                reasons[(left, right)] = f"insufficient finite paired rows (n={n}; need n>=2)"
                continue
            left_values, right_values = finite_values[:, 0], finite_values[:, 1]
            if np.unique(left_values).size == 1 or np.unique(right_values).size == 1:
                reasons[(left, right)] = "constant pair value (zero variance)"
                continue
            value = float(pd.Series(left_values).corr(pd.Series(right_values)))
            if not np.isfinite(value):
                reasons[(left, right)] = "non-finite Pearson correlation after finite pair filtering"
                continue
            correlation.loc[left, right] = value
            if left != right:
                has_finite_off_diagonal = True
                if n == 2:
                    reasons[(left, right)] = "n=2 is algebraically degenerate: |r|=1 is not substantive evidence"
    return {
        "correlation": correlation,
        "counts": counts,
        "reasons": reasons,
        "has_finite_off_diagonal": has_finite_off_diagonal,
    }


def _add_geometry_anchors(
    fig: go.Figure,
    frames: pd.DataFrame,
    *,
    three_dimensional: bool,
    axis_frames: pd.DataFrame | None = None,
) -> None:
    """Overlay normalized origins, targets, and bounded pose-axis context."""

    if frames.empty:
        return
    marker_type = go.Scatter3d if three_dimensional else go.Scatter
    origin: dict[str, object] = {
        "x": [0.0],
        "y": [0.0],
        "mode": "markers",
        "name": "Reference pose (all at origin)",
        "marker": {"size": 7, "symbol": "cross", "color": "white"},
        "hovertemplate": "Reference center: (0, 0, 0)<extra></extra>",
    }
    target: dict[str, object] = {
        "x": frames["target_x"],
        "y": frames["target_y"],
        "mode": "markers",
        "name": "Observed target center",
        "marker": {"size": 7, "symbol": "diamond-open", "color": "#F4D03F"},
        "customdata": frames[["rollout_row_id", "step_index", "scale_m"]],
        "hovertemplate": (
            "rollout=%{customdata[0]}<br>step=%{customdata[1]}<br>"
            "normalization distance=%{customdata[2]:.3f} m<br>normalized target norm=1<extra></extra>"
        ),
    }
    if three_dimensional:
        origin["z"] = [0.0]
        target["z"] = frames["target_z"]
    fig.add_trace(marker_type(**origin))
    fig.add_trace(marker_type(**target))
    if not three_dimensional:
        return

    bounded = frames.head(32) if axis_frames is None else axis_frames.head(32)
    if bounded.empty:
        return
    reference_centers = np.zeros((len(bounded), 3), dtype=float)
    target_centers = bounded.loc[:, ["target_x", "target_y", "target_z"]].to_numpy(dtype=float)
    for prefix, label, centers in (
        ("reference", "Reference pose axes (RGB)", reference_centers),
        ("target", "Target pose axes (RGB)", target_centers),
    ):
        axes = np.stack(
            [np.asarray(bounded[f"{prefix}_axis_{axis}"].tolist(), dtype=float) for axis in ("x", "y", "z")],
            axis=1,
        )
        add_pose_axes_to_figure(fig, centers, axes, title=label, scale=0.12, line_width=3)


def _add_trajectory_paths(fig: go.Figure, geometry: pd.DataFrame, *, three_dimensional: bool) -> None:
    """Connect only root and factual selected actions in their shared trajectory frame."""

    if geometry.empty or not {"rollout_row_id", "path_order", "x", "y", "z"}.issubset(geometry.columns):
        return
    for chain_index, (_, chain) in enumerate(geometry.groupby("rollout_row_id", sort=True)):
        chain = chain.sort_values("path_order")
        trace_kwargs = {
            "mode": "lines",
            "line": {"color": "rgba(230, 230, 230, 0.55)", "width": 2},
            "name": "Factual selected trajectory",
            "legendgroup": "selected-rollout-trajectory",
            "showlegend": chain_index == 0,
            "hoverinfo": "skip",
        }
        if three_dimensional:
            fig.add_trace(go.Scatter3d(x=chain["x"], y=chain["y"], z=chain["z"], **trace_kwargs))
        else:
            fig.add_trace(go.Scatter(x=chain["x"], y=chain["y"], **trace_kwargs))


def _add_selected_candidate_overlay(fig: go.Figure, geometry: pd.DataFrame, *, three_dimensional: bool) -> None:
    """Make selected actions visible without consuming the strategy marker encoding."""

    required_columns = {
        "selected",
        "rollout_row_id",
        "step_index",
        "position",
        "strategy",
        "x",
        "y",
        "z",
    }
    if not required_columns.issubset(geometry.columns):
        return
    selected = geometry.loc[geometry["selected"].astype(bool)]
    if selected.empty:
        return
    coordinates = selected.loc[:, ["x", "y", "z"]].to_numpy(dtype=float)
    trace_kwargs = {
        "mode": "markers",
        "name": "Selected candidate",
        "marker": {"size": 7 if three_dimensional else 8, "color": "white", "symbol": "circle-open"},
        "customdata": selected[["rollout_row_id", "step_index", "position", "strategy"]],
        "hovertemplate": (
            "selected<br>rollout=%{customdata[0]}<br>step=%{customdata[1]}<br>"
            "position=%{customdata[2]}<br>strategy=%{customdata[3]}<extra></extra>"
        ),
    }
    if three_dimensional:
        fig.add_trace(go.Scatter3d(x=coordinates[:, 0], y=coordinates[:, 1], z=coordinates[:, 2], **trace_kwargs))
    else:
        fig.add_trace(go.Scatter(x=coordinates[:, 0], y=coordinates[:, 1], **trace_kwargs))


def _render_geometry_projection(
    projection: GeometryProjection,
    geometry: pd.DataFrame,
    frames: pd.DataFrame,
    axis_frames: pd.DataFrame | None = None,
) -> None:
    """Render matched ground-plane and 3D views from one typed projection."""

    if geometry.empty or frames.empty:
        st.warning("No scientifically valid geometry frames are available for this selection.")
        return
    proposal = projection.view == "proposal_support"
    plotted = geometry if proposal else geometry.loc[geometry["role"] == "selected_action"]
    if plotted.empty:
        st.warning("The selected geometry view has no factual points to plot.")
        return
    color = "position" if plotted["position"].notna().any() else None
    symbol = "strategy" if plotted["strategy"].notna().any() else None
    hover_fields = [
        name
        for name in (
            "rollout_row_id",
            "step_index",
            "normalization_distance_m",
            "initial_target_distance_m",
            "displacement_m",
            "z",
            "actor_action",
            "position",
            "strategy",
            "mixture",
        )
        if name in plotted
    ]
    view_title = "Proposal support" if proposal else "Factual selected rollout trajectory"
    axis_prefix = "Current target distance" if proposal else "Initial target distance"
    explanation = _geometry_explanation(projection, three_dimensional=False)
    figure = px.scatter(
        plotted,
        x="x",
        y="y",
        color=color,
        symbol=symbol,
        hover_data=hover_fields,
        title=f"{view_title} (ground plane; target-distance normalized)",
    )
    figure.update_yaxes(scaleanchor="x", scaleratio=1, title=f"Left / {axis_prefix.lower()}")
    figure.update_xaxes(title=f"Forward / {axis_prefix.lower()}")
    figure.update_traces(marker={"size": 3, "opacity": 0.75})
    if proposal:
        _add_selected_candidate_overlay(figure, plotted, three_dimensional=False)
    else:
        _add_trajectory_paths(figure, geometry, three_dimensional=False)
    _add_geometry_anchors(figure, frames, three_dimensional=False, axis_frames=axis_frames)
    _render_plot(figure, explanation)

    figure_3d = px.scatter_3d(
        plotted,
        x="x",
        y="y",
        z="z",
        color=color,
        symbol=symbol,
        hover_data=hover_fields,
        title=f"{view_title} (3D; target-distance normalized)",
    )
    configure_3d_scene(
        figure_3d,
        axis_titles=(
            f"Forward / {axis_prefix.lower()}",
            f"Left / {axis_prefix.lower()}",
            f"World up / {axis_prefix.lower()}",
        ),
    )
    figure_3d.update_traces(marker={"size": 3, "opacity": 0.75})
    if proposal:
        _add_selected_candidate_overlay(figure_3d, plotted, three_dimensional=True)
    else:
        _add_trajectory_paths(figure_3d, geometry, three_dimensional=True)
    _add_geometry_anchors(figure_3d, frames, three_dimensional=True, axis_frames=axis_frames)
    _render_plot(figure_3d, _geometry_explanation(projection, three_dimensional=True))


def _pose_axis_frames(
    frames: pd.DataFrame,
    *,
    mode: str,
    frame_id: str | None = None,
) -> pd.DataFrame:
    """Return the bounded orientation frames requested by the presentation."""

    if mode == "Hidden":
        return frames.iloc[0:0]
    if mode == "One frame":
        if frame_id is None:
            raise ValueError("One-frame pose orientation requires a frame_id.")
        selected = frames.loc[frames["frame_id"] == frame_id]
        if len(selected) != 1:
            raise ValueError(f"Pose orientation frame {frame_id!r} is missing or ambiguous.")
        return selected
    if mode == "All frames":
        return frames.head(32)
    raise ValueError(f"Unsupported pose orientation overlay mode: {mode!r}.")


def _select_pose_axis_frames(frames: pd.DataFrame) -> pd.DataFrame:
    """Render minimal orientation controls and return the selected frame rows."""

    mode = st.segmented_control(
        "Pose orientation overlay",
        options=("Hidden", "One frame", "All frames"),
        default="Hidden",
        help=(
            "Pose triads are diagnostic, not additional plot coordinate systems. Hide them for support shape; "
            "inspect one factual frame for orientation; use all frames only to diagnose population spread."
        ),
    )
    if mode == "One frame":
        labels = {
            str(row.frame_id): (
                f"Rollout {int(row.rollout_row_id)} · "
                + ("initial frame" if pd.isna(row.step_index) else f"acquisition {int(row.step_index) + 1}")
            )
            for row in frames.itertuples(index=False)
        }
        frame_id = st.selectbox(
            "Orientation frame",
            options=tuple(labels),
            format_func=labels.__getitem__,
        )
        return _pose_axis_frames(frames, mode=mode, frame_id=str(frame_id))
    selected = _pose_axis_frames(frames, mode=str(mode))
    if mode == "All frames" and len(frames) > len(selected):
        st.caption(f"Orientation overlay is capped at the first {len(selected):,} deterministic frame(s).")
    return selected


def _normalized_radius_figure(geometry: pd.DataFrame) -> go.Figure:
    """Build proposal-radius distributions by factual depth and positional family."""

    rows = geometry.dropna(subset=["normalized_radius", "step_index"])
    figure = px.box(
        rows,
        x="step_index",
        y="normalized_radius",
        color="position" if rows["position"].notna().any() else None,
        points=False,
        title="Proposal radius / remaining target distance by rollout depth",
        labels={"step_index": "Factual rollout depth", "normalized_radius": "Normalized proposal radius"},
    )
    figure.add_hline(
        y=1.0,
        line_dash="dash",
        line_color="rgba(255, 255, 255, 0.55)",
        annotation_text="step equals remaining target distance",
    )
    return figure


def _orientation_diagnostic_rows(geometry: pd.DataFrame, frames: pd.DataFrame) -> pd.DataFrame:
    """Return comparable angle diagnostics without pooling their populations."""

    frame_columns = ["rollout_row_id", "step_index"]
    parts: list[pd.DataFrame] = []
    for field, label in (
        ("rig_target_yaw_error_deg", "Rig-to-target yaw error"),
        ("target_elevation_deg", "Target elevation"),
    ):
        if field not in frames:
            continue
        rows = frames.loc[:, [*frame_columns, field]].dropna(subset=[field]).rename(columns={field: "angle_deg"})
        rows["diagnostic"] = label
        rows["position"] = "frame-level"
        parts.append(rows)
    required = {"selected", "target_facing_error_deg", "rollout_row_id", "step_index", "position"}
    if required.issubset(geometry.columns):
        selected = geometry.loc[
            geometry["selected"].astype(bool),
            ["rollout_row_id", "step_index", "position", "target_facing_error_deg"],
        ].dropna(subset=["target_facing_error_deg"])
        selected = selected.rename(columns={"target_facing_error_deg": "angle_deg"})
        selected["position"] = selected["position"].fillna("unknown")
        selected["diagnostic"] = "Selected camera-to-target error"
        parts.append(selected)
    if not parts:
        return pd.DataFrame(columns=[*frame_columns, "position", "angle_deg", "diagnostic"])
    return pd.concat(parts, ignore_index=True)


def _orientation_diagnostic_figure(rows: pd.DataFrame) -> go.Figure:
    """Build depth-wise orientation distributions with one facet per estimand."""

    figure = px.box(
        rows,
        x="step_index",
        y="angle_deg",
        color="diagnostic",
        facet_row="diagnostic",
        points="all",
        title="Orientation diagnostics by rollout depth",
        labels={"step_index": "Factual rollout depth", "angle_deg": "Angle (degrees)"},
        hover_data=["position"],
    )
    figure.update_yaxes(matches=None)
    return figure


def _render_proposal_geometry_quality(geometry: pd.DataFrame, frames: pd.DataFrame) -> None:
    """Render actionable normalized-radius and orientation diagnostics."""

    radius_rows = geometry.dropna(subset=["normalized_radius", "step_index"])
    if not radius_rows.empty:
        _render_plot(
            _normalized_radius_figure(radius_rows),
            ScientificExplanation(
                question="Do fixed-metre proposal families become aggressive relative to the target range remaining?",
                answer=(
                    "Each box summarizes candidate displacement divided by current expansion-pose-to-target "
                    "distance, separated by factual depth and positional family."
                ),
                sections=(
                    ExplanationSection(
                        "Population and denominator",
                        "Every retained candidate row contributes its Euclidean expansion-relative displacement. "
                        "The denominator is the current 3D target distance for that factual step; no missing depth is zero-filled.",
                    ),
                    ExplanationSection(
                        "Reading the threshold",
                        "A value of 1 means the proposal step is as long as the remaining target distance. "
                        "Increasing late-depth values reveal fixed physical radii becoming relatively aggressive; "
                        "they are diagnostic and do not by themselves make a candidate invalid.",
                    ),
                ),
                evidence_role="actor-visible",
                source_fields=(
                    "inspection.proposal_support_geometry.normalized_radius",
                    "candidates/pose_world_cam",
                    "targets/target_pose_world_object",
                ),
                theory=TheoryReferences(equation_ids=("spatial.candidate_proposal_support_normalization",)),
                external_references=(_EVIDENCE_REPORTING_REFERENCE,),
            ),
        )
        with st.expander("Normalized proposal-radius rows and CSV", expanded=False):
            columns = [
                "rollout_row_id",
                "step_index",
                "candidate_row_id",
                "position",
                "strategy",
                "selected",
                "displacement_m",
                "normalization_distance_m",
                "normalized_radius",
            ]
            table = radius_rows.loc[:, [column for column in columns if column in radius_rows]]
            st.dataframe(table, hide_index=True, width="stretch")
            _download_frame("Download normalized proposal-radius CSV", "proposal-normalized-radius.csv", table)

    orientation_rows = _orientation_diagnostic_rows(geometry, frames)
    if not orientation_rows.empty:
        _render_plot(
            _orientation_diagnostic_figure(orientation_rows),
            ScientificExplanation(
                question="How do rig heading, target elevation, and selected camera aim evolve with rollout depth?",
                answer=(
                    "Separate facets report one frame-level rig yaw error, one frame-level target elevation, and "
                    "one selected-action camera-to-target error for every finite factual observation."
                ),
                sections=(
                    ExplanationSection(
                        "Populations",
                        "Rig yaw and target elevation contain one row per valid proposal frame. Selected target-facing "
                        "error contains only the factual selected candidate at that step; alternative candidates are excluded.",
                    ),
                    ExplanationSection(
                        "Interpretation",
                        "Small rig yaw means the expansion rig already faces the target horizontally. Target elevation "
                        "is signed relative to world-up. Small selected camera error means the selected optical forward "
                        "axis points toward the target; forward-rig strategies can legitimately remain offset.",
                    ),
                ),
                evidence_role="actor-visible",
                source_fields=(
                    "inspection.proposal_support_geometry.rig_target_yaw_error_deg",
                    "inspection.proposal_support_geometry.target_elevation_deg",
                    "inspection.proposal_support_geometry.target_facing_error_deg",
                ),
                theory=TheoryReferences(
                    equation_ids=("spatial.candidate_pose_features", "spatial.candidate_target_relation")
                ),
                external_references=(_EVIDENCE_REPORTING_REFERENCE,),
            ),
        )
        with st.expander("Orientation diagnostic rows and CSV", expanded=False):
            st.dataframe(orientation_rows, hide_index=True, width="stretch")
            _download_frame("Download proposal orientation CSV", "proposal-orientation.csv", orientation_rows)


def _geometry_explanation(
    projection: GeometryProjection,
    *,
    three_dimensional: bool,
) -> ScientificExplanation:
    """Describe exactly the population, frame, scale, and marker encodings."""

    rollout_count = len({point.rollout_row_id for point in projection.points})
    frame_count = len(projection.frames)
    issue_counts = Counter(issue.code for issue in projection.issues)
    evidence_state = (
        f"This projection contains {len(projection.points):,} point(s) from {rollout_count:,} rollout(s) "
        f"across {frame_count:,} valid frame(s). "
        f"Whole-shell truncation is {'active' if projection.truncated else 'not active'}; "
        f"explicit exclusions are {dict(sorted(issue_counts.items())) if issue_counts else 'none'}."
    )
    if projection.view == "proposal_support":
        alignment = projection.frames[0].alignment if projection.frames else "unavailable"
        dimensional_context = (
            "The 3D view additionally preserves normalized world-up displacement."
            if three_dimensional
            else "The ground-plane view omits Z from the axes but retains it in hover data."
        )
        return ScientificExplanation(
            question="What support did the generator offer around the factual pose that expanded each step?",
            answer=(
                "Every complete factual candidate shell is centered on its own expansion pose and scaled by the "
                "target distance remaining at that step. Proposal alternatives are never connected."
            ),
            sections=(
                ExplanationSection(
                    "Population and transformation",
                    "Step 0 uses the persisted rollout root; step t>0 uses the previous factual selected pose. "
                    "Each candidate displacement is divided by that reference pose's current 3D target distance. "
                    f"The yaw-only alignment is `{alignment}` and always preserves world +Z. {dimensional_context}",
                ),
                ExplanationSection(
                    "Target and marker context",
                    "The white cross is the reference origin and yellow diamonds are observed target centers. "
                    "Under target alignment, targets lie in the X-Z plane with unit norm; elevation remains visible. "
                    "Color encodes positional family, marker shape encodes directional strategy, and a white ring "
                    "marks the selected candidate.",
                ),
                ExplanationSection(
                    "Interpretation limits",
                    "Coordinates are dimensionless target-distance units, while hover/export retains physical "
                    "displacement and normalization distance in metres. Truncation retains complete shells; "
                    f"degenerate target or heading frames are reported rather than silently re-aligned. {evidence_state}",
                ),
            ),
            evidence_role="actor-visible",
            source_fields=(
                "inspection.proposal_support_geometry",
                "steps/selected_candidate_row_id",
                "candidates/pose_world_cam",
                "targets/target_pose_world_object",
            ),
            theory=TheoryReferences(
                equation_ids=("spatial.candidate_proposal_support_normalization",),
                symbol_ids=("oracle.candidate_qti", "oracle.center", "entity.center", "spatial.ref_pose"),
            ),
            external_references=(_PYTORCH3D_RENDERING_REFERENCE,),
        )
    return ScientificExplanation(
        question="Where did the factual selected rollout move relative to its initial target range?",
        answer=(
            "Each path contains only the initial rollout root and ordered factual selected actions, connected in one "
            "initial target-aligned Z-up frame."
        ),
        sections=(
            ExplanationSection(
                "Population and transformation",
                "All path points subtract the persisted initial root, use one initial root-to-target denominator, "
                "and use one initial target-aligned yaw frame. The shared frame makes connecting lines geometric; "
                "candidate alternatives are excluded.",
            ),
            ExplanationSection(
                "Target and marker context",
                "The white cross is the initial root and the yellow diamond is the observed target center. "
                "Targets lie in the X-Z plane with unit norm. Point color is the selected positional family and "
                "marker shape is its directional strategy.",
            ),
            ExplanationSection(
                "Interpretation limits",
                "Only persisted factual steps are shown, so early termination shortens a path without fabricated "
                "continuity. Coordinates are initial target-distance units; physical displacement remains in hover "
                f"and export fields. {evidence_state}",
            ),
        ),
        evidence_role="actor-visible",
        source_fields=(
            "inspection.rollout_trajectory_geometry",
            "rollouts/root_pose_world",
            "steps/selected_candidate_row_id",
            "candidates/pose_world_cam",
        ),
        theory=TheoryReferences(
            equation_ids=("spatial.rollout_trajectory_normalization",),
            symbol_ids=("oracle.candidate_qti", "oracle.center", "entity.center", "spatial.ref_pose"),
        ),
        external_references=(_PYTORCH3D_RENDERING_REFERENCE,),
    )


def _render_candidate_geometry_diagnostics(
    candidates: pd.DataFrame,
    store_path: str,
    *,
    total_candidates: int,
    candidate_plot_limit: int,
) -> None:
    """Render explicit proposal-support or factual-trajectory geometry."""

    if candidates.empty:
        return
    with st.expander("Candidate geometry, motion, angles, and reward support", expanded=True):
        view = st.segmented_control(
            "Geometry view",
            options=("Proposal support", "Rollout trajectory"),
            default="Proposal support",
            help=(
                "Proposal support compares complete candidate shells in each step's factual expansion frame. "
                "Rollout trajectory shows only the initial root and factual selected actions in one fixed frame."
            ),
        )
        if view == "Rollout trajectory":
            projection = _cached_projection(store_path, "trajectory_geometry")
        else:
            alignment_label = st.segmented_control(
                "Proposal alignment",
                options=("Target-aligned Z-up", "Rig-forward Z-up"),
                default="Target-aligned Z-up",
                help=(
                    "Both choices keep gravity as +Z. Target alignment removes horizontal target-bearing variation; "
                    "rig-forward alignment exposes forward, backward, and lateral proposal support."
                ),
            )
            alignment = (
                ProposalAlignment.RIG_FORWARD_Z_UP
                if alignment_label == "Rig-forward Z-up"
                else ProposalAlignment.TARGET_ALIGNED_Z_UP
            )
            projection = _cached_projection(
                store_path,
                "proposal_geometry",
                alignment=alignment.value,
                limit=candidate_plot_limit,
            )
        if not isinstance(projection, GeometryProjection):
            st.error("Candidate geometry cache returned an unsupported projection shape. Refresh rollout caches.")
            return
        geometry = pd.DataFrame(projection.point_rows())
        frames = pd.DataFrame(projection.frame_rows())
        issue_counts = Counter(issue.code for issue in projection.issues)
        rollout_count = int(geometry["rollout_row_id"].nunique()) if "rollout_row_id" in geometry else 0
        step_count = int(geometry["step_row_id"].nunique()) if "step_row_id" in geometry else 0
        st.caption(
            f"This {projection.view.replace('_', ' ')} projection contains {len(geometry):,} plotted point(s) "
            f"from {rollout_count:,} rollout(s) and {step_count:,} factual step(s). "
            f"The underlying store has {total_candidates:,} candidate rows. "
            + (
                f"Excluded/truncated frames: {dict(sorted(issue_counts.items()))}."
                if issue_counts
                else "No frame exclusions."
            )
        )
        axis_frames = _select_pose_axis_frames(frames)
        _render_geometry_projection(projection, geometry, frames, axis_frames)
        if projection.view == "proposal_support":
            _render_proposal_geometry_quality(geometry, frames)

        metric_options = [
            name
            for name in (
                "motion_step_length_m",
                "motion_height_delta_m",
                "motion_backward_step_m",
                "motion_yaw_delta_deg",
                "mesh_distance_m",
                "path_min_clearance_m",
                "free_space_margin_m",
                "target_distance_m",
                "target_root_gain",
                "target_rri",
            )
            if name in candidates and candidates[name].notna().any()
        ]
        if metric_options:
            metric = st.selectbox(
                "Geometry / label distribution",
                options=metric_options,
                format_func=current_scientific_label,
            )
            metric_rows = candidates.dropna(subset=[metric])
            render_scientific_notation(metric)
            fig = px.histogram(
                metric_rows,
                x=metric,
                color="invalid_reason" if "invalid_reason" in metric_rows else None,
                marginal="box",
                labels={metric: current_scientific_label(metric)},
                title=f"{current_scientific_label(metric)} distribution",
            )
            _render_plot(
                fig,
                ScientificExplanation(
                    question=f"What is the support, tail behavior, and invalidity structure of {metric}?",
                    answer=f"The distribution shows the observed support and tails of {metric}, with invalidity retained as a diagnostic stratum.",
                    sections=(
                        ExplanationSection(
                            title="Following the population",
                            body=("Bounded candidate audit rows with a finite selected metric.")
                            + "\n\n"
                            + (
                                f"{metric}; units follow the field suffix (`_m`, `_deg`) or are dimensionless for reward/RRI."
                            )
                            + "\n\n"
                            + ("Finite metric rows; invalid reasons remain explicit rather than silently filtered.")
                            + "\n\n"
                            + (
                                "Histogram bars count finite candidate rows, color separates invalidity reasons, and the marginal box plot summarizes center, spread, and outliers."
                            ),
                        ),
                        ExplanationSection(
                            title="Reading the evidence",
                            body=("Field definition, candidate protocol, and interactive row limit must match.")
                            + "\n\n"
                            + ("Support respects configured physical bounds and avoids unexplained clipping or spikes.")
                            + "\n\n"
                            + (
                                "Physical and scoring diagnostics are most useful when their full range and any validity-specific modes are visible before selecting an individual row to inspect."
                            )
                            + "\n\n"
                            + (
                                "This is a bounded interactive sample rather than a corpus estimate; rare tails can be absent at the current plot limit and invalid rows are not silently imputed."
                            ),
                        ),
                        ExplanationSection(
                            title="What to investigate",
                            body=(
                                "Heavy tails, discontinuities, or invalidity-specific modes guide row-level debugging."
                            )
                            + "\n\n"
                            + (
                                "Metric suffixes `_m` and `_deg` denote metres and degrees; target-root gain and RRI are dimensionless oracle-evaluation quantities."
                            ),
                        ),
                    ),
                    evidence_role="oracle/evaluation"
                    if metric in {"target_root_gain", "target_rri"}
                    else "actor-visible",
                    source_fields=(f"candidate audit/{metric}", "candidates/invalid_reason_bitset"),
                    theory=TheoryReferences(equation_ids=("rl.target_rri_reward",))
                    if metric == "target_root_gain"
                    else None,
                    external_references=(_EVIDENCE_REPORTING_REFERENCE,),
                ),
            )
        angle_cols = [
            name
            for name in ("target_bearing_yaw_deg", "motion_yaw_delta_deg")
            if name in candidates and candidates[name].notna().any()
        ]
        if angle_cols:
            angle_rows = candidates[angle_cols].melt(var_name="angle_source", value_name="angle_deg").dropna()
            fig = px.histogram(
                angle_rows,
                x="angle_deg",
                color="angle_source",
                nbins=72,
                barmode="overlay",
                opacity=0.7,
                title="Target-bearing and executed-yaw support",
            )
            fig.update_xaxes(range=[-180, 180])
            _render_plot(
                fig,
                ScientificExplanation(
                    question="Do candidate motions cover the target-bearing angles that the store presents?",
                    answer="The overlaid angle distributions show whether proposed motion yaw reaches the target-relative bearings represented in the stored candidate audit.",
                    sections=(
                        ExplanationSection(
                            title="Following the population",
                            body=("Bounded candidate rows with finite bearing or motion-yaw diagnostics.")
                            + "\n\n"
                            + ("Yaw angle in degrees in the persisted ARIA convention.")
                            + "\n\n"
                            + (
                                "Finite angle diagnostics; invalid candidates remain included unless absent from the persisted audit row."
                            )
                            + "\n\n"
                            + (
                                "Histogram position is yaw angle in degrees; color distinguishes target-bearing diagnostics from executed motion-yaw changes."
                            ),
                        ),
                        ExplanationSection(
                            title="Reading the evidence",
                            body=("Angle convention, generator families, and candidate budget must match.")
                            + "\n\n"
                            + ("Executed yaw support overlaps relevant target bearings without implausible spikes.")
                            + "\n\n"
                            + (
                                "A candidate family can meet translation limits yet miss the target if its camera orientation is systematically offset from useful bearing directions."
                            )
                            + "\n\n"
                            + (
                                "Finite diagnostic rows are counted without a directional-confidence model; wrap-around and sparse tails require row-level interpretation rather than a single average."
                            ),
                        ),
                        ExplanationSection(
                            title="What to investigate",
                            body=(
                                "Systematic offsets suggest frame errors; narrow motion support suggests generator or constraint collapse."
                            )
                            + "\n\n"
                            + (
                                "Yaw is the persisted signed horizontal rotation in degrees under the rollout coordinate convention, displayed on [-180°, 180°]."
                            ),
                        ),
                    ),
                    evidence_role="actor-visible",
                    source_fields=(
                        "candidate_diagnostics/target_bearing_yaw_deg",
                        "candidate_diagnostics/motion_yaw_delta_deg",
                    ),
                    external_references=(_PYTORCH3D_RENDERING_REFERENCE,),
                ),
            )

        motion_required = {"motion_step_length_m", "motion_yaw_delta_deg"}
        if motion_required.issubset(candidates.columns):
            motion = candidates.dropna(subset=list(motion_required))
            if not motion.empty:
                fig = px.scatter(
                    motion,
                    x="motion_step_length_m",
                    y="motion_yaw_delta_deg",
                    color="position" if "position" in motion else None,
                    symbol="selected" if "selected" in motion else None,
                    hover_data=[name for name in ("invalid_reason", "target_distance_m", "policy") if name in motion],
                    title="Motion length versus yaw change",
                )
                _render_plot(
                    fig,
                    ScientificExplanation(
                        question="Are translation and rotation jointly plausible for sampled and selected actions?",
                        answer="The scatter checks whether sampled and selected actions jointly respect plausible translation and rotation support.",
                        sections=(
                            ExplanationSection(
                                title="Following the population",
                                body=("Bounded candidate rows with finite motion diagnostics.")
                                + "\n\n"
                                + ("Step length in metres and yaw change in degrees.")
                                + "\n\n"
                                + ("Finite motion rows; validity, family, and selected state remain inspectable.")
                                + "\n\n"
                                + (
                                    "Each finite candidate is plotted by translation metres and yaw degrees; color identifies family and symbol marks selected candidates."
                                ),
                            ),
                            ExplanationSection(
                                title="Reading the evidence",
                                body=("Motion limits and generator configuration must match.")
                                + "\n\n"
                                + (
                                    "Samples respect configured motion support and selected actions avoid extreme corners."
                                )
                                + "\n\n"
                                + (
                                    "A view action is geometric: step length and yaw change must be interpreted together because an apparently modest value on either axis can be implausible in combination."
                                )
                                + "\n\n"
                                + (
                                    "This is a bounded audit sample with no fitted motion model; density and empty regions are diagnostic clues, not calibrated probabilities."
                                ),
                            ),
                            ExplanationSection(
                                title="What to investigate",
                                body=(
                                    "Outliers or family-specific streaks can indicate transform errors, unrealistic moves, or constraint failures."
                                )
                                + "\n\n"
                                + (
                                    "Motion step length is camera-center displacement in metres and motion yaw delta is the signed change in horizontal orientation in degrees."
                                ),
                            ),
                        ),
                        evidence_role="actor-visible",
                        source_fields=(
                            "candidate_diagnostics/motion_step_length_m",
                            "candidate_diagnostics/motion_yaw_delta_deg",
                        ),
                        external_references=(_PYTORCH3D_RENDERING_REFERENCE,),
                    ),
                )

        if {"target_root_gain", "position", "selected"}.issubset(candidates.columns):
            rewards = candidates.dropna(subset=["target_root_gain"])
            if not rewards.empty:
                render_scientific_notation("target_root_gain")
                fig = px.box(
                    rewards,
                    x="position",
                    y="target_root_gain",
                    color="selected",
                    points="outliers",
                    labels={"target_root_gain": current_scientific_label("target_root_gain")},
                    title=(f"{current_scientific_label('target_root_gain')} by candidate family and selection"),
                )
                _render_plot(
                    fig,
                    ScientificExplanation(
                        question="Which candidate families contain useful oracle reward support, and what does selection choose?",
                        answer="The boxes compare the oracle target-root-gain support offered by each family with the values on the actions actually selected.",
                        sections=(
                            ExplanationSection(
                                title="Following the population",
                                body=(
                                    "Bounded candidates with finite target root gain, split by family and selected state."
                                )
                                + "\n\n"
                                + (
                                    "Target root-normalized gain, dimensionless; negative valid rewards remain real values."
                                )
                                + "\n\n"
                                + (
                                    "Finite oracle labels only; invalid or missing labels are excluded rather than assigned low reward."
                                )
                                + "\n\n"
                                + (
                                    "Each box summarizes finite candidate gains by family and selected state; outliers remain visible instead of being folded into an average."
                                ),
                            ),
                            ExplanationSection(
                                title="Reading the evidence",
                                body=(
                                    "Target protocol, reward definition, candidate mixture, and row limit must match."
                                )
                                + "\n\n"
                                + (
                                    "Selected rewards occupy competitive support without every family collapsing to one value."
                                )
                                + "\n\n"
                                + (
                                    "Family-level reward support asks what choices were available, while selected marks reveal which part of that support the behavior policy used."
                                )
                                + "\n\n"
                                + (
                                    "Only candidates with finite privileged oracle labels contribute, and the bounded plot sample is descriptive; invalid or unlabeled rows are excluded rather than assigned a poor gain."
                                ),
                            ),
                            ExplanationSection(
                                title="What to investigate",
                                body=(
                                    "Selected low-tail rewards suggest policy mismatch; missing families suggest generator or label coverage gaps."
                                )
                                + "\n\n"
                                + (
                                    "Target root gain is the target reconstruction-error reduction normalized by the root reconstruction error; negative finite values remain valid measurements."
                                ),
                            ),
                        ),
                        evidence_role="oracle/evaluation",
                        source_fields=(
                            "candidates/target_root_gain",
                            "candidates/selected_mask",
                            "candidates/position_id",
                        ),
                        theory=TheoryReferences(equation_ids=("rl.target_rri_reward",)),
                        external_references=(_EVIDENCE_REPORTING_REFERENCE,),
                    ),
                )
