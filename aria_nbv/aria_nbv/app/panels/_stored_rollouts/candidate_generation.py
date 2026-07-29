"""Candidate generation, support, geometry, and selection evidence."""

from __future__ import annotations

from typing import cast

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ....rollouts.inspection import (
    CANDIDATE_GENERATION_COHORT_FIELDS,
    candidate_geometry_evidence_rows,
    candidate_plot_availability_rows,
    candidate_proposal_calibration_rows,
    candidate_selection_family_rows,
    candidate_selection_rank_family_rows,
)
from .session import StoredRolloutSession
from .shared import _download_frame, _info_popover, _render_plot

_PLOT_ROW_LIMIT = 20_000
_GENERATION_DIMENSIONS = ("mixture", "position", "strategy")
_GENERATION_DIMENSION_LABELS = {
    "mixture": "Mixture Component",
    "position": "Candidate Position",
    "strategy": "View Direction",
}
_GENERATION_COMPONENT_PREFIXES = {
    "mixture": "Mixture",
    "position": "Position",
    "strategy": "View",
}

_CANDIDATE_INFO = r"""
Candidate generation and candidate selection are different operations.

1. A **mixture component** chooses a proposal source.
2. A **candidate-position family** chooses where the camera center is placed.
3. A **view-direction strategy** chooses how that camera is oriented. Position
   plus view direction determine the candidate pose.
4. The actor-validity mask removes inadmissible poses. A **selection policy**
   then chooses among the remaining candidates using random selection, argmax,
   temperature-softmax, learned scores, or bounded oracle lookahead.

Generation frequencies need not equal persisted proposal probability.
Calibration compares empirical component share with finite proposal mass only
inside one exact generation cohort. Selection preference is reported as

$$
E_f =
\frac{n_{\mathrm{selected},f}/n_{\mathrm{selected}}}
     {n_{\mathrm{valid},f}/n_{\mathrm{valid}}}.
$$

$E_f=1$ means selection proportional to valid availability, $E_f>1$ means
enrichment, and $E_f<1$ means under-selection. The selector itself is never
plotted as though it were a generator component.

Geometry is expressed only in each rollout's root frame:
\((x_r,y_r,z_r)=t_{\mathrm{candidate}}-t_{\mathrm{root}}\). This removes
unrelated world origins while retaining Z-up axes. Actor score rank describes
the persisted selection mechanism. Target RRI/root-gain rank and regret use
privileged oracle/evaluation labels; they diagnose a selected action but are
not actor-visible inputs. Negative finite gain remains valid evidence.
"""


def _cohort_label(row: pd.Series) -> str:
    """Return a compact exact generation-cohort label for selection controls."""

    temperature = row.get("temperature")
    temperature_label = "none" if pd.isna(temperature) else f"{float(temperature):g}"
    return (
        f"{row['generation_cohort_id']} · {row.get('policy', 'unknown')} · H={row.get('horizon', '?')} · "
        f"B={row.get('branch_factor', '?')} · beam={row.get('beam_width', '?')} · τ={temperature_label}"
    )


