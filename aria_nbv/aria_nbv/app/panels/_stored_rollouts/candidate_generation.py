"""Candidate composition and support from session-owned scientific DTOs."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from .session import CandidateScientificEvidence, StoredRolloutSession
from .shared import _download_frame, _info_popover, _render_plot

_GENERATION_DIMENSIONS = ("mixture", "position", "strategy")
_GENERATION_DIMENSION_LABELS = {
    "mixture": "Mixture Component",
    "position": "Candidate Position",
    "strategy": "View Direction",
}
_GENERATION_COMPONENT_PREFIXES = {"mixture": "Mixture", "position": "Position", "strategy": "View"}

_CANDIDATE_INFO = r"""
Candidate support is summarized within each rollout/depth state and only then
averaged across states and scenes. Candidate rows are not independent samples.
For family (f), the displayed scientific reducer uses

$$
\bar p_f=\frac{1}{S}\sum_s\frac{1}{|T_s|}\sum_{t\in T_s}
\frac{N_{s,t,f}}{N_{s,t}},
$$

so states and then scenes, not candidate rows, define the denominator.
Directions use root-relative ARIA world coordinates (RIGHT_HAND_Z_UP): azimuth
and equal-area (\sin(\mathrm{elevation})); distances and heights are metres,
angles are degrees. Composition, covering gaps, motion support, and target-view
availability characterize the generated action space, not policy performance.

