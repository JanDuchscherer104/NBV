"""Candidate-generation provenance and aggregate evidence presentation."""

from __future__ import annotations

from collections import Counter
from itertools import pairwise

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ....rollouts.inspection import (
    CANDIDATE_GROUP_FIELDS,
    candidate_selection_pooled_summary_rows,
    candidate_selection_transition_rows,
)
from .session import (
    _cached_candidate_flow,
    _cached_candidate_group,
    _cached_candidate_population,
    _cached_ranks,
    _cached_steps,
    _cached_store_bundle,
)
from .shared import ScientificExplanation
from .shared import download_frame as _download_frame
from .shared import render_plot as _render_plot

_CANDIDATE_POPULATIONS = ("Selected step", "Selected rollout", "Explicit full store")


def _pooled_candidate_selection_figure(summary: pd.DataFrame) -> go.Figure:
    """Plot pooled policy mass by candidate family and factual acquisition."""

    figure = go.Figure()
    for family, rows in summary.sort_values("step_index").groupby("family", sort=True):
        figure.add_trace(
            go.Scatter(
                x=rows["step_index"].astype(int) + 1,
                y=rows["fraction"],
                mode="lines+markers",
                name=str(family),
            )
        )
    figure.update_layout(xaxis_title="acquisition number", yaxis_title="policy mass")
    return figure


def _candidate_transition_figure(rows: pd.DataFrame) -> go.Figure:
    """Show expected and realized family transitions as matched heatmaps."""

    families = sorted(set(rows["previous_family"]) | set(rows["next_family"]))
    expected = rows.pivot(index="previous_family", columns="next_family", values="expected_policy_mass_mean").reindex(
        index=families, columns=families
    )
    realized = rows.pivot(index="previous_family", columns="next_family", values="realized_rate").reindex(
        index=families, columns=families
    )
    figure = go.Figure()
    figure.add_trace(go.Heatmap(z=expected.to_numpy(), x=families, y=families, name="expected"))
    figure.add_trace(go.Heatmap(z=realized.to_numpy(), x=families, y=families, name="realized", visible=False))
    step = int(rows["step_index"].iloc[0])
    figure.update_layout(title=f"Candidate-family transitions at acquisition {step}")
    return figure


def _pose_axis_frames(frames: pd.DataFrame, *, mode: str, frame_id: str | None = None) -> pd.DataFrame:
    """Apply bounded pose-axis overlay disclosure controls."""

    if mode == "Hidden":
        return frames.iloc[0:0].copy()
    if mode == "One frame":
        return frames.loc[frames["frame_id"] == frame_id].copy()
    return frames.head(32).copy()


def _add_geometry_anchors(
    figure: go.Figure,
    frames: pd.DataFrame,
    *,
    three_dimensional: bool,
    axis_frames: pd.DataFrame,
) -> None:
    """Add reference and target anchors without implicitly adding pose triads."""

    if three_dimensional:
        figure.add_trace(go.Scatter3d(x=[0], y=[0], z=[0], mode="markers", name="Reference pose (all at origin)"))
        figure.add_trace(
            go.Scatter3d(
                x=frames["target_x"],
                y=frames["target_y"],
                z=frames["target_z"],
                mode="markers",
                name="Observed target center",
            )
        )


def _normalized_radius_figure(geometry: pd.DataFrame) -> go.Figure:
    """Plot target-distance-normalized candidate radii with the unit threshold."""

    figure = px.scatter(geometry, x="step_index", y="normalized_radius", color="position")
    figure.add_hline(y=1.0, line_dash="dash", line_color="red")
    return figure


def _orientation_diagnostic_rows(geometry: pd.DataFrame, frames: pd.DataFrame) -> pd.DataFrame:
    """Return explicit rig, selected-camera, and target-elevation diagnostics."""

    rows: list[dict[str, object]] = []
    for _, frame in frames.iterrows():
        rollout = int(frame["rollout_row_id"])
        step = int(frame["step_index"])
        selected = geometry[(geometry["rollout_row_id"] == rollout) & (geometry["step_index"] == step)]
        rows.extend(
            [
                {
                    "diagnostic": "Rig-to-target yaw error",
                    "rollout_row_id": rollout,
                    "step_index": step,
                    "angle_deg": frame["rig_target_yaw_error_deg"],
                },
                {
                    "diagnostic": "Selected camera-to-target error",
                    "rollout_row_id": rollout,
                    "step_index": step,
                    "angle_deg": selected.loc[selected["selected"], "target_facing_error_deg"].iloc[0]
                    if selected["selected"].any()
                    else np.nan,
                },
                {
                    "diagnostic": "Target elevation",
                    "rollout_row_id": rollout,
                    "step_index": step,
                    "angle_deg": frame["target_elevation_deg"],
                },
            ]
        )
    return pd.DataFrame(rows)