def _generator_component_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Return generation-only rows with unambiguous stage-qualified labels."""

    displayed = frame.loc[frame["dimension"].isin(_GENERATION_DIMENSIONS)].copy()
    displayed["dimension_label"] = displayed["dimension"].map(_GENERATION_DIMENSION_LABELS)
    displayed["family_label"] = displayed["family"].map(_title_label)
    displayed["component_label"] = displayed.apply(
        lambda row: f"{_GENERATION_COMPONENT_PREFIXES[str(row['dimension'])]} · {row['family_label']}",
        axis=1,
    )
    dimension_order = {name: index for index, name in enumerate(_GENERATION_DIMENSIONS)}
    displayed["dimension_order"] = displayed["dimension"].map(dimension_order)
    return displayed.sort_values(["dimension_order", "family_label"], kind="stable")


def _composition_figure(selected: pd.DataFrame) -> go.Figure:
    """Show how each generator stage composes the persisted candidate shell."""

    displayed = _generator_component_frame(selected)

    figure = px.bar(
        displayed,
        x="dimension_label",
        y="sampled_fraction",
        color="component_label",
        barmode="stack",
        category_orders={
            "dimension_label": [_GENERATION_DIMENSION_LABELS[name] for name in _GENERATION_DIMENSIONS],
            "component_label": displayed["component_label"].tolist(),
        },
        hover_data=("sampled_count", "actor_valid_count", "actor_valid_rate"),
        labels={
            "dimension_label": "Generator Stage",
            "sampled_fraction": "Share of Generated Candidates",
            "component_label": "Persisted Generator Component",
            "sampled_count": "Sampled Candidates",
            "actor_valid_count": "Actor-Valid Candidates",
            "actor_valid_rate": "Actor-Valid Fraction",
        },
        title="Marginal Candidate Composition by Generator Stage",
    )
    figure.update_layout(
        height=580,
        font={"size": 18},
        title_font={"size": 26},
        legend_title_font={"size": 18},
        legend_font={"size": 16},
        legend_title_text="Persisted Generator Component",
        margin={"t": 100, "r": 280, "b": 100, "l": 120},
    )
    figure.update_xaxes(tickfont={"size": 16}, title_font={"size": 20})
    figure.update_yaxes(
        range=[0.0, 1.0],
        tickformat=".0%",
        tickfont={"size": 16},
        title_font={"size": 20},
    )
    return figure


def _actor_validity_figure(selected: pd.DataFrame) -> go.Figure:
    """Show actor-valid support for each concrete generator component."""

    displayed = _generator_component_frame(selected)
    displayed["actor_invalid_count"] = displayed["sampled_count"] - displayed["actor_valid_count"]
    displayed["actor_invalid_rate"] = 1.0 - displayed["actor_valid_rate"]
    customdata = displayed[["actor_valid_count", "actor_invalid_count", "sampled_count"]]
    figure = go.Figure(
        [
            go.Bar(
                x=displayed["actor_valid_rate"],
                y=displayed["component_label"],
                orientation="h",
                name="Actor Valid",
                marker_color="#2a9d8f",
                customdata=customdata,
                hovertemplate=(
                    "Actor valid: %{customdata[0]} / %{customdata[2]}<br>Actor-valid fraction: %{x:.1%}<extra></extra>"
                ),
            ),
            go.Bar(
                x=displayed["actor_invalid_rate"],
                y=displayed["component_label"],
                orientation="h",
                name="Actor Invalid",
                marker_color="#64748b",
                customdata=customdata,
                hovertemplate=(
                    "Actor invalid: %{customdata[1]} / %{customdata[2]}<br>"
                    "Actor-invalid fraction: %{x:.1%}<extra></extra>"
                ),
            ),
        ]
    )
    figure.update_layout(
        title="Actor-Validity Support by Generator Component",
        barmode="stack",
        height=max(430, 58 * len(displayed) + 180),
        legend_title_text="Candidate Admission",
        margin={"t": 100, "r": 160, "b": 90, "l": 280},
    )
    figure.update_xaxes(title_text="Share of Generated Candidates", range=[0.0, 1.0], tickformat=".0%")
    figure.update_yaxes(title_text="Generator Component", automargin=True)
    return figure


def _recipe_frame(selected: pd.DataFrame) -> pd.DataFrame:
    """Return the joint pose-generation recipes for compact tabular inspection."""

    recipes = selected.loc[selected["dimension"] == "recipe"].copy()
    if recipes.empty:
        return recipes
    recipes["Joint Generator Recipe"] = recipes["family"].map(
        lambda value: " → ".join(
            f"{name.title()}: {_title_label(component)}"
            for name, component in (part.split("=", maxsplit=1) for part in str(value).split(" → "))
        )
    )
    return recipes.rename(
        columns={
            "sampled_count": "Generated",
            "sampled_fraction": "Candidate Share",
            "actor_valid_count": "Actor Valid",
            "actor_valid_rate": "Actor-Valid Fraction",
            "selected_count": "Selected",
        }
    )[
        [
            "Joint Generator Recipe",
            "Generated",
            "Candidate Share",
            "Actor Valid",
            "Actor-Valid Fraction",
            "Selected",
        ]
    ]


def _composition(session: StoredRolloutSession) -> str | None:
    composition = pd.DataFrame(session.candidate_composition())
    if composition.empty:
        st.info("No candidate composition rows are available.")
        return None
    cohorts = composition.drop_duplicates("generation_cohort_id").sort_values("generation_cohort_id")
    cohort_labels = {str(row["generation_cohort_id"]): _cohort_label(row) for _, row in cohorts.iterrows()}
    selected_cohort = st.selectbox(
        "Generation cohort",
        options=list(cohort_labels),
        format_func=cohort_labels.__getitem__,
        help=(
            "All candidate composition, calibration, geometry, selection, rank, regret, and gain evidence is "
            "restricted to this exact persisted generation cohort."
        ),
    )
    selected = composition.loc[composition["generation_cohort_id"].astype(str) == selected_cohort]
    cohort_fields = ["generation_cohort_id", *CANDIDATE_GENERATION_COHORT_FIELDS]
    st.dataframe(cohorts[cohort_fields], hide_index=True, width="stretch")
    policy = str(selected["policy"].iloc[0])
    st.markdown("#### Candidate generation")
    st.caption(
        "Each generator-stage column is a different marginal decomposition of the same candidate set and sums "
        "to 100%; the three columns are not additive. Colors use stage-qualified component names."
    )
    _render_plot(_composition_figure(selected))
    recipes = _recipe_frame(selected)
    if not recipes.empty:
        st.markdown("##### Joint pose-generation recipes")
        st.caption(
            "Each row is one persisted mixture-component → candidate-position → view-direction recipe; "
            "unlike the marginal stage columns, these rows partition the candidate set."
        )
        st.dataframe(recipes, hide_index=True, width="stretch")
    _render_plot(_actor_validity_figure(selected))
    st.markdown("#### Candidate selection and planning treatment")
    summary = selected.iloc[0]
    summary_columns = st.columns(4)
    summary_columns[0].metric("Selection Rule", _title_label(policy))
    summary_columns[1].metric("Horizon", int(summary["horizon"]))
    summary_columns[2].metric("Branch Factor", int(summary["branch_factor"]))
    summary_columns[3].metric("Beam Width", int(summary["beam_width"]))
    st.caption(_selection_policy_description(policy, temperature=selected["temperature"].iloc[0]))
    st.dataframe(selected, hide_index=True, width="stretch")
    _download_frame("Download candidate composition CSV", "candidate-composition.csv", selected)
    return str(selected_cohort)


def _proposal_calibration(audit: list[dict[str, object]]) -> None:
    calibration = pd.DataFrame(candidate_proposal_calibration_rows(audit))
    finite = calibration.loc[calibration["dimension"].isin(_GENERATION_DIMENSIONS)].dropna(subset=["proposal_mass"])
    if finite.empty:
        st.info("Proposal-mass accounting is unavailable: no finite persisted sampler_probability values exist.")
        return
    if finite["calibration_gap"].abs().max() < 1e-12:
        st.info(
            "Persisted proposal mass exactly matches empirical component frequency in this cohort. This is "
            "probability-mass accounting, not evidence that the continuous geometric sampler matches a density."
        )
        _download_frame("Download proposal-mass accounting CSV", "candidate-proposal-calibration.csv", calibration)
        return
    displayed = _generator_component_frame(finite)
    figure = px.scatter(
        displayed,
        x="proposal_mass",
        y="empirical_frequency",
        color="component_label",
        symbol="dimension_label",
        hover_data=("candidate_count", "finite_probability_count", "calibration_gap"),
        labels={
            "proposal_mass": "Persisted Proposal-Mass Share",
            "empirical_frequency": "Empirical Candidate Share",
            "component_label": "Persisted Generator Component",
            "dimension_label": "Generator Stage",
        },
        title="Empirical Candidate Share versus Persisted Proposal Mass",
    )
    figure.add_shape(type="line", x0=0.0, y0=0.0, x1=1.0, y1=1.0, line={"dash": "dot", "color": "#94a3b8"})
    figure.update_xaxes(range=[0.0, 1.0], tickformat=".0%")
    figure.update_yaxes(range=[0.0, 1.0], tickformat=".0%", scaleanchor="x", scaleratio=1)
    figure.update_layout(height=650, margin={"t": 100, "r": 280, "b": 100, "l": 120})
    _render_plot(figure)
    _download_frame("Download proposal-mass accounting CSV", "candidate-proposal-calibration.csv", calibration)


def _title_label(value: object) -> str:
    """Convert one persisted categorical value into a display label."""

    return str(value).replace("_", " ").replace("-", " ").title()


def _selection_policy_description(policy: str, *, temperature: object) -> str:
    """Explain the persisted selector without confusing it with pose generation."""

    descriptions = {
        "random": "samples without using an oracle or learned candidate score",
        "random_valid": "samples only from actor-valid candidates",
        "oracle_greedy": "takes the argmax of the one-step oracle score over actor-valid candidates",
        "oracle_lookahead": "identifies a bounded oracle-search treatment whose first retained action is executed",
        "oracle_lookahead_diverse": "identifies bounded oracle search with persisted diversity controls",
        "temperature_softmax": "samples actor-valid candidates from temperature-softmax oracle scores",
        "temperature_softmax_diverse": "samples temperature-softmax oracle scores with persisted diversity controls",
        "learned_one_step": "takes the argmax of the learned one-step scorer over actor-valid candidates",
        "q_h": "takes the argmax of learned finite-horizon Q_H values over actor-valid candidates",
    }
    detail = descriptions.get(policy, "uses the persisted rollout selector identified by this policy name")
    temperature_text = ""
    if pd.notna(temperature) and "softmax" in policy:
        temperature_text = f" at temperature {float(temperature):g}"
    return (
        f"**{_title_label(policy)}** {detail}{temperature_text}. This persisted treatment is separate from "
        "mixture, candidate position, and view direction; it acts after generation and masking."
    )


def _target_normalized_motion_figure(frame: pd.DataFrame):
    """Build root-to-candidate vectors in the target-normalized XY frame."""

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=[0.0, 1.0],
            y=[0.0, 0.0],
            mode="lines",
            line={"color": "#f8fafc", "dash": "dot", "width": 2},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=[0.0],
            y=[0.0],
            mode="markers",
            name="Root",
            marker={"color": "#f8fafc", "size": 14, "symbol": "circle-cross"},
        )
    )
    figure.add_trace(
        go.Scatter(
            x=[1.0],
            y=[0.0],
            mode="markers",
            name="Target",
            marker={"color": "#fbbf24", "size": 16, "symbol": "star"},
        )
    )
    plotted = frame.assign(
        strategy_label=frame["strategy"].map(_title_label),
        position_label=frame.get("position", pd.Series("unknown", index=frame.index)).map(_title_label),
        selected_label=frame["selected"].map({True: "Selected", False: "Not Selected"}),
    )
    palette = px.colors.qualitative.Safe
    position_colors = {
        position: palette[index % len(palette)]
        for index, position in enumerate(sorted(plotted["position_label"].dropna().unique()))
    }
    for (position, strategy, selected), group in plotted.groupby(
        ["position_label", "strategy_label", "selected_label"], dropna=False, sort=True
    ):
        color = position_colors[position]
        vector_x = (
            pd.DataFrame({"root": 0.0, "endpoint": group["target_normalized_forward"].to_numpy(), "break": None})
            .to_numpy()
            .reshape(-1)
        )
        vector_y = (
            pd.DataFrame({"root": 0.0, "endpoint": group["target_normalized_lateral"].to_numpy(), "break": None})
            .to_numpy()
            .reshape(-1)
        )
        figure.add_trace(
            go.Scattergl(
                x=vector_x,
                y=vector_y,
                mode="lines",
                line={"color": color, "width": 1},
                opacity=0.35,
                hoverinfo="skip",
                showlegend=False,
            )
        )
        figure.add_trace(
            go.Scattergl(
                x=group["target_normalized_forward"],
                y=group["target_normalized_lateral"],
                mode="markers",
                name=f"{position} · {strategy} · {selected}",
                marker={
                    "color": color,
                    "size": 12 if selected == "Selected" else 9,
                    "symbol": "diamond" if selected == "Selected" else "circle",
                },
                customdata=group[["candidate_row_id", "step_index", "actor_action"]],
                hovertemplate=(
                    "Candidate %{customdata[0]}<br>Step %{customdata[1]}<br>"
                    "Actor Valid: %{customdata[2]}<br>Forward: %{x:.2f}<br>Lateral: %{y:.2f}<extra></extra>"
                ),
            )
        )
    figure.update_layout(
        title="Target-Normalized Root-to-Candidate Motion Vectors",
        height=680,
        font={"size": 18},
        title_font={"size": 26},
        legend_title_text="Position · View Direction · Selection",
        legend_title_font={"size": 18},
        legend_font={"size": 16},
        margin={"t": 100, "r": 260, "b": 100, "l": 120},
    )
    figure.update_xaxes(
        title_text="Forward Relative To Root-Target Distance", tickfont={"size": 16}, title_font={"size": 20}
    )
    figure.update_yaxes(
        title_text="Rightward Relative To Root-Target Distance",
        tickfont={"size": 16},
        title_font={"size": 20},
        scaleanchor="x",
        scaleratio=1,
    )
    return figure


def _geometry(audit: list[dict[str, object]]) -> pd.DataFrame:
    geometry = pd.DataFrame(candidate_geometry_evidence_rows(audit))
    target_normalized = geometry.dropna(subset=["target_normalized_forward", "target_normalized_lateral"]).sort_values(
        "candidate_row_id"
    )
    if target_normalized.empty:
        st.info(
            "Target-normalized motion vectors are unavailable: the target center or a nonzero root-to-target XY baseline is absent."
        )
    else:
        plotted = target_normalized.head(_PLOT_ROW_LIMIT)
        _render_plot(_target_normalized_motion_figure(plotted))
        if len(target_normalized) > len(plotted):
            st.caption(
                f"Motion-vector plot is deterministically bounded to {len(plotted):,} of {len(target_normalized):,} rows."
            )

    _distribution_plot(
        geometry,
        ("root_radius_m", "root_relative_z_m"),
        "Root-relative radius and height distributions",
        color_field="position",
    )
    _distribution_plot(
        geometry,
        ("root_azimuth_deg", "root_elevation_deg"),
        "Candidate-position angle distributions",
        color_field="position",
    )
    _distribution_plot(
        geometry,
        ("orientation_to_target_bearing_deg",),
        "View orientation relative to target bearing",
        color_field="strategy",
    )
    return geometry


def _distribution_plot(
    frame: pd.DataFrame,
    fields: tuple[str, ...],
    title: str,
    *,
    color_field: str,
) -> None:
    available = [field for field in fields if field in frame and frame[field].notna().any()]
    missing = [field for field in fields if field not in available]
    if missing:
        st.info(f"{title}: unavailable field(s): {', '.join(missing)}.")
    if not available:
        return
    plotted = frame.sort_values("candidate_row_id").head(_PLOT_ROW_LIMIT)
    for field in available:
        figure = px.histogram(
            plotted.dropna(subset=[field]),
            x=field,
            color=color_field if color_field in plotted else None,
            marginal="box",
            barmode="overlay",
            opacity=0.5,
            labels={color_field: _GENERATION_DIMENSION_LABELS.get(color_field, _title_label(color_field))},
            title=f"{title} · {_title_label(field)}",
        )
        figure.update_layout(legend_title_text=_GENERATION_DIMENSION_LABELS.get(color_field, _title_label(color_field)))
        _render_plot(figure)


def _motion_support(audit: pd.DataFrame) -> None:
    _distribution_plot(
        audit,
        (
            "motion_step_length_m",
            "motion_backward_step_m",
            "motion_height_delta_m",
            "path_min_clearance_m",
            "free_space_margin_m",
        ),
        "Motion and free-space support",
        color_field="position",
    )
    collision_figure = _collision_support_figure(audit)
    if collision_figure is not None:
        _render_plot(collision_figure)
    elif "path_collision" not in audit or audit["path_collision"].dropna().empty:
        st.info("Path-collision evidence is unavailable: no finite persisted path_collision values exist.")
    else:
        st.success(f"No path collisions occur in {len(audit['path_collision'].dropna()):,} persisted candidate rows.")


def _collision_support_figure(audit: pd.DataFrame) -> go.Figure | None:
    """Return collision rates only when at least one persisted collision exists."""

    if "path_collision" not in audit:
        return None
    finite = audit.dropna(subset=["path_collision"]).copy()
    if finite.empty or not finite["path_collision"].astype(bool).any():
        return None
    collision = (
        finite.assign(position_label=finite["position"].map(_title_label))
        .groupby("position_label", dropna=False)["path_collision"]
        .agg(candidate_count="count", collision_count="sum", collision_rate="mean")
        .reset_index()
        .sort_values("collision_rate", ascending=True)
    )
    figure = px.bar(
        collision,
        x="collision_rate",
        y="position_label",
        orientation="h",
        hover_data=("candidate_count", "collision_count"),
        labels={
            "collision_rate": "Path Collision Rate",
            "position_label": "Candidate Position Family",
            "candidate_count": "Candidates",
            "collision_count": "Path Collisions",
        },
        title="Path Collision Rate by Candidate Position Family",
    )
    figure.update_traces(marker_color="#ef4444", texttemplate="%{x:.1%}", textposition="outside", cliponaxis=False)
    figure.update_xaxes(
        range=[0.0, min(1.0, max(0.05, float(collision["collision_rate"].max()) * 1.2))], tickformat=".1%"
    )
    figure.update_layout(
        height=max(420, 58 * len(collision) + 180),
        showlegend=False,
        margin={"t": 100, "r": 100, "b": 90, "l": 220},
    )
    return figure


def _selection(audit: list[dict[str, object]], rank_rows: list[dict[str, object]]) -> None:
    selection = pd.DataFrame(candidate_selection_family_rows(audit))
    if selection.empty:
        st.info("Selection preference is unavailable: no candidate-family rows exist.")
    else:
        policies = sorted(selection["policy"].dropna().astype(str).unique())
        policy = policies[0] if len(policies) == 1 else "multiple persisted policies"
        st.markdown("#### Selection preference within the persisted policy")
        st.caption(
            "Enrichment compares a generator component's share of selected candidates with its share of all "
            "actor-valid candidates. The reference value 1 means availability-proportional selection."
        )
        finite_selection = _generator_component_frame(selection).dropna(
            subset=["selection_enrichment_vs_valid_availability"]
        )
        if finite_selection.empty:
            st.info("Selection enrichment is unavailable because no generator component has actor-valid support.")
        else:
            _render_plot(_selection_preference_figure(selection, policy=policy))
    _download_frame("Download normalized selection CSV", "candidate-selection-normalized.csv", selection)

    ranks = pd.DataFrame(candidate_selection_rank_family_rows(audit, rank_rows))
    if ranks.empty:
        st.info("Rank/regret evidence is unavailable: selected candidates could not be joined to finite rank rows.")
    else:
        oracle_ranks = [field for field in ("selected_rank", "target_rri_rank") if ranks[field].notna().any()]
        actor_rank_available = "selection_score_rank" in ranks and ranks["selection_score_rank"].notna().any()
        if not actor_rank_available or not oracle_ranks:
            st.info("Rank comparison is unavailable: fewer than two persisted actor/oracle rank quantities are finite.")
        else:
            long = ranks.melt(
                id_vars=[
                    field
                    for field in ("step_row_id", "policy", "strategy", "regret_to_best", "selection_score_rank")
                    if field in ranks
                ],
                value_vars=oracle_ranks,
                var_name="rank_type",
                value_name="rank",
            ).dropna(subset=["rank"])
            _render_plot(
                px.scatter(
                    long,
                    x="selection_score_rank",
                    y="rank",
                    color="rank_type",
                    symbol="strategy",
                    facet_col="policy" if long["policy"].nunique() <= 4 else None,
                    hover_data=("step_row_id", "regret_to_best"),
                    labels={"strategy": "View Direction"},
                    title="Actor selection-score rank versus oracle root-gain/RRI ranks",
                )
            )
        if "regret_to_best" in ranks and ranks["regret_to_best"].notna().any():
            _render_plot(
                px.histogram(
                    ranks,
                    x="regret_to_best",
                    color="strategy",
                    marginal="box",
                    labels={"strategy": "View Direction"},
                    title="Regret to best actor-valid oracle root gain",
                )
            )

    audit_frame = pd.DataFrame(audit)
    gains = audit_frame.dropna(subset=["target_root_gain"])
    if gains.empty:
        st.info("Root-gain distributions by family are unavailable: oracle target_root_gain is nonfinite.")
    else:
        plotted = gains.sort_values("candidate_row_id").head(_PLOT_ROW_LIMIT)
        _render_plot(
            px.histogram(
                plotted,
                x="target_root_gain",
                color="strategy",
                pattern_shape="selected",
                barmode="overlay",
                opacity=0.55,
                labels={"strategy": "View Direction", "selected": "Selection State"},
                title="Oracle root-gain distributions by view direction and selected state",
            )
        )


def _selection_preference_figure(selection: pd.DataFrame, *, policy: str) -> go.Figure:
    """Plot generator-component enrichment while keeping policy as selector context."""

    displayed = _generator_component_frame(selection).dropna(subset=["selection_enrichment_vs_valid_availability"])
    figure = px.bar(
        displayed,
        x="selection_enrichment_vs_valid_availability",
        y="component_label",
        orientation="h",
        hover_data=(
            "candidate_count",
            "actor_valid_count",
            "selected_count",
            "valid_availability_share",
            "selected_share",
        ),
        labels={
            "selection_enrichment_vs_valid_availability": "Selection Enrichment Relative to Valid Availability",
            "component_label": "Generator Component",
            "candidate_count": "Candidates",
            "actor_valid_count": "Actor-Valid Candidates",
            "selected_count": "Selected Candidates",
            "valid_availability_share": "Share of Valid Availability",
            "selected_share": "Share of Selections",
        },
        title=f"Generator-Component Selection Enrichment · {_title_label(policy)}",
    )
    figure.update_traces(marker_color="#38bdf8", texttemplate="%{x:.2f}×", textposition="outside", cliponaxis=False)
    maximum = float(displayed["selection_enrichment_vs_valid_availability"].max()) if not displayed.empty else 1.0
    figure.update_xaxes(range=[0.0, max(1.15, maximum * 1.15)])
    figure.add_vline(
        x=1.0,
        line_dash="dot",
        line_color="#fbbf24",
        annotation_text="Availability-proportional",
        annotation_position="top",
    )
    figure.update_layout(
        height=max(430, 58 * len(displayed) + 180),
        showlegend=False,
        margin={"t": 120, "r": 140, "b": 100, "l": 280},
    )
    return figure


def _heavy_evidence(session: StoredRolloutSession, *, generation_cohort_id: str) -> None:
    st.warning(
        f"Loading normalized candidate-wide evidence across {session.candidate_count:,} rows. "
        f"Interactive point plots are bounded to {_PLOT_ROW_LIMIT:,} deterministic rows; reducers and downloads "
        "remain complete within the selected generation cohort."
    )
    all_audit = session.candidates()
    audit = [row for row in all_audit if str(row.get("generation_cohort_id")) == generation_cohort_id]
    if not audit:
        st.error("The selected generation cohort is absent from the normalized candidate audit.")
        return
    selected_candidate_ids = {
        int(cast(int, row["candidate_row_id"]))
        for row in audit
        if bool(row.get("selected")) and row.get("candidate_row_id") is not None
    }
    ranks = [
        row
        for row in session.selected_candidate_ranks()
        if row.get("selected_candidate_row_id") in selected_candidate_ids
    ]
    audit_frame = pd.DataFrame(audit)
    blockers = pd.DataFrame(candidate_plot_availability_rows(audit, ranks))
    st.markdown("#### Heavy evidence availability")
    st.dataframe(blockers, hide_index=True, width="stretch")
    _proposal_calibration(audit)
    geometry = _geometry(audit)
    _motion_support(audit_frame)
    _selection(audit, ranks)
    _download_frame("Download normalized candidate evidence CSV", "candidate-evidence.csv", audit_frame)
    _download_frame("Download root-relative geometry CSV", "candidate-root-relative-geometry.csv", geometry)


def render(session: StoredRolloutSession) -> None:
    """Render lightweight composition and explicitly gated heavy evidence."""

    st.subheader("Candidate Generation & Selection")
    _info_popover("Sampling, geometry, and selection interpretation", _CANDIDATE_INFO)
    st.caption(
        "The default view reads categorical provenance and masks only. It does not materialize full candidate audit rows, geometry, rewards, or ranks."
    )
    generation_cohort_id = _composition(session)
    availability = pd.DataFrame(session.candidate_evidence_availability())
    st.markdown("#### Persisted field availability")
    st.dataframe(availability, hide_index=True, width="stretch")

    state_key = f"stored_candidate_heavy:{session.identity}"
    if st.button("Load candidate-wide geometry, calibration, and selection evidence", key=f"{state_key}:load"):
        st.session_state[state_key] = True
    if not st.session_state.get(state_key, False):
        st.info("Candidate-wide geometry, probabilities, oracle labels, motion diagnostics, and ranks remain unloaded.")
        return
    if generation_cohort_id is not None:
        _heavy_evidence(session, generation_cohort_id=generation_cohort_id)


__all__ = ["render"]
