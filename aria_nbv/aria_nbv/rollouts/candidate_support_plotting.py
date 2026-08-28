"""Pure Plotly views for target-aligned candidate-support evidence."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .candidate_benchmark import CandidateBenchmark


def _point_frame(records: Iterable[CandidateBenchmark]) -> pd.DataFrame:
    rows = []
    for record in records:
        for point in record.points:
            xyz = point.xyz
            rows.append(
                {
                    "x": xyz[0],
                    "y": xyz[1],
                    "z": xyz[2],
                    "family": point.family,
                    "status": "selected" if point.selected else "valid" if point.actor_valid else "invalid",
                    "candidate_id": point.candidate_id,
                    "state": point.state_key,
                    "lineage": point.candidate_config or "unavailable",
                }
            )
    return pd.DataFrame(rows, columns=("x", "y", "z", "family", "status", "candidate_id", "state", "lineage"))


def candidate_support_figures(
    records: Iterable[CandidateBenchmark],
    *,
    show_view_directions: bool = False,
) -> tuple[go.Figure, go.Figure, go.Figure, go.Figure]:
    """Build ground-plane, 3-D, family-survival, and jitter figures.

    Args:
        records: Bounded factual-state records whose points already use the
            normalized target-aligned proposal-support frame.
        show_view_directions: Add short ground-plane camera-forward arrows for
            actor-valid candidates when their persisted direction is present.

    Returns:
        Ground-plane support, three-dimensional support, family-survival, and
        per-candidate view-jitter figures. The first two figures mark the
        factual expansion/root and persisted task target explicitly. The jitter view
        retains dotted caps only for bounded rows; any uncapped spherical row
        selects fixed yaw ``[-180, 180]`` and pitch ``[-90, 90]`` axes.
    """

    records = tuple(records)
    frame = _point_frame(records)
    ground = px.scatter(
        frame,
        x="x",
        y="y",
        color="family" if not frame.empty else None,
        symbol="status" if not frame.empty else None,
        hover_data=["candidate_id", "state"] if not frame.empty else None,
        title="Candidate centers in target-aligned support (ground plane)",
        labels={"x": "target-forward / d", "y": "target-lateral / d"},
    )
    ground.add_trace(
        go.Scatter(
            x=[0],
            y=[0],
            mode="markers",
            name="Factual expansion/root",
            marker={"symbol": "cross", "size": 12},
        )
    )
    targets = {
        (float(record.geometry["target_x"]), float(record.geometry["target_y"]))
        for record in records
        if record.geometry.get("target_x") is not None and record.geometry.get("target_y") is not None
    }
    if targets:
        ground.add_trace(
            go.Scatter(
                x=[target[0] for target in sorted(targets)],
                y=[target[1] for target in sorted(targets)],
                mode="markers",
                name="Persisted task target centre",
                marker={"symbol": "star", "size": 12},
            )
        )
    if show_view_directions:
        for record in records:
            for point in record.points:
                if not point.actor_valid or point.view_direction_xyz is None:
                    continue
                direction_x, direction_y, _ = point.view_direction_xyz
                norm = (direction_x**2 + direction_y**2) ** 0.5
                if norm <= 1e-9:
                    continue
                arrow_length = 0.04
                ground.add_annotation(
                    x=point.xyz[0] + arrow_length * direction_x / norm,
                    y=point.xyz[1] + arrow_length * direction_y / norm,
                    ax=point.xyz[0],
                    ay=point.xyz[1],
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

    unavailable_reasons = sorted(
        {
            reason
            for record in records
            if (reason := record.lineage.get("proposal_support_unavailable_reason")) is not None
        }
    )
    if unavailable_reasons:
        ground.add_annotation(
            text=f"proposal support unavailable: {', '.join(unavailable_reasons)}",
            x=0.01,
            y=0.99,
            xref="paper",
            yref="paper",
            showarrow=False,
        )

    support = go.Figure()
    if not frame.empty:
        support.add_trace(
            go.Scatter3d(
                x=frame.x,
                y=frame.y,
                z=frame.z,
                mode="markers",
                name="candidate support",
                marker={
                    "symbol": frame["status"].map({"selected": "diamond", "valid": "circle", "invalid": "x"}).tolist()
                },
                customdata=frame[["candidate_id", "family", "status", "lineage"]],
                hovertemplate="candidate=%{customdata[0]}<br>family=%{customdata[1]}<br>status=%{customdata[2]}<br>lineage=%{customdata[3]}<extra></extra>",
            )
        )
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
    targets_3d = {
        tuple(float(record.geometry[name]) for name in ("target_x", "target_y", "target_z"))
        for record in records
        if all(record.geometry.get(name) is not None for name in ("target_x", "target_y", "target_z"))
    }
    if targets_3d:
        support.add_trace(
            go.Scatter3d(
                x=[target[0] for target in sorted(targets_3d)],
                y=[target[1] for target in sorted(targets_3d)],
                z=[target[2] for target in sorted(targets_3d)],
                mode="markers",
                name="Persisted task target centre",
                marker={"symbol": "diamond", "size": 7},
            )
        )
    support.update_layout(
        title="Candidate centers in target-aligned support (3D)",
        scene_aspectmode="data",
        scene_camera={"eye": {"x": 1.5, "y": 1.5, "z": 1.2}},
    )
    if unavailable_reasons:
        support.add_annotation(
            text=f"proposal support unavailable: {', '.join(unavailable_reasons)}",
            x=0.01,
            y=0.99,
            xref="paper",
            yref="paper",
            showarrow=False,
        )

    survival_rows = []
    for record in records:
        for family in record.families:
            survival_rows.extend(
                [
                    {"family": family.family, "stage": stage, "count": count}
                    for stage, count in (
                        ("attempted", family.attempted),
                        ("valid", family.valid),
                        ("selected", family.selected),
                    )
                ]
            )
    survival = px.bar(
        pd.DataFrame(survival_rows, columns=("family", "stage", "count")),
        x="family",
        y="count",
        color="stage",
        barmode="group",
        title="Candidate family survival",
    )

    jitter_rows = []
    for record in records:
        for point in record.points:
            if point.view_jitter_yaw_deg is not None and point.view_jitter_pitch_deg is not None:
                jitter_rows.append(
                    {
                        "yaw": point.view_jitter_yaw_deg,
                        "pitch": point.view_jitter_pitch_deg,
                        "family": point.family,
                        "bounded": point.view_jitter_is_bounded,
                    }
                )
    jitter = px.scatter(
        pd.DataFrame(jitter_rows, columns=("yaw", "pitch", "family", "bounded")),
        x="yaw",
        y="pitch",
        color="family" if jitter_rows else None,
        symbol="bounded" if jitter_rows else None,
        title="Candidate view jitter",
        labels={"yaw": "yaw residual [deg]", "pitch": "pitch residual [deg]"},
    )
    for trace in jitter.data:
        trace.name = trace.name or "candidate jitter"
    bounded = [
        point
        for record in records
        for point in record.points
        if point.view_jitter_is_bounded is True
        and point.view_jitter_azimuth_limit_deg is not None
        and point.view_jitter_elevation_limit_deg is not None
    ]
    envelopes = {
        (
            cast(float, point.view_jitter_azimuth_limit_deg),
            cast(float, point.view_jitter_elevation_limit_deg),
        )
        for point in bounded
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
    if any(point.view_jitter_is_bounded is False for record in records for point in record.points):
        jitter.update_xaxes(range=[-180, 180])
        jitter.update_yaxes(range=[-90, 90])
        jitter.add_annotation(
            text="uncapped spherical support", x=0.01, y=0.99, xref="paper", yref="paper", showarrow=False
        )
    return ground, support, survival, jitter


__all__ = ["candidate_support_figures"]
