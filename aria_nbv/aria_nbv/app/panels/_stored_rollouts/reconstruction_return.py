"""Reconstruction, return, and temporal evidence presentation."""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ....rollouts.inspection import rollout_endpoint_metric_summary
from ....rollouts.reporting import RolloutCorpusSummary
from .shared import ScientificExplanation
from .shared import download_frame as _download_frame
from .shared import plot_control_key as _plot_control_key
from .shared import render_plot as _render_plot

_TEMPORAL_METRIC_LABELS = {
    "Cumulative target root gain": "cumulative_target_root_gain",
    "Selected one-step target root gain": "selected_target_root_gain",
    "Selected target RRI": "selected_target_rri",
    "Marginal target RRI": "marginal_target_rri",
    "Valid candidate fanout": "valid_fanout",
    "Invalid candidate fraction": "invalid_fraction",
    "Selected-action probability": "selected_probability",
    "Selected-action entropy": "selected_entropy",
}
_TEMPORAL_GROUP_CLASSES = {
    "Upstream experiment dimensions": ("policy", "horizon", "budget_configuration"),
    "Selected-action provenance (descriptive, non-causal)": (
        "selected_position",
        "selected_strategy",
        "selected_mixture",
    ),
}
_TEMPORAL_SOURCE_FIELDS = {"valid_fanout": "num_valid_candidates"}
_TEMPORAL_EVIDENCE_ROLES: dict[
    str, Literal["actor-visible", "oracle/evaluation", "derived training data", "provenance"]
] = {
    "cumulative_target_root_gain": "oracle/evaluation",
    "selected_target_root_gain": "oracle/evaluation",
    "selected_target_rri": "oracle/evaluation",
    "marginal_target_rri": "oracle/evaluation",
    "valid_fanout": "actor-visible",
    "invalid_fraction": "actor-visible",
    "selected_probability": "actor-visible",
    "selected_entropy": "actor-visible",
}


def _render_corpus_temporal_evidence(summary: RolloutCorpusSummary | None) -> None:
    """Render compatible-shard factual temporal reward/reconstruction evidence."""

    if summary is None:
        st.info("Build the corpus summary in Overview before viewing aggregate reward evidence.")
        return
    temporal = summary.temporal_summary
    if temporal.empty:
        st.info("No validated factual temporal rows are available.")
        return
    metric_names = list(dict.fromkeys(str(value) for value in temporal["metric"].dropna()))
    metric = st.selectbox("Corpus temporal metric", options=metric_names, key="corpus_temporal_metric")
    rows = temporal.loc[temporal["metric"] == metric].copy()
    group_fields = [field for field in ("contract", "policy", "temperature", "horizon") if field in rows]
    rows["series"] = rows[group_fields].astype(str).agg(" · ".join, axis=1) if group_fields else "corpus"
    figure = go.Figure()
    for series, group in rows.groupby("series", sort=True):
        group = group.sort_values("step_index")
        figure.add_trace(
            go.Scatter(x=group["step_index"], y=group["q25"], mode="lines", line={"width": 0}, showlegend=False)
        )
        figure.add_trace(
            go.Scatter(
                x=group["step_index"],
                y=group["q75"],
                mode="lines",
                line={"width": 0},
                fill="tonexty",
                name=str(series),
                opacity=0.2,
            )
        )
        figure.add_trace(
            go.Scatter(
                x=group["step_index"],
                y=group["median"],
                mode="lines+markers",
                name=str(series),
                customdata=group[["finite_count", "total_count", "store_count"]],
                hovertemplate="step=%{x}<br>median=%{y:.4g}<br>finite=%{customdata[0]:.0f} / %{customdata[1]:.0f}<br>stores=%{customdata[2]:.0f}<extra></extra>",
            )
        )
    figure.update_layout(
        title=f"{metric}: corpus median and IQR by factual depth", xaxis_title="factual step_index", yaxis_title="value"
    )
    _render_plot(
        figure,
        ScientificExplanation(
            question="How does this reward or reconstruction metric evolve across selected compatible shards?",
            population="Factual finite step rows separated by persisted contract, policy, temperature, and horizon.",
            metric="Median and interquartile range; hover shows finite/total rows and store count.",
            denominator_masks="Observed factual rows only; early-terminated rollouts are not zero-filled.",
            comparability="Only identical persisted contracts are comparable.",
            expected_pattern="The IQR reflects between-row spread, not a confidence interval.",
            failure_interpretation="Small depth counts or abrupt missingness require store-level drill-down.",
            evidence_role="oracle/evaluation",
            source_fields=("reporting.RolloutCorpusSummary.temporal_summary", "steps", "rollout contract"),
        ),
    )
    with st.expander("Temporal rows and CSV", expanded=False):
        st.dataframe(rows.drop(columns="series"), hide_index=True, width="stretch")
        _download_frame("Download temporal rows CSV", "corpus-temporal-summary.csv", rows.drop(columns="series"))


