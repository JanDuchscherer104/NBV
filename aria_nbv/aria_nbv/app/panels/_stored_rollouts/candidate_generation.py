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

from ....rollouts.inspection import CANDIDATE_GROUP_FIELDS
from .session import _cached_projection, _cached_store_bundle
from .shared import ScientificExplanation
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
            population="Every candidate row matching the visible policy/depth filters, including actor-valid and actor-invalid rows, aggregated through proposal signature, actor validity, and outcome.",
            metric="Candidate count and fraction of the filtered root population; no reward or geometric units.",
            denominator_masks="The filtered complete candidate population is the root denominator. Actor validity is a hard action constraint; selected actor-invalid rows remain explicit selection_contract_violation evidence.",
            comparability="Candidate proposal signatures, budgets, and active policy/depth filters must match.",
            expected_pattern="Intended center/view proposal signatures retain actor-valid support, while invalid rows terminate at explicit reasons and selected rows remain actor-valid.",
            failure_interpretation="Unknown provenance indicates missing persisted labels; concentrated invalid reasons indicate support loss; selection_contract_violation is a hard invariant failure.",
            evidence_role="provenance",
            answer="The flow separates what the generator proposed, what the actor could execute, and what the rollout ultimately selected or rejected.",
            intuition="Following one conserved candidate population through these stages distinguishes lack of support from a later selection or labeling problem.",
            visual_encoding="Link width is the candidate count and the hover label gives its fraction of the filtered root population; nodes are ordered by provenance stage.",
            uncertainty="This is an exact accounting of the filtered persisted rows, not a sampled estimate; filters change the root population and must be read with the result.",
            external_references=(_EVIDENCE_REPORTING_REFERENCE,),
            definition="Actor-valid means the candidate satisfies executable-action constraints; selected rows are the persisted actions actually taken.",
            source_fields=(
                "inspection.candidate_flow_rows",
                "candidates/mixture_id",
                "candidates/position_id",
                "candidates/strategy_id",
                "candidates/actor_action_mask",
                "candidates/selected_mask",
                "candidates/primary_invalid_reason",
            ),
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
                population="One persisted selected rollout step matching the active policy/depth filters.",
                metric="Selected-step count and target-RRI competition rank among finite actor-valid candidates.",
                denominator_masks="The root denominator is selected rollout steps. Target-RRI rank excludes actor-invalid and non-finite alternatives; unavailable ranks remain explicit.",
                comparability="Compare policies only under matched roots, targets, candidate proposals, acquisition budgets, and score semantics.",
                expected_pattern="Temperature-softmax covers more than rank one without collapsing to uniformly poor target-RRI ranks; greedy policies concentrate near the top.",
                failure_interpretation="Unavailable ranks indicate missing oracle diagnostics; high-rank concentration can indicate excessive temperature or score/RRI mismatch.",
                evidence_role="oracle/evaluation",
                answer="The flow shows which policy produced each executed action and how that action ranked among the valid oracle-scored alternatives available at that same step.",
                intuition="A selected action can be diverse without being arbitrary: its target-RRI rank gives a local opportunity-cost diagnostic after action validity has been enforced.",
                visual_encoding="Link width is selected-step count; policy and temperature label the first stage, while the terminal node is the shell-local target-RRI rank bucket.",
                uncertainty="Ranks are unavailable when oracle evaluation is absent and are shell-local, so the chart is descriptive rather than a cross-scene policy effect estimate.",
                external_references=(_EVIDENCE_REPORTING_REFERENCE,),
                definition="Target-RRI rank orders finite target-RRI values only among actor-valid candidates in one persisted candidate shell.",
                source_fields=(
                    "inspection.selected_candidate_rank_rows",
                    "rollouts/policy_id",
                    "rollouts/temperature",
                    "candidates/selection_probabilities",
                    "candidates/selection_logits",
                    "candidates/target_rri",
                ),
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
                population="Candidate rows grouped by root-relative position family.",
                metric="Actor-valid fraction of sampled rows and selected/actor-valid rate; both dimensionless fractions.",
                denominator_masks="Availability uses the full family shell; selection rate uses actor-valid family rows only.",
                comparability="Family names, mixture weights, and branch budgets must match across stores.",
                expected_pattern="Useful families retain availability and non-degenerate normalized selection without monopolizing support.",
                failure_interpretation="High raw selection with tiny availability can be unstable; zero availability is a generator/mask clue.",
                evidence_role="actor-visible",
                answer="The paired bars separate a family's opportunity to be chosen from the rate at which it is chosen when that opportunity exists.",
                intuition="Raw selections conflate availability and preference, whereas selection divided by actor-valid support asks which usable family the policy favors.",
                visual_encoding="For each family, one bar is its actor-valid fraction of the sampled shell and the other is selected divided by actor-valid count.",
                uncertainty="Both fractions are exact store summaries; a low-support family can have a volatile normalized rate, so read availability before inferring preference.",
                external_references=(_EVIDENCE_REPORTING_REFERENCE,),
                definition="Selection rate given availability = selected candidate rows / actor-valid candidate rows for that family.",
                source_fields=("candidate position_id", "actor_action_mask", "selected_mask"),
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
                population=f"Complete-store candidate rows grouped by persisted {breakdown_by} provenance.",
                metric="Candidate count in each explicitly named mask population.",
                denominator_masks="Actor-valid, q_train, and selected are overlapping sets, not sequential waterfall stages.",
                comparability="Candidate protocol, group vocabulary, and store schema must match.",
                expected_pattern="Trainable support is no larger than label availability permits, and selection stays within actor support.",
                failure_interpretation="Missing groups, selected-only spikes, or large actor/train gaps identify generator, mask, or label-cache issues.",
                evidence_role="derived training data",
                answer="The grouped counts reveal where candidates are executable, label-trainable, or actually selected without pretending those masks form a single pipeline.",
                intuition="Actor validity, oracle-label availability, and selection answer different questions; their overlap exposes where supervision or action support is lost.",
                visual_encoding="Each bar is an exact count for one persisted provenance group and mask population; grouped bars permit within-group comparison.",
                uncertainty="Counts are descriptive and mask populations overlap, so bar heights must not be added or read as mutually exclusive stages.",
                external_references=(_EVIDENCE_REPORTING_REFERENCE,),
                definition="q_train marks candidates with both actor-action validity and the required oracle-label evidence for Q_H supervision.",
                source_fields=(
                    "inspection.candidate_group_summary_rows",
                    f"candidate {breakdown_by}",
                    "candidate masks",
                ),
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
                    population="One target proposal with finite rank and selection score.",
                    metric="Selection rank is ordinal; selection score is a dimensionless configured composite.",
                    denominator_masks="All scored target proposals, including actor-invalid and GT-invalid rows.",
                    comparability="Target-selection weights, proposal source, and GT-matching protocol must match.",
                    expected_pattern="Higher-priority ranks follow higher scores while validity classes remain visibly distinct.",
                    failure_interpretation="Rank inversions, score ties, or high-scoring invalid targets indicate selection or matching problems.",
                    evidence_role="provenance",
                    answer="The scatter checks whether the persisted ordinal priority is consistent with the configured score while retaining each target's validity status.",
                    intuition="Rank is an ordering of a score, so inversions, ties, or valid/invalid separation make target-selection behavior inspectable rather than implicit.",
                    visual_encoding="Each mark is one target proposal; horizontal position is its stored rank, vertical position is score, and visual groups retain GT-match status and label validity.",
                    uncertainty="This is a finite proposal audit, not a calibration curve; scores are configuration-dependent and should only be compared under the same target protocol.",
                    external_references=(_EVIDENCE_REPORTING_REFERENCE,),
                    definition="Selection rank is the persisted ordinal priority assigned by the target-selection procedure; smaller ranks denote earlier priority.",
                    source_fields=("targets/selection_rank", "targets/selection_score", "targets/gt_match_status_id"),
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
                        population=f"One target proposal with finite selection score and {support_field}.",
                        metric=f"{support_field} and selection score are dimensionless configured diagnostics.",
                        denominator_masks="Scored target proposals; actor and GT validity remain explicit marks.",
                        comparability="Support computation, crop geometry, score weights, and target source must match.",
                        expected_pattern="Support contributes monotonically without becoming the only determinant of score.",
                        failure_interpretation="High scores at negligible support or validity-separated clusters can reveal weighting or GT-association issues.",
                        evidence_role="oracle/evaluation",
                        answer="The scatter shows whether the selected support diagnostic contributes plausibly to the persisted target-selection score.",
                        intuition="Support should inform confidence that a target is observable, but a composite score should not be explained by one diagnostic alone.",
                        visual_encoding="Each mark is one finite target proposal; x is the chosen support diagnostic, y is selection score, and groups retain validity and GT-match evidence.",
                        uncertainty="The apparent relationship is descriptive and may be shaped by other score terms, target sources, or missing GT labels; it is not a fitted effect.",
                        external_references=(_EVIDENCE_REPORTING_REFERENCE,),
                        definition="The persisted selection score is a configured target-priority composite; its individual components are diagnostics, not independent outcomes.",
                        source_fields=(
                            f"targets/{support_field}",
                            "targets/selection_score",
                            "targets/gt_label_valid_mask",
                        ),
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
                    population="Pairwise-complete target proposals for each component pair.",
                    metric="Pearson correlation coefficient, dimensionless in [-1, 1].",
                    denominator_masks="Finite pairwise component values; pairwise denominators may differ.",
                    comparability="Only compare matrices from identical score definitions and target protocols.",
                    expected_pattern="Components reflect their intended roles without perfect accidental duplication.",
                    failure_interpretation="Near-perfect correlations suggest redundancy; unexpected signs can expose score wiring errors.",
                    evidence_role="oracle/evaluation",
                    answer="The heatmap is descriptive evidence of linear association between persisted score components, with pair-local support shown for every cell.",
                    intuition="Pearson r compares centered component values within the same finite pair; it diagnoses redundancy or opposition but does not establish causality.",
                    visual_encoding="Cell color encodes r from -1 to 1; each annotation and hover label reports r and the exact pairwise finite n.",
                    uncertainty="Pairs with n=2 are algebraically forced to |r|=1 and are not substantive evidence; missing or constant pairs are withheld.",
                    external_references=(_CORRELATION_REFERENCE,),
                    definition="Pearson r is the standardized covariance of the same pair-local finite observations.",
                    source_fields=tuple(f"targets/{name}" for name in component_cols),
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


