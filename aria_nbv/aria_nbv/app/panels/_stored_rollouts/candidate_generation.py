"""Candidate-generation provenance and aggregate evidence presentation."""

from __future__ import annotations

from collections import Counter
from itertools import pairwise

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from ....rollouts.inspection import (
    CANDIDATE_GROUP_FIELDS,
    candidate_selection_pooled_summary_rows,
    candidate_selection_transition_rows,
    pairwise_finite_pearson,
)
from ....utils.data_plotting import add_pose_axes_to_figure, configure_3d_scene
from ...scientific_labels import TheoryReferences
from ..common import current_scientific_label, render_scientific_notation
from .shared import ExplanationSection, ScientificExplanation
from .shared import download_frame as _download_frame
from .shared import render_plot as _render_plot

_CANDIDATE_POPULATIONS = ("Selected step", "Selected rollout", "Explicit full store")
_CORRELATION_REFERENCE = (
    "SciPy Pearson correlation documentation",
    "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.pearsonr.html",
)


def _pooled_candidate_selection_figure(summary: pd.DataFrame) -> go.Figure:
    """Plot the selected pooled quantity with auditable support context."""

    figure = go.Figure()
    metric = str(summary["metric"].iloc[0]) if "metric" in summary and not summary.empty else "fraction"
    metric_labels = {
        "allocation_share": "candidate availability",
        "valid_share": "actor-valid support",
        "policy_mass": "policy mass",
        "selected_share": "realized selection",
    }
    metric_label = metric_labels.get(metric, metric)
    context_fields = [
        field
        for field in ("state_count", "finite_state_count", "missing_state_count", "numerator", "denominator")
        if field in summary
    ]
    for family, rows in summary.sort_values("step_index").groupby("family", sort=True):
        customdata = rows[context_fields].to_numpy() if context_fields else None
        hover_lines = ["family=%{fullData.name}", "acquisition=%{x}", f"{metric_label}=%{{y:.3f}}"]
        if context_fields:
            hover_lines.extend(f"{field}=%{{customdata[{index}]}}" for index, field in enumerate(context_fields))
        figure.add_trace(
            go.Scatter(
                x=rows["step_index"].astype(int) + 1,
                y=rows["fraction"],
                mode="lines+markers",
                name=str(family),
                customdata=customdata,
                hovertemplate="<br>".join(hover_lines) + "<extra></extra>",
            )
        )
    figure.update_layout(xaxis_title="acquisition number", yaxis_title=metric_label)
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
    context = (
        rows.pivot(index="previous_family", columns="next_family", values="context_count").reindex(
            index=families, columns=families
        )
        if "context_count" in rows
        else pd.DataFrame(0, index=families, columns=families)
    )
    customdata = context.fillna(0).to_numpy()
    figure = make_subplots(rows=1, cols=2, subplot_titles=("Expected policy mass", "Realized transition rate"))
    for column, values, name in ((1, expected, "expected"), (2, realized, "realized")):
        figure.add_trace(
            go.Heatmap(
                z=values.to_numpy(),
                x=families,
                y=families,
                zmin=0,
                zmax=1,
                name=name,
                customdata=customdata,
                hovertemplate="previous=%{y}<br>next=%{x}<br>fraction=%{z:.3f}<br>context_count=%{customdata}<extra></extra>",
            ),
            row=1,
            col=column,
        )
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
    """Add root/target anchors and optional RGB pose triads in one frame."""

    if three_dimensional:
        figure.add_trace(
            go.Scatter3d(
                x=[0],
                y=[0],
                z=[0],
                mode="markers",
                name="Reference pose (all at origin)",
                marker={"symbol": "cross", "color": "white"},
            )
        )
        target_x = frames.get("target_x", pd.Series(dtype=float)).dropna()
        target_y = frames.get("target_y", pd.Series(dtype=float)).dropna()
        target_z = frames.get("target_z", pd.Series(dtype=float)).dropna()
        figure.add_trace(
            go.Scatter3d(
                x=target_x,
                y=target_y,
                z=target_z,
                mode="markers",
                name="Observed target center",
                marker={"symbol": "diamond", "color": "gold"},
            )
        )
        axis_frames = _pose_axis_frames(frames, mode="All frames") if not axis_frames.empty else axis_frames
        for prefix, label, centers in (
            ("reference_axis", "Expansion-pose axes", np.zeros((len(axis_frames), 3))),
            (
                "target_axis",
                "Target-pose axes",
                np.column_stack(
                    [
                        axis_frames.get("target_x", pd.Series(0.0, index=axis_frames.index)),
                        axis_frames.get("target_y", pd.Series(0.0, index=axis_frames.index)),
                        axis_frames.get("target_z", pd.Series(0.0, index=axis_frames.index)),
                    ]
                ),
            ),
        ):
            axis_columns = [f"{prefix}_{axis}" for axis in ("x", "y", "z")]
            if axis_frames.empty or not set(axis_columns).issubset(axis_frames.columns):
                continue
            try:
                axes = axis_frames.loc[:, axis_columns].to_numpy(dtype=float).reshape(-1, 3, 3)
            except (TypeError, ValueError):
                # Malformed persisted axis payloads must not hide the bounded
                # point projection; omit only the optional triad overlay.
                continue
            add_pose_axes_to_figure(figure, centers, axes, title=label, scale=0.12, line_width=4)


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


def _trajectory_figure(points: pd.DataFrame, frames: pd.DataFrame) -> go.Figure:
    """Plot only the factual root and selected-pose path in target-normalized coordinates."""

    figure = go.Figure()
    for rollout_id, rows in points.sort_values("path_order").groupby("rollout_row_id", sort=True):
        figure.add_trace(
            go.Scatter3d(
                x=rows["x"],
                y=rows["y"],
                z=rows["z"],
                mode="lines+markers",
                name=f"rollout {rollout_id}",
                customdata=rows[[c for c in ("step_index", "path_order") if c in rows]],
                hovertemplate="rollout=%{fullData.name}<br>step=%{customdata[0]}<br>(x,y,z)=(%{x:.3f}, %{y:.3f}, %{z:.3f})<extra></extra>",
            )
        )
    _add_geometry_anchors(figure, frames, three_dimensional=True, axis_frames=frames)
    configure_3d_scene(
        figure,
        axis_titles=("target-forward / d₀", "target-lateral / d₀", "up / d₀"),
        title="Factual root and selected trajectory",
    )
    return figure


def _prepare_pairwise_correlation(frame: pd.DataFrame, columns: list[str]) -> dict[str, object]:
    """Adapt the typed domain reducer to the Streamlit dataframe surface."""

    result = pairwise_finite_pearson(
        {column: pd.to_numeric(frame[column], errors="coerce").to_numpy() for column in columns},
        columns,
    )
    return {
        "correlation": pd.DataFrame(result.correlation, index=columns, columns=columns),
        "counts": pd.DataFrame(result.counts, index=columns, columns=columns),
        "reasons": result.reasons,
        "has_finite_off_diagonal": result.has_finite_off_diagonal,
    }


