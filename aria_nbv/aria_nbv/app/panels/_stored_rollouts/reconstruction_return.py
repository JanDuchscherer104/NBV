"""Reconstruction, return, and temporal evidence presentation."""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ....rollouts import RolloutZarrStoreReader
from ....rollouts.inspection import (
    CANDIDATE_SELECTION_GROUP_FIELDS,
    GeometryProjection,
    rollout_endpoint_metric_summary,
)
from ....rollouts.reporting import RolloutCorpusSummary
from ...scientific_labels import LabelSurface, TheoryReferences
from ..common import current_scientific_label, render_scientific_notation
from .session import _cached_projection
from .shared import ExplanationSection, ScientificExplanation, render_explanation_popover
from .shared import download_frame as _download_frame
from .shared import plot_control_key as _plot_control_key
from .shared import render_plot as _render_plot

_EVIDENCE_REPORTING_REFERENCE = (
    "ARRIVE reporting guidance for individual data and summaries",
    "https://arriveguidelines.org/arrive-guidelines/results/10a/explanation",
)

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
_TEMPORAL_THEORY: dict[str, TheoryReferences] = {
    "cumulative_target_root_gain": TheoryReferences(
        equation_ids=("rl.observed_cumulative_root_gain", "rl.target_rri_reward", "entity.endpoint_gain"),
        symbol_ids=("entity.target_error", "entity.target_error_next", "entity.target_error_0", "rl.epsilon"),
        term_ids=("target-rri-reward", "finite-horizon-return"),
    ),
    "selected_target_root_gain": TheoryReferences(
        equation_ids=("rl.target_rri_reward", "entity.target_error"),
        symbol_ids=("entity.target_error", "entity.target_error_next", "entity.target_error_0", "rl.epsilon"),
        term_ids=("target-rri-reward", "target-specific-rri"),
    ),
    "selected_target_rri": TheoryReferences(
        equation_ids=("rri.target_rri",),
        term_ids=("target-specific-rri",),
    ),
    "marginal_target_rri": TheoryReferences(
        equation_ids=("rri.target_rri",),
        term_ids=("target-specific-rri",),
    ),
    "selected_probability": TheoryReferences(equation_ids=("action.robust_temperature_softmax",)),
    "selected_entropy": TheoryReferences(
        equation_ids=("action.robust_temperature_softmax", "metrics.categorical_entropy")
    ),
}
_SELECTION_DIAGNOSTIC_THEORY = TheoryReferences(
    equation_ids=("action.robust_temperature_softmax", "metrics.categorical_entropy")
)
_SEQUENCE_GROUP_LABELS = {
    "position": "Position family",
    "strategy": "Direction strategy",
    "mixture": "Generator component",
    "position_strategy": "Position × direction",
}
_ROLLOUT_RECIPE_THESIS_REFERENCE = (
    "Thesis: rollout recipes and temperature-softmax selection",
    "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ#L167-L188",
)


def _temporal_metric_label(metric: str, *, surface: LabelSurface = "plain") -> str:
    """Return the UI label for a persisted temporal metric key."""

    return current_scientific_label(metric, surface=surface)


