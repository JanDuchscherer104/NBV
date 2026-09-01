"""Typed Plotly models derived only from immutable candidate snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from ..reporting.results import ReportFigure, canonical_plotly_json
from .candidate_evidence import CandidateEvidenceRow, CandidateEvidenceSnapshot, CandidateFactAvailability


@dataclass(frozen=True, slots=True)
class CandidatePlotStateContext:
    """Rollout-only context retained for one plotted factual state."""

    state_key: str
    """Stable direct or rollout factual-state identity."""

    horizon: int | None
    """Configured rollout horizon ``H``, or ``None`` when unavailable."""

    factual_step: int | None
    """Zero-based factual step ``t``, or ``None`` for direct evidence."""

    remaining_budget: int | None
    """Current-decision-inclusive remaining budget, or ``None``."""

    history_coverage: int | None
    """Count of prior factual actions covered, when available."""


@dataclass(frozen=True, slots=True)
class CandidatePlotContext:
    """Rollout context coverage retained by one candidate plot model."""

    states: tuple[CandidatePlotStateContext, ...]
    """Ordered rollout context for every plotted state."""

    common_horizon: int | None
    """Shared horizon when every plotted state supplies the same ``H``."""


@dataclass(frozen=True, slots=True)
class CandidatePlotModel:
    """Immutable candidate plot consumable by UI and static-export adapters.

    Attributes:
        key: Stable plot identity.
        title: Complete rendered title, including factual rollout context.
        figure: Canonical Plotly JSON plus source identities for exact export.
        context: Per-state rollout-only horizon/step/budget facts; direct
            evidence keeps every field unavailable.

    Plot construction is complete when this DTO is returned. Presentation
    leaves may reconstruct a fresh mutable figure but must not reread stores,
    inspect generator configuration, or reduce scientific facts again.
    """

    key: str
    """Stable plot identity."""

    title: str
    """Rendered scientific title with minimal rollout context."""

    figure: ReportFigure
    """Canonical Plotly trace bytes shared with static export."""

    context: CandidatePlotContext
    """Per-state rollout context and common-horizon summary."""

    @property
    def plotly_json(self) -> bytes:
        """Return canonical immutable Plotly JSON bytes."""

        return self.figure.plotly_json

    def build_figure(self) -> go.Figure:
        """Reconstruct a fresh mutable Plotly figure from canonical bytes."""

        return go.Figure(json.loads(self.figure.plotly_json))


def candidate_support_plot_models(
    snapshots: tuple[CandidateEvidenceSnapshot, ...],
    *,
    show_view_directions: bool = False,
) -> tuple[CandidatePlotModel, CandidatePlotModel, CandidatePlotModel, CandidatePlotModel]:
    """Build ground, 3-D, survival, and jitter models from snapshots only.

    Args:
        snapshots: Immutable candidate evidence states. Every row already uses
            canonical target-aligned coordinates or marks them unavailable.
        show_view_directions: Add short actor-action gaze arrows when canonical
            target-frame directions are available.

    Returns:
        Four immutable models retaining exact Plotly traces for UI and static
        export. Bounded jitter rows retain dotted configured envelopes;
        uncapped spherical rows use fixed yaw ``[-180, 180]`` and pitch
        ``[-90, 90]`` axes with no envelope.
    """

    context = _plot_context(snapshots)
    suffix = _context_title_suffix(context)
    frame = _point_frame(snapshots)
    ground_title = f"Candidate centers in target-aligned support (ground plane){suffix}"
    support_title = f"Candidate centers in target-aligned support (3D){suffix}"
    survival_title = f"Candidate family survival{suffix}"
    jitter_title = f"Candidate view jitter{suffix}"

    ground = px.scatter(
        frame,
        x="x",
        y="y",
        color="family" if not frame.empty else None,
        symbol="status" if not frame.empty else None,
        hover_data=["candidate_id", "state"] if not frame.empty else None,
        title=ground_title,
        template="plotly",
        color_discrete_sequence=px.colors.qualitative.Plotly,
        labels={"x": "target-forward / d", "y": "target-lateral / d"},
    )
    if any(snapshot.projection_frame_availability is CandidateFactAvailability.AVAILABLE for snapshot in snapshots):
        ground.add_trace(
            go.Scatter(
                x=[0],
                y=[0],
                mode="markers",
                name="Factual expansion/root",
                marker={"symbol": "cross", "size": 12, "color": "black"},
            )
        )
    targets = sorted(
        {snapshot.target_target_normalized for snapshot in snapshots if snapshot.target_target_normalized is not None}
    )
    if targets:
        ground.add_trace(
            go.Scatter(
                x=[target[0] for target in targets],
                y=[target[1] for target in targets],
                mode="markers",
                name="Task target centre",
                marker={"symbol": "star", "size": 12, "color": "#9467bd"},
            )
        )
    if show_view_directions:
        for snapshot in snapshots:
            for row in snapshot.rows:
                if row.action is not True or row.center_target_normalized is None or row.gaze_target_unit is None:
                    continue
                direction_x, direction_y, _ = row.gaze_target_unit
                norm = (direction_x**2 + direction_y**2) ** 0.5
                if norm <= 1.0e-9:
                    continue
                x, y, _ = row.center_target_normalized
                ground.add_annotation(
                    x=x + 0.04 * direction_x / norm,
                    y=y + 0.04 * direction_y / norm,
                    ax=x,
                    ay=y,
                    xref="x",
                    yref="y",
                    axref="x",
                    ayref="y",
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=0.7,
                    arrowwidth=1.0,
                    arrowcolor="rgba(40,40,40,0.65)",
                )
    ground.update_xaxes(scaleanchor="y", scaleratio=1)
    ground.update_yaxes(constrain="domain")
    _annotate_missing_frame(ground, snapshots)

    support = go.Figure()
    if not frame.empty:
        support.add_trace(
            go.Scatter3d(
                x=frame.x,
                y=frame.y,
                z=frame.z,
                mode="markers",
                name="candidate support",
                customdata=frame[["candidate_id", "family", "status", "lineage"]],
                hovertemplate=(
                    "candidate=%{customdata[0]}<br>family=%{customdata[1]}"
                    "<br>status=%{customdata[2]}<br>lineage=%{customdata[3]}<extra></extra>"
                ),
            )
        )
    if not frame.empty:
        support.data[0].marker = {
            "symbol": frame["status"]
            .map({"selected": "diamond", "action": "circle", "valid": "circle", "invalid": "x"})
            .tolist()
        }
    if any(snapshot.projection_frame_availability is CandidateFactAvailability.AVAILABLE for snapshot in snapshots):
        support.add_trace(
            go.Scatter3d(
                x=[0],
                y=[0],
                z=[0],
                mode="markers",
                name="Factual expansion/root",
                marker={"symbol": "cross", "size": 7},
            )
        )
    if targets:
        support.add_trace(
            go.Scatter3d(
                x=[target[0] for target in targets],
                y=[target[1] for target in targets],
                z=[target[2] for target in targets],
                mode="markers",
                name="Task target centre",
                marker={"symbol": "diamond", "size": 7},
            )
        )
    support.update_layout(
        title=support_title,
        template="plotly",
        scene_aspectmode="data",
        scene_camera={"eye": {"x": 1.5, "y": 1.5, "z": 1.2}},
    )
    _annotate_missing_frame(support, snapshots)

    survival_rows = _survival_rows(snapshots)
    survival = px.bar(
        pd.DataFrame(survival_rows, columns=("family", "stage", "count")),
        x="family",
        y="count",
        color="stage",
        barmode="group",
        title=survival_title,
        template="plotly",
        color_discrete_sequence=px.colors.qualitative.Plotly,
    )

    jitter_rows = [
        {
            "yaw": row.view_jitter_yaw_deg,
            "pitch": row.view_jitter_pitch_deg,
            "family": _family_label(row),
            "bounded": row.view_jitter_is_bounded,
        }
        for snapshot in snapshots
        for row in snapshot.rows
        if row.view_jitter_yaw_deg is not None and row.view_jitter_pitch_deg is not None
    ]
    jitter = px.scatter(
        pd.DataFrame(jitter_rows, columns=("yaw", "pitch", "family", "bounded")),
        x="yaw",
        y="pitch",
        color="family" if jitter_rows else None,
        symbol="bounded" if jitter_rows else None,
        title=jitter_title,
        template="plotly",
        color_discrete_sequence=px.colors.qualitative.Plotly,
        labels={"yaw": "yaw residual [deg]", "pitch": "pitch residual [deg]"},
    )
    envelopes = {
        (row.view_jitter_azimuth_limit_deg, row.view_jitter_elevation_limit_deg)
        for snapshot in snapshots
        for row in snapshot.rows
        if row.view_jitter_is_bounded is True
        and row.view_jitter_azimuth_limit_deg is not None
        and row.view_jitter_elevation_limit_deg is not None
    }
    for azimuth, elevation in sorted(envelopes):
        jitter.add_shape(
            type="rect",
            x0=-azimuth,
            x1=azimuth,
            y0=-elevation,
            y1=elevation,
            line={"dash": "dot"},
            fillcolor="rgba(0,0,0,0)",
        )
    if any(row.view_jitter_is_bounded is False for snapshot in snapshots for row in snapshot.rows):
        jitter.update_xaxes(range=[-180, 180])
        jitter.update_yaxes(range=[-90, 90])
        jitter.add_annotation(
            text="uncapped spherical support",
            x=0.01,
            y=0.99,
            xref="paper",
            yref="paper",
            showarrow=False,
        )
    if snapshots and not jitter_rows:
        availability_counts = {
            availability: sum(
                row.jitter_availability is availability for snapshot in snapshots for row in snapshot.rows
            )
            for availability in CandidateFactAvailability
        }
        availability_summary = ", ".join(
            f"{availability.value.replace('_', '-')} for {count} attempted rows"
            for availability, count in availability_counts.items()
            if count
        )
        jitter.add_annotation(
            text=f"View-jitter evidence {availability_summary or 'unavailable: no attempted rows'}",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
        )
    if not snapshots:
        for figure in (ground, support, survival, jitter):
            figure.add_annotation(
                text="No matching benchmark candidates",
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
            )

    return (
        _model("candidate-ground-support", ground_title, ground, snapshots, context, uses_webgl=False),
        _model("candidate-support-3d", support_title, support, snapshots, context, uses_webgl=True),
        _model("candidate-family-survival", survival_title, survival, snapshots, context, uses_webgl=False),
        _model("candidate-view-jitter", jitter_title, jitter, snapshots, context, uses_webgl=False),
    )


def _point_frame(snapshots: tuple[CandidateEvidenceSnapshot, ...]) -> pd.DataFrame:
    rows = [
        {
            "x": row.center_target_normalized[0],
            "y": row.center_target_normalized[1],
            "z": row.center_target_normalized[2],
            "family": _family_label(row),
            "status": (
                "selected"
                if row.selected is True
                else "action"
                if row.action is True
                else "valid"
                if row.hard_valid
                else "invalid"
            ),
            "candidate_id": row.candidate_id if row.candidate_id is not None else row.attempted_index,
            "state": snapshot.state_key,
            "lineage": row.proposal_key or "unavailable",
        }
        for snapshot in snapshots
        for row in snapshot.rows
        if row.center_target_normalized is not None
    ]
    return pd.DataFrame(rows, columns=("x", "y", "z", "family", "status", "candidate_id", "state", "lineage"))


def _survival_rows(snapshots: tuple[CandidateEvidenceSnapshot, ...]) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    families = sorted({_family_label(row) for snapshot in snapshots for row in snapshot.rows})
    for family in families:
        candidates = tuple(row for snapshot in snapshots for row in snapshot.rows if _family_label(row) == family)
        rows.extend(
            (
                {"family": family, "stage": "attempted", "count": len(candidates)},
                {"family": family, "stage": "hard-valid", "count": sum(row.hard_valid for row in candidates)},
            )
        )
        if all(row.action is not None for row in candidates):
            rows.append({"family": family, "stage": "action", "count": sum(bool(row.action) for row in candidates)})
        if all(row.selected is not None for row in candidates):
            rows.append({"family": family, "stage": "selected", "count": sum(bool(row.selected) for row in candidates)})
    return rows


def _family_label(row: CandidateEvidenceRow) -> str:
    if row.candidate_family_id is not None:
        return row.candidate_family_id
    if row.legacy_family_label is not None:
        return row.legacy_family_label
    return "legacy-missing"


def _plot_context(snapshots: tuple[CandidateEvidenceSnapshot, ...]) -> CandidatePlotContext:
    states = tuple(
        CandidatePlotStateContext(
            state_key=snapshot.state_key,
            horizon=snapshot.overlay.horizon,
            factual_step=snapshot.overlay.factual_step,
            remaining_budget=snapshot.overlay.remaining_budget,
            history_coverage=snapshot.overlay.history_coverage,
        )
        for snapshot in snapshots
    )
    horizons = {state.horizon for state in states if state.horizon is not None}
    common_horizon = (
        next(iter(horizons)) if len(horizons) == 1 and all(state.horizon is not None for state in states) else None
    )
    return CandidatePlotContext(states, common_horizon)


def _context_title_suffix(context: CandidatePlotContext) -> str:
    if not context.states or all(
        state.horizon is state.factual_step is state.remaining_budget is None for state in context.states
    ):
        return " · H/t/budget unavailable"
    fields: list[str] = []
    if context.common_horizon is not None:
        fields.append(f"H={context.common_horizon}")
    else:
        horizons = tuple(state.horizon for state in context.states if state.horizon is not None)
        if horizons:
            value = f"{horizons[0]} (partial)" if len(set(horizons)) == 1 else f"{min(horizons)}…{max(horizons)}"
            fields.append(f"H={value}")
    steps = tuple(state.factual_step for state in context.states if state.factual_step is not None)
    remaining = tuple(state.remaining_budget for state in context.states if state.remaining_budget is not None)
    if steps:
        fields.append(f"t={steps[0]}" if len(set(steps)) == 1 else f"t={min(steps)}…{max(steps)}")
    if remaining:
        fields.append(
            f"remaining={remaining[0]}" if len(set(remaining)) == 1 else f"remaining={min(remaining)}…{max(remaining)}"
        )
    return f" · {', '.join(fields)}"


def _annotate_missing_frame(figure: go.Figure, snapshots: tuple[CandidateEvidenceSnapshot, ...]) -> None:
    missing = sum(row.center_target_normalized is None for snapshot in snapshots for row in snapshot.rows)
    unavailable = tuple(
        snapshot
        for snapshot in snapshots
        if snapshot.projection_frame_availability is not CandidateFactAvailability.AVAILABLE
    )
    if missing or unavailable:
        reasons = sorted(
            {
                snapshot.projection_unavailable_reason.value
                if snapshot.projection_unavailable_reason is not None
                else snapshot.projection_frame_availability.value
                for snapshot in snapshots
                if snapshot.projection_frame_availability is not CandidateFactAvailability.AVAILABLE
            }
        )
        figure.add_annotation(
            text=(
                (
                    f"target-relative support unavailable for {missing} attempted rows"
                    if missing
                    else "target-relative support unavailable"
                )
                + (f": {', '.join(reasons)}" if reasons else "")
            ),
            x=0.01,
            y=0.99,
            xref="paper",
            yref="paper",
            showarrow=False,
        )


def _model(
    key: str,
    title: str,
    figure: go.Figure,
    snapshots: tuple[CandidateEvidenceSnapshot, ...],
    context: CandidatePlotContext,
    *,
    uses_webgl: bool,
) -> CandidatePlotModel:
    source_ids = tuple(dict.fromkeys(f"candidate-snapshot:{snapshot.source_sha256}" for snapshot in snapshots)) or (
        "candidate-state:empty",
    )
    plotly_json = canonical_plotly_json(figure)
    identity_payload = b"\0".join(
        (
            b"candidate-plot-v1",
            key.encode(),
            plotly_json,
        )
    )
    report_identity = hashlib.sha256(identity_payload).hexdigest()[:16]
    report = ReportFigure(
        id=f"{key}:{report_identity}",
        plotly_json=plotly_json,
        source_ids=source_ids,
        source_result_ids=(),
        symbol_ids=(),
        uses_webgl=uses_webgl,
    )
    return CandidatePlotModel(key, title, report, context)


__all__ = [
    "CandidatePlotContext",
    "CandidatePlotModel",
    "CandidatePlotStateContext",
    "candidate_support_plot_models",
]