def _select_candidate_choice_controls(
    dynamics: pd.DataFrame, *, group_by: str
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Select only exact compatibility controls before pooling temperatures.

    Temperature and generation cohort are deliberately absent: pooling across
    those dimensions is the purpose of the pooled candidate-choice view.
    """

    selected_controls: dict[str, object] = {}
    control_fields = (
        "contract_id",
        "contract",
        "profile",
        "policy",
        "horizon",
        "branch_factor",
        "beam_width",
    )
    for field in control_fields:
        if field not in dynamics:
            continue
        values = sorted(dynamics[field].dropna().unique().tolist(), key=str)
        if len(values) <= 1:
            continue
        choice = st.selectbox(
            f"Candidate-choice {field}",
            options=values,
            format_func=str,
            key=f"candidate-choice-{group_by}-{field}",
        )
        if choice not in values:
            choice = values[0]
        selected_controls[field] = choice
        dynamics = dynamics.loc[dynamics[field].eq(choice)]
    return dynamics, selected_controls


def _render_candidate_population_evidence(session_handle: object) -> None:
    """Render complete candidate aggregates and a deterministic display-only sample."""

    st.markdown("#### Complete candidate-family lineage and choice")
    st.caption(
        "This explicit complete-store action keeps exact persisted contract controls fixed, pools compatible "
        "temperatures, and compares allocation, valid support, policy mass, realized selection, and adjacent-family transitions."
    )
    group_by = st.selectbox("Candidate evidence grouping", options=list(CANDIDATE_GROUP_FIELDS))
    population = session_handle.candidate_population()
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
        available_groups = [
            str(group) for group, value in selection_dynamics.items() if isinstance(value, list) and value
        ]
        dynamics = pd.DataFrame()
        if available_groups:
            group_by = st.selectbox(
                "Candidate-choice vocabulary",
                options=available_groups,
                index=available_groups.index("position_strategy") if "position_strategy" in available_groups else 0,
                key="candidate-choice-group-vocabulary",
                help="Select the exact persisted family vocabulary; policies, temperatures, and rollout contracts are not pooled.",
            )
            dynamics = pd.DataFrame(selection_dynamics[group_by])
            dynamics, selected_controls = _select_candidate_choice_controls(dynamics, group_by=group_by)
        if not dynamics.empty:
            quantity_options = ("allocation_share", "valid_share", "policy_mass", "selected_share")
            selection_metric = st.selectbox(
                "Per-step quantity",
                options=quantity_options,
                index=2,
                format_func={
                    "allocation_share": "Candidate availability",
                    "valid_share": "Actor-valid support",
                    "policy_mass": "Policy mass",
                    "selected_share": "Realized selection",
                }.get,
                help=(
                    "Availability uses the full candidate shell; actor-valid support uses actor-valid rows; "
                    "policy mass is the mean persisted probability; realized selection is the selected-family fraction."
                ),
            )
            if selection_metric not in quantity_options:
                selection_metric = "policy_mass"
            pooled = pd.DataFrame(
                candidate_selection_pooled_summary_rows(dynamics.to_dict("records"), metric=selection_metric)
            )
            if not pooled.empty:
                _render_plot(
                    _pooled_candidate_selection_figure(pooled),
                    _candidate_population_explanation(
                        "How does candidate-family choice evolve across factual acquisition?",
                        "Complete candidate-choice dynamics from compatible factual states.",
                        {
                            "allocation_share": "Candidate availability per family and acquisition; fraction of the full shell.",
                            "valid_share": "Actor-valid support per family and acquisition; fraction of actor-valid rows.",
                            "policy_mass": "Policy mass per family and acquisition; dimensionless fraction.",
                            "selected_share": "Realized selected-family fraction per acquisition; dimensionless.",
                        }[selection_metric],
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
                    depths = sorted(transitions["step_index"].dropna().astype(int).unique().tolist())
                    depth = st.selectbox(
                        "Candidate-choice transition depth",
                        options=depths,
                        format_func=lambda value: f"{value} → {value + 1}",
                        key=f"candidate-choice-transition-depth-{group_by}",
                    )
                    transitions = transitions.loc[transitions["step_index"].eq(depth)]
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
                with st.expander("Candidate-choice rows and CSV", expanded=False):
                    st.dataframe(pooled, hide_index=True, width="stretch")
                    _download_frame("Download candidate-choice CSV", "candidate-choice-dynamics.csv", pooled)

            sequence_rows = pd.DataFrame(population.get("selection_sequences", {}).get(group_by, []))
            return_rows = pd.DataFrame(population.get("sequence_returns", {}).get(group_by, []))
            for field, choice in selected_controls.items():
                if field in sequence_rows:
                    sequence_rows = sequence_rows.loc[sequence_rows[field].eq(choice)]
                if field in return_rows:
                    return_rows = return_rows.loc[return_rows[field].eq(choice)]
            if not sequence_rows.empty and not return_rows.empty:
                st.markdown("#### Selected-family sequences and terminal returns")
                st.caption(
                    "Sequences preserve factual rollout order. Terminal returns are descriptive root-normalized gains;"
                    " incomplete horizons remain visible and are not zero-filled."
                )
                finite_returns = return_rows.dropna(subset=["terminal_return_median"])
                if not finite_returns.empty:
                    _render_plot(
                        px.bar(
                            finite_returns,
                            x="sequence",
                            y="terminal_return_median",
                            error_y=(finite_returns["terminal_return_q75"] - finite_returns["terminal_return_median"]),
                            error_y_minus=(
                                finite_returns["terminal_return_median"] - finite_returns["terminal_return_q25"]
                            ),
                            title="Terminal target-root gain by selected-family sequence",
                        ),
                        _candidate_population_explanation(
                            "Which selected-family sequences produce the observed terminal return distribution?",
                            "One factual selected-family sequence per rollout in the exact compatible facet.",
                            "Median terminal target-root gain with interquartile range; units are fraction.",
                            "Finite terminal gains only; incomplete horizons remain counted separately.",
                            "Repeated sequences should show descriptive spread rather than a fabricated continuous path.",
                            "Small counts or wide IQRs require raw sequence inspection and are not causal policy effects.",
                            "inspection.candidate_population_evidence.sequence_returns",
                            evidence_role or "provenance",
                        ),
                    )
                with st.expander("Selected-family sequence rows and CSV", expanded=False):
                    st.dataframe(return_rows, hide_index=True, width="stretch")
                    _download_frame(
                        "Download selected-family sequence CSV", "selected-family-sequences.csv", sequence_rows
                    )

    with st.expander("Candidate choice rows, aggregate tables, and CSV", expanded=False):
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


_CANDIDATE_POPULATION_ANSWERS = {
    "How does candidate-family choice evolve across factual acquisition?": "The traces separate available family support, actor-valid support, policy probability mass, and realized selections by factual acquisition.",
    "How does the previously selected family relate to the next family?": "The heatmaps compare expected policy mass with realized next-family frequency for the same adjacent factual contexts.",
    "Which selected-family sequences produce the observed terminal return distribution?": "The grouped distributions connect complete selected-family sequences to their observed terminal target-root gains.",
    "Does candidate direction support cover solid angle without coordinate-latitude bias?": "The equal-area direction bins show where the complete candidate shell supplies angular support without overweighting the poles.",
    "How far does the observed direction distribution depart from an isotropic reference?": "The distance summarizes how far observed normalized directions depart from the uniform-sphere reference at each factual state.",
    "Do sampled directions cover the sphere locally and globally?": "Nearest-neighbor separation and covering radius expose local gaps and the largest uncovered angular region in the sampled support.",
    "How often do evaluated candidates collide, at population and state-macro levels?": "The paired summaries distinguish candidate-weighted collision frequency from the equal-weight state macro, preserving both denominators.",
    "How much geometric clearance is observed for the candidate population?": "The summaries report finite path clearance for the full candidate population and separately for state-level macros.",
    "How much of the candidate shell is represented by collision and clearance evidence?": "The additive counts show which portions of the candidate shell were evaluated, collision-labelled, and assigned finite clearance.",
    "What finite target distance is represented in the selected target-view population?": "The bars show the finite target-distance scale represented in the selected target-view population, separate from optical availability.",
    "Which optical and visibility measurements are actually persisted?": "The grouped counts show which optical and visibility measurements are finite or missing, without treating absence as a zero-valued measurement.",
}


def _candidate_population_explanation(
    question: str,
    population_text: str,
    metric_text: str,
    denominator_text: str,
    expected_text: str,
    warning_text: str,
    source: str,
    role: str,
    theory: TheoryReferences | None = None,
    external_references: tuple[tuple[str, str], ...] = (),
) -> ScientificExplanation:
    """Build consistent scientific context for complete candidate-support plots."""

    return ScientificExplanation(
        question=question,
        answer=_CANDIDATE_POPULATION_ANSWERS.get(
            question,
            f"Complete persisted candidate evidence is used to answer: {question}",
        ),
        sections=(
            ExplanationSection("Population / grain", population_text),
            ExplanationSection("Metric / units", metric_text),
            ExplanationSection("Denominator / masks", denominator_text),
            ExplanationSection(
                "comparability", "Compare only matching persisted candidate contracts and generation cohorts."
            ),
            ExplanationSection("Expected pattern", expected_text),
            ExplanationSection("Warnings / failure modes", warning_text),
        ),
        evidence_role=role,
        source_fields=(source,),
        theory=theory,
        external_references=external_references,
    )


def _support_count_caption(frame: pd.DataFrame) -> None:
    """Show additive support denominators for the currently selected facet."""

    labels = {
        "candidate_total_count": "candidates",
        "candidate_count": "candidates",
        "candidate_finite_count": "finite candidates",
        "candidate_missing_count": "missing/unavailable candidates",
        "state_count": "states",
        "defined_state_count": "defined states",
        "scene_count": "scenes",
    }
    values: list[str] = []
    for field, label in labels.items():
        if field in frame and not frame[field].dropna().empty:
            value = frame[field].max()
            values.append(f"{label}={int(value):,}")
    if values:
        st.caption("Selected support facet: " + ", ".join(values) + ".")


def _require_family_cohort_columns(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    """Fail closed when a family plot lacks its persisted cohort identity."""

    required = {"family", "generation_cohort_id"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        st.warning(
            f"{label} unavailable: complete candidate composition must provide "
            f"{', '.join(sorted(required))}; missing {', '.join(missing)}."
        )
        return frame.iloc[0:0].copy()
    return frame


def _render_complete_candidate_support(population: dict[str, object], *, evidence_role: str) -> None:
    """Render PR101 support facets through the decomposed candidate owner."""

    direction = population.get("direction", {})
    if isinstance(direction, dict):
        density = pd.DataFrame(direction.get("density_rows", []))
        if not density.empty:
            selected = _select_support_facet(density, "Direction support")
            if not selected.empty:
                _support_count_caption(selected)
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
                        TheoryReferences(
                            equation_ids=("action.angle_cap_transform",),
                            term_ids=("finite-candidate-action-set",),
                        ),
                    ),
                )
                with st.expander("Direction support rows and CSV"):
                    st.dataframe(selected, hide_index=True, width="stretch")
                    _download_frame("Download direction support CSV", "candidate-direction-support.csv", selected)
        cap = pd.DataFrame(direction.get("cap_rows", []))
        if not cap.empty and "discrepancy" in cap:
            cap = _select_support_facet(cap, "Direction isotropy")
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
        angular = pd.DataFrame(direction.get("angular_support_rows", []))
        if not angular.empty:
            angular = _select_support_facet(angular, "Angular support")
            value_columns = [name for name in ("nearest_neighbor_deg", "covering_radius_deg") if name in angular]
            if value_columns:
                angular_plot = angular.melt(
                    id_vars=[name for name in ("metric", "population") if name in angular],
                    value_vars=value_columns,
                    var_name="support_metric",
                    value_name="degrees",
                ).dropna(subset=["degrees"])
                if not angular_plot.empty:
                    _render_plot(
                        px.bar(
                            angular_plot,
                            x="support_metric",
                            y="degrees",
                            color="population" if "population" in angular_plot else None,
                            title="Angular nearest-neighbor and covering support",
                        ),
                        _candidate_population_explanation(
                            "Do sampled directions cover the sphere locally and globally?",
                            "Complete direction-support summaries for the selected exact facet.",
                            "Mean nearest-neighbor separation and probe covering radius in degrees.",
                            "Finite normalized directions; singleton states report unavailable nearest-neighbor support.",
                            "Small nearest-neighbor gaps and bounded covering radius indicate broad angular support.",
                            "Large gaps or unavailable values expose sparse direction generation or missing geometry.",
                            "inspection.candidate_direction_evidence.angular_support_rows",
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
        selected = _select_metric_unit(selected, title)
        if selected.empty:
            continue
        _support_count_caption(selected)
        fig = px.bar(
            selected,
            x="metric",
            y=value,
            color="population" if "population" in selected else None,
            facet_row="declared_shell" if key == "spatial" and "declared_shell" in selected else None,
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

    collision = pd.DataFrame(population.get("collision", []))
    if not collision.empty:
        collision = _select_support_facet(collision, "Collision support")
        _support_count_caption(collision)
        rate_rows = collision.melt(
            id_vars=[field for field in ("generation_cohort_id", "generation_cohort") if field in collision],
            value_vars=[field for field in ("population_collision_rate", "collision_rate") if field in collision],
            var_name="population",
            value_name="fraction",
        ).dropna(subset=["fraction"])
        if not rate_rows.empty:
            _render_plot(
                px.bar(
                    rate_rows,
                    x="generation_cohort_id",
                    y="fraction",
                    color="population",
                    barmode="group",
                    title="Collision rates: candidate population and state macro",
                    labels={"fraction": "collision rate [fraction]"},
                ),
                _candidate_population_explanation(
                    "How often do evaluated candidates collide, at population and state-macro levels?",
                    "Collision rates are shown separately for the complete candidate population and the state-then-scene macro.",
                    "Collision rate is a dimensionless fraction of explicitly evaluated candidates.",
                    "The population denominator is collision_evaluated_count; the macro averages finite state rates.",
                    "The two estimates agree when candidate fan-out is balanced across states.",
                    "A zero rate is a valid result; missing evaluation is not silently treated as no collision.",
                    "inspection.candidate_motion_support_evidence.collision",
                    evidence_role,
                    external_references=(
                        (
                            "Candidate inspection contract",
                            "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/aria_nbv/aria_nbv/rollouts/inspection.py",
                        ),
                    ),
                ),
            )
        clearance_rows = collision.melt(
            id_vars=[field for field in ("generation_cohort_id", "generation_cohort") if field in collision],
            value_vars=[field for field in ("population_clearance_mean_m", "clearance_mean_m") if field in collision],
            var_name="population",
            value_name="clearance_m",
        ).dropna(subset=["clearance_m"])
        if not clearance_rows.empty:
            _render_plot(
                px.bar(
                    clearance_rows,
                    x="generation_cohort_id",
                    y="clearance_m",
                    color="population",
                    barmode="group",
                    title="Clearance means: candidate population and state macro",
                    labels={"clearance_m": "minimum path clearance [m]"},
                ),
                _candidate_population_explanation(
                    "How much geometric clearance is observed for the candidate population?",
                    "Population and state-macro clearance means remain separate because they answer different weighting questions.",
                    "Mean minimum path clearance in metres; collision and clearance are not the same metric.",
                    "Only finite path_min_clearance_m values enter the population denominator or state macro.",
                    "Positive clearance indicates separation from the evaluated obstacle boundary.",
                    "Missing clearance means unavailable evaluation, not zero clearance.",
                    "inspection.candidate_motion_support_evidence.collision",
                    evidence_role,
                    external_references=(
                        (
                            "Candidate inspection contract",
                            "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/aria_nbv/aria_nbv/rollouts/inspection.py",
                        ),
                    ),
                ),
            )
        count_fields = (
            "collision_available_count",
            "collision_evaluated_count",
            "collision_not_applicable_count",
            "collision_unavailable_count",
            "collision_count",
            "clearance_finite_count",
            "collision_denominator",
            "clearance_denominator",
        )
        count_rows = (
            collision[[field for field in count_fields if field in collision]].sum().rename("count").reset_index()
        )
        count_rows.columns = ["metric", "count"]
        if not count_rows.empty:
            _render_plot(
                px.bar(
                    count_rows,
                    x="metric",
                    y="count",
                    title="Collision and clearance applicability denominators",
                    labels={"count": "candidate evidence rows [count]"},
                ),
                _candidate_population_explanation(
                    "How much of the candidate shell is represented by collision and clearance evidence?",
                    "Only explicit applicability, evaluation, collision, and finite-clearance denominator counts are shown.",
                    "Counts of additive candidate evidence rows; zero collision is a valid measured count, while unavailable evidence remains separate.",
                    "The eight displayed fields are additive denominators or outcomes and are never inferred from status flags.",
                    "Evaluated and finite-clearance counts make the scientific rates auditable.",
                    "A small denominator limits interpretation even when the observed collision count is zero.",
                    "inspection.candidate_motion_support_evidence.collision",
                    evidence_role,
                    external_references=(
                        (
                            "Candidate inspection contract",
                            "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/aria_nbv/aria_nbv/rollouts/inspection.py",
                        ),
                    ),
                ),
            )
            with st.expander("Collision and clearance denominator rows", expanded=False):
                st.dataframe(count_rows, hide_index=True, width="stretch")
                _download_frame(
                    "Download collision denominator CSV", "candidate-collision-denominators.csv", count_rows
                )

    target_view = pd.DataFrame(population.get("target_view", []))
    if evidence_role in {"actor-visible", "oracle/evaluation"} and not target_view.empty and "evidence" in target_view:
        target_view = _select_support_facet(target_view, "Target-view support")
        _support_count_caption(target_view)
        distance = target_view.loc[target_view["evidence"].eq("target_distance")].copy()
        if not distance.empty and "mean" in distance:
            fig = px.bar(
                distance.dropna(subset=["mean"]),
                x="population" if "population" in distance else "aggregation_level",
                y="mean",
                color="aggregation_level" if "aggregation_level" in distance else None,
                title="Finite target distance by target-view population",
                labels={"mean": "target distance [m]"},
            )
            _render_plot(
                fig,
                _candidate_population_explanation(
                    "What finite target distance is represented in the selected target-view population?",
                    "Only persisted finite target-distance measurements are plotted; optical and line-of-sight evidence remains a separate availability diagnostic.",
                    "Mean target distance is measured in metres; missing target distances are not imputed.",
                    "The denominator is the selected factual candidate state facet after exact contract/cohort filters.",
                    "Target distance describes geometric scale, not visibility or admission quality.",
                    "Large missingness or absent optical evidence indicates evaluator coverage gaps.",
                    "inspection.candidate_target_view_evidence",
                    evidence_role,
                    TheoryReferences(term_ids=("target-of-interest",)),
                ),
            )
        availability = target_view.loc[target_view["evidence"].ne("target_distance")].copy()
        if not availability.empty:
            availability_rows = availability.melt(
                id_vars=[field for field in ("evidence", "population") if field in availability],
                value_vars=[field for field in ("finite_count", "missing_count") if field in availability],
                var_name="availability_count",
                # The reducer also persists the total candidate ``count``.
                # Keep the melted value distinct from that source column;
                # pandas rejects a melt whose value_name already exists.
                value_name="availability_value",
            )
            if not availability_rows.empty:
                _render_plot(
                    px.bar(
                        availability_rows,
                        x="evidence",
                        y="availability_value",
                        color="availability_count",
                        barmode="group",
                        title="Target-view availability and missingness",
                        labels={"availability_value": "candidate evidence rows [count]"},
                    ),
                    _candidate_population_explanation(
                        "Which optical and visibility measurements are actually persisted?",
                        "Availability counts are shown separately from metric-valued target distance.",
                        "Counts of finite and missing candidate-state evidence rows; no boolean status is treated as a measurement.",
                        "Each evidence category keeps its own candidate-state denominator.",
                        "Unavailable FOV, pixel, or line-of-sight rows remain explicit rather than becoming zeros.",
                        "Missing optical evidence limits interpretation of visibility, not geometric target distance.",
                        "inspection.candidate_target_view_evidence",
                        evidence_role,
                    ),
                )
        with st.expander("Target-view evidence rows and CSV", expanded=False):
            st.dataframe(target_view, hide_index=True, width="stretch")
            _download_frame("Download target-view support CSV", "candidate-target-view-support.csv", target_view)


def _select_support_facet(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    """Select one exact persisted support facet before rendering a plot."""

    selected = frame.copy()
    # These are factual support keys, not display conveniences.  A plot must
    # never silently pool distinct scene/state populations or generation
    # contracts before the user has selected the exact persisted facet.
    for field in (
        "contract_id",
        "generation_cohort_id",
        "population",
        "aggregation_level",
        "scene",
        "scene_id",
        "rollout_row_id",
        "step_row_id",
        "step_index",
        "grain",
    ):
        if field not in selected.columns:
            continue
        values = sorted(selected[field].dropna().astype(str).unique())
        if len(values) <= 1:
            continue
        default = "cohort_macro" if field == "aggregation_level" and "cohort_macro" in values else values[0]
        choice = st.selectbox(f"{label}: {field}", values, index=values.index(default), key=f"support-{label}-{field}")
        selected = selected[selected[field].astype(str).eq(str(choice))]
    return selected


def _select_metric_unit(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    """Keep one metric/unit family on a single quantitative axis."""

    selected = frame.copy()
    if "metric" in selected.columns:
        metrics = sorted(selected["metric"].dropna().astype(str).unique())
        if len(metrics) > 1:
            metric = st.selectbox(
                f"{label}: metric",
                metrics,
                key=f"support-metric-{label.lower().replace(' ', '-')}",
            )
            selected = selected.loc[selected["metric"].astype(str).eq(str(metric))]
    if "units" in selected.columns:
        units = sorted(selected["units"].dropna().astype(str).unique())
        if len(units) > 1:
            unit = st.selectbox(
                f"{label}: units",
                units,
                key=f"support-units-{label.lower().replace(' ', '-')}",
            )
            selected = selected.loc[selected["units"].astype(str).eq(str(unit))]
    return selected


def _render_candidate_provenance_flow(session_handle: object) -> None:
    """Render the lightweight complete-population candidate provenance flow."""

    store_candidate_count = int(session_handle.validation.num_candidates)
    steps = pd.DataFrame(session_handle.steps())
    policy_options = sorted(str(value) for value in steps.get("policy", pd.Series(dtype=str)).dropna().unique())
    depth_options = sorted(int(value) for value in steps.get("step_index", pd.Series(dtype=int)).dropna().unique())
    col_policy, col_depth = st.columns(2)
    selected_policies = col_policy.multiselect("Flow policies", options=policy_options, default=policy_options)
    selected_depths = col_depth.multiselect("Flow rollout depths", options=depth_options, default=depth_options)
    flow = pd.DataFrame(
        session_handle.candidate_flow(
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
                    "population",
                    "Every candidate row matching the visible policy/depth filters, including actor-valid and actor-invalid rows, aggregated through proposal signature, actor validity, and outcome.",
                ),
                ExplanationSection(
                    "metric",
                    "Candidate count and fraction of the filtered root population; no reward or geometric units.",
                ),
                ExplanationSection(
                    "denominator masks",
                    "The filtered complete candidate population is the root denominator. Actor validity is a hard action constraint; selected actor-invalid rows remain explicit selection_contract_violation evidence.",
                ),
                ExplanationSection(
                    "comparability",
                    "Candidate proposal signatures, budgets, and active policy/depth filters must match.",
                ),
                ExplanationSection(
                    "expected pattern",
                    "Intended center/view proposal signatures retain actor-valid support, while invalid rows terminate at explicit reasons and selected rows remain actor-valid.",
                ),
                ExplanationSection(
                    "failure interpretation",
                    "Unknown provenance indicates missing persisted labels; concentrated invalid reasons indicate support loss; selection_contract_violation is a hard invariant failure.",
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
        ),
    )
    st.dataframe(flow, hide_index=True, width="stretch")
    _download_frame("Download candidate provenance flow CSV", "candidate-provenance-flow.csv", flow)

    ranks = pd.DataFrame(
        session_handle.ranks(
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
                        "population", "One persisted selected rollout step matching the active policy/depth filters."
                    ),
                    ExplanationSection(
                        "metric",
                        "Selected-step count and target-RRI competition rank among finite actor-valid candidates.",
                    ),
                    ExplanationSection(
                        "denominator masks",
                        "The root denominator is selected rollout steps. Target-RRI rank excludes actor-invalid and non-finite alternatives; unavailable ranks remain explicit.",
                    ),
                    ExplanationSection(
                        "comparability",
                        "Compare policies only under matched roots, targets, candidate proposals, acquisition budgets, and score semantics.",
                    ),
                    ExplanationSection(
                        "expected pattern",
                        "Temperature-softmax covers more than rank one without collapsing to uniformly poor target-RRI ranks; greedy policies concentrate near the top.",
                    ),
                    ExplanationSection(
                        "failure interpretation",
                        "Unavailable ranks indicate missing oracle diagnostics; high-rank concentration can indicate excessive temperature or score/RRI mismatch.",
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


def _render_candidate_aggregate_breakdowns(session_handle: object) -> None:
    """Render restored complete-store candidate audit plots on demand."""

    population = session_handle.candidate_population()
    composition_by_group = population.get("composition", {})
    families = _require_family_cohort_columns(
        pd.DataFrame(composition_by_group.get("position", [])), "Candidate-family breakdown"
    )
    if not families.empty:
        family_field = "family"
        cohort_field = "generation_cohort_id"
        families["selection_rate_given_available"] = np.where(
            families["actor_valid_count"] > 0,
            families["selected_count"] / families["actor_valid_count"],
            np.nan,
        )
        long = families.melt(
            id_vars=[field for field in (family_field, cohort_field) if field is not None],
            value_vars=["macro_actor_valid_rate", "selection_rate_given_available"],
            var_name="metric",
            value_name="fraction",
        )
        fig = px.bar(
            long,
            x=family_field,
            y="fraction",
            color="metric",
            facet_col=cohort_field,
            barmode="group",
            title="Candidate-family availability and normalized selection",
        )
        _render_plot(
            fig,
            ScientificExplanation(
                question="Is a candidate family selected because it is useful, or merely because it is frequently available?",
                answer="The paired bars separate a family's opportunity to be chosen from the rate at which it is chosen when that opportunity exists.",
                sections=(
                    ExplanationSection("population", "Candidate rows grouped by root-relative position family."),
                    ExplanationSection(
                        "metric",
                        "Actor-valid fraction of sampled rows and selected/actor-valid rate; both dimensionless fractions.",
                    ),
                    ExplanationSection(
                        "denominator masks",
                        "Availability uses the full family shell; selection rate uses actor-valid family rows only.",
                    ),
                    ExplanationSection(
                        "comparability", "Family names, mixture weights, and branch budgets must match across stores."
                    ),
                    ExplanationSection(
                        "expected pattern",
                        "Useful families retain availability and non-degenerate normalized selection without monopolizing support.",
                    ),
                    ExplanationSection(
                        "failure interpretation",
                        "High raw selection with tiny availability can be unstable; zero availability is a generator/mask clue.",
                    ),
                ),
                evidence_role="actor-visible",
                source_fields=("candidate position_id", "actor_action_mask", "selected_mask"),
                theory=TheoryReferences(symbol_ids=("rl.validity_mask",), term_ids=("validity-mask",)),
                external_references=(
                    (
                        "Candidate inspection contract",
                        "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/aria_nbv/aria_nbv/rollouts/inspection.py",
                    ),
                ),
            ),
        )
        _download_frame("Download family support CSV", "candidate-family-support.csv", families)

    breakdown_by = st.selectbox(
        "Candidate aggregate breakdown",
        options=list(CANDIDATE_GROUP_FIELDS),
        help="Switches one complete-store aggregate plot without rebuilding the candidate audit.",
    )
    breakdown = _require_family_cohort_columns(
        pd.DataFrame(composition_by_group.get(breakdown_by, [])), "Candidate mask-population breakdown"
    )
    count_fields = [name for name in ("actor_valid_count", "trainable_count", "selected_count") if name in breakdown]
    if not breakdown.empty and count_fields:
        family_field = "family"
        cohort_field = "generation_cohort_id"
        long = breakdown.melt(
            id_vars=[field for field in (family_field, cohort_field) if field is not None],
            value_vars=count_fields,
            var_name="mask_population",
            value_name="count",
        )
        fig = px.bar(
            long,
            x=family_field,
            y="count",
            color="mask_population",
            facet_col=cohort_field,
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
                        "population", f"Complete-store candidate rows grouped by persisted {breakdown_by} provenance."
                    ),
                    ExplanationSection("metric", "Candidate count in each explicitly named mask population."),
                    ExplanationSection(
                        "denominator masks",
                        "Actor-valid, q_train, and selected are overlapping sets, not sequential waterfall stages.",
                    ),
                    ExplanationSection(
                        "comparability", "Candidate protocol, group vocabulary, and store schema must match."
                    ),
                    ExplanationSection(
                        "expected pattern",
                        "Trainable support is no larger than label availability permits, and selection stays within actor support.",
                    ),
                    ExplanationSection(
                        "failure interpretation",
                        "Missing groups, selected-only spikes, or large actor/train gaps identify generator, mask, or label-cache issues.",
                    ),
                ),
                evidence_role="derived training data",
                source_fields=(
                    "inspection.candidate_group_summary_rows",
                    f"candidate {breakdown_by}",
                    "candidate masks",
                ),
                theory=TheoryReferences(symbol_ids=("rl.validity_mask",), term_ids=("validity-mask",)),
                external_references=(
                    (
                        "Candidate inspection contract",
                        "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/aria_nbv/aria_nbv/rollouts/inspection.py",
                    ),
                ),
            ),
        )

    with st.expander("Invalid reasons and valid fanout", expanded=False):
        invalid = pd.DataFrame(composition_by_group.get("invalid_reason", []))
        fanout = pd.DataFrame(session_handle.steps())
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
                        ExplanationSection("population", "One target proposal with finite rank and selection score."),
                        ExplanationSection(
                            "metric",
                            "Selection rank is ordinal; selection score is a dimensionless configured composite.",
                        ),
                        ExplanationSection(
                            "denominator masks",
                            "All scored target proposals, including actor-invalid and GT-invalid rows.",
                        ),
                        ExplanationSection(
                            "comparability",
                            "Target-selection weights, proposal source, and GT-matching protocol must match.",
                        ),
                        ExplanationSection(
                            "expected pattern",
                            "Higher-priority ranks follow higher scores while validity classes remain visibly distinct.",
                        ),
                        ExplanationSection(
                            "failure interpretation",
                            "Rank inversions, score ties, or high-scoring invalid targets indicate selection or matching problems.",
                        ),
                    ),
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
                        answer="The scatter shows whether the selected support diagnostic contributes plausibly to the persisted target-selection score.",
                        sections=(
                            ExplanationSection(
                                "population", f"One target proposal with finite selection score and {support_field}."
                            ),
                            ExplanationSection(
                                "metric",
                                f"{support_field} and selection score are dimensionless configured diagnostics.",
                            ),
                            ExplanationSection(
                                "denominator masks",
                                "Scored target proposals; actor and GT validity remain explicit marks.",
                            ),
                            ExplanationSection(
                                "comparability",
                                "Support computation, crop geometry, score weights, and target source must match.",
                            ),
                            ExplanationSection(
                                "expected pattern",
                                "Support contributes monotonically without becoming the only determinant of score.",
                            ),
                            ExplanationSection(
                                "failure interpretation",
                                "High scores at negligible support or validity-separated clusters can reveal weighting or GT-association issues.",
                            ),
                        ),
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
        if len(component_cols) >= 2:
            prepared = _prepare_pairwise_correlation(targets, component_cols)
            corr = prepared["correlation"]
            counts = prepared["counts"]
            reasons = prepared["reasons"]
            if prepared["has_finite_off_diagonal"]:
                labels = [
                    [
                        "n/a"
                        if pd.isna(corr.iloc[row, col])
                        else f"r={corr.iloc[row, col]:.2f}, n={int(counts.iloc[row, col])}"
                        for col in range(len(component_cols))
                    ]
                    for row in range(len(component_cols))
                ]
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
                        text=labels,
                        texttemplate="%{text}",
                        customdata=np.stack([counts.to_numpy(), np.array(labels, dtype=object)], axis=-1),
                        hovertemplate="%{y} × %{x}<br>%{customdata[1]}<extra></extra>",
                    )
                )
                fig.update_layout(
                    title="Target score-component correlation (descriptive; pairwise n shown)", height=440
                )
                if any("n=2" in reason for reason in reasons.values()):
                    st.warning(
                        "Some correlation cells have n=2; Pearson |r| is algebraically forced to 1 and is not substantive evidence."
                    )
                _render_plot(
                    fig,
                    ScientificExplanation(
                        question="Which target-score components are redundant, opposed, or unexpectedly disconnected?",
                        answer="The heatmap is descriptive evidence of linear association between persisted score components, with pair-local support shown for every cell.",
                        sections=(
                            ExplanationSection(
                                "population",
                                "Pairwise-complete target proposals; each heatmap cell reports its own finite pair count.",
                            ),
                            ExplanationSection(
                                "metric",
                                "Pearson correlation coefficient, dimensionless in [-1, 1]; hover shows pair-local n.",
                            ),
                            ExplanationSection(
                                "denominator masks",
                                "Only rows finite for both components enter that pair; ±inf and missing values are excluded.",
                            ),
                            ExplanationSection(
                                "comparability",
                                "Only compare matrices from identical score definitions and target protocols.",
                            ),
                            ExplanationSection(
                                "expected pattern",
                                "Components reflect their intended roles without perfect accidental duplication.",
                            ),
                            ExplanationSection(
                                "failure interpretation",
                                "Near-perfect n=2 correlations are algebraically degenerate; sparse or unexpected signs need more evidence.",
                            ),
                        ),
                        evidence_role="oracle/evaluation",
                        source_fields=tuple(f"targets/{name}" for name in component_cols),
                        external_references=(_CORRELATION_REFERENCE,),
                    ),
                )
            else:
                reason_text = "; ".join(f"{pair}: {reason}" for pair, reason in reasons.items() if pair[0] != pair[1])
                st.info("Correlation heatmap unavailable: no estimable finite off-diagonal pair. " + reason_text)
        elif len(component_cols) == 1:
            st.info(
                "Correlation heatmap unavailable: one target-score component has finite observations; at least two components are required."
            )
        else:
            st.info("Correlation heatmap unavailable: no target-score components have finite observations.")


def _render_candidate_geometry_diagnostics(
    candidates: pd.DataFrame,
    root_geometry: pd.DataFrame | dict[str, object],
    trajectory_geometry: dict[str, object] | None = None,
    *,
    total_candidates: int,
) -> None:
    """Restore bounded candidate plots in scientifically valid root-relative coordinates."""

    proposal_frames = pd.DataFrame()
    if isinstance(root_geometry, dict):
        proposal_frames = pd.DataFrame(root_geometry.get("frames", []))
        root_geometry = pd.DataFrame(root_geometry.get("points", []))
    with st.expander("Candidate geometry, motion, angles, and reward support", expanded=True):
        st.caption(
            f"Interactive plots use {len(candidates):,} of {total_candidates:,} candidate rows. "
            "Proposal coordinates are target-distance-normalized (RIGHT_HAND_Z_UP), never pooled absolute scene origins; factual trajectories remain a separate projection."
        )
        axis_mode = "Hidden"
        axis_frame_id: str | None = None
        if "frame_id" in proposal_frames and not proposal_frames.empty:
            axis_mode = st.selectbox(
                "Proposal pose-axis overlay",
                options=("Hidden", "One frame", "All frames"),
                index=2,
                help="Pose triads are optional context overlays; the candidate points remain the primary projection.",
            )
            if axis_mode not in {"Hidden", "One frame", "All frames"}:
                # Streamlit's bare-mode fallback returns None; keep direct renderer tests deterministic.
                axis_mode = "All frames"
            if axis_mode == "One frame":
                axis_frame_id = st.selectbox("Proposal frame", options=proposal_frames["frame_id"].astype(str).tolist())
        proposal_axis_frames = (
            _pose_axis_frames(proposal_frames, mode=axis_mode, frame_id=axis_frame_id)
            if not proposal_frames.empty
            else proposal_frames
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
                        ExplanationSection("population", "Bounded candidate audit rows with a finite selected metric."),
                        ExplanationSection(
                            "metric",
                            f"{metric}; units follow the field suffix (`_m`, `_deg`) or are dimensionless for reward/RRI.",
                        ),
                        ExplanationSection(
                            "denominator masks",
                            "Finite metric rows; invalid reasons remain explicit rather than silently filtered.",
                        ),
                        ExplanationSection(
                            "comparability",
                            "Field definition, candidate protocol, and interactive row limit must match.",
                        ),
                        ExplanationSection(
                            "expected pattern",
                            "Support respects configured physical bounds and avoids unexplained clipping or spikes.",
                        ),
                        ExplanationSection(
                            "failure interpretation",
                            "Heavy tails, discontinuities, or invalidity-specific modes guide row-level debugging.",
                        ),
                    ),
                    evidence_role="oracle/evaluation"
                    if metric in {"target_root_gain", "target_rri"}
                    else "actor-visible",
                    source_fields=(f"candidate audit/{metric}", "candidates/invalid_reason_bitset"),
                ),
            )
        if not root_geometry.empty:
            x_column = "root_relative_x_m" if "root_relative_x_m" in root_geometry else "x"
            y_column = "root_relative_y_m" if "root_relative_y_m" in root_geometry else "y"
            z_column = "root_relative_z_m" if "root_relative_z_m" in root_geometry else "z"
            fig = px.scatter(
                root_geometry,
                x=x_column,
                y=y_column,
                color="position" if "position" in root_geometry else None,
                symbol="selected" if "selected" in root_geometry else None,
                hover_data=[
                    name
                    for name in ("rollout_row_id", "step_index", z_column, "actor_action", "mixture")
                    if name in root_geometry
                ],
                title="Candidate centers in the proposal expansion frame (ground plane)",
            )
            fig.update_layout(xaxis_title="target-forward / d", yaxis_title="target-lateral / d")
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
                    question="Do candidate families cover the intended local motion support around each proposal expansion pose?",
                    answer="The equal-area support map shows whether candidate families cover the local proposal shell around each expansion pose.",
                    sections=(
                        ExplanationSection(
                            "population",
                            "Bounded candidate rows expressed in their own proposal expansion frame and current target-distance scale.",
                        ),
                        ExplanationSection(
                            "metric",
                            "Target-distance-normalized X/Y displacement (dimensionless); Z-up height is available on hover.",
                        ),
                        ExplanationSection(
                            "denominator masks",
                            "Bounded full candidate shell; actor validity and selection remain explicit fields.",
                        ),
                        ExplanationSection(
                            "comparability",
                            "Coordinate convention, generator profile, and plotting row limit must match.",
                        ),
                        ExplanationSection(
                            "expected pattern",
                            "Families occupy their intended local regions with selected actions inside actor-valid support.",
                        ),
                        ExplanationSection(
                            "failure interpretation",
                            "Collapsed clusters, extreme radii, or family overlap can expose pose, frame, or generator defects.",
                        ),
                    ),
                    evidence_role="actor-visible",
                    source_fields=(
                        "inspection.proposal_support_geometry",
                        "proposal expansion pose",
                        "current target-distance scale",
                    ),
                    theory=TheoryReferences(
                        equation_ids=("spatial.candidate_proposal_support_normalization",),
                        symbol_ids=("oracle.candidate_qti", "oracle.center", "entity.center", "spatial.ref_pose"),
                    ),
                ),
            )

            if {x_column, y_column, z_column}.issubset(root_geometry.columns):
                figure_3d = px.scatter_3d(
                    root_geometry,
                    x=x_column,
                    y=y_column,
                    z=z_column,
                    color="position" if "position" in root_geometry else None,
                    symbol="selected" if "selected" in root_geometry else None,
                    title="Candidate centers in target-normalized 3D support",
                )
                frame_rows = proposal_frames
                configure_3d_scene(
                    figure_3d,
                    axis_titles=("target-forward / d", "target-lateral / d", "up / d"),
                )
                if not frame_rows.empty:
                    _add_geometry_anchors(
                        figure_3d,
                        frame_rows,
                        three_dimensional=True,
                        axis_frames=proposal_axis_frames,
                    )
                _render_plot(
                    figure_3d,
                    ScientificExplanation(
                        question="Where do candidate poses lie relative to the root and observed target?",
                        answer="The 3D view keeps the candidate shell and factual anchors in one target-aligned frame.",
                        sections=(
                            ExplanationSection(
                                "population", "Bounded candidate shell rows with persisted root/target anchors."
                            ),
                            ExplanationSection(
                                "metric",
                                "Coordinates are dimensionless displacements divided by the target-distance scale.",
                            ),
                            ExplanationSection(
                                "denominator masks",
                                "Only finite pose rows are plotted; missing geometry remains unavailable.",
                            ),
                            ExplanationSection(
                                "comparability", "Compare only matching pose conventions and generation contracts."
                            ),
                            ExplanationSection(
                                "expected pattern",
                                "Candidate support surrounds the root without unexplained frame rotation or scale.",
                            ),
                            ExplanationSection(
                                "failure interpretation",
                                "Offset anchors or collapsed axes indicate pose decoding or target association defects.",
                            ),
                        ),
                        evidence_role="actor-visible",
                        source_fields=("inspection.proposal_support_geometry",),
                    ),
                )

        if trajectory_geometry:
            trajectory_points = pd.DataFrame(trajectory_geometry.get("points", []))
            trajectory_frames = pd.DataFrame(trajectory_geometry.get("frames", []))
            if not trajectory_points.empty and {"x", "y", "z", "path_order"}.issubset(trajectory_points.columns):
                _render_plot(
                    _trajectory_figure(trajectory_points, trajectory_frames),
                    ScientificExplanation(
                        question="How did the factual selected pose move from the rollout root?",
                        answer="Only persisted root and selected actions are shown; candidate alternatives are excluded from this path.",
                        sections=(
                            ExplanationSection("population", "Factual selected steps plus the root for each rollout."),
                            ExplanationSection(
                                "metric", "Target-aligned displacement normalized by initial root-to-target distance."
                            ),
                            ExplanationSection(
                                "denominator masks",
                                "Early termination is retained as a shorter factual path; no missing steps are fabricated.",
                            ),
                            ExplanationSection(
                                "comparability",
                                "Compare only stores with matching target-alignment and rollout contracts.",
                            ),
                            ExplanationSection(
                                "expected pattern",
                                "The path remains physically coherent and its target anchor stays fixed.",
                            ),
                            ExplanationSection(
                                "failure interpretation",
                                "Jumps or anchor inconsistencies expose pose/frame or persisted-step defects.",
                            ),
                        ),
                        evidence_role="actor-visible",
                        source_fields=("inspection.rollout_trajectory_geometry",),
                        theory=TheoryReferences(
                            equation_ids=("spatial.rollout_trajectory_normalization",),
                            symbol_ids=("oracle.candidate_qti", "oracle.center", "entity.center", "spatial.ref_pose"),
                        ),
                    ),
                )

        if "normalized_radius" in candidates and candidates["normalized_radius"].notna().any():
            radius = candidates.dropna(subset=["normalized_radius"])
            _render_plot(
                _normalized_radius_figure(radius),
                ScientificExplanation(
                    question="Do candidate radii respect the target-normalized geometry envelope?",
                    answer="The radius distribution compares candidate displacement with the target distance remaining at each factual expansion pose.",
                    sections=(
                        ExplanationSection(
                            "population", "Bounded candidate rows with finite target-distance-normalized radius."
                        ),
                        ExplanationSection(
                            "metric", "Candidate radius divided by the persisted target-distance scale; dimensionless."
                        ),
                        ExplanationSection(
                            "denominator masks", "Finite normalized-radius rows; missing geometry remains unavailable."
                        ),
                        ExplanationSection(
                            "comparability",
                            "Compare only stores sharing the same target normalization and candidate contract.",
                        ),
                        ExplanationSection(
                            "expected pattern", "Most support remains within the unit target-normalized envelope."
                        ),
                        ExplanationSection(
                            "failure interpretation",
                            "Clipping or heavy tails can expose impossible geometry or frame mistakes.",
                        ),
                    ),
                    evidence_role="actor-visible",
                    source_fields=("candidate_diagnostics/normalized_radius", "target_distance_m"),
                ),
            )

        frame_fields_required = {"rollout_row_id", "step_index", "rig_target_yaw_error_deg", "target_elevation_deg"}
        geometry_fields_required = {"rollout_row_id", "step_index", "selected", "target_facing_error_deg"}
        frame_orientation = (
            _orientation_diagnostic_rows(root_geometry, proposal_frames)
            if frame_fields_required.issubset(proposal_frames.columns)
            and geometry_fields_required.issubset(root_geometry.columns)
            else pd.DataFrame()
        )
        orientation_fields = {
            "rig_target_yaw_error_deg",
            "target_elevation_deg",
        }
        if not frame_orientation.empty:
            orientation = frame_orientation
            orientation_sources = tuple(str(value) for value in orientation.get("diagnostic", pd.Series()).unique())
        elif orientation_fields.intersection(candidates.columns):
            frame_fields = [name for name in orientation_fields if name in candidates]
            orientation_sources = tuple(frame_fields)
            orientation = candidates[frame_fields].copy()
            orientation["step_index"] = candidates.get("step_index", pd.Series(index=candidates.index))
            orientation["diagnostic"] = "candidate orientation"
            orientation = orientation.melt(
                id_vars=["step_index", "diagnostic"], var_name="source", value_name="angle_deg"
            ).dropna(subset=["angle_deg"])
        else:
            orientation = pd.DataFrame()
            orientation_sources = ()
        if not orientation.empty:
            _render_plot(
                _orientation_diagnostic_figure(orientation),
                ScientificExplanation(
                    question="Are candidate and target-facing orientations consistent with the persisted frame?",
                    answer="The orientation diagnostics compare persisted candidate and target-facing frames in the store's declared coordinate convention.",
                    sections=(
                        ExplanationSection(
                            "population", "Bounded finite candidate orientation diagnostics by factual step."
                        ),
                        ExplanationSection("metric", "Yaw/elevation diagnostic angles in degrees."),
                        ExplanationSection(
                            "denominator masks",
                            "Finite persisted orientation fields; absent fields are not imputed.",
                        ),
                        ExplanationSection(
                            "comparability",
                            "Use the same pose convention and target-facing contract across stores.",
                        ),
                        ExplanationSection(
                            "expected pattern", "Errors remain within configured orientation envelopes."
                        ),
                        ExplanationSection(
                            "failure interpretation",
                            "Systematic offsets indicate frame or target-pose inconsistencies.",
                        ),
                    ),
                    evidence_role="actor-visible",
                    source_fields=tuple(f"proposal_geometry/{name}" for name in orientation_sources),
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
                            "population", "Bounded candidate rows with finite bearing or motion-yaw diagnostics."
                        ),
                        ExplanationSection("metric", "Yaw angle in degrees in the persisted ARIA convention."),
                        ExplanationSection(
                            "denominator masks",
                            "Finite angle diagnostics; invalid candidates remain included unless absent from the persisted audit row.",
                        ),
                        ExplanationSection(
                            "comparability", "Angle convention, generator families, and candidate budget must match."
                        ),
                        ExplanationSection(
                            "expected pattern",
                            "Executed yaw support overlaps relevant target bearings without implausible spikes.",
                        ),
                        ExplanationSection(
                            "failure interpretation",
                            "Systematic offsets suggest frame errors; narrow motion support suggests generator or constraint collapse.",
                        ),
                    ),
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
                        answer="The scatter checks whether sampled and selected actions jointly respect plausible translation and rotation support.",
                        sections=(
                            ExplanationSection("population", "Bounded candidate rows with finite motion diagnostics."),
                            ExplanationSection("metric", "Step length in metres and yaw change in degrees."),
                            ExplanationSection(
                                "denominator masks",
                                "Finite motion rows; validity, family, and selected state remain inspectable.",
                            ),
                            ExplanationSection(
                                "comparability", "Motion limits and generator configuration must match."
                            ),
                            ExplanationSection(
                                "expected pattern",
                                "Samples respect configured motion support and selected actions avoid extreme corners.",
                            ),
                            ExplanationSection(
                                "failure interpretation",
                                "Outliers or family-specific streaks can indicate transform errors, unrealistic moves, or constraint failures.",
                            ),
                        ),
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
                                "population",
                                "Bounded candidates with finite target root gain, split by family and selected state.",
                            ),
                            ExplanationSection(
                                "metric",
                                "Target root-normalized gain, dimensionless; negative valid rewards remain real values.",
                            ),
                            ExplanationSection(
                                "denominator masks",
                                "Finite oracle labels only; invalid or missing labels are excluded rather than assigned low reward.",
                            ),
                            ExplanationSection(
                                "comparability",
                                "Target protocol, reward definition, candidate mixture, and row limit must match.",
                            ),
                            ExplanationSection(
                                "expected pattern",
                                "Selected rewards occupy competitive support without every family collapsing to one value.",
                            ),
                            ExplanationSection(
                                "failure interpretation",
                                "Selected low-tail rewards suggest policy mismatch; missing families suggest generator or label coverage gaps.",
                            ),
                        ),
                        evidence_role="oracle/evaluation",
                        source_fields=(
                            "candidates/target_root_gain",
                            "candidates/selected_mask",
                            "candidates/position_id",
                        ),
                        theory=TheoryReferences(
                            equation_ids=("rl.target_root_gain_reward",),
                            symbol_ids=("entity.target_reward",),
                            term_ids=("target-root-gain-reward",),
                        ),
                    ),
                )