def _render_scientific_evidence(session_handle: object) -> None:
    st.subheader("Scientific evidence")
    _render_reconstruction_summary(session_handle)
    cohort = session_handle.cohorts()
    eligibility = bool(cohort.get("eligible"))
    st.metric("Matched comparison eligible", "YES" if eligibility else "NO")
    st.caption(
        "Policies are comparison dimensions only after source sample, target protocol, horizon/budget, candidate/oracle configuration, and branch schedule match."
    )
    if eligibility:
        comparison = pd.DataFrame(session_handle.paired())
        if comparison.empty:
            st.info("Matched cohorts exist, but no finite paired endpoint metric is available.")
        else:
            y = (
                "median_paired_delta"
                if "median_paired_delta" in comparison
                else comparison.select_dtypes("number").columns[-1]
            )
            label = "policy_pair" if "policy_pair" in comparison else comparison.columns[0]
            color = "metric" if "metric" in comparison else None
            comparison[y] = pd.to_numeric(comparison[y], errors="coerce")
            ci_high = pd.to_numeric(comparison["bootstrap_ci_high"], errors="coerce")
            ci_low = pd.to_numeric(comparison["bootstrap_ci_low"], errors="coerce")
            comparison["ci_plus"] = ci_high - comparison[y]
            comparison["ci_minus"] = comparison[y] - ci_low
            fig = px.bar(
                comparison,
                x=label,
                y=y,
                color=color,
                error_y="ci_plus",
                error_y_minus="ci_minus",
                barmode="group",
                title="Paired matched-cohort deltas with deterministic bootstrap intervals",
            )
            _render_plot(
                fig,
                ScientificExplanation(
                    question="Within exactly matched cohorts, how do policies differ at the rollout endpoint?",
                    population="One paired delta per matched source/target/recipe/budget cohort, summarized by policy pair.",
                    metric="Median paired target endpoint or root-gain delta; RRI/root gain are dimensionless.",
                    denominator_masks="Only finite matched endpoint rows; sample count and IQR/bootstrap interval remain in the table.",
                    comparability="All cohort keys must match; policy/recipe is the only intended comparison dimension.",
                    expected_pattern="Intervals and paired deltas are stable across cohorts rather than driven by one scene.",
                    failure_interpretation="Wide intervals or sign changes indicate weak evidence; they are not policy wins.",
                    evidence_role="oracle/evaluation",
                    source_fields=("inspection.paired_policy_comparison_rows", "rollouts", "steps"),
                ),
            )
            st.dataframe(comparison, hide_index=True, width="stretch")
            _download_frame("Download paired comparison CSV", "paired-policy-comparison.csv", comparison)
    else:
        mismatch = pd.DataFrame(cohort.get("mismatch_rows", []))
        st.warning("Policy comparison is blocked because the store does not contain an exact matched cohort.")
        if not mismatch.empty:
            st.dataframe(mismatch, hide_index=True, width="stretch")
            _download_frame("Download mismatch evidence CSV", "policy-cohort-mismatches.csv", mismatch)

    steps = pd.DataFrame(session_handle.steps())
    if not steps.empty:
        _render_temporal_explorer(session_handle, steps, matched_cohorts=eligibility)
        _download_frame("Download selected-chain CSV", "selected-chain-evidence.csv", steps)

    with st.expander("Additional branching and selected-rank evidence", expanded=False):
        if st.toggle(
            "Load branching, rank/regret, and root-relative evidence",
            value=False,
            help="These projections traverse every factual step and candidate shell, then remain cached for this store.",
        ):
            _render_branching_evidence(steps, pd.DataFrame(session_handle.tree()))
            _render_selected_rank_and_geometry(session_handle)


