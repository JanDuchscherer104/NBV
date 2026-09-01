"""Pure Plotly views for target-aligned candidate-support evidence."""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from typing import cast

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .candidate_benchmark import CandidateBenchmark, CandidateFamilyPreflight
from .candidate_evidence import (
    CandidateEvidenceRow,
    CandidateEvidenceSnapshot,
    CandidateFactAvailability,
    CandidateProjectionUnavailableReason,
    CandidateRolloutOverlay,
)
from .candidate_plotting import candidate_support_plot_models

_BENCHMARK_FIGURE_TITLES = (
    "Candidate family attempted → valid → selected funnel",
    "Candidate family survival",
    "Candidate support (target-normalized ground plane)",
    "Candidate support (target-normalized 3D)",
    "Candidate view jitter (bounded boxes and uncapped spherical support)",
    "Candidate benchmark resource and timing summary",
)


def _benchmark_snapshot(record: CandidateBenchmark) -> CandidateEvidenceSnapshot:
    """Project legacy benchmark facts without upgrading them to semantic identity."""

    if len(record.points) != sum(family.attempted for family in record.families):
        raise ValueError("legacy benchmark lacks a complete attempted-row table")
    phase_a_action_shell = record.lineage.get("selection_semantics") == "final_valid_action_shell"
    unavailable_reason = record.lineage.get("proposal_support_unavailable_reason")
    target: tuple[float, float, float] | None = (
        (
            float(record.geometry["target_x"]),
            float(record.geometry["target_y"]),
            float(record.geometry["target_z"]),
        )
        if all(record.geometry.get(name) is not None for name in ("target_x", "target_y", "target_z"))
        else None
    )
    rows = tuple(
        CandidateEvidenceRow(
            attempted_index=index,
            candidate_id=point.candidate_id,
            center_world_m=None,
            world_pose_availability=CandidateFactAvailability.LEGACY_MISSING,
            world_pose_unavailable_reason=None,
            center_target_normalized=(None if unavailable_reason is not None else point.xyz),
            gaze_target_unit=(None if unavailable_reason is not None else point.view_direction_xyz),
            projection_availability=(
                CandidateFactAvailability.UNAVAILABLE
                if unavailable_reason is not None
                else CandidateFactAvailability.AVAILABLE
            ),
            projection_unavailable_reason=(
                CandidateProjectionUnavailableReason.TARGET_MISSING if unavailable_reason is not None else None
            ),
            hard_valid=point.actor_valid,
            action=point.actor_valid,
            selected=(None if phase_a_action_shell else point.selected),
            semantic_group_id=None,
            center_family_id=None,
            gaze_family_id=None,
            candidate_family_id=None,
            legacy_family_label=point.family,
            legacy_invalid_reason_bitset=None,
            legacy_primary_invalid_reason=None,
            legacy_admission_measurements=(),
            center_id=None,
            position_pair_id=None,
            gaze_variant_id=None,
            legacy_position_pair_id=None,
            legacy_gaze_variant_id=None,
            attempt_round_id=None,
            draw_id=None,
            proposal_key=None,
            proposal_probability=None,
            view_jitter_yaw_deg=point.view_jitter_yaw_deg,
            view_jitter_pitch_deg=point.view_jitter_pitch_deg,
            view_jitter_is_bounded=point.view_jitter_is_bounded,
            view_jitter_azimuth_limit_deg=point.view_jitter_azimuth_limit_deg,
            view_jitter_elevation_limit_deg=point.view_jitter_elevation_limit_deg,
            target_frame_identity=None,
            admission=(),
            semantic_lineage_availability=CandidateFactAvailability.LEGACY_MISSING,
            action_availability=CandidateFactAvailability.AVAILABLE,
            selection_availability=(
                CandidateFactAvailability.UNAVAILABLE if phase_a_action_shell else CandidateFactAvailability.AVAILABLE
            ),
            proposal_key_availability=CandidateFactAvailability.LEGACY_MISSING,
            proposal_probability_availability=CandidateFactAvailability.LEGACY_MISSING,
            jitter_availability=(
                CandidateFactAvailability.AVAILABLE
                if all(
                    value is not None
                    for value in (
                        point.view_jitter_yaw_deg,
                        point.view_jitter_pitch_deg,
                        point.view_jitter_is_bounded,
                        point.view_jitter_azimuth_limit_deg,
                        point.view_jitter_elevation_limit_deg,
                    )
                )
                else CandidateFactAvailability.LEGACY_MISSING
            ),
            admission_availability=CandidateFactAvailability.LEGACY_MISSING,
            generation_frame_availability=CandidateFactAvailability.LEGACY_MISSING,
            legacy_family_label_availability=CandidateFactAvailability.AVAILABLE,
            legacy_admission_availability=CandidateFactAvailability.LEGACY_MISSING,
            legacy_pair_lineage_availability=CandidateFactAvailability.LEGACY_MISSING,
        )
        for index, point in enumerate(record.points)
    )
    return CandidateEvidenceSnapshot(
        schema_revision="candidate-evidence-snapshot-v1",
        state_key=record.state_key,
        rows=rows,
        completion_mode=None,
        attempted_count=len(rows),
        valid_count=sum(row.hard_valid for row in rows),
        action_count=sum(bool(row.action) for row in rows),
        selected_count=(None if phase_a_action_shell else sum(bool(row.selected) for row in rows)),
        projection_frame_identity=(None if unavailable_reason is not None else f"legacy-benchmark:{record.state_key}"),
        target_target_normalized=(None if unavailable_reason is not None else target),
        candidate_program_hash=None,
        request_binding_hash=None,
        execution_hash=None,
        overlay=CandidateRolloutOverlay.unavailable(),
        completion_availability=CandidateFactAvailability.PARTIAL,
        projection_frame_availability=(
            CandidateFactAvailability.UNAVAILABLE
            if unavailable_reason is not None
            else CandidateFactAvailability.AVAILABLE
        ),
        projection_unavailable_reason=(
            CandidateProjectionUnavailableReason.TARGET_MISSING if unavailable_reason is not None else None
        ),
        program_hash_availability=CandidateFactAvailability.LEGACY_MISSING,
        request_hash_availability=CandidateFactAvailability.LEGACY_MISSING,
        execution_hash_availability=CandidateFactAvailability.LEGACY_MISSING,
    )