def _orientation_diagnostic_figure(rows: pd.DataFrame) -> go.Figure:
    """Plot diagnostic angle distributions by named diagnostic."""

    figure = px.scatter(rows, x="step_index", y="angle_deg", color="diagnostic")
    return figure


def _prepare_pairwise_correlation(frame: pd.DataFrame, columns: list[str]) -> dict[str, object]:
    """Prepare pair-local finite Pearson evidence, including auditable support counts."""

    numeric = frame.loc[:, columns].apply(pd.to_numeric, errors="coerce")
    correlation = pd.DataFrame(np.nan, index=columns, columns=columns, dtype=float)
    counts = pd.DataFrame(0, index=columns, columns=columns, dtype=int)
    reasons: dict[tuple[str, str], str] = {}
    has_finite_off_diagonal = False
    for left in columns:
        for right in columns:
            values = numeric.loc[:, [left, right]].to_numpy(dtype=float)
            finite_values = values[np.isfinite(values).all(axis=1)]
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


def _render_candidate_population_evidence(store_path: str) -> None:
    """Render complete candidate aggregates and a deterministic display-only sample."""

    group_by = st.selectbox("Candidate evidence grouping", options=list(CANDIDATE_GROUP_FIELDS))
    population = _cached_candidate_population(store_path)
    composition = pd.DataFrame(population["composition"][group_by])
    calibration = pd.DataFrame(population["calibration"][group_by])
    collision = pd.DataFrame(population["collision"])
    sample = population["sample"]

    evidence_role = _candidate_population_role(population)
    if evidence_role is None:
        st.warning(
            "Normalized target-view evidence is withheld: complete-store target provenance is mixed, unknown, "
            "or unclassified. The bounded display sample is never used to infer provenance."
        )
    _render_complete_candidate_support(population, evidence_role=evidence_role or "provenance")

    selection_dynamics = population.get("selection_dynamics", {})
    if isinstance(selection_dynamics, dict):
        dynamics = next(
            (pd.DataFrame(value) for value in selection_dynamics.values() if isinstance(value, list) and value),
            pd.DataFrame(),
        )
        if not dynamics.empty:
            pooled = pd.DataFrame(
                candidate_selection_pooled_summary_rows(dynamics.to_dict("records"), metric="policy_mass")
            )
            if not pooled.empty:
                _render_plot(
                    _pooled_candidate_selection_figure(pooled),
                    _candidate_population_explanation(
                        "How does candidate-family choice evolve across factual acquisition?",
                        "Complete candidate-choice dynamics from compatible factual states.",
                        "Policy mass per family and acquisition; dimensionless fraction.",
                        "Persisted selection probabilities over finite candidate rows; observed states remain explicit.",
                        "Choice mass changes smoothly without unexplained family monopolies or missing depths.",
                        "Abrupt changes or absent families can indicate generator, policy, or state-frame issues.",
                        "inspection.candidate_population_evidence.selection_dynamics",
                        evidence_role or "provenance",
                    ),
                )
                transitions = pd.DataFrame(
                    candidate_selection_transition_rows(dynamics.to_dict("records"), pool_temperatures=True)
                )
                if not transitions.empty:
                    _render_plot(
                        _candidate_transition_figure(transitions),
                        _candidate_population_explanation(
                            "How does the previously selected family relate to the next family?",
                            "Complete adjacent-step candidate-choice transitions in the selected compatible cohort.",
                            "Expected policy mass and realized transition frequency; dimensionless fractions.",
                            "Only factual adjacent-step contexts with persisted selection evidence contribute.",
                            "Expected and realized transitions broadly agree where context support is substantial.",
                            "Sparse or divergent cells are diagnostics of support and policy/state effects, not causal proof.",
                            "inspection.candidate_population_evidence.selection_transitions",
                            evidence_role or "provenance",
                        ),
                    )
                with st.expander("Candidate-choice rows and CSV"):
                    st.dataframe(pooled, hide_index=True, width="stretch")
                    _download_frame("Download candidate-choice CSV", "candidate-choice-dynamics.csv", pooled)

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


