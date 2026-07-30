"""Target validity, candidate support, and failure-triage section."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from .session import StoredRolloutSession
from .shared import _SECTION_KEY, _download_frame, _format_plot_label, _info_popover, _render_plot

_VALIDITY_INFO = r"""
Validity is a hard admission contract, never a low reconstruction score.
Invalid-reason codes explain rejection.
Actor, oracle-label, QH-training, and selected masks are separate denominators;
selection must imply actor validity. Full reason bitsets and signed margins
retain state/path/combined predicate ownership, comparison operator, threshold,
frame, and units. Counts are reduced within decision state and then scene.

Independent confusion/boundary evidence uses the frozen stratified audit with
inverse inclusion weights (1/\pi_h). Confirmatory soundness-style language
requires a sealed PASS artifact under the exact same predicate contract.
Without it, flow, masks, reasons, and margins characterize persisted behavior
only. Missing labels/margins remain unavailable and never become false or zero.
Development triage and correlations are collapsed diagnostics, not thesis
claims.
"""
_VALID_FANOUT_COLORS = ("#14b8a6", "#2dd4bf", "#0f766e", "#5eead4")
_INVALID_FRACTION_COLORS = ("#ef4444", "#fb7185", "#be123c", "#f97316")
_ADMISSION_STATE_ORDER = (
    "Actor Ineligible",
    "Actor Valid, No Oracle Label",
    "Actor + Oracle, Not QH Admitted",
    "QH Admitted",
    "Contract Violation",
)
_ADMISSION_STATE_COLORS = {
    "Actor Ineligible": "#64748b",
    "Actor Valid, No Oracle Label": "#f59e0b",
    "Actor + Oracle, Not QH Admitted": "#a855f7",
    "QH Admitted": "#14b8a6",
    "Contract Violation": "#ef4444",
}


def _render_targets_and_support(session: StoredRolloutSession) -> None:
    st.subheader("Targets & Action Support")
    _info_popover("Masks, invalidity, and denominators", _VALIDITY_INFO)
    _render_temporal_validity(session)
    _render_invariant_status(session)
    targets = pd.DataFrame(session.targets())
    if not targets.empty:
        _render_target_protocol_audit(targets)
        _download_frame("Download target protocol CSV", "target-protocol.csv", targets)
        _render_target_score_diagnostics(targets)

    masks = pd.DataFrame(session.mask_combinations())
    if not masks.empty:
        composition = _candidate_mask_composition(masks)
        _render_plot(_candidate_mask_composition_figure(composition))
        st.caption(
            "Admission state follows the gate order Actor Valid → Oracle Label → QH Admitted. "
            "Hatching marks the separate factual selection decision; selection is not an admission gate."
        )
        with st.expander("Admission Gate Waterfall"):
            _render_candidate_admission_waterfall(masks)
        _download_frame("Download mask combinations CSV", "candidate-mask-combinations.csv", masks)

    composition = pd.DataFrame(session.candidate_composition())
    if composition.empty or "generation_cohort_id" not in composition:
        return
    cohort = st.selectbox(
        "Validity generation cohort",
        sorted(composition["generation_cohort_id"].astype(str).unique().tolist()),
    )
    state_key = f"stored_validity_heavy:{session.identity}:{cohort}"
    if st.button("Load full validity scientific evidence", key=f"{state_key}:load"):
        st.session_state[state_key] = True
    if not st.session_state.get(state_key, False):
        st.info("Full candidate validity rows and independent-audit reducers remain unloaded until requested.")
        return
    evidence = session.validity_scientific_evidence(generation_cohort_id=str(cohort))
    st.caption(f"Evidence tier: {evidence.evidence_tier}. Candidate rows are characterized over the full cohort.")
    for title, rows in (
        ("Count-conserving candidate flow", evidence.characterization.get("flow_rows", [])),
        ("Mask intersections and implication checks", evidence.characterization.get("mask_intersection_rows", [])),
        ("Invalid-reason intersections", evidence.characterization.get("reason_intersection_rows", [])),
        ("State/scene conditional validity", evidence.characterization.get("conditional_availability_rows", [])),
    ):
        with st.expander(title, expanded=title.startswith("Count")):
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if evidence.audit is None:
        st.warning("Independent same-contract validity audit is unavailable; evidence remains characterization-only.")
        if evidence.blockers:
            st.dataframe(pd.DataFrame({"blocker": evidence.blockers}), hide_index=True, width="stretch")
    else:
        for title, key in (
            ("Independent weighted confusion", "confusion_rows"),
            ("Signed-margin summaries", "margin_rows"),
            ("Predicate-boundary agreement", "boundary_rows"),
            ("Audit coverage and blockers", "coverage_rows"),
        ):
            with st.expander(title, expanded=False):
                st.dataframe(pd.DataFrame(evidence.audit.get(key, [])), hide_index=True, width="stretch")


def _render_temporal_validity(session: StoredRolloutSession) -> None:
    """Show support and invalidity over depth without redefining validity."""

    steps = pd.DataFrame(session.steps())
    if steps.empty:
        st.info("No factual step rows are available for temporal validity evidence.")
        return

    st.markdown("#### Temporal action support")
    summary_rows: list[dict[str, object]] = []
    temporal_frames: list[pd.DataFrame] = []
    for label, metric, source in (
        ("Valid candidate fanout", "valid_fanout", "num_valid_candidates"),
        ("Invalid candidate fraction", "invalid_fraction", "invalid_fraction"),
    ):
        values = pd.to_numeric(steps.get(source, pd.Series(dtype=float)), errors="coerce")
        finite = values[np.isfinite(values)]
        summary_rows.append(
            {
                "metric": label,
                "total_count": int(len(values)),
                "finite_count": int(len(finite)),
                "missing_count": int(len(values) - len(finite)),
                "mean": None if finite.empty else float(finite.mean()),
                "median": None if finite.empty else float(finite.median()),
                "q25": None if finite.empty else float(finite.quantile(0.25)),
                "q75": None if finite.empty else float(finite.quantile(0.75)),
                "min": None if finite.empty else float(finite.min()),
                "max": None if finite.empty else float(finite.max()),
            }
        )
        temporal = pd.DataFrame(session.temporal_summary(metric=metric, group_fields=("policy", "horizon")))
        if not temporal.empty:
            temporal["metric_label"] = label
            temporal_frames.append(temporal)

    summary = pd.DataFrame(summary_rows)
    st.dataframe(summary, hide_index=True, width="stretch")
    _download_frame("Download temporal validity summary CSV", "temporal-validity-summary.csv", summary)
    if temporal_frames:
        temporal = pd.concat(temporal_frames, ignore_index=True)
        chart_specs = (
            ("Valid Candidate Fanout", "Valid Candidates", _VALID_FANOUT_COLORS),
            ("Invalid Candidate Fraction", "Invalid Candidate Fraction", _INVALID_FRACTION_COLORS),
        )
        for column, (metric_label, y_label, colors) in zip(st.columns(2), chart_specs, strict=True):
            metric_rows = temporal.loc[temporal["metric_label"] == metric_label]
            with column:
                _render_plot(_temporal_validity_figure(metric_rows, y_label=y_label, colors=colors))
        st.dataframe(temporal, hide_index=True, width="stretch")
        _download_frame("Download temporal validity rows CSV", "temporal-validity-by-depth.csv", temporal)


def _temporal_validity_figure(
    temporal: pd.DataFrame,
    *,
    y_label: str,
    colors: tuple[str, ...],
):
    """Build one metric-specific depth chart with a stable policy/horizon legend."""

    plotted = temporal.assign(
        series_label=temporal.apply(
            lambda row: f"{_format_plot_label(row.get('policy', 'unknown'))} · Horizon {row.get('horizon', '?')}",
            axis=1,
        )
    )
    return px.line(
        plotted,
        x="step_index",
        y="median",
        color="series_label",
        markers=True,
        color_discrete_sequence=colors,
        hover_data=[name for name in ("finite_count", "total_count", "q25", "q75") if name in plotted],
        labels={
            "step_index": "Rollout Step",
            "median": y_label,
            "series_label": "Policy · Horizon",
            "finite_count": "Finite Steps",
            "total_count": "Total Steps",
            "q25": "25th Percentile",
            "q75": "75th Percentile",
        },
        title=f"{y_label} By Rollout Step",
    )


def _candidate_mask_composition(masks: pd.DataFrame) -> pd.DataFrame:
    """Translate raw mask tuples into named admission states plus factual selection."""

    composition_rows: list[dict[str, object]] = []
    for _, row in masks.iterrows():
        actor_action = bool(row.get("actor_action", False))
        oracle_label = bool(row.get("oracle_label", False))
        q_train = bool(row.get("q_train", False))
        selected = bool(row.get("selected", False))
        if (q_train and not (actor_action and oracle_label)) or (selected and not actor_action):
            admission_state = "Contract Violation"
        elif not actor_action:
            admission_state = "Actor Ineligible"
        elif not oracle_label:
            admission_state = "Actor Valid, No Oracle Label"
        elif not q_train:
            admission_state = "Actor + Oracle, Not QH Admitted"
        else:
            admission_state = "QH Admitted"
        count = pd.to_numeric(row.get("count"), errors="coerce")
        composition_rows.append(
            {
                "admission_state": admission_state,
                "selection_state": "Selected" if selected else "Not Selected",
                "count": 0 if pd.isna(count) else int(count),
            }
        )
    return (
        pd.DataFrame(composition_rows)
        .groupby(["admission_state", "selection_state"], as_index=False, sort=False)["count"]
        .sum()
    )


def _candidate_mask_composition_figure(composition: pd.DataFrame) -> go.Figure:
    """Build the named admission-state composition with selection encoded separately."""

    figure = px.bar(
        composition,
        x="admission_state",
        y="count",
        color="admission_state",
        pattern_shape="selection_state",
        text="count",
        barmode="stack",
        category_orders={"admission_state": list(_ADMISSION_STATE_ORDER)},
        color_discrete_map=_ADMISSION_STATE_COLORS,
        pattern_shape_map={"Selected": "/", "Not Selected": "."},
        labels={
            "admission_state": "Admission State",
            "selection_state": "Factual Selection",
            "count": "Candidates",
        },
        title="Candidate Admission States and Factual Selection",
    )
    figure.update_xaxes(tickangle=-20)
    return figure


def _render_target_protocol_audit(targets: pd.DataFrame) -> None:
    """Render target-admission composition and GT-match evidence without a count-only bar chart."""

    st.markdown("#### Target Protocol Audit")
    summary = _target_protocol_summary(targets)
    metrics = st.columns(4)
    metrics[0].metric("Targets", summary["target_count"])
    metrics[1].metric("Actor Valid", f"{summary['actor_valid_count']}/{summary['target_count']}")
    metrics[2].metric("GT Label Coverage", f"{summary['gt_label_valid_count']}/{summary['target_count']}")
    metrics[3].metric("GT Matched", f"{summary['matched_count']}/{summary['target_count']}")

    matrix_column, quality_column = st.columns(2)
    with matrix_column:
        _render_plot(_target_protocol_matrix_figure(targets))
    with quality_column:
        quality = targets.dropna(subset=["gt_match_iou", "gt_match_score"])
        if len(quality) >= 2:
            figure = px.scatter(
                quality,
                x="gt_match_iou",
                y="gt_match_score",
                color="gt_match_status",
                symbol="target_valid",
                hover_data=[
                    field
                    for field in ("target_id", "class", "confidence", "selection_rank", "selection_score")
                    if field in quality
                ],
                labels={"gt_match_iou": "GT Match IoU", "gt_match_score": "GT Match Score"},
                title="GT Match Quality",
            )
            figure.update_xaxes(range=[0.0, 1.0])
            figure.update_yaxes(range=[0.0, 1.0])
            _render_plot(figure)
        else:
            _render_single_target_match_card(targets)


def _target_protocol_summary(targets: pd.DataFrame) -> dict[str, int]:
    """Summarize the target-admission and GT-matching stages for protocol metrics."""

    statuses = targets.get("gt_match_status", pd.Series(dtype=str)).astype(str).str.lower()
    return {
        "target_count": int(len(targets)),
        "actor_valid_count": int(targets.get("target_valid", pd.Series(dtype=bool)).astype(bool).sum()),
        "gt_label_valid_count": int(targets.get("gt_label_valid", pd.Series(dtype=bool)).astype(bool).sum()),
        "matched_count": int(statuses.eq("matched").sum()),
    }


def _target_protocol_matrix_figure(targets: pd.DataFrame) -> go.Figure:
    """Build the actor-validity by GT-label-availability composition matrix."""

    protocol = targets.assign(
        actor_validity=np.where(targets["target_valid"].astype(bool), "Actor Valid", "Actor Invalid"),
        gt_label_availability=np.where(targets["gt_label_valid"].astype(bool), "GT Label Valid", "GT Label Missing"),
    )
    actor_order = ["Actor Valid", "Actor Invalid"]
    label_order = ["GT Label Valid", "GT Label Missing"]
    matrix = (
        pd.crosstab(protocol["actor_validity"], protocol["gt_label_availability"])
        .reindex(index=actor_order, columns=label_order, fill_value=0)
        .astype(int)
    )
    return go.Figure(
        go.Heatmap(
            z=matrix.to_numpy(),
            x=label_order,
            y=actor_order,
            colorscale=[[0.0, "#1f2937"], [0.5, "#2563eb"], [1.0, "#93c5fd"]],
            text=matrix.to_numpy(),
            texttemplate="%{text}",
            textfont={"size": 24},
            colorbar={"title": "Targets"},
            hovertemplate="Actor Validity: %{y}<br>GT Label Availability: %{x}<br>Targets: %{z}<extra></extra>",
        )
    ).update_layout(title="Actor Validity × GT-Label Availability", height=430)


def _render_single_target_match_card(targets: pd.DataFrame) -> None:
    """Show detailed GT-match evidence when a scatter would collapse to one point."""

    target = targets.iloc[0]
    status = str(target.get("gt_match_status", "unavailable"))
    with st.container(border=True):
        (st.success if status.lower() == "matched" else st.warning)(f"GT Match: {_format_plot_label(status)}")
        st.caption(
            f"{_format_plot_label(target.get('target_id', 'unnamed target'))} · "
            f"{_format_plot_label(target.get('class', 'unknown class'))}"
        )
        metrics = st.columns(2)
        metrics[0].metric("GT Match IoU", _format_optional_metric(target.get("gt_match_iou")))
        metrics[1].metric("GT Match Score", _format_optional_metric(target.get("gt_match_score")))


def _format_optional_metric(value: object) -> str:
    """Format a finite scalar metric without turning missing target evidence into zero."""

    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return "Unavailable" if pd.isna(number) else f"{float(number):.3f}"


def _render_invariant_status(session: StoredRolloutSession) -> None:
    """Show failing invariants and selected-row consistency in the validity owner."""

    invariants = pd.DataFrame(session.invariants())
    if invariants.empty:
        st.info("No store invariant evidence is available.")
        return
    status = invariants.get("status", pd.Series(dtype=str)).astype(str).str.upper()
    failures = invariants[status.eq("FAIL")]
    selected = invariants[
        invariants.get("invariant_id", pd.Series(dtype=str))
        .astype(str)
        .isin(("selected_actor_mask", "q_train_supervision", "q_h_selected_transition", "q_h_factual_consistency"))
    ]
    cols = st.columns(3)
    cols[0].metric("Invariant failures", f"{len(failures):,}")
    cols[1].metric("Selected actor-mask", _invariant_status(selected, "selected_actor_mask"))
    cols[2].metric("QH factual consistency", _invariant_status(selected, "q_h_factual_consistency"))
    evidence = pd.concat((failures, selected), ignore_index=True)
    dedupe_columns = [name for name in ("invariant_id", "status") if name in evidence]
    if dedupe_columns:
        evidence = evidence.drop_duplicates(subset=dedupe_columns)
    if not evidence.empty:
        _render_invariant_cards(evidence)
        _download_frame("Download validity invariant CSV", "validity-invariants.csv", evidence)


def _render_invariant_cards(evidence: pd.DataFrame) -> None:
    """Render invariant evidence as category-level contract cards rather than a wide table."""

    for category, rows in _invariant_groups(evidence):
        st.markdown(f"#### {category}")
        columns = st.columns(2)
        for index, (_, row) in enumerate(rows.iterrows()):
            with columns[index % len(columns)]:
                _render_invariant_card(row)


def _invariant_groups(evidence: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    """Group invariant rows by their persisted contract category for composition-first display."""

    grouped = evidence.assign(
        category_label=evidence.get("category", pd.Series("uncategorized", index=evidence.index))
        .fillna("uncategorized")
        .map(_format_plot_label)
    )
    return [
        (category, rows.drop(columns="category_label").sort_values("invariant_id"))
        for category, rows in grouped.groupby("category_label", sort=True)
    ]


def _render_invariant_card(row: pd.Series) -> None:
    """Render one concise invariant result with expandable contract evidence."""

    status = str(row.get("status", "unavailable")).upper()
    invariant = _format_plot_label(row.get("invariant_id", "unnamed invariant"))
    message = f"{status} · {invariant}"
    with st.container(border=True):
        if status == "PASS":
            st.success(message)
        elif status == "FAIL":
            st.error(message)
        else:
            st.warning(message)
        summary = row.get("summary")
        if pd.notna(summary):
            st.caption(str(summary))
        with st.expander("Expected Versus Observed", expanded=status == "FAIL"):
            st.markdown("**Expected**")
            st.code(str(row.get("expected", "Unavailable")), language="text")
            st.markdown("**Observed**")
            st.code(str(row.get("observed", "Unavailable")), language="text")


def _invariant_status(rows: pd.DataFrame, invariant_id: str) -> str:
    """Return one compact invariant status without treating absence as success."""

    if rows.empty or "invariant_id" not in rows or "status" not in rows:
        return "Unavailable"
    matches = rows.loc[rows["invariant_id"].astype(str) == invariant_id, "status"]
    return "Unavailable" if matches.empty else str(matches.iloc[0]).upper()


def _render_candidate_admission_waterfall(masks: pd.DataFrame) -> None:
    """Render nested QH admission counts while keeping selection a separate decision."""

    required = {"actor_action", "oracle_label", "q_train", "selected", "count"}
    if not required.issubset(masks.columns):
        st.info("Candidate admission waterfall is unavailable because persisted mask combinations are incomplete.")
        return
    count = pd.to_numeric(masks["count"], errors="coerce").fillna(0).astype(int)
    actor = masks["actor_action"].astype(bool)
    oracle = masks["oracle_label"].astype(bool)
    q_train = masks["q_train"].astype(bool)
    selected = masks["selected"].astype(bool)
    total = int(count.sum())
    actor_count = int(count[actor].sum())
    actor_oracle_count = int(count[actor & oracle].sum())
    q_train_count = int(count[q_train & actor & oracle].sum())
    q_train_violations = int(count[q_train & ~(actor & oracle)].sum())
    selected_count = int(count[selected].sum())
    figure = go.Figure(
        go.Waterfall(
            measure=["absolute", "relative", "total", "relative", "total", "relative", "total"],
            x=[
                "Sampled",
                "Actor-invalid",
                "Actor-valid",
                "Missing oracle label",
                "Actor + oracle",
                "Not QH-admitted",
                "QH-admitted",
            ],
            y=[
                total,
                -(total - actor_count),
                actor_count,
                -(actor_count - actor_oracle_count),
                actor_oracle_count,
                -(actor_oracle_count - q_train_count),
                q_train_count,
            ],
            connector={"line": {"color": "#9ca3af"}},
        )
    )
    figure.update_layout(title="Candidate admission to QH supervision")
    _render_plot(figure)
    if q_train_violations:
        st.error(
            f"{q_train_violations:,} q_train rows violate actor/oracle admission; "
            "the waterfall reports only contract-consistent QH-admitted rows."
        )
    st.caption(
        f"Selected actions are a separate factual decision population: {selected_count:,} of {total:,} candidates. "
        "Selection is not a stage after q_train admission."
    )


def _render_invalid_reason_distributions(candidates: pd.DataFrame) -> None:
    """Show persisted invalid-reason counts by policy and candidate family."""

    required = {"actor_action", "invalid_reason"}
    if candidates.empty or not required.issubset(candidates.columns):
        st.info("Invalid-reason distributions are unavailable in this persisted candidate projection.")
        return
    invalid = candidates.loc[~candidates["actor_action"].astype(bool)].copy()
    if invalid.empty:
        st.success("No actor-invalid candidate rows are persisted.")
        return
    distributions: list[pd.DataFrame] = []
    for field in ("policy", "position", "strategy", "mixture"):
        if field not in invalid:
            continue
        grouped = (
            invalid.groupby([field, "invalid_reason"], dropna=False)
            .size()
            .reset_index(name="count")
            .rename(columns={field: "group_value"})
        )
        grouped["group_field"] = field
        distributions.append(grouped)
    if not distributions:
        st.info("Invalid reasons are persisted, but policy and candidate-family fields are unavailable.")
        st.dataframe(
            invalid.groupby("invalid_reason", dropna=False).size().reset_index(name="count"),
            hide_index=True,
            width="stretch",
        )
        return
    evidence = pd.concat(distributions, ignore_index=True)
    figure = px.bar(
        evidence,
        x="group_value",
        y="count",
        color="invalid_reason",
        facet_col="group_field",
        facet_col_wrap=2,
        title="Persisted hard-invalid reasons by policy and candidate family",
    )
    figure.update_xaxes(matches=None)
    _render_plot(figure)
    st.dataframe(evidence, hide_index=True, width="stretch")
    _download_frame("Download invalid-reason distribution CSV", "invalid-reasons-by-family.csv", evidence)


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
            _render_plot(fig)

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
                _render_plot(fig)

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
        if len(component_cols) >= 3:
            corr = targets[component_cols].apply(pd.to_numeric, errors="coerce").corr(min_periods=2)
            fig = go.Figure(
                go.Heatmap(
                    z=corr.to_numpy(),
                    x=corr.columns.tolist(),
                    y=corr.index.tolist(),
                    zmin=-1,
                    zmax=1,
                    colorscale="RdBu",
                    reversescale=True,
                    text=np.round(corr.to_numpy(), 2),
                    texttemplate="%{text}",
                )
            )
            fig.update_layout(title="Target score-component correlation", height=440)
            _render_plot(fig)


def _render_failure_triage(session: StoredRolloutSession) -> None:
    st.subheader("Failure Triage")
    st.caption(
        "Triage uses the repository's fixed diagnostic defaults. These findings prioritize debugging; "
        "they do not redefine persisted validity or infer invalidity from reconstruction scores."
    )
    failures = pd.DataFrame(session.failures())
    if failures.empty:
        st.success("No failure rows match the fixed diagnostic predicates.")
        return
    severity = failures.groupby(["severity", "kind"], dropna=False).size().reset_index(name="count")
    fig = px.bar(severity, x="kind", y="count", color="severity", title="Failure evidence by kind and severity")
    _render_plot(fig)
    st.dataframe(failures, hide_index=True, width="stretch")
    _download_frame("Download failure triage CSV", "failure-triage.csv", failures)
    choices = failures.to_dict("records")
    chosen = st.selectbox(
        "Failure to inspect",
        choices,
        format_func=lambda row: f"{row.get('severity', '?')} · {row.get('kind', '?')} · {row.get('message', '')}",
    )
    st.button(
        "Inspect selected failure",
        on_click=_carry_failure_to_inspect,
        args=(chosen,),
        type="primary",
    )


def _carry_failure_to_inspect(row: dict[str, object]) -> None:
    """Carry stable rollout/step identifiers into the inspection workspace."""

    if row.get("rollout_row_id") is not None:
        st.session_state["stored_rollout_id"] = int(cast(int, row["rollout_row_id"]))
    if row.get("step_row_id") is not None:
        st.session_state["stored_step_id"] = int(cast(int, row["step_row_id"]))
    st.session_state[_SECTION_KEY] = "Inspect & Rerun"


def render(session: StoredRolloutSession) -> None:
    """Render target/action support followed by actionable failure triage."""

    _render_targets_and_support(session)
    with st.expander("Development triage and score correlations", expanded=False):
        _render_failure_triage(session)


__all__ = ["render"]
