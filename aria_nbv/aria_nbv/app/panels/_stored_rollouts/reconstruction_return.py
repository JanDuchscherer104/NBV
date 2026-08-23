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
from ...scientific_labels import TheoryReferences
from ..common import current_scientific_label
from .shared import ExplanationSection, ScientificExplanation
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

# Reward/reconstruction is intentionally disjoint from actor-feasibility
# diagnostics.  The latter belongs on Admission & feasibility, where its
# denominators can be read without mixing units into a reward trajectory.
_REWARD_TEMPORAL_METRICS = frozenset(
    {
        "cumulative_target_root_gain",
        "selected_target_root_gain",
        "selected_target_rri",
        "marginal_target_rri",
    }
)
_SELECTION_DIAGNOSTIC_METRICS = ("selected_probability", "selected_entropy")
_TEMPORAL_THEORY: dict[str, TheoryReferences | None] = {
    "cumulative_target_root_gain": TheoryReferences(
        equation_ids=("rl.cumulative_target_root_gain",),
        symbol_ids=("entity.target_root_gain_cumulative",),
        term_ids=("target-root-gain-reward",),
    ),
    "selected_target_root_gain": TheoryReferences(
        equation_ids=("rl.target_root_gain_reward",),
        symbol_ids=("entity.target_reward",),
        term_ids=("target-root-gain-reward",),
    ),
    "selected_target_rri": TheoryReferences(
        equation_ids=("rl.marginal_target_rri",),
        symbol_ids=("entity.target_rri_marginal",),
        term_ids=("relative-reconstruction-improvement",),
    ),
    "marginal_target_rri": TheoryReferences(
        equation_ids=("rl.marginal_target_rri",),
        symbol_ids=("entity.target_rri_marginal",),
        term_ids=("relative-reconstruction-improvement",),
    ),
    "selected_probability": TheoryReferences(
        equation_ids=("action.robust_temperature_softmax",),
        term_ids=("finite-candidate-action-set",),
    ),
    "selected_entropy": TheoryReferences(
        equation_ids=("action.robust_temperature_softmax",),
        term_ids=("finite-candidate-action-set",),
    ),
    "valid_fanout": TheoryReferences(symbol_ids=("rl.validity_mask",), term_ids=("validity-mask",)),
    "invalid_fraction": TheoryReferences(symbol_ids=("rl.validity_mask",), term_ids=("validity-mask",)),
}


def _temporal_theory(metric: str) -> TheoryReferences | None:
    """Return metric-owned theory, failing closed for an unregistered metric."""

    try:
        return _TEMPORAL_THEORY[metric]
    except KeyError as exc:
        raise ValueError(f"Temporal metric {metric!r} has no theory mapping.") from exc


def _selection_diagnostic_explanation(metric: str) -> ScientificExplanation:
    """Explain one persisted selection diagnostic with its own denominator."""

    if metric == "selected_probability":
        question = "How much probability mass does the persisted policy assign to the selected action?"
        answer = "The selected-action probability is the policy mass of the action that was actually executed."
        metric_text = "Selected-action probability is a dimensionless fraction in [0, 1]."
    elif metric == "selected_entropy":
        question = "How concentrated is the persisted action distribution at each acquisition?"
        answer = "Entropy summarizes uncertainty over the finite candidate action set before the selected action is executed."
        metric_text = "Selected-action entropy is dimensionless; its scale depends on the finite candidate-set size."
    else:
        raise ValueError(f"Selection diagnostic {metric!r} is not supported.")
    return ScientificExplanation(
        question=question,
        answer=answer,
        sections=(
            ExplanationSection("population", "Validated factual selected-step rows from compatible corpus contexts."),
            ExplanationSection("metric / units", metric_text),
            ExplanationSection(
                "denominator / masks",
                "Only finite persisted diagnostic values contribute at each acquisition; missing values are not zero-filled.",
            ),
            ExplanationSection(
                "intuition",
                "High selected probability means the policy concentrated mass on the executed action; lower entropy means a more concentrated distribution.",
            ),
            ExplanationSection(
                "failure interpretation",
                "Sparse or abruptly changing diagnostics can indicate candidate-support, temperature, or policy-state differences and require denominator inspection.",
            ),
        ),
        evidence_role="actor-visible",
        source_fields=("steps/selected_probability", "steps/selected_entropy", "rollout contract"),
        theory=_temporal_theory(metric),
    )