def _render_candidate_geometry_diagnostics(
    candidates: pd.DataFrame,
    root_geometry: pd.DataFrame,
    *,
    total_candidates: int,
) -> None:
    """Restore bounded candidate plots in scientifically valid root-relative coordinates."""

    if candidates.empty:
        return
    with st.expander("Candidate geometry, motion, angles, and reward support", expanded=True):
        st.caption(
            f"Interactive plots use {len(candidates):,} of {total_candidates:,} candidate rows. "
            "Coordinates are root-relative ARIA world metres (RIGHT_HAND_Z_UP), never pooled absolute scene origins."
        )
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
            metric = st.selectbox("Geometry / label distribution", options=metric_options)
            metric_rows = candidates.dropna(subset=[metric])
            fig = px.histogram(
                metric_rows,
                x=metric,
                color="invalid_reason" if "invalid_reason" in metric_rows else None,
                marginal="box",
                title=f"{metric} distribution",
            )
            _render_plot(
                fig,
                ScientificExplanation(
                    question=f"What is the support, tail behavior, and invalidity structure of {metric}?",
                    population="Bounded candidate audit rows with a finite selected metric.",
                    metric=f"{metric}; units follow the field suffix (`_m`, `_deg`) or are dimensionless for reward/RRI.",
                    denominator_masks="Finite metric rows; invalid reasons remain explicit rather than silently filtered.",
                    comparability="Field definition, candidate protocol, and interactive row limit must match.",
                    expected_pattern="Support respects configured physical bounds and avoids unexplained clipping or spikes.",
                    failure_interpretation="Heavy tails, discontinuities, or invalidity-specific modes guide row-level debugging.",
                    evidence_role="oracle/evaluation"
                    if metric in {"target_root_gain", "target_rri"}
                    else "actor-visible",
                    answer=f"The distribution shows the observed support and tails of {metric}, with invalidity retained as a diagnostic stratum.",
                    intuition="Physical and scoring diagnostics are most useful when their full range and any validity-specific modes are visible before selecting an individual row to inspect.",
                    visual_encoding="Histogram bars count finite candidate rows, color separates invalidity reasons, and the marginal box plot summarizes center, spread, and outliers.",
                    uncertainty="This is a bounded interactive sample rather than a corpus estimate; rare tails can be absent at the current plot limit and invalid rows are not silently imputed.",
                    external_references=(_EVIDENCE_REPORTING_REFERENCE,),
                    definition="Metric suffixes `_m` and `_deg` denote metres and degrees; target-root gain and RRI are dimensionless oracle-evaluation quantities.",
                    source_fields=(f"candidate audit/{metric}", "candidates/invalid_reason_bitset"),
                ),
            )
        if not root_geometry.empty:
            fig = px.scatter(
                root_geometry,
                x="root_relative_x_m",
                y="root_relative_y_m",
                color="position" if "position" in root_geometry else None,
                symbol="selected" if "selected" in root_geometry else None,
                hover_data=[
                    name
                    for name in ("rollout_row_id", "step_index", "root_relative_z_m", "actor_action", "mixture")
                    if name in root_geometry
                ],
                title="Candidate centers relative to each rollout root (ground plane)",
            )
            fig.update_yaxes(scaleanchor="x", scaleratio=1)
            _render_plot(
                fig,
                ScientificExplanation(
                    question="Do candidate families cover the intended local motion support around each rollout root?",
                    population="Bounded candidate rows translated by their own rollout root; unrelated scene origins are removed.",
                    metric="Root-relative X/Y displacement in metres; Z-up height is available on hover.",
                    denominator_masks="Bounded full candidate shell; actor validity and selection remain explicit fields.",
                    comparability="Coordinate convention, generator profile, and plotting row limit must match.",
                    expected_pattern="Families occupy their intended local regions with selected actions inside actor-valid support.",
                    failure_interpretation="Collapsed clusters, extreme radii, or family overlap can expose pose, frame, or generator defects.",
                    evidence_role="actor-visible",
                    answer="The ground-plane map tests whether each candidate family occupies its intended local support around its own rollout root.",
                    intuition="Subtracting every rollout root makes local candidate motion comparable without mixing unrelated scene-world origins.",
                    visual_encoding="Each point is one candidate center in root-relative metres; color is family and symbol retains whether the candidate was selected.",
                    uncertainty="Only bounded plotted rows with finite coordinates appear, so this supports geometric diagnosis rather than an exhaustive count or an uncertainty estimate.",
                    external_references=(_PYTORCH3D_RENDERING_REFERENCE,),
                    definition="Root-relative position = candidate camera center in world coordinates minus the selected rollout root camera center, expressed in metres.",
                    source_fields=(
                        "inspection.root_relative_candidate_rows",
                        "candidate pose_world_cam",
                        "rollout root_pose_world",
                    ),
                ),
            )
            three_dimensional = root_geometry.dropna(
                subset=["root_relative_x_m", "root_relative_y_m", "root_relative_z_m"]
            )
            if not three_dimensional.empty:
                fig = px.scatter_3d(
                    three_dimensional,
                    x="root_relative_x_m",
                    y="root_relative_y_m",
                    z="root_relative_z_m",
                    color="position" if "position" in three_dimensional else None,
                    symbol="selected" if "selected" in three_dimensional else None,
                    hover_data=[
                        name
                        for name in ("rollout_row_id", "step_index", "actor_action", "mixture")
                        if name in three_dimensional
                    ],
                    title="Candidate centers relative to each rollout root (3D)",
                )
                fig.update_layout(scene={"aspectmode": "data"})
                _render_plot(
                    fig,
                    ScientificExplanation(
                        question="Do candidate families occupy the intended local three-dimensional motion support?",
                        population="Bounded candidate rows translated by their own rollout root; unrelated scene origins are removed.",
                        metric="Root-relative X/Y/Z displacement in metres, with Z as ARIA world up.",
                        denominator_masks="Rows with finite root-relative X, Y, and Z coordinates; actor validity and selection remain explicit fields.",
                        comparability="Coordinate convention, generator profile, and plotting row limit must match.",
                        expected_pattern="Families occupy their intended local volume with selected actions inside actor-valid support.",
                        failure_interpretation="Flattened, collapsed, or implausibly elevated clusters can expose frame, pose, or generator defects.",
                        evidence_role="actor-visible",
                        answer="The three-dimensional view tests the same root-relative candidate support while making vertical displacement visible rather than hover-only.",
                        intuition="A family can appear plausible in the ground plane but still collapse or drift vertically, so the Z-up dimension is a separate geometry check.",
                        visual_encoding="Each point is one finite root-relative candidate center; x, y, and z are metres, color is family, and symbol retains selection state.",
                        uncertainty="The display is bounded to interactive rows and preserves only finite coordinates; it is a diagnostic projection, not a rendered reconstruction or coverage proof.",
                        external_references=(_PYTORCH3D_RENDERING_REFERENCE,),
                        definition="ARIA uses a right-handed Z-up world convention here; the plotted coordinates are local differences, not absolute scene positions.",
                        source_fields=(
                            "inspection.root_relative_candidate_rows",
                            "candidate pose_world_cam",
                            "rollout root_pose_world",
                        ),
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
                    population="Bounded candidate rows with finite bearing or motion-yaw diagnostics.",
                    metric="Yaw angle in degrees in the persisted ARIA convention.",
                    denominator_masks="Finite angle diagnostics; invalid candidates remain included unless absent from the persisted audit row.",
                    comparability="Angle convention, generator families, and candidate budget must match.",
                    expected_pattern="Executed yaw support overlaps relevant target bearings without implausible spikes.",
                    failure_interpretation="Systematic offsets suggest frame errors; narrow motion support suggests generator or constraint collapse.",
                    evidence_role="actor-visible",
                    answer="The overlaid angle distributions show whether proposed motion yaw reaches the target-relative bearings represented in the stored candidate audit.",
                    intuition="A candidate family can meet translation limits yet miss the target if its camera orientation is systematically offset from useful bearing directions.",
                    visual_encoding="Histogram position is yaw angle in degrees; color distinguishes target-bearing diagnostics from executed motion-yaw changes.",
                    uncertainty="Finite diagnostic rows are counted without a directional-confidence model; wrap-around and sparse tails require row-level interpretation rather than a single average.",
                    external_references=(_PYTORCH3D_RENDERING_REFERENCE,),
                    definition="Yaw is the persisted signed horizontal rotation in degrees under the rollout coordinate convention, displayed on [-180°, 180°].",
                    source_fields=(
                        "candidate_diagnostics/target_bearing_yaw_deg",
                        "candidate_diagnostics/motion_yaw_delta_deg",
                    ),
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
                        population="Bounded candidate rows with finite motion diagnostics.",
                        metric="Step length in metres and yaw change in degrees.",
                        denominator_masks="Finite motion rows; validity, family, and selected state remain inspectable.",
                        comparability="Motion limits and generator configuration must match.",
                        expected_pattern="Samples respect configured motion support and selected actions avoid extreme corners.",
                        failure_interpretation="Outliers or family-specific streaks can indicate transform errors, unrealistic moves, or constraint failures.",
                        evidence_role="actor-visible",
                        answer="The scatter checks whether sampled and selected actions jointly respect plausible translation and rotation support.",
                        intuition="A view action is geometric: step length and yaw change must be interpreted together because an apparently modest value on either axis can be implausible in combination.",
                        visual_encoding="Each finite candidate is plotted by translation metres and yaw degrees; color identifies family and symbol marks selected candidates.",
                        uncertainty="This is a bounded audit sample with no fitted motion model; density and empty regions are diagnostic clues, not calibrated probabilities.",
                        external_references=(_PYTORCH3D_RENDERING_REFERENCE,),
                        definition="Motion step length is camera-center displacement in metres and motion yaw delta is the signed change in horizontal orientation in degrees.",
                        source_fields=(
                            "candidate_diagnostics/motion_step_length_m",
                            "candidate_diagnostics/motion_yaw_delta_deg",
                        ),
                    ),
                )

        if {"target_root_gain", "position", "selected"}.issubset(candidates.columns):
            rewards = candidates.dropna(subset=["target_root_gain"])
            if not rewards.empty:
                fig = px.box(
                    rewards,
                    x="position",
                    y="target_root_gain",
                    color="selected",
                    points="outliers",
                    title="Target root gain by candidate family and selection",
                )
                _render_plot(
                    fig,
                    ScientificExplanation(
                        question="Which candidate families contain useful oracle reward support, and what does selection choose?",
                        population="Bounded candidates with finite target root gain, split by family and selected state.",
                        metric="Target root-normalized gain, dimensionless; negative valid rewards remain real values.",
                        denominator_masks="Finite oracle labels only; invalid or missing labels are excluded rather than assigned low reward.",
                        comparability="Target protocol, reward definition, candidate mixture, and row limit must match.",
                        expected_pattern="Selected rewards occupy competitive support without every family collapsing to one value.",
                        failure_interpretation="Selected low-tail rewards suggest policy mismatch; missing families suggest generator or label coverage gaps.",
                        evidence_role="oracle/evaluation",
                        answer="The boxes compare the oracle target-root-gain support offered by each family with the values on the actions actually selected.",
                        intuition="Family-level reward support asks what choices were available, while selected marks reveal which part of that support the behavior policy used.",
                        visual_encoding="Each box summarizes finite candidate gains by family and selected state; outliers remain visible instead of being folded into an average.",
                        uncertainty="Only candidates with finite privileged oracle labels contribute, and the bounded plot sample is descriptive; invalid or unlabeled rows are excluded rather than assigned a poor gain.",
                        external_references=(_EVIDENCE_REPORTING_REFERENCE,),
                        definition="Target root gain is the target reconstruction-error reduction normalized by the root reconstruction error; negative finite values remain valid measurements.",
                        source_fields=(
                            "candidates/target_root_gain",
                            "candidates/selected_mask",
                            "candidates/position_id",
                        ),
                    ),
                )
