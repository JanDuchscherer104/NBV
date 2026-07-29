from __future__ import annotations

import time
from collections.abc import Iterable
from typing import cast

import pytest

from aria_nbv.rollouts.inspection import (
    candidate_direction_evidence,
    candidate_geometry_evidence_rows,
    candidate_motion_support_evidence,
    candidate_regret_evidence,
    candidate_spatial_support_evidence,
    candidate_state_composition_evidence,
    candidate_target_view_evidence,
)


def _candidate(
    candidate_id: int,
    *,
    cohort: str = "cohort-a",
    rollout: int = 0,
    step: int = 0,
    scene: str = "scene-a",
    strategy: str = "family-a",
    position: str = "shell",
    actor_valid: bool = True,
    selected: bool = False,
    xyz: tuple[float | None, float | None, float | None] = (1.0, 0.0, 0.0),
    path_collision: bool | None = False,
    motion_step: float | None = 1.0,
) -> dict[str, object]:
    x, y, z = xyz
    distance = None if x is None or y is None or z is None else (x * x + y * y + z * z) ** 0.5
    return {
        "candidate_row_id": candidate_id,
        "generation_cohort_id": cohort,
        "policy": "policy",
        "horizon": 2,
        "acquisition_budget_steps": 2,
        "branch_factor": 1,
        "beam_width": 1,
        "temperature": 1.0,
        "candidate_config": f"candidate-{cohort}",
        "rollout_config": "rollout",
        "branch_schedule": "schedule",
        "rollout_row_id": rollout,
        "step_row_id": step,
        "scene": scene,
        "strategy": strategy,
        "position": position,
        "mixture": "mixture",
        "actor_action": actor_valid,
        "selected": selected,
        "root_relative_x_m": x,
        "root_relative_y_m": y,
        "root_relative_z_m": z,
        "root_distance_m": distance,
        "root_to_target_x_m": 2.0,
        "root_to_target_y_m": 0.0,
        "motion_yaw_delta_deg": 10.0,
        "target_bearing_yaw_deg": 5.0,
        "target_distance_m": 2.0,
        "path_collision": path_collision,
        "motion_step_length_m": motion_step,
        "motion_height_delta_m": 0.1,
        "motion_backward_step_m": 0.2,
        "path_min_clearance_m": 0.3,
        "free_space_margin_m": 0.4,
    }