def _render_corpus_temporal_evidence(summary: RolloutCorpusSummary | None) -> None:
    """Render compatible-shard factual temporal reward/reconstruction evidence."""

    if summary is None:
        st.info("Build the corpus summary in Overview before viewing aggregate reward evidence.")
        return
    temporal = summary.temporal_summary
    if temporal.empty:
        st.info("No validated factual temporal rows are available.")
        return
    reward_metrics = (
        ("cumulative_target_root_gain", "Cumulative target root gain"),
        ("selected_target_root_gain", "Selected one-step target root gain"),
    )
    available = {str(value) for value in temporal["metric"].dropna()}
    visible_metrics = tuple(item for item in reward_metrics if item[0] in available)
    if not visible_metrics:
        st.info("No validated reward or reconstruction metrics are available in the selected corpus.")
        return
    for metric, metric_label in visible_metrics:
        rows = temporal.loc[temporal["metric"] == metric].copy()
        # Factual rollout rows are selected actions: step 0 is acquisition 1,
        # not a synthetic root-baseline row.  Keep early-terminated rows as
        # observed and shift only the display axis to one-based numbering.
        rows = rows.loc[pd.to_numeric(rows["step_index"], errors="coerce").notna()].copy()
        figure = _corpus_temporal_figure(rows, metric_label=metric_label)
        context_count = rows[_corpus_temporal_group_fields(rows)].drop_duplicates().shape[0]
        finite = int(rows["finite_count"].sum())
        total = int(rows["total_count"].sum())
        stores = int(rows["store_count"].max())
        cols = st.columns(3)
        cols[0].metric("Finite / observed acquisitions", f"{finite:,} / {total:,}")
        cols[1].metric("Compatible contexts", f"{context_count:,}")
        cols[2].metric("Max stores / context", f"{stores:,}")
        st.caption(
            "Acquisition 1 is the first persisted selected view; no synthetic root-baseline row is added. "
            "Ribbon = descriptive IQR, not a confidence interval. n is finite / observed at each depth."
        )
        _render_plot(
            figure,
            _corpus_temporal_explanation(metric),
            log_y_key=_plot_control_key("corpus-temporal", metric),
        )
        with st.expander(f"{metric_label} rows and CSV", expanded=False):
            st.dataframe(rows, hide_index=True, width="stretch")
            _download_frame("Download temporal rows CSV", f"corpus-{metric}.csv", rows)

    diagnostics = temporal.loc[temporal["metric"].isin(_SELECTION_DIAGNOSTIC_METRICS)]
    if not diagnostics.empty:
        with st.expander("Selection diagnostics (optional)", expanded=False):
            st.caption(
                "Probability and entropy are descriptive policy diagnostics, kept separate from reward and reconstruction."
            )
            for diagnostic in _SELECTION_DIAGNOSTIC_METRICS:
                rows = diagnostics.loc[diagnostics["metric"].eq(diagnostic)].copy()
                if rows.empty:
                    continue
                label = current_scientific_label(diagnostic)
                _render_plot(
                    _corpus_temporal_figure(rows, metric_label=label),
                    _selection_diagnostic_explanation(diagnostic),
                    log_y_key=_plot_control_key("corpus-temporal-diagnostic", diagnostic),
                )
                with st.expander(f"{label} rows and CSV", expanded=False):
                    st.dataframe(rows, hide_index=True, width="stretch")
                    _download_frame("Download selection diagnostic CSV", f"corpus-{diagnostic}.csv", rows)

    target_rri_diagnostics = temporal.loc[temporal["metric"].isin(("selected_target_rri", "marginal_target_rri"))]
    if not target_rri_diagnostics.empty:
        with st.expander("Target-RRI diagnostics (optional)", expanded=False):
            st.caption("Target-RRI rows are oracle/evaluation diagnostics, not policy selection diagnostics.")
            st.dataframe(target_rri_diagnostics, hide_index=True, width="stretch")
            _download_frame(
                "Download target-RRI diagnostics CSV", "corpus-target-rri-diagnostics.csv", target_rri_diagnostics
            )