def _snapshot_support_figures(
    records: Iterable[CandidateBenchmark],
    *,
    show_view_directions: bool,
) -> tuple[go.Figure, go.Figure, go.Figure, go.Figure]:
    records = tuple(records)
    complete = tuple(
        record
        for record in records
        if len(record.points) == sum(family.attempted for family in record.families)
        and record.lineage.get("proposal_support_unavailable_reason") is None
        and all(record.geometry.get(name) is not None for name in ("target_x", "target_y", "target_z"))
    )
    snapshots = tuple(_benchmark_snapshot(record) for record in complete)
    models = candidate_support_plot_models(snapshots, show_view_directions=show_view_directions)
    figures = [model.build_figure() for model in models]
    incomplete_with_points = tuple(
        record
        for record in records
        if record not in complete
        and record.points
        and record.lineage.get("proposal_support_unavailable_reason") is None
    )
    if incomplete_with_points:
        _append_legacy_known_point_traces(
            figures,
            incomplete_with_points,
            show_view_directions=show_view_directions,
        )
    survival_rows = [
        {"family": family.family, "stage": stage, "count": count}
        for record in records
        for family in record.families
        for stage, count in (
            ("attempted", family.attempted),
            ("valid", family.valid),
            ("selected", family.selected),
        )
    ]
    figures[2] = px.bar(
        pd.DataFrame(survival_rows, columns=("family", "stage", "count")),
        x="family",
        y="count",
        color="stage",
        barmode="group",
        title="Candidate family survival",
    )
    unavailable_reasons = sorted(
        {
            reason
            for record in records
            if (reason := record.lineage.get("proposal_support_unavailable_reason")) is not None
        }
    )
    if unavailable_reasons:
        for figure in figures[:2]:
            figure.add_annotation(
                text=f"proposal support unavailable: {', '.join(unavailable_reasons)}",
                x=0.01,
                y=0.99,
                xref="paper",
                yref="paper",
                showarrow=False,
            )
    for figure in figures[:2]:
        for trace in figure.data:
            if isinstance(trace.name, str):
                trace.name = trace.name.replace("action", "valid").replace(
                    "Task target centre", "Persisted task target centre"
                )
    for trace in figures[1].data:
        if trace.customdata is None:
            continue
        customdata = np.asarray(trace.customdata, dtype=object)
        if customdata.ndim == 2 and customdata.shape[1] >= 3:
            customdata[:, 2] = np.where(customdata[:, 2] == "action", "valid", customdata[:, 2])
            trace.customdata = customdata
    for figure, title in zip(
        figures,
        (
            "Candidate centers in target-aligned support (ground plane)",
            "Candidate centers in target-aligned support (3D)",
            "Candidate family survival",
            "Candidate view jitter",
        ),
        strict=True,
    ):
        figure.update_layout(title=title)
    return cast(tuple[go.Figure, go.Figure, go.Figure, go.Figure], tuple(figures))