def _render_reconstruction_summary(session_handle: object) -> None:
    """Render frozen reconstruction, return, and headroom rows on demand."""

    if not st.toggle(
        "Load reconstruction endpoints, discounted returns, and oracle headroom",
        value=False,
        help="Materializes only frozen inspection projections after this explicit request.",
    ):
        return

    metric_rows = pd.DataFrame(session_handle.reconstruction_metrics())
    endpoint_rows = pd.DataFrame(session_handle.reconstruction_endpoints())
    discounted = session_handle.discounted_returns()
    headroom = session_handle.headroom()

    st.markdown("#### Reconstruction and selection metric plan")
    if metric_rows.empty:
        st.info("No factual reconstruction metric rows are available.")
    else:
        st.dataframe(metric_rows, hide_index=True, width="stretch")
        _download_frame("Download reconstruction metric CSV", "reconstruction-metrics.csv", metric_rows)
    if not endpoint_rows.empty:
        st.dataframe(endpoint_rows, hide_index=True, width="stretch")
        _download_frame("Download endpoint summary CSV", "reconstruction-endpoints.csv", endpoint_rows)

    st.markdown("#### Discounted factual selected gain")
    discounted_rows = pd.DataFrame(discounted.get("rows", []))
    if bool(discounted.get("available")) and not discounted_rows.empty:
        st.caption(str(discounted.get("reason")))
        st.dataframe(discounted_rows, hide_index=True, width="stretch")
        _download_frame("Download discounted return CSV", "discounted-returns.csv", discounted_rows)
    else:
        st.info(f"Discounted return unavailable: {discounted.get('reason', 'no factual rows')}")

    st.markdown("#### Exact-role oracle headroom diagnostics")
    st.caption("These are diagnostic contrasts, not causal policy comparisons. Exclusions remain explicit.")
    headroom_rows = pd.DataFrame(headroom.get("contrast_rows", []))
    headroom_summary = pd.DataFrame(headroom.get("summary_rows", []))
    if headroom_rows.empty:
        st.info("No exact-role headroom contrasts are available.")
    else:
        st.dataframe(headroom_rows, hide_index=True, width="stretch")
        _download_frame("Download headroom contrasts CSV", "oracle-headroom-contrasts.csv", headroom_rows)
    if not headroom_summary.empty:
        st.dataframe(headroom_summary, hide_index=True, width="stretch")