def _rows(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    return cast(list[dict[str, object]], value)


def _find(rows: Iterable[dict[str, object]], **expected: object) -> dict[str, object]:
    return next(row for row in rows if all(row.get(key) == value for key, value in expected.items()))


def test_composition_weights_states_equally_instead_of_pooling_candidates() -> None:
    rows = [_candidate(0, step=0, strategy="a")]
    rows.extend(_candidate(index + 1, step=1, strategy="b") for index in range(9))

    evidence = candidate_state_composition_evidence(rows, family_fields=("strategy",))
    family_a = _find(
        evidence,
        family_dimension="strategy",
        family="a",
        population="sampled",
        aggregation_level="cohort_scene_macro",
    )
    family_b = _find(
        evidence,
        family_dimension="strategy",
        family="b",
        population="sampled",
        aggregation_level="cohort_scene_macro",
    )

    assert family_a["mean_state_family_share"] == pytest.approx(0.5)
    assert family_b["mean_state_family_share"] == pytest.approx(0.5)
    assert family_a["state_count"] == 2
    assert family_a["full_count"] == 10


def test_composition_macros_states_then_scenes_for_every_population() -> None:
    rows = [_candidate(0, scene="scene-a", step=0, position="shell", selected=True)]
    rows.extend(
        _candidate(
            index + 1,
            scene="scene-b",
            step=index + 1,
            position="explore",
            selected=True,
        )
        for index in range(9)
    )

    evidence = candidate_state_composition_evidence(rows, family_fields=("position",))
    shell_rows = [row for row in evidence if row["family"] == "shell"]
    for population in ("sampled", "actor_valid", "selected", "selected_to_valid_enrichment"):
        population_rows = [row for row in shell_rows if row["population"] == population]
        assert {row["aggregation_level"] for row in population_rows} == {
            "state",
            "scene_macro",
            "cohort_scene_macro",
        }
        cohort = _find(population_rows, aggregation_level="cohort_scene_macro")
        value_field = (
            "mean_state_selection_enrichment"
            if population == "selected_to_valid_enrichment"
            else "mean_state_family_share"
        )
        expected = 1.0 if population == "selected_to_valid_enrichment" else 0.5
        assert cohort[value_field] == pytest.approx(expected)
        assert cohort["scene_count"] == (1 if population == "selected_to_valid_enrichment" else 2)
        assert cohort["state_count"] == 10


def test_equal_area_density_separates_all_and_actor_valid_populations() -> None:
    rows = [
        _candidate(0, xyz=(1.0, 0.0, 1.0), actor_valid=True),
        _candidate(1, xyz=(-1.0, 0.0, -1.0), actor_valid=False),
    ]

    evidence = candidate_direction_evidence(rows)
    density = _rows(evidence["density_rows"])
    all_rows = [
        row for row in density if row["population"] == "all" and row["aggregation_level"] == "cohort_scene_macro"
    ]
    valid_rows = [
        row
        for row in density
        if row["population"] == "actor_valid" and row["aggregation_level"] == "cohort_scene_macro"
    ]

    assert sum(cast(float, row["mean_state_fraction"]) for row in all_rows) == pytest.approx(1.0)
    assert sum(cast(float, row["mean_state_fraction"]) for row in valid_rows) == pytest.approx(1.0)
    assert sum(row["mean_state_fraction"] not in (None, 0.0) for row in all_rows) == 2
    assert sum(row["mean_state_fraction"] not in (None, 0.0) for row in valid_rows) == 1


def test_direction_density_uses_equal_state_then_equal_scene_macros() -> None:
    positive = candidate_direction_evidence([_candidate(0, xyz=(1.0, 0.0, 0.0))])
    positive_bin = next(
        row
        for row in _rows(positive["density_rows"])
        if row["population"] == "all"
        and row["aggregation_level"] == "cohort_scene_macro"
        and row["mean_state_fraction"] == 1.0
    )
    rows = [_candidate(0, scene="scene-a", step=0, xyz=(1.0, 0.0, 0.0))]
    rows.extend(_candidate(index + 1, scene="scene-b", step=index + 1, xyz=(-1.0, 0.0, 0.0)) for index in range(9))

    evidence = candidate_direction_evidence(rows)
    cohort_bin = _find(
        _rows(evidence["density_rows"]),
        population="all",
        aggregation_level="cohort_scene_macro",
        azimuth_bin=positive_bin["azimuth_bin"],
        sin_elevation_bin=positive_bin["sin_elevation_bin"],
    )

    assert cohort_bin["mean_state_fraction"] == pytest.approx(0.5)
    assert cohort_bin["scene_count"] == 2
    assert cohort_bin["state_count"] == 10


def test_cap_covering_and_neighbor_statistics_macro_states_then_scenes() -> None:
    rows = [
        _candidate(0, scene="scene-a", step=0, xyz=(1.0, 0.0, 0.0)),
        _candidate(1, scene="scene-a", step=0, xyz=(-1.0, 0.0, 0.0)),
    ]
    candidate_id = 2
    for step in range(1, 10):
        rows.extend(
            (
                _candidate(candidate_id, scene="scene-b", step=step, xyz=(1.0, 0.0, 0.0)),
                _candidate(candidate_id + 1, scene="scene-b", step=step, xyz=(1.0, 0.0, 0.0)),
            )
        )
        candidate_id += 2

    evidence = candidate_direction_evidence(rows)
    for evidence_name, value_field, collection in (
        ("uniform_spherical_cap_discrepancy", "mean_state_max_abs_discrepancy", "cap_rows"),
        ("reference_grid_covering_radius", "mean_state_value", "angular_support_rows"),
        ("nearest_neighbor_angular_separation_median", "mean_state_value", "angular_support_rows"),
    ):
        metric_rows = [
            row
            for row in _rows(evidence[collection])
            if row["population"] == "all"
            and row["evidence"] == evidence_name
            and (collection != "cap_rows" or row["cap_radius_deg"] == 60.0)
        ]
        scene_a = _find(metric_rows, aggregation_level="scene_macro", scene="scene-a")
        scene_b = _find(metric_rows, aggregation_level="scene_macro", scene="scene-b")
        cohort = _find(metric_rows, aggregation_level="cohort_scene_macro")

        assert cohort[value_field] == pytest.approx(
            (cast(float, scene_a[value_field]) + cast(float, scene_b[value_field])) / 2.0
        )
        assert cohort["scene_count"] == 2
        assert cohort["state_count"] == 10


def test_spherical_cap_protocol_reports_analytic_uniform_fraction() -> None:
    evidence = candidate_direction_evidence([_candidate(0)])
    cap_rows = _rows(evidence["cap_rows"])
    radius_60 = _find(
        cap_rows,
        population="all",
        cap_radius_deg=60.0,
        aggregation_level="cohort_scene_macro",
    )

    assert radius_60["uniform_reference_fraction"] == pytest.approx(0.25)
    assert "uniform-sphere reference" in str(radius_60["protocol"])


def test_covering_and_nearest_neighbor_handle_singletons_antipodes_and_duplicates() -> None:
    singleton = candidate_direction_evidence([_candidate(0)])
    singleton_support = _rows(singleton["angular_support_rows"])
    covering = _find(
        singleton_support,
        population="all",
        evidence="reference_grid_covering_radius",
        aggregation_level="cohort_scene_macro",
    )
    nearest = _find(
        singleton_support,
        population="all",
        evidence="nearest_neighbor_angular_separation_median",
        aggregation_level="cohort_scene_macro",
    )
    assert covering["mean_state_value"] == pytest.approx(180.0)
    assert nearest["available"] is False

    antipodes = candidate_direction_evidence([_candidate(0, xyz=(1.0, 0.0, 0.0)), _candidate(1, xyz=(-1.0, 0.0, 0.0))])
    antipode_covering = _find(
        _rows(antipodes["angular_support_rows"]),
        population="all",
        evidence="reference_grid_covering_radius",
        aggregation_level="cohort_scene_macro",
    )
    assert cast(float, antipode_covering["mean_state_value"]) == pytest.approx(90.0, abs=3.0)

    duplicates = candidate_direction_evidence([_candidate(0), _candidate(1)])
    duplicate_nn = _find(
        _rows(duplicates["angular_support_rows"]),
        population="all",
        evidence="nearest_neighbor_angular_separation_median",
        aggregation_level="cohort_scene_macro",
    )
    assert duplicate_nn["mean_state_value"] == pytest.approx(0.0)


def test_spatial_shell_support_keeps_zero_radius_and_macros_states() -> None:
    rows = [_candidate(0, step=0, xyz=(0.0, 0.0, 0.0))]
    rows.extend(_candidate(index + 1, step=1, xyz=(2.0, 0.0, 0.0)) for index in range(9))
    geometry = candidate_geometry_evidence_rows(rows)

    evidence = candidate_spatial_support_evidence(geometry)
    radius = _find(
        evidence,
        population="all",
        evidence="root_xy_radius",
        aggregation_level="cohort_scene_macro",
        declared_shell="shell",
    )

    assert radius["mean"] == pytest.approx(1.0)
    assert radius["finite_count"] == 10
    assert radius["zero_radius_policy"] == "included"


def test_target_view_keeps_only_distance_and_blocks_unobserved_view_claims() -> None:
    geometry = candidate_geometry_evidence_rows([_candidate(0)])

    evidence = candidate_target_view_evidence(geometry)
    distance = _find(
        evidence,
        population="all",
        evidence="target_distance",
        aggregation_level="cohort_scene_macro",
    )
    orientation = _find(evidence, population="all", evidence="target_orientation_alignment")
    los = _find(evidence, population="all", evidence="target_line_of_sight")
    fov = _find(evidence, population="all", evidence="target_fov_margin")

    assert distance["available"] is True
    assert distance["mean"] == pytest.approx(2.0)
    assert orientation["available"] is False
    assert "not commensurate" in str(orientation["reason"])
    assert not any(row["evidence"] == "horizontal_yaw_alignment_proxy" for row in evidence)
    assert los["available"] is False
    assert "path collision is not LOS" in str(los["reason"])
    assert fov["available"] is False
    assert fov["mean"] is None


def test_motion_support_is_state_macro_and_keeps_missing_values_explicit() -> None:
    rows = [_candidate(0, step=0, path_collision=False, motion_step=1.0)]
    rows.extend(_candidate(index + 1, step=1, path_collision=True, motion_step=3.0) for index in range(8))
    rows.append(_candidate(9, step=1, path_collision=True, motion_step=None))

    evidence = candidate_motion_support_evidence(rows)
    collision = _find(evidence, evidence="path_collision_rate", aggregation_level="cohort_scene_macro")
    step = _find(evidence, evidence="motion_step_length", aggregation_level="cohort_scene_macro")

    assert collision["mean"] == pytest.approx(0.5)
    assert step["mean"] == pytest.approx(2.0)
    assert step["full_count"] == 10
    assert step["finite_count"] == 9
    assert step["missing_count"] == 1

    assert not any(row["evidence"] == "explicit_joint_motion_support" for row in evidence)
    joint = candidate_motion_support_evidence(
        rows,
        joint_support_conjunction=("actor_valid", "path_collision_free"),
    )
    assert _find(joint, evidence="explicit_joint_motion_support", aggregation_level="cohort_scene_macro")
    with pytest.raises(ValueError, match="Unsupported joint support"):
        candidate_motion_support_evidence(rows, joint_support_conjunction=("line_of_sight",))


def test_path_collision_requires_boolean_and_clearance_diagnostic() -> None:
    false_sentinel = _candidate(0, step=0, path_collision=False)
    false_sentinel["path_min_clearance_m"] = None
    nan_sentinel = _candidate(1, step=1)
    nan_sentinel["path_collision"] = float("nan")

    evidence = candidate_motion_support_evidence(
        [false_sentinel, nan_sentinel],
        joint_support_conjunction=("path_collision_free",),
    )
    collision = _find(evidence, evidence="path_collision_rate", aggregation_level="cohort_scene_macro")
    joint = _find(evidence, evidence="explicit_joint_motion_support", aggregation_level="cohort_scene_macro")

    assert collision["available"] is False
    assert collision["finite_count"] == 0
    assert collision["missing_count"] == 2
    assert joint["available"] is False
    assert joint["finite_count"] == 0
    assert joint["missing_count"] == 2


def test_regret_is_state_macro_and_contract_violations_are_explicit() -> None:
    audit = [
        _candidate(0, step=0, selected=True, actor_valid=True),
        _candidate(1, step=1, selected=True, actor_valid=True),
        _candidate(2, step=2, selected=True, actor_valid=False),
    ]
    ranks = [
        {
            "selected_candidate_row_id": 0,
            "selected_actor_valid": True,
            "valid_candidate_count": 2,
            "finite_valid_label_count": 2,
            "regret_to_best": 0.2,
            "selected_rank": 2,
            "target_rri_rank": 2,
        },
        {
            "selected_candidate_row_id": 1,
            "selected_actor_valid": True,
            "valid_candidate_count": 2,
            "finite_valid_label_count": 2,
            "regret_to_best": 0.4,
            "selected_rank": 1,
            "target_rri_rank": 1,
        },
        {
            "selected_candidate_row_id": 2,
            "selected_actor_valid": False,
            "valid_candidate_count": 1,
            "finite_valid_label_count": 1,
            "regret_to_best": 0.0,
        },
    ]

    evidence = candidate_regret_evidence(audit, ranks)
    summary = _find(
        _rows(evidence["summary_rows"]),
        evidence="regret_to_best",
        aggregation_level="cohort_scene_macro",
    )
    violations = _rows(evidence["violation_rows"])

    assert summary["mean"] == pytest.approx(0.3)
    assert {row["violation"] for row in violations} >= {"selected_actor_invalid"}


def test_exact_generation_cohorts_are_never_pooled() -> None:
    rows = [_candidate(0, cohort="a", strategy="family"), _candidate(1, cohort="b", strategy="family")]

    evidence = candidate_state_composition_evidence(rows, family_fields=("strategy",))
    sampled = [row for row in evidence if row["population"] == "sampled"]

    assert {row["generation_cohort_id"] for row in sampled} == {"a", "b"}
    assert all(row["full_count"] == 1 for row in sampled)


def test_full_population_scan_includes_final_row_and_is_order_invariant() -> None:
    rows = [_candidate(index, strategy="a") for index in range(20_000)]
    rows.append(_candidate(20_000, strategy="final"))

    forward = candidate_state_composition_evidence(rows, family_fields=("strategy",))
    reverse = candidate_state_composition_evidence(reversed(rows), family_fields=("strategy",))
    final = _find(forward, population="sampled", family="final", aggregation_level="cohort_scene_macro")

    assert forward == reverse
    assert final["finite_count"] == 1
    assert final["mean_state_family_share"] == pytest.approx(1 / 20_001)


def test_direction_full_scan_is_sparse_complete_and_order_invariant() -> None:
    rows = [_candidate(index, xyz=(1.0, 0.0, 0.0)) for index in range(20_000)]
    rows.append(_candidate(20_000, xyz=(-1.0, 0.0, 0.0)))

    started = time.perf_counter()
    forward = candidate_direction_evidence(rows)
    reverse = candidate_direction_evidence(reversed(rows))
    elapsed_s = time.perf_counter() - started

    assert forward == reverse
    density = _rows(forward["density_rows"])
    all_state_rows = [row for row in density if row["population"] == "all" and row["aggregation_level"] == "state"]
    all_cohort_rows = [
        row for row in density if row["population"] == "all" and row["aggregation_level"] == "cohort_scene_macro"
    ]
    nonzero = sorted(
        cast(float, row["mean_state_fraction"]) for row in all_cohort_rows if row["mean_state_fraction"] != 0.0
    )

    assert nonzero == pytest.approx([1 / 20_001, 20_000 / 20_001])
    assert len(all_state_rows) == 2
    assert len(all_cohort_rows) == 72
    assert len(density) < 400
    assert "implicit zero" in str(all_cohort_rows[0]["protocol"])
    assert elapsed_s < 30.0


def test_missing_geometry_is_unavailable_not_zero_or_nan() -> None:
    rows = [_candidate(0, xyz=(0.0, 0.0, 0.0)), _candidate(1, xyz=(None, None, None))]

    direction = candidate_direction_evidence(rows)
    covering = _find(
        _rows(direction["angular_support_rows"]),
        population="all",
        evidence="reference_grid_covering_radius",
        aggregation_level="cohort_scene_macro",
    )
    motion_rows = [_candidate(0, motion_step=None)]
    motion_rows[0]["path_min_clearance_m"] = None
    motion = candidate_motion_support_evidence(motion_rows)
    clearance = _find(motion, evidence="path_min_clearance", aggregation_level="cohort_scene_macro")

    assert covering["available"] is False
    assert covering["mean_state_value"] is None
    assert covering["missing_count"] == 2
    assert clearance["available"] is False
    assert clearance["mean"] is None
    assert clearance["missing_count"] == 1