def _append_legacy_known_point_traces(
    figures: list[go.Figure],
    records: tuple[CandidateBenchmark, ...],
    *,
    show_view_directions: bool,
) -> None:
    """Retain known legacy point traces without inventing missing attempted rows."""

    ground, support, _, jitter = figures
    for figure in (ground, support, jitter):
        figure.layout.annotations = tuple(
            annotation
            for annotation in figure.layout.annotations or ()
            if annotation.text != "No matching benchmark candidates"
        )
    ground.data = tuple(trace for trace in ground.data if trace.x is not None and len(trace.x) > 0)
    jitter.data = tuple(trace for trace in jitter.data if trace.x is not None and len(trace.x) > 0)
    rows = [
        {
            "x": point.xyz[0],
            "y": point.xyz[1],
            "z": point.xyz[2],
            "family": point.family,
            "status": "selected" if point.selected else "valid" if point.actor_valid else "invalid",
            "candidate_id": point.candidate_id,
            "state": point.state_key,
            "lineage": point.candidate_config or "unavailable",
        }
        for record in records
        for point in record.points
    ]
    frame = pd.DataFrame(
        rows,
        columns=("x", "y", "z", "family", "status", "candidate_id", "state", "lineage"),
    )
    legacy_ground = px.scatter(
        frame,
        x="x",
        y="y",
        color="family",
        symbol="status",
        hover_data=["candidate_id", "state"],
    )
    for trace in legacy_ground.data:
        ground.add_trace(trace)
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
        {
            tuple(float(record.geometry[name]) for name in ("target_x", "target_y", "target_z"))
            for record in records
            if all(record.geometry.get(name) is not None for name in ("target_x", "target_y", "target_z"))
        }
    )
    if targets:
        ground.add_trace(
            go.Scatter(
                x=[target[0] for target in targets],
                y=[target[1] for target in targets],
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
                if norm <= 1.0e-9:
                    continue
                ground.add_annotation(
                    x=point.xyz[0] + 0.04 * direction_x / norm,
                    y=point.xyz[1] + 0.04 * direction_y / norm,
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
    support.add_trace(
        go.Scatter3d(
            x=frame.x,
            y=frame.y,
            z=frame.z,
            mode="markers",
            name="candidate support",
            marker={"symbol": frame["status"].map({"selected": "diamond", "valid": "circle", "invalid": "x"}).tolist()},
            customdata=frame[["candidate_id", "family", "status", "lineage"]],
            hovertemplate=(
                "candidate=%{customdata[0]}<br>family=%{customdata[1]}"
                "<br>status=%{customdata[2]}<br>lineage=%{customdata[3]}<extra></extra>"
            ),
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
    if targets:
        support.add_trace(
            go.Scatter3d(
                x=[target[0] for target in targets],
                y=[target[1] for target in targets],
                z=[target[2] for target in targets],
                mode="markers",
                name="Persisted task target centre",
                marker={"symbol": "diamond", "size": 7},
            )
        )
    jitter_rows = [
        {
            "yaw": point.view_jitter_yaw_deg,
            "pitch": point.view_jitter_pitch_deg,
            "family": point.family,
            "bounded": point.view_jitter_is_bounded,
        }
        for record in records
        for point in record.points
        if point.view_jitter_yaw_deg is not None and point.view_jitter_pitch_deg is not None
    ]
    if jitter_rows:
        legacy_jitter = px.scatter(
            pd.DataFrame(jitter_rows),
            x="yaw",
            y="pitch",
            color="family",
            symbol="bounded",
        )
        for trace in legacy_jitter.data:
            trace.name = trace.name or "candidate jitter"
            jitter.add_trace(trace)
    envelopes = {
        (point.view_jitter_azimuth_limit_deg, point.view_jitter_elevation_limit_deg)
        for record in records
        for point in record.points
        if point.view_jitter_is_bounded is True
        and point.view_jitter_azimuth_limit_deg is not None
        and point.view_jitter_elevation_limit_deg is not None
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
            text="uncapped spherical support",
            x=0.01,
            y=0.99,
            xref="paper",
            yref="paper",
            showarrow=False,
        )


def candidate_ground_support_figure(
    records: Iterable[CandidateBenchmark],
    *,
    show_view_directions: bool = False,
    family_colors: Mapping[str, str] | None = None,
) -> go.Figure:
    """Compatibility projection through the canonical snapshot-only plot core."""

    figure = _snapshot_support_figures(records, show_view_directions=show_view_directions)[0]
    if family_colors:
        for trace in figure.data:
            if trace.name in family_colors and hasattr(trace, "marker"):
                trace.marker.color = family_colors[trace.name]
    return figure


def candidate_support_figures(
    records: Iterable[CandidateBenchmark],
    *,
    show_view_directions: bool = False,
) -> tuple[go.Figure, go.Figure, go.Figure, go.Figure]:
    """Compatibility projection through the canonical snapshot-only plot core."""

    return _snapshot_support_figures(records, show_view_directions=show_view_directions)


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


def candidate_family_preflight_figures(
    result: CandidateFamilyPreflight,
    *,
    funnel_identities: Collection[tuple[str, str]] | None = None,
) -> tuple[go.Figure, go.Figure]:
    """Plot applicability-aware survival and per-family stage funnels.

    Applicable cells encode selected/attempted survival. Inapplicable cells use
    an explicit ``N/A`` annotation and unknown legacy applicability uses ``?``;
    neither is silently mapped to zero support. Hover data retains exact
    attempted, valid, selected, denominator, and failure provenance.
    """

    rows = [
        {
            "scene": scene,
            "state": state,
            "identity": f"{scene} · {state}",
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
        for scene, state, cell in result.cells
    ]
    frame = pd.DataFrame(rows)
    identities = sorted({(str(row["scene"]), str(row["state"])) for row in rows})
    identity_labels = {identity: f"{identity[0]} · {identity[1]}" for identity in identities}
    families = sorted(frame["family"].unique()) if not frame.empty else []
    heatmap = go.Figure()
    if rows:
        indexed = frame.set_index(["scene", "state", "family"])
        z = [[indexed.loc[(*identity, family), "survival"] for family in families] for identity in identities]
        text = [[indexed.loc[(*identity, family), "label"] for family in families] for identity in identities]
        custom = [
            [
                [
                    identity[0],
                    identity[1],
                    family,
                    indexed.loc[(*identity, family), "applicable"],
                    indexed.loc[(*identity, family), "attempted"],
                    indexed.loc[(*identity, family), "valid"],
                    indexed.loc[(*identity, family), "selected"],
                    indexed.loc[(*identity, family), "denominator"],
                    indexed.loc[(*identity, family), "support_failure"],
                ]
                for family in families
            ]
            for identity in identities
        ]
        heatmap.add_trace(
            go.Heatmap(
                x=families,
                y=[identity_labels[identity] for identity in identities],
                z=z,
                text=text,
                texttemplate="%{text}",
                customdata=custom,
                zmin=0,
                zmax=1,
                colorbar={"title": "selected / attempted"},
                hovertemplate=(
                    "scene=%{customdata[0]}<br>state=%{customdata[1]}<br>family=%{customdata[2]}"
                    "<br>applicable=%{customdata[3]}<br>attempted=%{customdata[4]}"
                    "<br>valid=%{customdata[5]}<br>selected=%{customdata[6]}"
                    "<br>denominator=%{customdata[7]}<br>support failure=%{customdata[8]}<extra></extra>"
                ),
            )
        )
        for state_index, identity in enumerate(identities):
            for family_index, family in enumerate(families):
                if indexed.loc[(*identity, family), "applicable"] is not False:
                    continue
                for offset in (-0.4, -0.2, 0.0, 0.2, 0.4):
                    heatmap.add_shape(
                        type="line",
                        x0=family_index - 0.45,
                        x1=family_index + 0.45,
                        y0=state_index + offset - 0.35,
                        y1=state_index + offset + 0.35,
                        line={"color": "rgba(70,70,70,0.65)", "width": 1},
                        layer="above",
                    )
    else:
        heatmap.add_annotation(text="No candidate-family cells", x=0.5, y=0.5, showarrow=False)
    heatmap.update_layout(title="State × family applicability and selected survival")

    retained_funnel_identities = set(funnel_identities) if funnel_identities is not None else None
    funnel_rows = [
        {
            "family": cell.family,
            "stage": stage,
            "count": count,
            "state": f"{scene} · {state}",
        }
        for scene, state, cell in result.cells
        if retained_funnel_identities is None or (scene, state) in retained_funnel_identities
        if cell.applicable is True
        for stage, count in (("attempted", cell.attempted), ("valid", cell.valid), ("selected", cell.selected))
    ]
    funnel = px.bar(
        pd.DataFrame(funnel_rows, columns=("family", "stage", "count", "state")),
        x="family",
        y="count",
        color="stage",
        facet_row="state" if funnel_rows else None,
        facet_row_spacing=(min(0.03, 0.8 / (len(identities) - 1)) if funnel_rows and len(identities) > 1 else None),
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