def _render_temporal_explorer(session_handle: object, steps: pd.DataFrame, *, matched_cohorts: bool) -> None:
    """Render one population metric at a time and a one-rollout raw drill-down."""

    available_labels = [
        label
        for label, metric in _TEMPORAL_METRIC_LABELS.items()
        if (source := _TEMPORAL_SOURCE_FIELDS.get(metric, metric)) in steps and steps[source].notna().any()
    ]
    if not available_labels:
        st.info("No supported finite temporal metric is available in this store.")
        return
    metric_label = st.selectbox("Temporal metric", options=available_labels)
    metric = _TEMPORAL_METRIC_LABELS[metric_label]
    group_class = st.selectbox("Temporal grouping class", options=list(_TEMPORAL_GROUP_CLASSES))
    group_field = st.selectbox("Temporal grouping field", options=list(_TEMPORAL_GROUP_CLASSES[group_class]))
    if group_class.startswith("Selected-action provenance"):
        st.warning(
            "Selected-action provenance is descriptive and post-selection, not a causal sampling-policy effect. "
            "It explains which persisted provenance supplied selected outcomes; full candidate-family availability "
            "belongs to the support flow in Targets & Action Support."
        )
    elif group_field == "policy":
        comparison_status = "eligible" if matched_cohorts else "not eligible"
        st.caption(
            f"Policy trajectories are descriptive here; exact matched-cohort inference is {comparison_status} "
            "and remains a separate surface above."
        )

    summary = pd.DataFrame(
        session_handle.temporal(
            metric=metric,
            group_fields=(group_field,),
        )
    )
    if summary.empty:
        st.info(f"No temporal rows are available for {metric_label} grouped by {group_field}.")
        return
    finite_count = int(summary["finite_count"].sum())
    total_count = int(summary["total_count"].sum())
    missing_count = int(summary["missing_count"].sum())
    endpoint_depth = int(summary["step_index"].max())
    endpoint = rollout_endpoint_metric_summary(steps.to_dict("records"), metric=metric)
    endpoint_median = endpoint["median"]
    cols = st.columns(4)
    cols[0].metric("Finite temporal rows", f"{finite_count:,} / {total_count:,}")
    cols[1].metric("Missing temporal rows", f"{missing_count:,}")
    cols[2].metric("Observed depth", f"0–{endpoint_depth}")
    cols[3].metric(
        "Factual endpoint median",
        "n/a" if endpoint_median is None else f"{float(endpoint_median):.4g}",
        delta=f"{int(endpoint['finite_count']):,} / {int(endpoint['total_count']):,} finite",
        delta_color="off",
        help="One terminal factual step per rollout, including rollouts whose persisted horizon ends earlier.",
    )
    _render_plot(
        _temporal_summary_figure(summary, group_field=group_field, metric_label=metric_label),
        ScientificExplanation(
            question=f"How does {metric_label.lower()} change over persisted rollout depth?",
            population=f"One aggregate per {group_field} and step_index over factual selected-step rows; individual rollouts are not connected.",
            metric=f"Median with linear-interpolated IQR; units are {summary['units'].iloc[0]}.",
            denominator_masks="Each point reports finite_count / total_count and missing fraction; statistics use finite values only with no zero fill or depth interpolation.",
            comparability="Upstream policy/recipe groups are descriptive unless exact cohort keys match; selected-action provenance groups are post-selection strata only.",
            expected_pattern="Central tendency and dispersion change smoothly where repeated evidence exists, with sample size visible at every depth.",
            failure_interpretation="Wide IQR, small n, abrupt missingness, or divergent strata require row-level inspection; they are not automatically policy effects.",
            evidence_role=_temporal_evidence_role(metric),
            source_fields=(
                "inspection.temporal_metric_summary_rows",
                f"steps/{_TEMPORAL_SOURCE_FIELDS.get(metric, metric)}",
            ),
        ),
        log_y_key=_plot_control_key("temporal-summary", session_handle.canonical_path.as_posix(), metric, group_field),
    )
    st.dataframe(summary, hide_index=True, width="stretch")
    _download_frame("Download temporal summary CSV", "temporal-metric-summary.csv", summary)

    with st.expander("Raw selected-rollout trajectory drill-down", expanded=False):
        rollout_ids = sorted(int(value) for value in steps["rollout_row_id"].dropna().unique().tolist())
        selected_rollout = st.selectbox("Raw trajectory rollout", options=rollout_ids)
        selected_rows = steps.loc[steps["rollout_row_id"] == selected_rollout].sort_values("step_index")
        source_field = _TEMPORAL_SOURCE_FIELDS.get(metric, metric)
        raw = selected_rows.dropna(subset=[source_field])
        if raw.empty:
            st.info(f"Rollout {selected_rollout} has no finite {metric_label.lower()} rows.")
        else:
            fig = px.line(
                raw,
                x="step_index",
                y=source_field,
                markers=True,
                title=f"Raw trajectory for rollout {selected_rollout}",
                hover_data=[column for column in ("step_row_id", "policy") if column in raw],
            )
            _render_plot(
                fig,
                ScientificExplanation(
                    question=f"What exact {metric_label.lower()} trajectory produced rollout {selected_rollout}?",
                    population="One explicitly selected rollout only; no line joins unrelated rollout_row_id values.",
                    metric=f"Persisted {source_field}; units follow the aggregate view above.",
                    denominator_masks="Finite factual selected-step rows for this rollout; missing depths remain absent rather than interpolated.",
                    comparability="Use this for case inspection, not population or policy inference.",
                    expected_pattern="The raw trajectory should explain one aggregate contribution without hiding its exact step ids.",
                    failure_interpretation="Abrupt jumps or negative valid gains can identify an interesting case for Inspect/Rerun.",
                    evidence_role=_temporal_evidence_role(metric),
                    source_fields=("inspection.rollout_step_objective_rows", f"steps/{source_field}"),
                ),
                log_y_key=_plot_control_key(
                    "raw-trajectory", session_handle.canonical_path.as_posix(), metric, selected_rollout
                ),
            )