def _corpus_temporal_group_fields(rows: pd.DataFrame) -> list[str]:
    """Return the persisted dimensions that define a comparable corpus series."""

    return [
        field
        for field in (
            "contract_id",
            "contract",
            "profile",
            "policy",
            "temperature",
            "horizon",
            "branch_factor",
            "beam_width",
        )
        if field in rows
    ]


def _corpus_temporal_figure(rows: pd.DataFrame, *, metric_label: str) -> go.Figure:
    """Plot compatible corpus rows by one-based selected acquisition number."""

    figure = go.Figure()
    group_fields = _corpus_temporal_group_fields(rows)
    working = rows.copy()
    working["acquisition_number"] = pd.to_numeric(working["step_index"], errors="coerce") + 1
    grouped = list(working.groupby(group_fields, sort=True, dropna=False)) if group_fields else [((), working)]
    display_labels = _temporal_series_display_labels(grouped, group_fields)
    palette = px.colors.qualitative.Plotly
    for index, ((_, group), series) in enumerate(zip(grouped, display_labels, strict=True)):
        ordered = group.sort_values("acquisition_number")
        color = palette[index % len(palette)]
        figure.add_trace(
            go.Scatter(
                x=ordered["acquisition_number"],
                y=ordered["q25"],
                mode="lines",
                line={"color": color, "width": 0},
                legendgroup=str(series),
                showlegend=False,
                hoverinfo="skip",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=ordered["acquisition_number"],
                y=ordered["q75"],
                mode="lines",
                line={"color": color, "width": 0},
                fill="tonexty",
                fillcolor=_with_alpha(color, 0.18),
                legendgroup=str(series),
                showlegend=False,
                hoverinfo="skip",
            )
        )
        custom_frame = ordered[["finite_count", "total_count", "store_count", "iqr_width"]].copy()
        for field in (
            "contract_id",
            "contract",
            "profile",
            "policy",
            "temperature",
            "horizon",
            "branch_factor",
            "beam_width",
        ):
            custom_frame[field] = ordered[field] if field in ordered else "unknown"
        custom = custom_frame.to_numpy()
        figure.add_trace(
            go.Scatter(
                x=ordered["acquisition_number"],
                y=ordered["median"],
                mode="lines+markers",
                line={"color": color},
                name=series,
                legendgroup=series,
                customdata=custom,
                hovertemplate=(
                    "acquisition=%{x}<br>median=%{y:.4g}<br>"
                    "n=%{customdata[0]:.0f} / %{customdata[1]:.0f}<br>"
                    "stores=%{customdata[2]:.0f}<br>IQR width=%{customdata[3]:.4g}<br>"
                    "contract_id=%{customdata[4]}<br>contract=%{customdata[5]}<br>"
                    "profile=%{customdata[6]}<br>policy=%{customdata[7]}<br>"
                    "temperature=%{customdata[8]}<br>horizon=%{customdata[9]}<br>"
                    "branch=%{customdata[10]}<br>beam=%{customdata[11]}<extra></extra>"
                ),
            )
        )
    figure.update_layout(
        title=f"{metric_label}: median and interquartile range by acquisition number",
        xaxis_title="acquisition number (1 = first selected view; factual step_index + 1)",
        yaxis_title=current_scientific_label(str(rows["metric"].iloc[0]), surface="plain"),
        hovermode="x unified",
    )
    return figure