def _candidate_population_role(population: dict[str, object]) -> str | None:
    """Return one complete-store target-evidence role, never infer it from samples."""

    rows = population.get("target_evidence_roles", [])
    if not isinstance(rows, list):
        return None
    roles = {
        str(row.get("target_evidence_role"))
        for row in rows
        if isinstance(row, dict) and int(row.get("candidate_count", 0)) > 0
    }
    return (
        next(iter(roles)) if len(roles) == 1 and next(iter(roles)) in {"actor-visible", "oracle/evaluation"} else None
    )


def _candidate_population_explanation(
    question: str,
    population: str,
    metric: str,
    denominator_masks: str,
    expected_pattern: str,
    failure_interpretation: str,
    source: str,
    role: str,
) -> ScientificExplanation:
    """Build consistent scientific context for complete candidate-support plots."""

    return ScientificExplanation(
        question=question,
        population=population,
        metric=metric,
        denominator_masks=denominator_masks,
        comparability="Compare only matching persisted candidate contracts and generation cohorts.",
        expected_pattern=expected_pattern,
        failure_interpretation=failure_interpretation,
        evidence_role=role,
        source_fields=(source,),
        intuition="These are descriptive diagnostics of persisted support, not causal policy effects.",
        visual_encoding="Bars and heatmaps retain generation-cohort and population facets where available.",
        uncertainty="Missing values remain unavailable; descriptive summaries are not confidence intervals.",
    )


def _render_complete_candidate_support(population: dict[str, object], *, evidence_role: str) -> None:
    """Render PR101 support facets through the decomposed candidate owner."""

    direction = population.get("direction", {})
    if isinstance(direction, dict):
        density = pd.DataFrame(direction.get("density_rows", []))
        if not density.empty:
            selected = _select_support_facet(density, "Direction support")
            if not selected.empty:
                pivot = selected.pivot(
                    index="sin_elevation_bin", columns="azimuth_bin", values="mean_state_fraction"
                ).sort_index()
                fig = px.imshow(
                    pivot,
                    origin="lower",
                    aspect="auto",
                    labels={"x": "azimuth bin", "y": "sin(elevation) bin", "color": "fraction"},
                    title="Candidate direction support (equal-area bins)",
                )
                _render_plot(
                    fig,
                    _candidate_population_explanation(
                        "Does candidate direction support cover solid angle without coordinate-latitude bias?",
                        "Complete candidate direction rows, retaining zero-valid states and finite/missing counts.",
                        "Fraction per azimuth × sin(elevation) equal-area bin.",
                        "Finite non-zero direction vectors define the state-local direction denominator.",
                        "Support is broad rather than concentrated in unexplained angular bands.",
                        "Spikes or missing direction rows indicate support or pose-frame issues.",
                        "inspection.candidate_direction_evidence",
                        evidence_role,
                    ),
                )
                with st.expander("Direction support rows and CSV"):
                    st.dataframe(selected, hide_index=True, width="stretch")
                    _download_frame("Download direction support CSV", "candidate-direction-support.csv", selected)
        cap = pd.DataFrame(direction.get("cap_rows", []))
        if not cap.empty and "discrepancy" in cap:
            cap = cap.copy()
            cap["metric"] = "distance_from_isotropy"
            fig = px.bar(
                cap,
                x="radius_deg" if "radius_deg" in cap else "metric",
                y="discrepancy",
                color="population" if "population" in cap else None,
                title="Angular total-variation distance from isotropic reference",
            )
            _render_plot(
                fig,
                _candidate_population_explanation(
                    "How far does the observed direction distribution depart from an isotropic reference?",
                    "Complete factual-state direction support summaries.",
                    "Angular total-variation distance from the uniform-S² reference; dimensionless fraction.",
                    "Finite normalized directions only; missing directions are not zero-filled.",
                    "A small value means closer descriptive agreement with the isotropic reference at that scale.",
                    "A large value is anisotropy evidence, not proof of generator collapse.",
                    "inspection.candidate_direction_evidence.cap_rows",
                    evidence_role,
                ),
            )

    for key, title in (("spatial", "Spatial candidate support"), ("motion", "Motion and collision support")):
        frame = pd.DataFrame(population.get(key, []))
        if frame.empty:
            continue
        value = "mean" if "mean" in frame else "count"
        if "metric" not in frame or value not in frame:
            continue
        selected = _select_support_facet(frame, title)
        fig = px.bar(
            selected,
            x="metric",
            y=value,
            color="population" if "population" in selected else None,
            barmode="group",
            title=title,
        )
        _render_plot(
            fig,
            _candidate_population_explanation(
                f"What physical {key.replace('_', ' ')} support is present?",
                "Complete candidate audit summaries, including states with no finite support.",
                "Metric units are persisted per row; metres, degrees, fractions, and counts are not pooled.",
                "Finite values use their metric-specific denominator; unavailable evidence remains explicit.",
                "Configured spatial and motion support remains represented across compatible cohorts.",
                "Concentration, clipping, or missingness indicates a component or evaluator coverage issue.",
                f"inspection.candidate_{key}_support_evidence",
                evidence_role,
            ),
        )
        with st.expander(f"{title} rows and CSV"):
            st.dataframe(selected, hide_index=True, width="stretch")
            _download_frame(f"Download {key} support CSV", f"candidate-{key}-support.csv", selected)

    target_view = pd.DataFrame(population.get("target_view", []))
    if evidence_role in {"actor-visible", "oracle/evaluation"} and not target_view.empty:
        value = "mean" if "mean" in target_view else "count"
        if "metric" in target_view and value in target_view:
            fig = px.bar(
                _select_support_facet(target_view, "Target-view support"),
                x="metric",
                y=value,
                color="population" if "population" in target_view else None,
                title="Target-view support and availability",
            )
            _render_plot(
                fig,
                _candidate_population_explanation(
                    "How much target-view evidence is available for the selected candidate population?",
                    "Complete target-view audit rows for one unambiguous target-evidence role.",
                    "Metric values retain their persisted units; missingness is counted separately.",
                    "Only finite target-view measurements enter metric summaries; missing rows remain unavailable.",
                    "Optical and geometric target-view evidence is available for the declared protocol.",
                    "Large missing counts indicate evaluator coverage gaps, not poor visibility.",
                    "inspection.candidate_target_view_evidence",
                    evidence_role,
                ),
            )