def _temporal_summary_figure(summary: pd.DataFrame, *, group_field: str, metric_label: str) -> go.Figure:
    """Build deterministic median/IQR traces without connecting rollout rows."""

    figure = go.Figure()
    palette = px.colors.qualitative.Plotly
    for index, (group_value, rows) in enumerate(summary.groupby(group_field, sort=True, dropna=False)):
        ordered = rows.sort_values("step_index")
        color = palette[index % len(palette)]
        custom = np.column_stack(
            (
                ordered["finite_count"],
                ordered["total_count"],
                ordered["missing_count"] / ordered["total_count"].clip(lower=1),
                ordered["mean"],
                ordered["min"],
                ordered["max"],
            )
        )
        figure.add_trace(
            go.Scatter(
                x=ordered["step_index"],
                y=ordered["q25"],
                mode="lines",
                line={"color": color, "width": 0},
                legendgroup=str(group_value),
                showlegend=False,
                hoverinfo="skip",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=ordered["step_index"],
                y=ordered["q75"],
                mode="lines",
                line={"color": color, "width": 0},
                fill="tonexty",
                fillcolor=_with_alpha(color, 0.18),
                legendgroup=str(group_value),
                showlegend=False,
                hoverinfo="skip",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=ordered["step_index"],
                y=ordered["median"],
                mode="lines+markers",
                line={"color": color},
                name=str(group_value),
                legendgroup=str(group_value),
                customdata=custom,
                hovertemplate=(
                    f"{group_field}={group_value}<br>step=%{{x}}<br>median=%{{y:.4g}}"
                    "<br>finite=%{customdata[0]:.0f} / %{customdata[1]:.0f}"
                    "<br>missing=%{customdata[2]:.1%}<br>mean=%{customdata[3]:.4g}"
                    "<br>min=%{customdata[4]:.4g}<br>max=%{customdata[5]:.4g}<extra></extra>"
                ),
            )
        )
    figure.update_layout(
        title=f"{metric_label}: median and interquartile range by rollout depth",
        xaxis_title="rollout step_index",
        yaxis_title=f"{summary['metric'].iloc[0]} ({summary['units'].iloc[0]})",
        hovermode="x unified",
    )
    return figure


def _with_alpha(color: str, alpha: float) -> str:
    """Convert one Plotly hex color into an rgba fill color."""

    red, green, blue = (int(color[index : index + 2], 16) for index in (1, 3, 5))
    return f"rgba({red},{green},{blue},{alpha})"


def _temporal_evidence_role(
    metric: str,
) -> Literal["actor-visible", "oracle/evaluation", "derived training data", "provenance"]:
    """Return the information boundary for one validated temporal metric."""

    try:
        return _TEMPORAL_EVIDENCE_ROLES[metric]
    except KeyError as exc:
        raise ValueError(f"Temporal metric {metric!r} has no explicit evidence role.") from exc


def _render_selected_rank_and_geometry(session_handle: object) -> None:
    """Render expensive selected-rank and complete root-relative evidence on demand."""

    ranks = pd.DataFrame(session_handle.ranks())
    if not ranks.empty:
        rank_col = "selected_rank" if "selected_rank" in ranks else next((c for c in ranks if "rank" in c), None)
        regret_col = "regret" if "regret" in ranks else next((c for c in ranks if "regret" in c), None)
        if rank_col and regret_col:
            fig = px.scatter(
                ranks,
                x=rank_col,
                y=regret_col,
                color="policy" if "policy" in ranks else None,
                hover_data=[c for c in ("rollout_row_id", "step_row_id", "valid_candidate_count") if c in ranks],
                title="Selected rank and regret among valid alternatives",
            )
            _render_plot(
                fig,
                ScientificExplanation(
                    question="How far is each selected action from the best valid persisted alternative?",
                    population="One factual selected step ranked only against actor-valid alternatives in its own candidate shell.",
                    metric="Rank is ordinal; regret is best-valid minus selected target root gain, dimensionless.",
                    denominator_masks="Actor-action-valid alternatives with finite target root gain; invalid/missing labels are excluded, not assigned low reward.",
                    comparability="Ranks are shell-local; compare regret only under equivalent reward definitions and budgets.",
                    expected_pattern="Most selected actions have low rank and small regret without total diversity collapse.",
                    failure_interpretation="High regret suggests selection/model mismatch; negative valid rewards remain distinct from invalid rows.",
                    evidence_role="oracle/evaluation",
                    source_fields=(
                        "inspection.selected_candidate_rank_rows",
                        "candidates/actor_action_mask",
                        "candidates/target_root_gain",
                    ),
                ),
            )
        st.dataframe(ranks, hide_index=True, width="stretch")
        _download_frame("Download selected rank/regret CSV", "selected-rank-regret.csv", ranks)

    geometry = pd.DataFrame(session_handle.root_geometry())
    if not geometry.empty:
        st.caption(
            "Coordinates are translated by each rollout root. Absolute world coordinates from unrelated scenes are never aggregated."
        )
        st.dataframe(geometry.head(500), hide_index=True, width="stretch")
        st.caption(f"Showing {min(500, len(geometry)):,} of {len(geometry):,}; export is complete.")
        _download_frame("Download root-relative geometry CSV", "root-relative-candidates.csv", geometry)