def _temporal_series_display_labels(grouped: list[tuple[object, pd.DataFrame]], group_fields: list[str]) -> list[str]:
    """Build compact legend labels while retaining exact identity in hover data."""

    labels: list[str] = []
    for key, _ in grouped:
        values = dict(zip(group_fields, key if isinstance(key, tuple) else (key,), strict=True))
        profile = str(values.get("profile", "unknown"))
        policy = str(values.get("policy", "unknown")).replace("temperature_", "")
        parts = [profile, policy]
        if values.get("temperature") is not None:
            parts.append(f"T={values['temperature']}")
        if values.get("horizon") is not None:
            parts.append(f"H={values['horizon']}")
        if values.get("branch_factor") is not None:
            parts.append(f"B={values['branch_factor']}")
        if values.get("beam_width") is not None:
            parts.append(f"beam={values['beam_width']}")
        labels.append(" · ".join(part for part in parts if part not in {"unknown", "nan"}))

    counts = pd.Series(labels).value_counts()
    unique: list[str] = []
    for label, (key, _) in zip(labels, grouped, strict=True):
        if counts[label] == 1:
            unique.append(label)
            continue
        values = dict(zip(group_fields, key if isinstance(key, tuple) else (key,), strict=True))
        contract_id = str(values.get("contract_id", "unknown"))
        suffix = (
            contract_id[:12] if contract_id not in {"unknown", "nan"} else str(values.get("contract", "unknown"))[:12]
        )
        unique.append(f"{label} · contract={suffix}")
    return unique


