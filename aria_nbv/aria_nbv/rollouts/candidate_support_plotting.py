"""Pure Plotly views for target-aligned candidate-support evidence."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import cast

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .candidate_benchmark import CandidateBenchmark, CandidateFamilyPreflight

_BENCHMARK_FIGURE_TITLES = (
    "Candidate family attempted → valid → selected funnel",
    "Candidate family survival",
    "Candidate support (target-normalized ground plane)",
    "Candidate support (target-normalized 3D)",
    "Candidate view jitter (bounded boxes and uncapped spherical support)",
    "Candidate benchmark resource and timing summary",
)


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


def candidate_ground_support_figure(
    records: Iterable[CandidateBenchmark],
    *,
    show_view_directions: bool = False,
    family_colors: Mapping[str, str] | None = None,
) -> go.Figure:
    """Build the canonical target-aligned ground-plane support figure."""

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
        color_discrete_map=dict(family_colors or {}),
    )
    ground.add_trace(
        go.Scatter(
            x=[0],
            y=[0],
            mode="markers",
            name="Factual expansion/root",
            marker={"symbol": "cross", "size": 12, "color": "black"},
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
                marker={"symbol": "star", "size": 12, "color": "#9467bd"},
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
    return ground


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
    ground = candidate_ground_support_figure(records, show_view_directions=show_view_directions)

    unavailable_reasons = sorted(
        {
            reason
            for record in records
            if (reason := record.lineage.get("proposal_support_unavailable_reason")) is not None
        }
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


def candidate_benchmark_figures(
    records: Iterable[CandidateBenchmark],
    *,
    show_view_directions: bool = False,
) -> tuple[go.Figure, ...]:
    """Build the six stable scientific views of candidate benchmark facts.

    Runtime and peak GPU-memory values remain per-state observations on
    separate subplots. Peak memory is never summed across states, because each
    value is a high-water mark rather than an additive consumption quantity.
    Missing runtime or memory evidence is annotated independently.
    """

    records = tuple(records)
    if not records:
        figures = []
        for title in _BENCHMARK_FIGURE_TITLES[:5]:
            figure = go.Figure()
            figure.update_layout(title=title)
            figure.add_annotation(
                text="No matching benchmark candidates",
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
            )
            figures.append(figure)
        resources = _candidate_resource_figure(records)
        return (*figures, resources)

    attempted = sum(family.attempted for record in records for family in record.families)
    valid = sum(family.valid for record in records for family in record.families)
    selected = sum(family.selected for record in records for family in record.families)
    funnel = px.bar(
        pd.DataFrame(
            {
                "stage": ("attempted", "actor-valid", "selected"),
                "count": (attempted, valid, selected),
            }
        ),
        x="stage",
        y="count",
        title=_BENCHMARK_FIGURE_TITLES[0],
    )
    for trace in funnel.data:
        trace.name = trace.name or "candidate funnel"
    plane, support, survival, jitter = candidate_support_figures(
        records,
        show_view_directions=show_view_directions,
    )
    survival.update_layout(title=_BENCHMARK_FIGURE_TITLES[1])
    plane.update_layout(title=_BENCHMARK_FIGURE_TITLES[2])
    support.update_layout(title=_BENCHMARK_FIGURE_TITLES[3])
    jitter.update_layout(title=_BENCHMARK_FIGURE_TITLES[4])
    return funnel, survival, plane, support, jitter, _candidate_resource_figure(records)


def _candidate_resource_figure(records: tuple[CandidateBenchmark, ...]) -> go.Figure:
    """Plot per-state runtime and peak-memory observations without aggregation."""

    figure = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=False,
        vertical_spacing=0.2,
        subplot_titles=("Runtime observations", "Peak GPU-memory observations"),
    )
    runtimes = [
        (record.scene_key, record.state_key, f"{record.scene_key}<br>{record.state_key}", value)
        for record in records
        if (value := record.timings_ms.get("total_ms")) is not None
    ]
    memory = [
        (record.scene_key, record.state_key, f"{record.scene_key}<br>{record.state_key}", value)
        for record in records
        if (value := record.resources.get("gpu_memory_mb")) is not None
    ]
    if runtimes:
        figure.add_trace(
            go.Bar(
                x=[identity for _, _, identity, _ in runtimes],
                y=[value for _, _, _, value in runtimes],
                customdata=[(scene, state) for scene, state, _, _ in runtimes],
                hovertemplate=(
                    "scene=%{customdata[0]}<br>state=%{customdata[1]}<br>runtime=%{y:.3f} ms<extra></extra>"
                ),
                name="runtime per state",
            ),
            row=1,
            col=1,
        )
    else:
        figure.add_annotation(
            text="unavailable: no persisted runtime",
            x=0.5,
            y=0.82,
            xref="paper",
            yref="paper",
            showarrow=False,
        )
    if memory:
        figure.add_trace(
            go.Bar(
                x=[identity for _, _, identity, _ in memory],
                y=[value for _, _, _, value in memory],
                customdata=[(scene, state) for scene, state, _, _ in memory],
                hovertemplate=(
                    "scene=%{customdata[0]}<br>state=%{customdata[1]}<br>peak GPU memory=%{y:.3f} MB<extra></extra>"
                ),
                name="peak GPU memory per state",
            ),
            row=2,
            col=1,
        )
    else:
        figure.add_annotation(
            text="unavailable: no persisted peak GPU memory",
            x=0.5,
            y=0.18,
            xref="paper",
            yref="paper",
            showarrow=False,
        )
    if not runtimes and not memory:
        figure.add_annotation(
            text="unavailable: no persisted timing/resource facts",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
        )
    figure.update_yaxes(title_text="runtime [ms]", row=1, col=1)
    figure.update_yaxes(title_text="peak GPU memory [MB]", row=2, col=1)
    figure.update_xaxes(tickangle=-25, automargin=True)
    figure.update_xaxes(title_text="scene / factual state", row=2, col=1)
    figure.update_layout(title=_BENCHMARK_FIGURE_TITLES[5], barmode="group")
    return figure


def candidate_family_preflight_figures(result: CandidateFamilyPreflight) -> tuple[go.Figure, go.Figure]:
    """Plot applicability-aware survival and per-family stage funnels.

    Applicable cells encode selected/attempted survival. Inapplicable cells use
    an explicit ``N/A`` annotation and unknown legacy applicability uses ``?``;
    neither is silently mapped to zero support. Hover data retains exact
    attempted, valid, selected, denominator, and failure provenance.
    """

    rows = [
        {
            "state": state,
            "family": cell.family,
            "applicable": cell.applicable,
            "attempted": cell.attempted,
            "valid": cell.valid,
            "selected": cell.selected,
            "denominator": cell.denominator,
            "support_failure": cell.support_failure or "",
            "survival": None if cell.applicable is not True or cell.attempted == 0 else cell.selected / cell.attempted,
            "label": "N/A"
            if cell.applicable is False
            else "?"
            if cell.applicable is None
            else "0"
            if cell.attempted == 0
            else f"{cell.selected / cell.attempted:.0%}",
        }
        for state, cell in result.cells
    ]
    frame = pd.DataFrame(rows)
    states = sorted(frame["state"].unique()) if not frame.empty else []
    families = sorted(frame["family"].unique()) if not frame.empty else []
    heatmap = go.Figure()
    if rows:
        indexed = frame.set_index(["state", "family"])
        z = [[indexed.loc[(state, family), "survival"] for family in families] for state in states]
        text = [[indexed.loc[(state, family), "label"] for family in families] for state in states]
        custom = [
            [
                [
                    indexed.loc[(state, family), "applicable"],
                    indexed.loc[(state, family), "attempted"],
                    indexed.loc[(state, family), "valid"],
                    indexed.loc[(state, family), "selected"],
                    indexed.loc[(state, family), "denominator"],
                    indexed.loc[(state, family), "support_failure"],
                ]
                for family in families
            ]
            for state in states
        ]
        heatmap.add_trace(
            go.Heatmap(
                x=families,
                y=states,
                z=z,
                text=text,
                texttemplate="%{text}",
                customdata=custom,
                zmin=0,
                zmax=1,
                colorbar={"title": "selected / attempted"},
                hovertemplate=(
                    "state=%{y}<br>family=%{x}<br>applicable=%{customdata[0]}"
                    "<br>attempted=%{customdata[1]}<br>valid=%{customdata[2]}"
                    "<br>selected=%{customdata[3]}<br>denominator=%{customdata[4]}"
                    "<br>support failure=%{customdata[5]}<extra></extra>"
                ),
            )
        )
    else:
        heatmap.add_annotation(text="No candidate-family cells", x=0.5, y=0.5, showarrow=False)
    heatmap.update_layout(title="State × family applicability and selected survival")

    funnel_rows = [
        {"family": cell.family, "stage": stage, "count": count, "state": state}
        for state, cell in result.cells
        if cell.applicable is True
        for stage, count in (("attempted", cell.attempted), ("valid", cell.valid), ("selected", cell.selected))
    ]
    funnel = px.bar(
        pd.DataFrame(funnel_rows, columns=("family", "stage", "count", "state")),
        x="family",
        y="count",
        color="stage",
        facet_row="state" if funnel_rows else None,
        barmode="group",
        title="Applicable family attempted → valid → selected funnels",
    )
    return heatmap, funnel


__all__ = [
    "candidate_benchmark_figures",
    "candidate_family_preflight_figures",
    "candidate_ground_support_figure",
    "candidate_support_figures",
]