def _select_support_facet(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    """Select one exact persisted support facet before rendering a plot."""

    selected = frame.copy()
    for field in ("contract_id", "generation_cohort_id", "population", "aggregation_level", "scene_id", "step_index"):
        if field not in selected.columns:
            continue
        values = sorted(selected[field].dropna().astype(str).unique())
        if len(values) <= 1:
            continue
        default = "cohort_macro" if field == "aggregation_level" and "cohort_macro" in values else values[0]
        choice = st.selectbox(f"{label}: {field}", values, index=values.index(default), key=f"support-{label}-{field}")
        selected = selected[selected[field].astype(str).eq(str(choice))]
    return selected


def _render_candidate_provenance_flow(store_path: str) -> None:
    """Render the lightweight complete-population candidate provenance flow."""

    _, validation, _ = _cached_store_bundle(store_path)
    store_candidate_count = int(validation.num_candidates)
    steps = pd.DataFrame(_cached_steps(store_path))
    policy_options = sorted(str(value) for value in steps.get("policy", pd.Series(dtype=str)).dropna().unique())
    depth_options = sorted(int(value) for value in steps.get("step_index", pd.Series(dtype=int)).dropna().unique())
    col_policy, col_depth = st.columns(2)
    selected_policies = col_policy.multiselect("Flow policies", options=policy_options, default=policy_options)
    selected_depths = col_depth.multiselect("Flow rollout depths", options=depth_options, default=depth_options)
    flow = pd.DataFrame(
        _cached_candidate_flow(
            store_path,
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
        _cached_ranks(
            store_path,
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

    families = pd.DataFrame(_cached_candidate_group(store_path, "position"))
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
                source_fields=("candidate position_id", "actor_action_mask", "selected_mask"),
            ),
        )
        _download_frame("Download family support CSV", "candidate-family-support.csv", families)

    breakdown_by = st.selectbox(
        "Candidate aggregate breakdown",
        options=list(CANDIDATE_GROUP_FIELDS),
        help="Switches one complete-store aggregate plot without rebuilding the candidate audit.",
    )
    breakdown = pd.DataFrame(_cached_candidate_group(store_path, breakdown_by))
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
                source_fields=(
                    "inspection.candidate_group_summary_rows",
                    f"candidate {breakdown_by}",
                    "candidate masks",
                ),
            ),
        )

    with st.expander("Invalid reasons and valid fanout"):
        invalid = pd.DataFrame(_cached_candidate_group(store_path, "invalid_reason"))
        fanout = pd.DataFrame(_cached_steps(store_path))
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
        if len(component_cols) >= 3:
            prepared = _prepare_pairwise_correlation(targets, component_cols)
            corr = prepared["correlation"]
            if prepared["has_finite_off_diagonal"]:
                counts = prepared["counts"]
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
                        customdata=counts.to_numpy(),
                        hovertemplate="x=%{x}<br>y=%{y}<br>r=%{z:.3f}<br>pair n=%{customdata}<extra></extra>",
                    )
                )
                fig.update_layout(title="Target score-component correlation", height=440)
                _render_plot(
                    fig,
                    ScientificExplanation(
                        question="Which target-score components are redundant, opposed, or unexpectedly disconnected?",
                        population="Pairwise-complete target proposals; each heatmap cell reports its own finite pair count.",
                        metric="Pearson correlation coefficient, dimensionless in [-1, 1]; hover shows pair-local n.",
                        denominator_masks="Only rows finite for both components enter that pair; ±inf and missing values are excluded.",
                        comparability="Only compare matrices from identical score definitions and target protocols.",
                        expected_pattern="Components reflect their intended roles without perfect accidental duplication.",
                        failure_interpretation="Near-perfect n=2 correlations are algebraically degenerate; sparse or unexpected signs need more evidence.",
                        evidence_role="oracle/evaluation",
                        source_fields=tuple(f"targets/{name}" for name in component_cols),
                    ),
                )
            else:
                st.info(
                    "Correlation heatmap unavailable: no component pair has at least two finite, non-constant rows."
                )


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
            if {"target_x", "target_y"}.issubset(root_geometry.columns):
                _add_geometry_anchors(
                    fig,
                    root_geometry,
                    three_dimensional=False,
                    axis_frames=root_geometry,
                )
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
                    source_fields=(
                        "inspection.root_relative_candidate_rows",
                        "candidate pose_world_cam",
                        "rollout root_pose_world",
                    ),
                ),
            )

        if "normalized_radius" in candidates and candidates["normalized_radius"].notna().any():
            radius = candidates.dropna(subset=["normalized_radius"])
            _render_plot(
                _normalized_radius_figure(radius),
                ScientificExplanation(
                    question="Do candidate radii respect the target-normalized geometry envelope?",
                    population="Bounded candidate rows with finite target-distance-normalized radius.",
                    metric="Candidate radius divided by the persisted target-distance scale; dimensionless.",
                    denominator_masks="Finite normalized-radius rows; missing geometry remains unavailable.",
                    comparability="Compare only stores sharing the same target normalization and candidate contract.",
                    expected_pattern="Most support remains within the unit target-normalized envelope.",
                    failure_interpretation="Clipping or heavy tails can expose impossible geometry or frame mistakes.",
                    evidence_role="actor-visible",
                    source_fields=("candidate_diagnostics/normalized_radius", "target_distance_m"),
                ),
            )

        orientation_fields = {
            "rig_target_yaw_error_deg",
            "target_elevation_deg",
        }
        if orientation_fields.intersection(candidates.columns):
            frame_fields = [name for name in orientation_fields if name in candidates]
            orientation = candidates[frame_fields].copy()
            orientation["step_index"] = candidates.get("step_index", pd.Series(index=candidates.index))
            orientation["diagnostic"] = "candidate orientation"
            orientation = orientation.melt(
                id_vars=["step_index", "diagnostic"], var_name="source", value_name="angle_deg"
            ).dropna(subset=["angle_deg"])
            if not orientation.empty:
                _render_plot(
                    _orientation_diagnostic_figure(orientation),
                    ScientificExplanation(
                        question="Are candidate and target-facing orientations consistent with the persisted frame?",
                        population="Bounded finite candidate orientation diagnostics by factual step.",
                        metric="Yaw/elevation diagnostic angles in degrees.",
                        denominator_masks="Finite persisted orientation fields; absent fields are not imputed.",
                        comparability="Use the same pose convention and target-facing contract across stores.",
                        expected_pattern="Errors remain within configured orientation envelopes.",
                        failure_interpretation="Systematic offsets indicate frame or target-pose inconsistencies.",
                        evidence_role="actor-visible",
                        source_fields=tuple(f"candidate_diagnostics/{name}" for name in frame_fields),
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
                        source_fields=(
                            "candidates/target_root_gain",
                            "candidates/selected_mask",
                            "candidates/position_id",
                        ),
                    ),
                )