def _corpus_temporal_explanation(metric: str) -> ScientificExplanation:
    """Build the metric-specific scientific guide for corpus reward plots."""

    cumulative = metric == "cumulative_target_root_gain"
    label = "cumulative target root gain" if cumulative else "selected one-step target root gain"
    equation = "rl.cumulative_target_root_gain" if cumulative else "rl.target_root_gain_reward"
    symbol = "entity.target_root_gain_cumulative" if cumulative else "entity.target_reward"
    term = "target-root-gain-reward"
    return ScientificExplanation(
        question=f"How does {label} evolve across the selected compatible shards?",
        answer=(
            "Each line summarizes the same persisted contract and control context across factual selected steps; "
            "the center is the median and the shaded band is the between-row IQR."
        ),
        sections=(
            ExplanationSection(
                "population", "Only validated factual rows are included; incompatible contracts remain separate."
            ),
            ExplanationSection(
                "metric / units",
                "The target-root gain is a dimensionless fraction normalized by the rollout-root target error.",
            ),
            ExplanationSection(
                "denominator / masks",
                "n is finite / observed at that acquisition. Early-terminated rollouts are not zero-filled.",
            ),
            ExplanationSection(
                "comparison",
                "Policy, temperature, horizon, branch, beam, profile, and contract identify each series; this is descriptive evidence, not a causal estimate.",
            ),
            ExplanationSection(
                "intuition",
                "A rising cumulative curve means persisted selected views reduced the target-root reconstruction error; a one-step curve shows the gain attributable to that acquisition alone.",
            ),
            ExplanationSection(
                "uncertainty",
                "The IQR describes dispersion among observed rows. It is not a confidence interval, and small n should be read as fragile evidence.",
            ),
        ),
        evidence_role="oracle/evaluation",
        source_fields=("reporting.RolloutCorpusSummary.temporal_summary", "steps", "rollout contract"),
        theory=TheoryReferences(equation_ids=(equation,), symbol_ids=(symbol,), term_ids=(term,)),
    )


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
                    answer="This plot answers the question using the persisted evidence rows and preserves the denominator and comparison caveats below.",
                    sections=(
                        ExplanationSection(
                            "population",
                            "One paired delta per matched source/target/recipe/budget cohort, summarized by policy pair.",
                        ),
                        ExplanationSection(
                            "metric",
                            "Median paired target endpoint or root-gain delta; RRI/root gain are dimensionless.",
                        ),
                        ExplanationSection(
                            "denominator masks",
                            "Only finite matched endpoint rows; sample count and IQR/bootstrap interval remain in the table.",
                        ),
                        ExplanationSection(
                            "comparability",
                            "All cohort keys must match; policy/recipe is the only intended comparison dimension.",
                        ),
                        ExplanationSection(
                            "expected pattern",
                            "Intervals and paired deltas are stable across cohorts rather than driven by one scene.",
                        ),
                        ExplanationSection(
                            "failure interpretation",
                            "Wide intervals or sign changes indicate weak evidence; they are not policy wins.",
                        ),
                    ),
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
    endpoint_depth = int(summary["step_index"].max()) + 1
    endpoint = rollout_endpoint_metric_summary(steps.to_dict("records"), metric=metric)
    endpoint_median = endpoint["median"]
    cols = st.columns(4)
    cols[0].metric("Finite temporal rows", f"{finite_count:,} / {total_count:,}")
    cols[1].metric("Missing temporal rows", f"{missing_count:,}")
    cols[2].metric("Observed acquisitions", f"1–{endpoint_depth}")
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
            answer="This plot answers the question using the persisted evidence rows and preserves the denominator and comparison caveats below.",
            sections=(
                ExplanationSection(
                    "population",
                    f"One aggregate per {group_field} and step_index over factual selected-step rows; individual rollouts are not connected.",
                ),
                ExplanationSection(
                    "metric", f"Median with linear-interpolated IQR; units are {summary['units'].iloc[0]}."
                ),
                ExplanationSection(
                    "denominator masks",
                    "Each point reports finite_count / total_count and missing fraction; statistics use finite values only with no zero fill or depth interpolation.",
                ),
                ExplanationSection(
                    "comparability",
                    "Upstream policy/recipe groups are descriptive unless exact cohort keys match; selected-action provenance groups are post-selection strata only.",
                ),
                ExplanationSection(
                    "expected pattern",
                    "Central tendency and dispersion change smoothly where repeated evidence exists, with sample size visible at every depth.",
                ),
                ExplanationSection(
                    "failure interpretation",
                    "Wide IQR, small n, abrupt missingness, or divergent strata require row-level inspection; they are not automatically policy effects.",
                ),
            ),
            evidence_role=_temporal_evidence_role(metric),
            source_fields=(
                "inspection.temporal_metric_summary_rows",
                f"steps/{_TEMPORAL_SOURCE_FIELDS.get(metric, metric)}",
            ),
            theory=_temporal_theory(metric),
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
            raw = raw.assign(acquisition_number=pd.to_numeric(raw["step_index"], errors="coerce") + 1)
            fig = px.line(
                raw,
                x="acquisition_number",
                y=source_field,
                markers=True,
                title=f"Raw trajectory for rollout {selected_rollout}",
                hover_data=[column for column in ("step_row_id", "step_index", "policy") if column in raw],
            )
            fig.update_xaxes(title="acquisition number (1 = first selected view; persisted step_index + 1)")
            _render_plot(
                fig,
                ScientificExplanation(
                    question=f"What exact {metric_label.lower()} trajectory produced rollout {selected_rollout}?",
                    answer="This plot answers the question using the persisted evidence rows and preserves the denominator and comparison caveats below.",
                    sections=(
                        ExplanationSection(
                            "population",
                            "One explicitly selected rollout only; no line joins unrelated rollout_row_id values.",
                        ),
                        ExplanationSection(
                            "metric", f"Persisted {source_field}; units follow the aggregate view above."
                        ),
                        ExplanationSection(
                            "denominator masks",
                            "Finite factual selected-step rows for this rollout; missing depths remain absent rather than interpolated.",
                        ),
                        ExplanationSection(
                            "comparability", "Use this for case inspection, not population or policy inference."
                        ),
                        ExplanationSection(
                            "expected pattern",
                            "The raw trajectory should explain one aggregate contribution without hiding its exact step ids.",
                        ),
                        ExplanationSection(
                            "failure interpretation",
                            "Abrupt jumps or negative valid gains can identify an interesting case for Inspect/Rerun.",
                        ),
                    ),
                    evidence_role=_temporal_evidence_role(metric),
                    source_fields=("inspection.rollout_step_objective_rows", f"steps/{source_field}"),
                    theory=_temporal_theory(metric),
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
        ordered = rows.sort_values("step_index").copy()
        ordered["acquisition_number"] = pd.to_numeric(ordered["step_index"], errors="coerce") + 1
        color = palette[index % len(palette)]
        custom = np.column_stack(
            (
                ordered["finite_count"],
                ordered["total_count"],
                ordered["missing_count"] / ordered["total_count"].clip(lower=1),
                ordered["mean"],
                ordered["min"],
                ordered["max"],
                ordered["step_index"],
            )
        )
        figure.add_trace(
            go.Scatter(
                x=ordered["acquisition_number"],
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
                x=ordered["acquisition_number"],
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
                x=ordered["acquisition_number"],
                y=ordered["median"],
                mode="lines+markers",
                line={"color": color},
                name=str(group_value),
                legendgroup=str(group_value),
                customdata=custom,
                hovertemplate=(
                    f"{group_field}={group_value}<br>acquisition=%{{x}}<br>persisted step=%{{customdata[6]:.0f}}<br>median=%{{y:.4g}}"
                    "<br>finite=%{customdata[0]:.0f} / %{customdata[1]:.0f}"
                    "<br>missing=%{customdata[2]:.1%}<br>mean=%{customdata[3]:.4g}"
                    "<br>min=%{customdata[4]:.4g}<br>max=%{customdata[5]:.4g}<extra></extra>"
                ),
            )
        )
    figure.update_layout(
        title=f"{metric_label}: median and interquartile range by rollout depth",
        xaxis_title="acquisition number (1 = first selected view; persisted step_index + 1)",
        yaxis_title=current_scientific_label(str(summary["metric"].iloc[0]), surface="plain"),
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
                    answer="This plot answers the question using the persisted evidence rows and preserves the denominator and comparison caveats below.",
                    sections=(
                        ExplanationSection(
                            "population",
                            "One factual selected step ranked only against actor-valid alternatives in its own candidate shell.",
                        ),
                        ExplanationSection(
                            "metric",
                            "Rank is ordinal; regret is best-valid minus selected target root gain, dimensionless.",
                        ),
                        ExplanationSection(
                            "denominator masks",
                            "Actor-action-valid alternatives with finite target root gain; invalid/missing labels are excluded, not assigned low reward.",
                        ),
                        ExplanationSection(
                            "comparability",
                            "Ranks are shell-local; compare regret only under equivalent reward definitions and budgets.",
                        ),
                        ExplanationSection(
                            "expected pattern",
                            "Most selected actions have low rank and small regret without total diversity collapse.",
                        ),
                        ExplanationSection(
                            "failure interpretation",
                            "High regret suggests selection/model mismatch; negative valid rewards remain distinct from invalid rows.",
                        ),
                    ),
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
        display_steps = steps.assign(acquisition_number=pd.to_numeric(steps["step_index"], errors="coerce") + 1)
        probability_cols = [
            name for name in ("selected_probability", "selected_entropy") if name in steps and steps[name].notna().any()
        ]
        if probability_cols:
            long = display_steps.melt(
                id_vars=[
                    name
                    for name in ("rollout_row_id", "policy", "step_index", "acquisition_number")
                    if name in display_steps
                ],
                value_vars=probability_cols,
                var_name="metric",
                value_name="value",
            ).dropna(subset=["value"])
            fig = px.line(
                long,
                x="acquisition_number",
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
                    answer="This plot answers the question using the persisted evidence rows and preserves the denominator and comparison caveats below.",
                    sections=(
                        ExplanationSection(
                            "population",
                            "One factual selected step; probability and entropy are shown on independent axes.",
                        ),
                        ExplanationSection(
                            "metric", "Selected probability and categorical entropy, both dimensionless."
                        ),
                        ExplanationSection(
                            "denominator masks",
                            "The persisted candidate shell and selection distribution for each factual step.",
                        ),
                        ExplanationSection(
                            "comparability", "Candidate budget, temperature, beam width, and policy recipe must agree."
                        ),
                        ExplanationSection(
                            "expected pattern",
                            "Confidence can rise with evidence while entropy does not collapse identically across every sample.",
                        ),
                        ExplanationSection(
                            "failure interpretation",
                            "Near-zero entropy everywhere suggests collapse; low probability with high regret suggests selection mismatch.",
                        ),
                    ),
                    evidence_role=_temporal_evidence_role("selected_probability"),
                    source_fields=("steps/selected_probability", "steps/selected_entropy"),
                    theory=_temporal_theory("selected_probability"),
                ),
            )

        fanout_cols = [
            name for name in ("num_valid_candidates", "invalid_fraction") if name in steps and steps[name].notna().any()
        ]
        if fanout_cols:
            long = display_steps.melt(
                id_vars=[
                    name
                    for name in ("rollout_row_id", "policy", "step_index", "acquisition_number")
                    if name in display_steps
                ],
                value_vars=fanout_cols,
                var_name="metric",
                value_name="value",
            ).dropna(subset=["value"])
            fig = px.line(
                long,
                x="acquisition_number",
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
                    answer="This plot answers the question using the persisted evidence rows and preserves the denominator and comparison caveats below.",
                    sections=(
                        ExplanationSection("population", "One candidate shell per factual rollout step."),
                        ExplanationSection(
                            "metric",
                            "Valid candidate count and invalid fraction; separate axes prevent mixed-unit distortion.",
                        ),
                        ExplanationSection(
                            "denominator masks",
                            "Fanout counts actor-action-valid candidates; invalid fraction uses the complete sampled shell.",
                        ),
                        ExplanationSection(
                            "comparability", "Candidate shell size and generator configuration must match."
                        ),
                        ExplanationSection(
                            "expected pattern",
                            "Fanout remains sufficient across depth and invalidity does not abruptly dominate.",
                        ),
                        ExplanationSection(
                            "failure interpretation",
                            "Low fanout or rising invalidity points to geometry, collision, or generator-support failures.",
                        ),
                    ),
                    evidence_role="actor-visible",
                    source_fields=("steps/num_valid_candidates", "steps/invalid_fraction"),
                    theory=_temporal_theory("valid_fanout"),
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
                    answer="This plot answers the question using the persisted evidence rows and preserves the denominator and comparison caveats below.",
                    sections=(
                        ExplanationSection(
                            "population",
                            "Aggregated factual selected steps grouped by recipe, depth, and persisted family provenance.",
                        ),
                        ExplanationSection(
                            "metric",
                            "Selected-step count; this is observed provenance, not a reconstructed search tree.",
                        ),
                        ExplanationSection("denominator masks", "Selected actor-valid transitions only."),
                        ExplanationSection(
                            "comparability",
                            "Family vocabulary, mixture weights, policy recipe, and horizon must match.",
                        ),
                        ExplanationSection(
                            "expected pattern",
                            "Multiple intended families contribute without unexplained monopolies or disappearing depths.",
                        ),
                        ExplanationSection(
                            "failure interpretation",
                            "Single-family dominance can reflect policy preference, generator imbalance, or mask collapse and needs row-level inspection.",
                        ),
                    ),
                    evidence_role="provenance",
                    source_fields=(
                        "inspection.rollout_tree_summary_rows",
                        "candidate family ids",
                        "steps/selected_candidate_row_id",
                    ),
                ),
            )
            _download_frame("Download branching provenance CSV", "rollout-branching-provenance.csv", tree)