def _render_corpus_temporal_evidence(summary: RolloutCorpusSummary | None) -> None:
    """Show each factual corpus quantity once while retaining contract strata."""

    st.subheader("Corpus reward and reconstruction")
    if summary is None:
        st.info("Build the corpus summary in Overview before viewing corpus trajectories.")
        return
    temporal = summary.temporal_summary
    if temporal.empty:
        st.info("No validated factual temporal rows are available.")
        return
    contract_count = int(temporal["contract_id"].nunique())
    included_count = len(summary.included_stores)
    selected_count = len(summary.selected_paths)
    st.caption(
        f"{included_count} validated stores from {selected_count} selected stores · {contract_count} exact contracts. "
        "Every validated store contributes; incompatible candidate/return contracts remain separate traces in the same plots. "
        "Trace labels show the persisted profile (or profile hash) and candidate-config hash; the exact contract also binds "
        "the oracle configuration, return semantics, discount, and Q_H semantics."
    )
    for metric in (
        "cumulative_target_root_gain",
        "selected_target_root_gain",
    ):
        rows = temporal[temporal["metric"] == metric].copy()
        if rows.empty:
            continue
        rows["trajectory"] = _trajectory_label(rows)
        _render_corpus_temporal_plot(
            rows,
            metric=metric,
            label=_temporal_metric_label(metric),
        )

    render_explanation_popover(
        "Interpret selection probability and entropy",
        ScientificExplanation(
            question="How concentrated were the temperature-softmax draws in this selected corpus?",
            answer=(
                "Selection probability is the mass assigned to the candidate that was actually drawn; entropy summarizes "
                "the full actor-valid probability table. Both remain separated by exact persisted contract in the rows below."
            ),
            sections=(
                ExplanationSection(
                    "Selected-action probability",
                    "A value near 100% means almost all probability mass sat on the selected action. It does not mean the "
                    "action achieved a large reconstruction gain.",
                ),
                ExplanationSection(
                    "Policy entropy",
                    "Entropy is measured in nats, not percent. Zero is deterministic; larger values mean the valid candidate "
                    "mass is more diffuse. Compare it only alongside candidate support and within a matched generator contract.",
                ),
                ExplanationSection(
                    "How comparisons stay valid",
                    "Every validated selected store contributes factual rows. Incompatible candidate, oracle, and return "
                    "contracts are never pooled into one statistic.",
                ),
            ),
            theory=_SELECTION_DIAGNOSTIC_THEORY,
            evidence_role="actor-visible",
            source_fields=(
                "reporting.RolloutCorpusSummary.temporal_summary",
                "audits.candidate_policy_entropy",
            ),
            external_references=(_ROLLOUT_RECIPE_THESIS_REFERENCE,),
        ),
    )

    with st.expander("Diagnostic target RRI, selection-distribution rows, and CSV", expanded=False):
        diagnostics = temporal[
            temporal["metric"].isin(("cumulative_target_rri", "selected_probability", "selected_entropy"))
        ].copy()
        if diagnostics.empty:
            st.info("No optional diagnostic rows are available for this corpus.")
        else:
            st.dataframe(diagnostics, hide_index=True, width="stretch")
            _download_frame("Download diagnostic temporal CSV", "corpus-diagnostics.csv", diagnostics)


def _sequence_stratum_columns() -> tuple[str, ...]:
    """Return the persisted controls that selected-family sequences never pool."""

    return (
        "generation_cohort_id",
        "policy",
        "temperature",
        "horizon",
        "branch_factor",
        "beam_width",
    )


def _sequence_stratum_label(row: pd.Series) -> str:
    """Return a compact exact-cohort label for the sequence comparison."""

    return (
        f"{row['generation_cohort_id']} · {row['policy']} · T={row['temperature']} · "
        f"H={row['horizon']} · B={row['branch_factor']} · beam={row['beam_width']}"
    )


