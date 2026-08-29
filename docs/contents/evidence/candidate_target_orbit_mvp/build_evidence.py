"""Rebuild the target-orbit pilot summary and plots from reduced candidate rows.

The committed JSONL is the portable evidence input. Passing both raw Zarr
stores refreshes that input through the canonical proposal-support reducer;
omitting them rebuilds the public summary and plots without private data paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from collections.abc import Collection
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from aria_nbv.rollouts.candidate_benchmark import (
    CandidateBenchmark,
    CandidateFamilyCounts,
    CandidatePoint,
    candidate_support_metrics,
)
from aria_nbv.rollouts.candidate_support_plotting import candidate_ground_support_figure

HERE = Path(__file__).resolve().parent
ROWS_PATH = HERE / "candidate-rows.jsonl"
SUMMARY_PATH = HERE / "summary.json"
MANIFEST_PATH = HERE / "manifest.json"
HTML_PATH = HERE / "candidate-centers.html"
PNG_PATH = HERE / "candidate-centers.png"
ARROW_HTML_PATH = HERE / "candidate-centers-with-view-directions.html"
ARROW_PNG_PATH = HERE / "candidate-centers-with-view-directions.png"
PROFILES = ("realistic_core", "target_orbit_mvp")
PROFILE_FAMILIES = {
    "realistic_core": frozenset(
        {"forward_local", "target_bearing_local", "lateral_target_bypass"}
    ),
    "target_orbit_mvp": frozenset(
        {
            "forward_local",
            "target_bearing_local",
            "target_orbit",
            "lateral_target_bypass",
        }
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_profile(profile: str, store: Path) -> list[dict[str, Any]]:
    from aria_nbv.rollouts import RolloutZarrStoreReader
    from aria_nbv.rollouts.inspection import (
        candidate_audit_rows,
        proposal_support_geometry,
    )

    reader = RolloutZarrStoreReader(store)
    projection = proposal_support_geometry(reader, max_candidates=None)
    if projection.truncated or projection.issues:
        raise ValueError(f"{profile} projection is incomplete: {projection.issues}")
    points = {point.candidate_row_id: point for point in projection.points}
    frames = {frame.frame_id: frame for frame in projection.frames}
    rows = []
    for audit in candidate_audit_rows(reader):
        candidate_id = int(audit["candidate_row_id"])
        point = points[candidate_id]
        frame = frames[point.frame_id]
        rows.append(
            {
                "profile": profile,
                "scene": str(audit["scene"]),
                "rollout_row_id": int(audit["rollout_row_id"]),
                "step_row_id": int(audit["step_row_id"]),
                "candidate_row_id": candidate_id,
                "family": str(audit["mixture"]),
                "position": str(audit["position"]),
                "actor_valid": bool(audit["actor_action"]),
                "selected": bool(audit["selected"]),
                "target_root_gain": audit["target_root_gain"],
                "target_view_evaluated": bool(audit["target_view_evaluated"]),
                "target_center_in_calibrated_image": audit["target_in_fov"],
                "view_jitter_yaw_deg": audit["view_jitter_yaw_deg"],
                "view_jitter_pitch_deg": audit["view_jitter_pitch_deg"],
                "view_jitter_is_bounded": audit["view_jitter_is_bounded"],
                "view_jitter_azimuth_limit_deg": audit["view_jitter_azimuth_limit_deg"],
                "view_jitter_elevation_limit_deg": audit[
                    "view_jitter_elevation_limit_deg"
                ],
                "x": point.x,
                "y": point.y,
                "z": point.z,
                "target_x": frame.target_x,
                "target_y": frame.target_y,
                "target_z": frame.target_z,
                "view_direction_x": point.camera_forward_x,
                "view_direction_y": point.camera_forward_y,
                "view_direction_z": point.camera_forward_z,
            }
        )
    return rows


def _write_rows(rows: list[dict[str, Any]]) -> None:
    ordered = sorted(
        rows,
        key=lambda row: (
            PROFILES.index(row["profile"]),
            row["scene"],
            row["rollout_row_id"],
            row["step_row_id"],
            row["candidate_row_id"],
        ),
    )
    ROWS_PATH.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in ordered
        ),
        encoding="utf-8",
    )


def _read_rows() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in ROWS_PATH.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _read_expected_states() -> tuple[tuple[str, int, int], ...]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return tuple(
        (
            str(state["scene"]),
            int(state["rollout_row_id"]),
            int(state["step_row_id"]),
        )
        for state in manifest["evidence_population"]["states"]
    )


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _candidate_points(rows: Collection[dict[str, Any]]) -> tuple[CandidatePoint, ...]:
    """Project portable rows into the canonical candidate-support DTO."""

    points = []
    for row in rows:
        direction_values = tuple(row.get(f"view_direction_{axis}") for axis in "xyz")
        direction = (
            None
            if any(value is None for value in direction_values)
            else tuple(float(value) for value in direction_values)
        )
        xyz = tuple(float(row[axis]) for axis in "xyz")
        target_relative = tuple(
            float(row[axis]) - float(row[f"target_{axis}"]) for axis in "xyz"
        )
        state_key = (
            f"rollout:{int(row['rollout_row_id'])}/step:{int(row['step_row_id'])}"
        )
        points.append(
            CandidatePoint(
                candidate_id=int(row["candidate_row_id"]),
                xyz=xyz,
                family=str(row["family"]),
                position=str(row["position"]),
                actor_valid=bool(row["actor_valid"]),
                selected=bool(row["selected"]),
                state_key=state_key,
                target_relative_xyz=target_relative,
                view_direction_xyz=direction,
                view_jitter_yaw_deg=row["view_jitter_yaw_deg"],
                view_jitter_pitch_deg=row["view_jitter_pitch_deg"],
                view_jitter_is_bounded=row["view_jitter_is_bounded"],
                view_jitter_azimuth_limit_deg=row["view_jitter_azimuth_limit_deg"],
                view_jitter_elevation_limit_deg=row["view_jitter_elevation_limit_deg"],
            )
        )
    return tuple(points)


def _profile_benchmarks(
    rows: Collection[dict[str, Any]],
) -> tuple[CandidateBenchmark, ...]:
    """Build state records consumed by the shared candidate-support plot owner."""

    grouped: dict[tuple[str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[
            (str(row["scene"]), int(row["rollout_row_id"]), int(row["step_row_id"]))
        ].append(row)
    records = []
    for (scene, rollout_id, step_id), state_rows in sorted(grouped.items()):
        points = _candidate_points(state_rows)
        families = []
        for family in sorted({point.family for point in points}):
            family_points = [point for point in points if point.family == family]
            families.append(
                CandidateFamilyCounts(
                    family=family,
                    applicable=True,
                    attempted=len(family_points),
                    valid=sum(point.actor_valid for point in family_points),
                    selected=sum(point.selected for point in family_points),
                    denominator=len(family_points),
                )
            )
        targets = {
            tuple(float(row[f"target_{axis}"]) for axis in "xyz") for row in state_rows
        }
        if len(targets) != 1:
            raise ValueError(
                f"portable evidence state {(scene, rollout_id, step_id)!r} spans multiple targets"
            )
        target_x, target_y, target_z = targets.pop()
        records.append(
            CandidateBenchmark(
                state_key=f"rollout:{rollout_id}/step:{step_id}",
                scene_key=scene,
                families=tuple(families),
                geometry={
                    "target_x": target_x,
                    "target_y": target_y,
                    "target_z": target_z,
                },
                candidate_ids=tuple(point.candidate_id for point in points),
                coordinates=tuple(point.xyz for point in points),
                lineage={"family_identity": "mixture_component"},
                points=points,
            )
        )
    return tuple(records)


def _state_metrics(
    rows: list[dict[str, Any]], families: Collection[str]
) -> dict[str, float | int | None]:
    points = _candidate_points(rows)
    valid = [row for row in rows if row["actor_valid"]]
    gains = [
        float(row["target_root_gain"])
        for row in valid
        if row["target_root_gain"] is not None
    ]
    evaluated = [row for row in rows if row["target_view_evaluated"]]
    support = candidate_support_metrics(
        points,
        configured_families=families,
        projected_target_centers=sum(
            row["target_center_in_calibrated_image"] is True for row in evaluated
        ),
        total_target_centers=len(evaluated),
    )
    jitter_count = int(support["view_jitter_evaluated_count"] or 0)
    bounded_count = int(support["view_jitter_bounded_count"] or 0)
    return {
        "actor_valid_fraction": support["actor_valid_fraction"] if rows else 0.0,
        "valid_count": int(support["per_state_valid_support"] or 0),
        "family_zero_rate": support["zero_valid_family_state_rate"],
        "family_zero_count": int(support["zero_valid_family_count"] or 0),
        "side_balance": support["target_side_count_balance"],
        "side_positive_count": int(support["target_side_positive_count"] or 0),
        "side_negative_count": int(support["target_side_negative_count"] or 0),
        "side_neutral_count": int(support["target_side_neutral_count"] or 0),
        "side_balance_undefined": int(support["target_side_balance_undefined"] or 0),
        "orbit_span_deg": support["target_relative_orbit_span_deg"],
        "best_target_root_gain": max(gains) if gains else None,
        "oracle_opportunity_undefined": int(not gains),
        "projection_fraction": support["target_center_projection_fraction"],
        "projection_undefined": int(not evaluated),
        "jitter_count": jitter_count,
        "bounded_jitter_count": bounded_count,
        "uncapped_spherical_count": int(support["uncapped_spherical_count"] or 0),
        "jitter_nonzero_fraction": support["nonzero_jitter_fraction"],
        "bounded_jitter_declaration_fraction": support[
            "bounded_jitter_declaration_fraction"
        ],
        "bounded_jitter_cap_compliance_fraction": support[
            "bounded_jitter_cap_compliance_fraction"
        ],
        "jitter_undefined": int(jitter_count == 0),
        "bounded_jitter_compliance_undefined": int(bounded_count == 0),
    }


def _profile_summary(
    rows: list[dict[str, Any]],
    *,
    profile: str,
    expected_states: Collection[tuple[str, int, int]],
) -> dict[str, Any]:
    families = PROFILE_FAMILIES[profile]
    states: dict[tuple[str, int, int], list[dict[str, Any]]] = {
        state: [] for state in expected_states
    }
    for row in rows:
        state = (
            str(row["scene"]),
            int(row["rollout_row_id"]),
            int(row["step_row_id"]),
        )
        if state not in states:
            raise ValueError(f"unexpected evidence state for {profile}: {state}")
        states[state].append(row)
    by_scene: dict[str, list[dict[str, float | int | None]]] = defaultdict(list)
    state_values = []
    for (scene, _, _), state_rows in sorted(states.items()):
        value = _state_metrics(state_rows, families)
        state_values.append(value)
        by_scene[scene].append(value)

    def scene_macro(key: str) -> float | None:
        scene_values = []
        for values in by_scene.values():
            finite = [float(value[key]) for value in values if value[key] is not None]
            if finite:
                scene_values.append(sum(finite) / len(finite))
        return _mean(scene_values)

    def undefined_scene_count(key: str) -> int:
        return sum(
            not any(value[key] is not None for value in values)
            for values in by_scene.values()
        )

    evaluated = [row for row in rows if row["target_view_evaluated"]]
    return {
        "actor_valid_count": sum(row["actor_valid"] for row in rows),
        "actor_valid_fraction": scene_macro("actor_valid_fraction"),
        "family_state_pair_count": len(families) * len(states),
        "family_zero_valid_state_count": sum(
            int(value["family_zero_count"]) for value in state_values
        ),
        "family_zero_valid_state_rate": scene_macro("family_zero_rate"),
        "mean_state_best_target_root_gain": scene_macro("best_target_root_gain"),
        "oracle_opportunity_undefined_state_count": sum(
            int(value["oracle_opportunity_undefined"]) for value in state_values
        ),
        "oracle_opportunity_undefined_scene_count": undefined_scene_count(
            "best_target_root_gain"
        ),
        "mean_target_side_count_balance": scene_macro("side_balance"),
        "target_side_positive_count": sum(
            int(value["side_positive_count"]) for value in state_values
        ),
        "target_side_negative_count": sum(
            int(value["side_negative_count"]) for value in state_values
        ),
        "target_side_neutral_count": sum(
            int(value["side_neutral_count"]) for value in state_values
        ),
        "target_side_balance_undefined_state_count": sum(
            int(value["side_balance_undefined"]) for value in state_values
        ),
        "target_side_balance_undefined_scene_count": undefined_scene_count(
            "side_balance"
        ),
        "mean_circular_target_orbit_span_deg": scene_macro("orbit_span_deg"),
        "target_orbit_span_undefined_state_count": sum(
            value["orbit_span_deg"] is None for value in state_values
        ),
        "target_orbit_span_undefined_scene_count": undefined_scene_count(
            "orbit_span_deg"
        ),
        "target_center_inside_calibrated_image_count": sum(
            row["target_center_in_calibrated_image"] is True for row in evaluated
        ),
        "target_center_inside_calibrated_image_fraction": scene_macro(
            "projection_fraction"
        ),
        "target_center_projection_undefined_state_count": sum(
            int(value["projection_undefined"]) for value in state_values
        ),
        "target_center_projection_undefined_scene_count": undefined_scene_count(
            "projection_fraction"
        ),
        "view_jitter_evaluated_count": sum(
            int(value["jitter_count"]) for value in state_values
        ),
        "view_jitter_bounded_count": sum(
            int(value["bounded_jitter_count"]) for value in state_values
        ),
        "view_jitter_uncapped_spherical_count": sum(
            int(value["uncapped_spherical_count"]) for value in state_values
        ),
        "view_jitter_bounded_cap_compliance_fraction": scene_macro(
            "bounded_jitter_cap_compliance_fraction"
        ),
        "view_jitter_bounded_declaration_fraction": scene_macro(
            "bounded_jitter_declaration_fraction"
        ),
        "view_jitter_nonzero_fraction": scene_macro("jitter_nonzero_fraction"),
        "view_jitter_undefined_state_count": sum(
            int(value["jitter_undefined"]) for value in state_values
        ),
        "view_jitter_undefined_scene_count": undefined_scene_count(
            "jitter_nonzero_fraction"
        ),
        "view_jitter_bounded_compliance_undefined_state_count": sum(
            int(value["bounded_jitter_compliance_undefined"]) for value in state_values
        ),
        "view_jitter_bounded_compliance_undefined_scene_count": undefined_scene_count(
            "bounded_jitter_cap_compliance_fraction"
        ),
        "worst_state_valid_count": (
            min(int(value["valid_count"]) for value in state_values)
            if state_values
            else None
        ),
    }


def _candidate_plot(
    rows: list[dict[str, Any]], *, show_view_directions: bool
) -> go.Figure:
    """Compose the shared ground-support view into the frozen two-profile layout."""

    figure = make_subplots(
        rows=1, cols=2, subplot_titles=("realistic_core", "target-orbit MVP")
    )
    families = sorted({str(row["family"]) for row in rows})
    colors = dict(
        zip(families, ("#1f77b4", "#2ca02c", "#ff7f0e", "#d62728"), strict=True)
    )
    legend_names: set[str] = set()
    for column, profile in enumerate(PROFILES, start=1):
        profile_rows = [row for row in rows if row["profile"] == profile]
        profile_figure = candidate_ground_support_figure(
            _profile_benchmarks(profile_rows),
            show_view_directions=show_view_directions,
            family_colors=colors,
        )
        for trace in profile_figure.data:
            name = str(trace.name)
            trace.showlegend = name not in legend_names
            legend_names.add(name)
            figure.add_trace(trace, row=1, col=column)
        for annotation in profile_figure.layout.annotations:
            payload = annotation.to_plotly_json()
            for key in ("xref", "yref", "axref", "ayref"):
                payload.pop(key, None)
            figure.add_annotation(**payload, row=1, col=column)
    figure.update_xaxes(
        title_text="target-forward displacement / d", scaleanchor="y", scaleratio=1
    )
    figure.update_yaxes(
        title_text="target-lateral displacement / d", constrain="domain"
    )
    figure.update_layout(
        title="Candidate centres in the factual target-aligned proposal-support frame",
        template="plotly_white",
        width=1800,
        height=1050,
        legend_title="candidate family / status / anchor",
        annotations=[
            *figure.layout.annotations,
            {
                "text": "circle: actor-valid · ×: invalid · diamond: selected"
                + (
                    " · arrow: projected camera optical axis"
                    if show_view_directions
                    else ""
                ),
                "x": 0.5,
                "y": -0.11,
                "xref": "paper",
                "yref": "paper",
                "showarrow": False,
            },
        ],
    )
    return figure


def _plot(rows: list[dict[str, Any]], *, show_view_directions: bool) -> None:
    """Write canonical interactive and raster evidence from portable rows."""

    figure = _candidate_plot(rows, show_view_directions=show_view_directions)
    html_path = ARROW_HTML_PATH if show_view_directions else HTML_PATH
    png_path = ARROW_PNG_PATH if show_view_directions else PNG_PATH
    html_path.write_text(
        figure.to_html(
            full_html=True, include_plotlyjs="cdn", div_id="candidate-target-orbit-mvp"
        ),
        encoding="utf-8",
    )
    figure.write_image(png_path, width=1800, height=1050, scale=1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-store", type=Path)
    parser.add_argument("--candidate-store", type=Path)
    parser.add_argument(
        "--view-directions",
        action="store_true",
        help="Overlay short camera-forward arrows for actor-valid candidates.",
    )
    args = parser.parse_args()
    if (args.baseline_store is None) != (args.candidate_store is None):
        parser.error("both raw stores are required when refreshing reduced rows")
    if args.baseline_store is not None and args.candidate_store is not None:
        _write_rows(
            _extract_profile("realistic_core", args.baseline_store)
            + _extract_profile("target_orbit_mvp", args.candidate_store)
        )
    rows = _read_rows()
    expected_states = _read_expected_states()
    summary = {
        profile: _profile_summary(
            [row for row in rows if row["profile"] == profile],
            profile=profile,
            expected_states=expected_states,
        )
        for profile in PROFILES
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _plot(rows, show_view_directions=args.view_directions)
    print(
        json.dumps(
            {
                "rows_sha256": _sha256(ROWS_PATH),
                "summary_sha256": _sha256(SUMMARY_PATH),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