def _render_branching_evidence(steps: pd.DataFrame, tree: pd.DataFrame) -> None:
    """Restore selection, fanout, and family-provenance plots from the prior inspector."""

    with st.expander("Branching, selection confidence, and sampled families", expanded=True):
        probability_cols = [
            name for name in ("selected_probability", "selected_entropy") if name in steps and steps[name].notna().any()
        ]
        if probability_cols:
            long = steps.melt(
                id_vars=[name for name in ("rollout_row_id", "policy", "step_index") if name in steps],
                value_vars=probability_cols,
                var_name="metric",
                value_name="value",
            ).dropna(subset=["value"])
            fig = px.line(
                long,
                x="step_index",
                y="value",
                color="policy" if "policy" in long else "rollout_row_id",
                facet_row="metric",
                markers=True,
                title="Selected-action probability and entropy by depth",
            )
            fig.update_yaxes(matches=None)
            _render_plot(
                fig,
                ScientificExplanation(
                    question="Does action selection become prematurely deterministic or remain indecisive with depth?",
                    population="One factual selected step; probability and entropy are shown on independent axes.",
                    metric="Selected probability and categorical entropy, both dimensionless.",
                    denominator_masks="The persisted candidate shell and selection distribution for each factual step.",
                    comparability="Candidate budget, temperature, beam width, and policy recipe must agree.",
                    expected_pattern="Confidence can rise with evidence while entropy does not collapse identically across every sample.",
                    failure_interpretation="Near-zero entropy everywhere suggests collapse; low probability with high regret suggests selection mismatch.",
                    evidence_role=_temporal_evidence_role("selected_probability"),
                    source_fields=("steps/selected_probability", "steps/selected_entropy"),
                ),
            )

        fanout_cols = [
            name for name in ("num_valid_candidates", "invalid_fraction") if name in steps and steps[name].notna().any()
        ]
        if fanout_cols:
            long = steps.melt(
                id_vars=[name for name in ("rollout_row_id", "policy", "step_index") if name in steps],
                value_vars=fanout_cols,
                var_name="metric",
                value_name="value",
            ).dropna(subset=["value"])
            fig = px.line(
                long,
                x="step_index",
                y="value",
                color="policy" if "policy" in long else "rollout_row_id",
                facet_row="metric",
                markers=True,
                title="Valid fanout and invalid fraction by depth",
            )
            fig.update_yaxes(matches=None)
            _render_plot(
                fig,
                ScientificExplanation(
                    question="Where does the usable action set narrow along the selected chain?",
                    population="One candidate shell per factual rollout step.",
                    metric="Valid candidate count and invalid fraction; separate axes prevent mixed-unit distortion.",
                    denominator_masks="Fanout counts actor-action-valid candidates; invalid fraction uses the complete sampled shell.",
                    comparability="Candidate shell size and generator configuration must match.",
                    expected_pattern="Fanout remains sufficient across depth and invalidity does not abruptly dominate.",
                    failure_interpretation="Low fanout or rising invalidity points to geometry, collision, or generator-support failures.",
                    evidence_role="actor-visible",
                    source_fields=("steps/num_valid_candidates", "steps/invalid_fraction"),
                ),
            )

        if not tree.empty and {"step_label", "selected_steps", "selected_position"}.issubset(tree.columns):
            fig = px.bar(
                tree,
                x="step_label",
                y="selected_steps",
                color="selected_position",
                facet_col="policy" if "policy" in tree and tree["policy"].nunique() > 1 else None,
                hover_data=[
                    name
                    for name in ("selected_strategy", "selected_mixture", "mean_valid_fanout", "mean_invalid_fraction")
                    if name in tree
                ],
                title="Observed selected-family provenance by rollout depth",
            )
            _render_plot(
                fig,
                ScientificExplanation(
                    question="Which candidate families actually supply the selected actions at each depth?",
                    population="Aggregated factual selected steps grouped by recipe, depth, and persisted family provenance.",
                    metric="Selected-step count; this is observed provenance, not a reconstructed search tree.",
                    denominator_masks="Selected actor-valid transitions only.",
                    comparability="Family vocabulary, mixture weights, policy recipe, and horizon must match.",
                    expected_pattern="Multiple intended families contribute without unexplained monopolies or disappearing depths.",
                    failure_interpretation="Single-family dominance can reflect policy preference, generator imbalance, or mask collapse and needs row-level inspection.",
                    evidence_role="provenance",
                    source_fields=(
                        "inspection.rollout_tree_summary_rows",
                        "candidate family ids",
                        "steps/selected_candidate_row_id",
                    ),
                ),
            )
            _download_frame("Download branching provenance CSV", "rollout-branching-provenance.csv", tree)