def _candidate_sequence_return_figure(summary: pd.DataFrame, *, max_sequences: int = 20) -> go.Figure:
    """Plot observed terminal return for the best-supported selected-family sequences."""

    finite = summary.dropna(subset=["terminal_return_median"]).copy()
    finite = finite.sort_values(
        ["terminal_return_median", "rollout_count", "sequence"],
        ascending=[False, False, True],
    ).head(max_sequences)
    finite = finite.sort_values(["terminal_return_median", "sequence"], ascending=[True, True])
    median = pd.to_numeric(finite["terminal_return_median"], errors="coerce")
    q25 = pd.to_numeric(finite["terminal_return_q25"], errors="coerce")
    q75 = pd.to_numeric(finite["terminal_return_q75"], errors="coerce")
    completion = finite["completed_count"] / finite["rollout_count"].clip(lower=1)
    figure = go.Figure(
        go.Scatter(
            x=median,
            y=finite["sequence"],
            mode="markers",
            marker={
                "size": 10,
                "color": completion,
                "colorscale": "Viridis",
                "cmin": 0.0,
                "cmax": 1.0,
                "colorbar": {"title": "completed horizon"},
            },
            error_x={
                "type": "data",
                "symmetric": False,
                "array": (q75 - median).clip(lower=0.0),
                "arrayminus": (median - q25).clip(lower=0.0),
            },
            customdata=np.column_stack(
                (
                    finite["rollout_count"],
                    finite["finite_return_count"],
                    finite["completed_count"],
                    q25,
                    q75,
                )
            ),
            hovertemplate=(
                "sequence=%{y}<br>median terminal gain=%{x:.4g}<br>IQR=[%{customdata[3]:.4g}, "
                "%{customdata[4]:.4g}]<br>finite returns=%{customdata[1]:.0f} / %{customdata[0]:.0f}"
                "<br>completed horizon=%{customdata[2]:.0f}<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        title=f"Observed terminal gain by selected-family sequence (top {len(finite)})",
        xaxis_title="terminal cumulative target root gain",
        yaxis_title="selected family sequence",
    )
    return figure


def _render_active_store_sequence_returns(store_path: str) -> None:
    """Render one explicit, cached sequence/return comparison for the active store."""

    if not st.toggle(
        "Load active-store selected-family sequence comparison",
        value=False,
        help=(
            "Reuses the complete candidate-population audit to compare factual selected-family sequences with their "
            "observed terminal cumulative target root gain."
        ),
    ):
        return
    group_by = st.selectbox(
        "Sequence family vocabulary",
        options=list(CANDIDATE_SELECTION_GROUP_FIELDS),
        index=list(CANDIDATE_SELECTION_GROUP_FIELDS).index("position_strategy"),
        format_func=_SEQUENCE_GROUP_LABELS.__getitem__,
    )
    population = _cached_projection(store_path, "candidate_population")
    summary = pd.DataFrame(population["sequence_returns"][group_by])
    sequences = pd.DataFrame(population["selection_sequences"][group_by])
    if summary.empty:
        st.info("No complete factual selected-family sequences are available for this vocabulary.")
        return

    stratum_columns = list(_sequence_stratum_columns())
    strata = summary[stratum_columns].drop_duplicates().reset_index(drop=True)
    strata["label"] = strata.apply(_sequence_stratum_label, axis=1)
    selected_label = st.selectbox("Sequence comparison cohort", options=strata["label"].tolist())
    selected_stratum = strata.loc[strata["label"] == selected_label].iloc[0]
    selected_summary = summary.copy()
    selected_sequences = sequences.copy()
    for column in stratum_columns:
        selected_summary = selected_summary.loc[selected_summary[column].astype(str) == str(selected_stratum[column])]
        selected_sequences = selected_sequences.loc[
            selected_sequences[column].astype(str) == str(selected_stratum[column])
        ]
    finite = selected_summary.dropna(subset=["terminal_return_median"])
    if finite.empty:
        st.info("This exact cohort has no finite terminal cumulative target root gain.")
        return

    cols = st.columns(3)
    cols[0].metric("Observed rollouts", int(selected_summary["rollout_count"].sum()))
    cols[1].metric("Distinct sequences", len(selected_summary))
    cols[2].metric("Repeated sequences", int((selected_summary["rollout_count"] > 1).sum()))
    _render_plot(
        _candidate_sequence_return_figure(selected_summary),
        ScientificExplanation(
            question="Which factual selected-family sequences coincide with the largest observed terminal gain?",
            answer=(
                "Each point summarizes terminal cumulative target root gain for one exact ordered family sequence in "
                "one persisted generation cohort."
            ),
            sections=(
                ExplanationSection(
                    "Population and marks",
                    "A sequence contains one family label per factual selected acquisition. The point is the median "
                    "terminal cumulative target root gain; horizontal whiskers are the descriptive IQR; color is the "
                    "fraction that reached the configured horizon. Hover reports rollout support.",
                ),
                ExplanationSection(
                    "Matched controls",
                    "The selected cohort fixes generation cohort, policy, temperature, horizon, branch factor, and beam "
                    "width. Early-terminated trajectories remain shorter sequences rather than fabricated continuations.",
                ),
                ExplanationSection(
                    "Exploratory interpretation",
                    "The ranking is post-selection and descriptive. Geometry and state difficulty influence both family "
                    "choice and gain, so a high-return sequence is a debugging lead—not evidence that forcing that "
                    "sequence will improve return. Sequences with n=1 have no population uncertainty estimate.",
                ),
            ),
            theory=TheoryReferences(equation_ids=("rl.observed_cumulative_root_gain",)),
            evidence_role="oracle/evaluation",
            source_fields=(
                "inspection.candidate_population_evidence.sequence_returns",
                "steps/selected_candidate_row_id",
                "steps/cumulative_target_root_gain",
            ),
            external_references=(_EVIDENCE_REPORTING_REFERENCE,),
        ),
    )
    with st.expander("Selected-family sequence rows and CSV", expanded=False):
        st.dataframe(selected_summary, hide_index=True, width="stretch")
        _download_frame("Download sequence return summary CSV", "candidate-sequence-returns.csv", selected_summary)
        st.dataframe(selected_sequences, hide_index=True, width="stretch")
        _download_frame(
            "Download factual selected sequences CSV", "candidate-selected-sequences.csv", selected_sequences
        )


def _trajectory_label(rows: pd.DataFrame) -> pd.Series:
    """Return the compact display stratum for one corpus temporal frame."""

    return rows.apply(
        lambda row: (
            f"{row['contract']} · {row['policy']} · T={row['temperature']} · H={row['horizon']} · "
            f"B={row['branch_factor']} · beam={row['beam_width']}"
        ),
        axis=1,
    )


def _format_percent(value: object) -> str:
    """Format a dimensionless fraction as a percentage with four significant digits."""

    numeric = pd.to_numeric(value, errors="coerce")
    return "n/a" if pd.isna(numeric) else f"{100.0 * float(numeric):.4g}%"


def _render_corpus_temporal_plot(rows: pd.DataFrame, *, metric: str, label: str) -> None:
    """Render one default corpus plot with interpretation and its raw rows collapsed below."""

    store_count = int(rows.groupby("contract_id", sort=False)["store_count"].max().sum())
    iqr_width = pd.to_numeric(rows["iqr_width"], errors="coerce").max()
    cols = st.columns(3)
    cols[0].metric("Validated shards", store_count)
    cols[1].metric("Observed rows", f"{int(rows['finite_count'].sum()):,} / {int(rows['total_count'].sum()):,}")
    cols[2].metric("Maximum IQR width", _format_percent(iqr_width))
    render_scientific_notation(metric)
    _render_plot(
        _temporal_summary_figure(rows, group_field="trajectory"),
        ScientificExplanation(
            question=f"How does {label.lower()} evolve across the selected corpus without pooling incompatible contracts?",
            answer=(
                "Each point sums the observed root-normalized gains through that acquisition; the line is the "
                "median and the ribbon is the descriptive IQR."
                if metric == "cumulative_target_root_gain"
                else "Each point is the gain contributed by the selected view at that acquisition; the line is the "
                "median and the ribbon is the descriptive IQR."
            ),
            sections=(
                ExplanationSection(
                    "Reading the trajectory",
                    "Each line keeps the exact persisted contract, policy, temperature, horizon, branch factor, and beam width separate. "
                    "The center is the median across finite factual rows; the shaded band spans the "
                    "linear-interpolated interquartile range. Acquisition 1 is the first selected view, not the root state.",
                ),
                ExplanationSection(
                    "Population and uncertainty",
                    f"Only shards with the same persisted profile, candidate, oracle, and return contract are pooled. "
                    f"Values use {rows['units'].iloc[0]} units. Hover reports finite/total n and exact quartiles; "
                    "the IQR is descriptive spread, not a confidence interval. Missing later acquisitions are not zero-filled.",
                ),
                ExplanationSection(
                    "What to investigate",
                    "A narrow ribbon can still have nonzero width at this scale. Small n, disappearing late depths, "
                    "near-zero first-view gain, or divergent temperature traces are reasons to inspect the factual rows, "
                    "not automatic evidence of a policy effect.",
                ),
            ),
            theory=_TEMPORAL_THEORY[metric],
            evidence_role="oracle/evaluation",
            source_fields=(
                "reporting.RolloutCorpusSummary.temporal_summary",
                "inspection.temporal_metric_summary_rows",
            ),
            external_references=(_EVIDENCE_REPORTING_REFERENCE,),
        ),
        log_y_key=_plot_control_key("corpus-temporal", metric),
    )
    with st.expander(f"{label} rows and CSV", expanded=False):
        st.dataframe(rows.drop(columns="trajectory"), hide_index=True, width="stretch")
        _download_frame(f"Download {label} CSV", f"corpus-{metric}.csv", rows.drop(columns="trajectory"))


def _render_scientific_evidence(reader: RolloutZarrStoreReader) -> None:
    st.subheader("Scientific evidence")
    store_path = reader.store_dir.as_posix()
    _render_reconstruction_summary(store_path)
    cohort = _cached_projection(store_path, "cohorts")
    eligibility = bool(cohort.get("eligible"))
    st.metric("Matched comparison eligible", "YES" if eligibility else "NO")
    st.caption(
        "Policies are comparison dimensions only after source sample, target protocol, horizon/budget, candidate/oracle configuration, and branch schedule match."
    )
    if eligibility:
        comparison = pd.DataFrame(_cached_projection(store_path, "paired"))
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
                    answer="The bars summarize endpoint differences only after source, target, recipe, budget, and rollout controls have been exactly matched across policies.",
                    sections=(
                        ExplanationSection(
                            "Why pairing matters",
                            "Each delta compares two policies on the same persisted source, target, recipe, budget, "
                            "and rollout controls. Removing that shared context makes policy the intended comparison dimension.",
                        ),
                        ExplanationSection(
                            "Reading the interval",
                            "Bar height is the median paired endpoint delta and whiskers are deterministic bootstrap "
                            "intervals over finite matched deltas. They describe resampling variation in this observed "
                            "cohort; wide intervals or sign changes are weak evidence, not policy wins.",
                        ),
                    ),
                    theory=TheoryReferences(equation_ids=("entity.endpoint_gain",)),
                    evidence_role="oracle/evaluation",
                    source_fields=("inspection.paired_policy_comparison_rows", "rollouts", "steps"),
                    external_references=(_EVIDENCE_REPORTING_REFERENCE,),
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

    steps = pd.DataFrame(_cached_projection(store_path, "steps"))
    if not steps.empty:
        _render_temporal_explorer(store_path, steps, matched_cohorts=eligibility)
        _download_frame("Download selected-chain CSV", "selected-chain-evidence.csv", steps)

    with st.expander("Additional branching and selected-rank evidence", expanded=False):
        if st.toggle(
            "Load branching, rank/regret, and factual trajectory evidence",
            value=False,
            help="These projections traverse every factual step and candidate shell, then remain cached for this store.",
        ):
            _render_branching_evidence(steps, pd.DataFrame(_cached_projection(store_path, "tree")))
            _render_selected_rank_and_geometry(store_path)


def _render_reconstruction_summary(store_path: str) -> None:
    """Render frozen reconstruction, return, and headroom rows on demand."""

    if not st.toggle(
        "Load reconstruction endpoints, discounted returns, and oracle headroom",
        value=False,
        help="Materializes only frozen inspection projections after this explicit request.",
    ):
        return

    metric_rows = pd.DataFrame(_cached_projection(store_path, "reconstruction_metrics"))
    endpoint_rows = pd.DataFrame(_cached_projection(store_path, "reconstruction_endpoints"))
    discounted = _cached_projection(store_path, "discounted_returns")
    headroom = _cached_projection(store_path, "headroom")

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


def _render_temporal_explorer(store_path: str, steps: pd.DataFrame, *, matched_cohorts: bool) -> None:
    """Render one population metric at a time and a one-rollout raw drill-down."""

    available_labels = [
        label
        for label, metric in _TEMPORAL_METRIC_LABELS.items()
        if (source := _TEMPORAL_SOURCE_FIELDS.get(metric, metric)) in steps and steps[source].notna().any()
    ]
    if not available_labels:
        st.info("No supported finite temporal metric is available in this store.")
        return
    selected_metric_label = st.selectbox(
        "Temporal metric",
        options=[_temporal_metric_label(_TEMPORAL_METRIC_LABELS[label]) for label in available_labels],
    )
    metric = next(
        metric for metric in _TEMPORAL_METRIC_LABELS.values() if _temporal_metric_label(metric) == selected_metric_label
    )
    metric_label = _temporal_metric_label(metric)
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

    render_scientific_notation(metric)

    summary = pd.DataFrame(
        _cached_projection(
            store_path,
            "temporal",
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
    cols[2].metric("Observed acquisitions", f"1–{endpoint_depth + 1}")
    cols[3].metric(
        "Factual endpoint median",
        "n/a" if endpoint_median is None else f"{float(endpoint_median):.4g}",
        delta=f"{int(endpoint['finite_count']):,} / {int(endpoint['total_count']):,} finite",
        delta_color="off",
        help="One terminal factual step per rollout, including rollouts whose persisted horizon ends earlier.",
    )
    _render_plot(
        _temporal_summary_figure(summary, group_field=group_field),
        ScientificExplanation(
            question=f"How does {metric_label.lower()} change over persisted rollout depth?",
            answer=f"The trace summarizes how {metric_label.lower()} is observed to change with acquisition number for the selected descriptive grouping.",
            sections=(
                ExplanationSection(
                    "Reading the marks",
                    f"Each colored line is one {group_field} summary at a one-based acquisition number. The line is "
                    f"the median in {summary['units'].iloc[0]} and the ribbon is the linear-interpolated IQR across "
                    "finite factual selected-step values.",
                ),
                ExplanationSection(
                    "Support and comparison",
                    "Hover reports finite/total counts and missingness at every depth. Later depths include only "
                    "rollouts that factually reached them; nothing is zero-filled or interpolated. Policy and recipe "
                    "groups remain descriptive unless their full cohort keys match.",
                ),
                ExplanationSection(
                    "When to inspect rows",
                    "Wide IQR, small n, abrupt missingness, or divergent strata require row-level inspection and are "
                    "not automatically policy effects.",
                ),
            ),
            theory=_TEMPORAL_THEORY.get(metric),
            evidence_role=_temporal_evidence_role(metric),
            source_fields=(
                "inspection.temporal_metric_summary_rows",
                f"steps/{_TEMPORAL_SOURCE_FIELDS.get(metric, metric)}",
            ),
            external_references=(_EVIDENCE_REPORTING_REFERENCE,),
        ),
        log_y_key=_plot_control_key("temporal-summary", store_path, metric, group_field),
    )
    st.dataframe(summary, hide_index=True, width="stretch")
    _download_frame("Download temporal summary CSV", "temporal-metric-summary.csv", summary)

    with st.expander("Raw selected-rollout trajectory drill-down", expanded=False):
        rollout_ids = sorted(int(value) for value in steps["rollout_row_id"].dropna().unique().tolist())
        selected_rollout = st.selectbox("Raw trajectory rollout", options=rollout_ids)
        selected_rows = steps.loc[steps["rollout_row_id"] == selected_rollout].sort_values("step_index").copy()
        source_field = _TEMPORAL_SOURCE_FIELDS.get(metric, metric)
        raw = selected_rows.dropna(subset=[source_field])
        if raw.empty:
            st.info(f"Rollout {selected_rollout} has no finite {metric_label.lower()} rows.")
        else:
            raw["acquisition_number"] = raw["step_index"].astype(int) + 1
            fig = px.line(
                raw,
                x="acquisition_number",
                y=source_field,
                markers=True,
                title=f"Raw trajectory for rollout {selected_rollout}: {_temporal_metric_label(metric)}",
                hover_data=[column for column in ("step_index", "step_row_id", "policy") if column in raw],
            )
            _render_plot(
                fig,
                ScientificExplanation(
                    question=f"What exact {metric_label.lower()} trajectory produced rollout {selected_rollout}?",
                    answer="The line exposes the exact stored trajectory for one chosen rollout so the aggregate view can be traced back to factual step identifiers.",
                    sections=(
                        ExplanationSection(
                            "Following one case",
                            f"Markers are the finite persisted {source_field} values for one rollout, ordered by "
                            "acquisition number. Acquisition 1 is stored step_index 0; the root baseline is not plotted, "
                            "and no line joins another rollout_row_id.",
                        ),
                        ExplanationSection(
                            "Diagnostic limits",
                            "This is one case, not a population statistic or policy comparison. Missing steps stay "
                            "absent. Abrupt jumps or negative valid gains identify cases worth opening in Inspect/Rerun.",
                        ),
                    ),
                    theory=_TEMPORAL_THEORY.get(metric),
                    evidence_role=_temporal_evidence_role(metric),
                    source_fields=("inspection.rollout_step_objective_rows", f"steps/{source_field}"),
                    external_references=(_EVIDENCE_REPORTING_REFERENCE,),
                ),
                log_y_key=_plot_control_key("raw-trajectory", store_path, metric, selected_rollout),
            )


def _temporal_summary_figure(summary: pd.DataFrame, *, group_field: str) -> go.Figure:
    """Build deterministic median/IQR traces without connecting rollout rows."""

    figure = go.Figure()
    palette = px.colors.qualitative.Plotly
    for index, (group_value, rows) in enumerate(summary.groupby(group_field, sort=True, dropna=False)):
        ordered = rows.sort_values("step_index").copy()
        acquisition_number = ordered["step_index"].to_numpy(dtype=np.int64) + 1
        color = palette[index % len(palette)]
        custom = np.column_stack(
            (
                ordered["step_index"],
                ordered["finite_count"],
                ordered["total_count"],
                ordered["missing_count"] / ordered["total_count"].clip(lower=1),
                ordered["store_count"] if "store_count" in ordered else np.ones(len(ordered), dtype=np.int64),
                ordered["q75"] - ordered["q25"],
                ordered["mean"],
                ordered["min"],
                ordered["max"],
            )
        )
        figure.add_trace(
            go.Scatter(
                x=acquisition_number,
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
                x=acquisition_number,
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
                x=acquisition_number,
                y=ordered["median"],
                mode="lines+markers",
                line={"color": color},
                name=str(group_value),
                legendgroup=str(group_value),
                customdata=custom,
                hovertemplate=(
                    f"{group_field}={group_value}<br>acquisition=%{{x}}"
                    "<br>stored step_index=%{customdata[0]:.0f}<br>median=%{y:.4g}"
                    "<br>finite=%{customdata[1]:.0f} / %{customdata[2]:.0f}"
                    "<br>missing=%{customdata[3]:.1%}<br>stores=%{customdata[4]:.0f}"
                    "<br>IQR width=%{customdata[5]:.4g}<br>mean=%{customdata[6]:.4g}"
                    "<br>min=%{customdata[7]:.4g}<br>max=%{customdata[8]:.4g}<extra></extra>"
                ),
            )
        )
    figure.update_layout(
        title=f"{_temporal_metric_label(str(summary['metric'].iloc[0]))}: median and interquartile range by acquisition number",
        xaxis_title="acquisition number (1 = first selected view; root baseline omitted)",
        yaxis_title=(f"{_temporal_metric_label(str(summary['metric'].iloc[0]))} ({summary['units'].iloc[0]})"),
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


def _render_selected_rank_and_geometry(store_path: str) -> None:
    """Render expensive selected-rank and factual trajectory evidence on demand."""

    ranks = pd.DataFrame(_cached_projection(store_path, "ranks"))
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
                    answer="The scatter shows the opportunity cost of each selected action relative to the best valid oracle-scored option in its own candidate shell.",
                    sections=(
                        ExplanationSection(
                            "Rank and magnitude answer different questions",
                            "Each point is one factual selected step. Rank records where the selected action sits among "
                            "actor-valid alternatives; regret records how much root-normalized gain was left relative to "
                            "the best finite valid candidate in that same shell.",
                        ),
                        ExplanationSection(
                            "Interpretation limits",
                            "Ranks are shell-local and oracle regret is privileged evaluation evidence. Compare only "
                            "equivalent reward definitions and budgets. High regret suggests selection mismatch, while "
                            "negative valid gain remains distinct from invalid or missing labels.",
                        ),
                    ),
                    theory=TheoryReferences(
                        equation_ids=("metrics.selected_oracle_regret", "rl.target_rri_reward"),
                        term_ids=("finite-candidate-action-set", "target-rri-reward"),
                    ),
                    evidence_role="oracle/evaluation",
                    source_fields=(
                        "inspection.selected_candidate_rank_rows",
                        "candidates/actor_action_mask",
                        "candidates/target_root_gain",
                    ),
                    external_references=(_EVIDENCE_REPORTING_REFERENCE,),
                ),
            )
        st.dataframe(ranks, hide_index=True, width="stretch")
        _download_frame("Download selected rank/regret CSV", "selected-rank-regret.csv", ranks)

    projection = _cached_projection(store_path, "trajectory_geometry")
    geometry = pd.DataFrame(projection.point_rows()) if isinstance(projection, GeometryProjection) else pd.DataFrame()
    if not geometry.empty:
        st.caption(
            "Factual selected paths use one initial target-aligned Z-up frame and initial target-distance scale per rollout."
        )
        st.dataframe(geometry.head(500), hide_index=True, width="stretch")
        st.caption(f"Showing {min(500, len(geometry)):,} of {len(geometry):,}; export is complete.")
        _download_frame("Download factual trajectory geometry CSV", "factual-rollout-trajectories.csv", geometry)


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
                    answer="The faceted traces reveal whether the persisted selection distribution is becoming concentrated or remains broad as rollout depth increases.",
                    sections=(
                        ExplanationSection(
                            "Concentration versus the chosen action",
                            "Selected probability is the mass placed on the action that was sampled. Entropy summarizes "
                            "how dispersed the complete actor-valid selection distribution was. The facets use independent axes.",
                        ),
                        ExplanationSection(
                            "What collapse looks like",
                            "Near-zero entropy across nearly every sample suggests premature concentration; low selected "
                            "probability together with high regret suggests a selection mismatch. These are descriptive "
                            "diagnostics, not calibrated uncertainty estimates, and require matched recipes and budgets.",
                        ),
                    ),
                    theory=TheoryReferences(equation_ids=("metrics.categorical_entropy",)),
                    evidence_role=_temporal_evidence_role("selected_probability"),
                    source_fields=("steps/selected_probability", "steps/selected_entropy"),
                    external_references=(_EVIDENCE_REPORTING_REFERENCE,),
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
                    answer="The facets show whether the action set remains usable across factual rollout depth or is being eroded by invalid candidates.",
                    sections=(
                        ExplanationSection(
                            "Usable support before reward",
                            "Valid fanout counts actor-action-valid candidates; invalid fraction uses the complete persisted "
                            "candidate shell. Separate facets avoid mixing counts and fractions. Missing or terminated depths are absent.",
                        ),
                        ExplanationSection(
                            "Diagnosing support loss",
                            "Compare only matching shell sizes and generator configurations. Low fanout or rising invalidity "
                            "points toward geometry, collision, or generator-support failures; these observed fractions are "
                            "not estimates of collision probability.",
                        ),
                    ),
                    theory=TheoryReferences(term_ids=("finite-candidate-action-set", "validity-mask")),
                    evidence_role="actor-visible",
                    source_fields=("steps/num_valid_candidates", "steps/invalid_fraction"),
                    external_references=(_EVIDENCE_REPORTING_REFERENCE,),
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
                    answer="The bars identify which persisted candidate families supplied the actions actually selected at each factual rollout depth.",
                    sections=(
                        ExplanationSection(
                            "Realized family provenance",
                            "Each bar counts selected actor-valid transitions for one persisted family and depth. Policy "
                            "facets remain separate when present, and hover retains fanout context. This is observed provenance, "
                            "not a reconstructed search tree.",
                        ),
                        ExplanationSection(
                            "Why availability still matters",
                            "Selection counts cannot reveal whether an absent family was unavailable, invalid, or merely "
                            "unselected. Compare only matching family vocabularies, mixture weights, recipes, and horizons; "
                            "single-family dominance requires the full-shell support view.",
                        ),
                    ),
                    evidence_role="provenance",
                    source_fields=(
                        "inspection.rollout_tree_summary_rows",
                        "candidate family ids",
                        "steps/selected_candidate_row_id",
                    ),
                    external_references=(_EVIDENCE_REPORTING_REFERENCE,),
                ),
            )
            _download_frame("Download branching provenance CSV", "rollout-branching-provenance.csv", tree)