Full reducers consume the exact generation cohort. Point displays use a
deterministic hash-priority stratified sample over scene, state, family,
actor-validity, and invalid reason. The display records (N_h,n_h,\pi_h), seed,
where (\pi_h=n_h/N_h), and `display_only`; inverse display weights are for
visual traceability only and never change full-reducer denominators or create
confidence intervals. Scene-bootstrap uncertainty is eligible only for a
predeclared complete cohort; this display sample supports no inference.
Missing calibration,
LOS/FOV, clearance, or motion fields remain unavailable rather than false.
"""


def _title_label(value: object) -> str:
    return str(value).replace("_", " ").title()


def _generator_component_frame(frame: pd.DataFrame) -> pd.DataFrame:
    selected = frame.loc[frame["dimension"].isin(_GENERATION_DIMENSIONS)].copy()
    selected["stage"] = selected["dimension"].map(_GENERATION_DIMENSION_LABELS)
    selected["component"] = selected.apply(
        lambda row: f"{_GENERATION_COMPONENT_PREFIXES[str(row['dimension'])]} · {_title_label(row['family'])}", axis=1
    )
    return selected


def _composition_figure(selected: pd.DataFrame) -> go.Figure:
    """Render pooled candidate counts as descriptive stored-mass context."""

    frame = _generator_component_frame(selected)
    figure = go.Figure()
    for row in frame.sort_values(["stage", "component"]).itertuples():
        figure.add_bar(x=[row.stage], y=[row.sampled_fraction], name=row.component)
    figure.update_layout(
        barmode="stack",
        title="Descriptive Stored-Mass Characterization",
        yaxis_title="Pooled Share of Stored Candidates",
        yaxis_range=[0.0, 1.0],
        legend_title_text="Persisted Generator Component",
        font={"size": 18},
    )
    return figure


def _scientific_composition_figure(rows: pd.DataFrame) -> go.Figure:
    """Render equal-state, then equal-scene candidate-family composition."""

    selected = rows.loc[
        (rows["population"] == "sampled")
        & (rows["aggregation_level"] == "cohort_scene_macro")
        & rows["family_dimension"].isin(_GENERATION_DIMENSIONS)
    ].copy()
    selected["stage"] = selected["family_dimension"].map(_GENERATION_DIMENSION_LABELS)
    selected["component"] = selected.apply(
        lambda row: f"{_GENERATION_COMPONENT_PREFIXES[str(row['family_dimension'])]} · {_title_label(row['family'])}",
        axis=1,
    )
    figure = go.Figure()
    for row in selected.sort_values(["stage", "component"]).itertuples():
        figure.add_bar(x=[row.stage], y=[row.mean_state_family_share], name=row.component)
    figure.update_layout(
        barmode="stack",
        title="State-Then-Scene Macro Candidate Composition",
        yaxis_title="Mean Within-State Candidate Share",
        yaxis_range=[0.0, 1.0],
        legend_title_text="Persisted Generator Component",
        font={"size": 18},
    )
    return figure


def _actor_validity_figure(selected: pd.DataFrame) -> go.Figure:
    frame = _generator_component_frame(selected).sort_values("component")
    valid = pd.to_numeric(frame["actor_valid_rate"], errors="coerce").fillna(0.0)
    figure = go.Figure()
    figure.add_bar(y=frame["component"], x=valid, orientation="h", name="Actor Valid")
    figure.add_bar(y=frame["component"], x=1.0 - valid, orientation="h", name="Actor Invalid")
    figure.update_layout(
        barmode="stack", xaxis_range=[0.0, 1.0], xaxis_title="Share", yaxis_title="Generator Component"
    )
    return figure


def _target_normalized_motion_figure(frame: pd.DataFrame) -> go.Figure:
    figure = go.Figure()
    figure.add_scatter(x=[0.0], y=[0.0], mode="markers", name="Root")
    figure.add_scatter(x=[1.0], y=[0.0], mode="markers", name="Target")
    for _, row in frame.iterrows():
        name = f"{_title_label(row.get('position'))} · {_title_label(row.get('strategy'))}"
        if bool(row.get("selected")):
            name += " · Selected"
        x = float(row["target_normalized_forward"])
        y = float(row["target_normalized_lateral"])
        figure.add_scatter(x=[x], y=[y], mode="markers", name=name)
        figure.add_scatter(x=[0.0, x, None], y=[0.0, y, None], mode="lines", showlegend=False)
    figure.update_layout(
        xaxis_title="Forward Relative To Root-Target Distance",
        yaxis_title="Lateral Relative To Root-Target Distance",
    )
    figure.update_yaxes(scaleanchor="x", scaleratio=1)
    return figure


def _collision_support_figure(frame: pd.DataFrame) -> go.Figure | None:
    if "path_collision" not in frame or frame["path_collision"].dropna().empty:
        return None
    finite = frame.dropna(subset=["path_collision"]).copy()
    grouped = (
        finite.assign(path_collision=finite["path_collision"].astype(bool))
        .groupby("position", dropna=False)["path_collision"]
        .agg(candidate_count="count", collision_count="sum", collision_rate="mean")
        .reset_index()
    )
    if not bool(grouped["collision_count"].sum()):
        return None
    grouped["position"] = grouped["position"].map(_title_label)
    return px.bar(
        grouped,
        x="collision_rate",
        y="position",
        orientation="h",
        hover_data=("candidate_count", "collision_count"),
        labels={"collision_rate": "Path Collision Rate", "position": "Candidate Position Family"},
        title="Persisted Path Collision Support",
    )


def _composition(session: StoredRolloutSession) -> str | None:
    composition = pd.DataFrame(session.candidate_composition())
    if composition.empty:
        st.info("No candidate composition rows are available.")
        return None
    cohorts = sorted(composition["generation_cohort_id"].astype(str).unique().tolist())
    cohort = st.selectbox("Exact generation cohort", cohorts)
    selected = composition.loc[composition["generation_cohort_id"].astype(str) == cohort]
    st.markdown("#### Descriptive stored-mass characterization")
    st.caption(
        "These pooled stored-candidate totals are operational context only. They do not define the scientific "
        "sampling unit and are not used for candidate-composition claims."
    )
    _render_plot(_composition_figure(selected))
    _render_plot(_actor_validity_figure(selected))
    _download_frame("Download pooled stored-mass CSV", "candidate-stored-mass.csv", selected)
    return str(cohort)


def _render_scientific_evidence(evidence: CandidateScientificEvidence) -> None:
    st.caption(
        f"Full reducers: {evidence.population_count:,} candidates in exact cohort {evidence.generation_cohort_id}. "
        "The bounded point projection is display-only."
    )
    composition = pd.DataFrame(evidence.composition_rows)
    st.markdown("#### Scientific candidate composition")
    st.caption(
        "Family shares are computed within each rollout/depth state, averaged equally across states in each "
        "scene, and then averaged equally across scenes."
    )
    if composition.empty:
        st.info("State-then-scene macro composition is unavailable for the selected cohort.")
    else:
        _render_plot(_scientific_composition_figure(composition))
        _download_frame(
            "Download state-then-scene composition CSV",
            "candidate-state-scene-composition.csv",
            composition,
        )
    for title, rows in (
        ("State/scene-macro composition rows", evidence.composition_rows),
        ("Equal-area directional density", evidence.direction_evidence.get("density_rows", [])),
        ("Spherical caps and covering support", evidence.direction_evidence.get("cap_rows", [])),
        ("Angular separation support", evidence.direction_evidence.get("angular_support_rows", [])),
        ("Spatial shell support", evidence.spatial_rows),
        ("Target-view support and missingness", evidence.target_view_rows),
        ("Motion/path support", evidence.motion_rows),
    ):
        with st.expander(title, expanded=False):
            frame = pd.DataFrame(rows)
            if frame.empty:
                st.info("This evidence is unavailable for the selected cohort.")
            else:
                st.dataframe(frame, hide_index=True, width="stretch")
    display = pd.DataFrame(evidence.display_sample.get("rows", []))
    strata = pd.DataFrame(evidence.display_sample.get("strata", []))
    with st.expander("Deterministic display sample design", expanded=False):
        st.json(evidence.display_sample.get("metadata", {}), expanded=False)
        st.dataframe(strata, hide_index=True, width="stretch")
        if not display.empty:
            st.dataframe(display, hide_index=True, width="stretch")
    unavailable = pd.DataFrame(evidence.unavailable_rows)
    if not unavailable.empty:
        st.info("Some candidate evidence is explicitly unavailable; no negative value is inferred.")
        st.dataframe(unavailable, hide_index=True, width="stretch")
    _download_frame("Download display sample CSV", "candidate-display-sample.csv", display)


def render(session: StoredRolloutSession) -> None:
    """Render lightweight composition and explicitly requested full reducers."""

    st.subheader("Candidate Generation & Selection")
    _info_popover("Candidate support, units, denominators, and claim limits", _CANDIDATE_INFO)
    cohort = _composition(session)
    availability = pd.DataFrame(session.candidate_evidence_availability())
    st.dataframe(availability, hide_index=True, width="stretch")
    state_key = f"stored_candidate_heavy:{session.identity}:{cohort}"
    if st.button("Load candidate-wide geometry, calibration, and selection evidence", key=f"{state_key}:load"):
        st.session_state[state_key] = True
    if not st.session_state.get(state_key, False):
        st.info("Full candidate arrays and scientific reducers remain unloaded until explicitly requested.")
        return
    if cohort is not None:
        _render_scientific_evidence(session.candidate_scientific_evidence(generation_cohort_id=cohort))


__all__ = ["render"]
