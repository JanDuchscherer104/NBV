"""Rebuild the target-orbit pilot summary and plots from reduced candidate rows.

The committed JSONL is the portable evidence input. Passing both raw Zarr
stores refreshes that input through the canonical proposal-support reducer;
omitting them rebuilds the public summary and plots without private data paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Collection
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
TARGET_POSITIONS = {"target_bearing_local", "target_orbit"}


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


def _circular_span_deg(angles: list[float]) -> float | None:
    if not angles:
        return None
    wrapped = sorted(angle % 360.0 for angle in angles)
    gaps = [right - left for left, right in zip(wrapped, wrapped[1:], strict=False)]
    gaps.append(wrapped[0] + 360.0 - wrapped[-1])
    return 360.0 - max(gaps)


def _state_metrics(
    rows: list[dict[str, Any]], families: Collection[str]
) -> dict[str, float | int | None]:
    valid = [row for row in rows if row["actor_valid"]]
    target_rows = [row for row in rows if row["position"] in TARGET_POSITIONS]
    lateral = []
    for row in target_rows:
        value = float(row["y"]) - float(row["target_y"])
        if math.isfinite(value):
            lateral.append(value)
    positive = sum(value > 1e-9 for value in lateral)
    negative = sum(value < -1e-9 for value in lateral)
    non_neutral = positive + negative
    neutral = len(lateral) - non_neutral
    angles = [
        math.degrees(
            math.atan2(
                float(row["y"]) - float(row["target_y"]),
                float(row["x"]) - float(row["target_x"]),
            )
        )
        for row in target_rows
        if math.hypot(
            float(row["x"]) - float(row["target_x"]),
            float(row["y"]) - float(row["target_y"]),
        )
        > 1e-9
    ]
    gains = [
        float(row["target_root_gain"])
        for row in valid
        if row["target_root_gain"] is not None
    ]
    evaluated = [row for row in rows if row["target_view_evaluated"]]
    jitter = [
        row
        for row in rows
        if row["view_jitter_yaw_deg"] is not None
        and row["view_jitter_pitch_deg"] is not None
    ]
    bounded = [row for row in jitter if row["view_jitter_is_bounded"] is True]
    compliant = [
        row
        for row in bounded
        if row["view_jitter_azimuth_limit_deg"] is not None
        and row["view_jitter_elevation_limit_deg"] is not None
        and abs(float(row["view_jitter_yaw_deg"]))
        <= float(row["view_jitter_azimuth_limit_deg"])
        and abs(float(row["view_jitter_pitch_deg"]))
        <= float(row["view_jitter_elevation_limit_deg"])
    ]
    return {
        "actor_valid_fraction": len(valid) / len(rows) if rows else 0.0,
        "valid_count": len(valid),
        "family_zero_rate": sum(
            not any(row["family"] == family and row["actor_valid"] for row in rows)
            for family in families
        )
        / len(families),
        "family_zero_count": sum(
            not any(row["family"] == family and row["actor_valid"] for row in rows)
            for family in families
        ),
        "side_balance": None
        if not non_neutral
        else 1.0 - abs(positive - negative) / non_neutral,
        "side_positive_count": positive,
        "side_negative_count": negative,
        "side_neutral_count": neutral,
        "side_balance_undefined": int(non_neutral == 0),
        "orbit_span_deg": _circular_span_deg(angles),
        "best_target_root_gain": max(gains) if gains else None,
        "oracle_opportunity_undefined": int(not gains),
        "projection_fraction": (
            sum(row["target_center_in_calibrated_image"] is True for row in evaluated)
            / len(evaluated)
            if evaluated
            else None
        ),
        "projection_undefined": int(not evaluated),
        "jitter_count": len(jitter),
        "bounded_jitter_count": len(bounded),
        "uncapped_spherical_count": sum(
            row["view_jitter_is_bounded"] is False for row in jitter
        ),
        "jitter_nonzero_fraction": (
            sum(
                abs(float(row["view_jitter_yaw_deg"])) > 1e-9
                or abs(float(row["view_jitter_pitch_deg"])) > 1e-9
                for row in jitter
            )
            / len(jitter)
            if jitter
            else None
        ),
        "bounded_jitter_declaration_fraction": (
            len(bounded) / len(jitter) if jitter else None
        ),
        "bounded_jitter_cap_compliance_fraction": (
            len(compliant) / len(bounded) if bounded else None
        ),
        "jitter_undefined": int(not jitter),
        "bounded_jitter_compliance_undefined": int(not bounded),
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


def _plot(rows: list[dict[str, Any]], *, show_view_directions: bool) -> None:
    figure = make_subplots(
        rows=1, cols=2, subplot_titles=("realistic_core", "target-orbit MVP")
    )
    families = sorted({str(row["family"]) for row in rows})
    colors = dict(
        zip(families, ("#1f77b4", "#2ca02c", "#ff7f0e", "#d62728"), strict=True)
    )
    for column, profile in enumerate(PROFILES, start=1):
        profile_rows = [row for row in rows if row["profile"] == profile]
        for family in families:
            family_rows = [row for row in profile_rows if row["family"] == family]
            if not family_rows:
                continue
            figure.add_trace(
                go.Scatter(
                    x=[row["x"] for row in family_rows],
                    y=[row["y"] for row in family_rows],
                    mode="markers",
                    name=family,
                    legendgroup=family,
                    showlegend=column == 1,
                    marker={
                        "color": colors[family],
                        "size": 8,
                        "symbol": [
                            "diamond"
                            if row["selected"]
                            else "circle"
                            if row["actor_valid"]
                            else "x"
                            for row in family_rows
                        ],
                    },
                    customdata=[
                        [row["scene"], row["candidate_row_id"], row["actor_valid"]]
                        for row in family_rows
                    ],
                    hovertemplate="scene=%{customdata[0]}<br>candidate=%{customdata[1]}<br>actor-valid=%{customdata[2]}<extra></extra>",
                ),
                row=1,
                col=column,
            )
        figure.add_trace(
            go.Scatter(
                x=[0],
                y=[0],
                mode="markers",
                name="Factual expansion/root",
                showlegend=column == 1,
                marker={"symbol": "cross", "size": 13, "color": "black"},
            ),
            row=1,
            col=column,
        )
        if show_view_directions:
            for candidate in profile_rows:
                if (
                    not candidate["actor_valid"]
                    or candidate["view_direction_x"] is None
                ):
                    continue
                direction_x = float(candidate["view_direction_x"])
                direction_y = float(candidate["view_direction_y"])
                norm = math.hypot(direction_x, direction_y)
                if norm <= 1e-9:
                    continue
                arrow_length = 0.04
                axis_suffix = "" if column == 1 else str(column)
                figure.add_annotation(
                    x=float(candidate["x"]) + arrow_length * direction_x / norm,
                    y=float(candidate["y"]) + arrow_length * direction_y / norm,
                    ax=float(candidate["x"]),
                    ay=float(candidate["y"]),
                    xref=f"x{axis_suffix}",
                    yref=f"y{axis_suffix}",
                    axref=f"x{axis_suffix}",
                    ayref=f"y{axis_suffix}",
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=0.7,
                    arrowwidth=1.0,
                    arrowcolor="rgba(40,40,40,0.65)",
                )
        targets = sorted(
            {(float(row["target_x"]), float(row["target_y"])) for row in profile_rows}
        )
        figure.add_trace(
            go.Scatter(
                x=[target[0] for target in targets],
                y=[target[1] for target in targets],
                mode="markers",
                name="Oracle task target centre",
                showlegend=column == 1,
                marker={"symbol": "star", "size": 14, "color": "#9467bd"},
            ),
            row=1,
            col=column,
        )
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
        legend_title="candidate family / anchor",
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
