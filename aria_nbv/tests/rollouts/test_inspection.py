"""Rollout inspection helper tests."""

# ruff: noqa: S101

from __future__ import annotations

import copy
from typing import Any, cast

import numpy as np
import pytest
import zarr

pytest.importorskip("efm3d")

from aria_nbv.rollouts import RolloutZarrStoreReader
from aria_nbv.rollouts.inspection import (
    RolloutSuspiciousQueryConfig,
    candidate_audit_rows,
    candidate_collision_support_rows,
    candidate_composition_rows,
    candidate_flow_rows,
    candidate_group_summary_rows,
    candidate_proposal_calibration_rows,
    comparable_policy_cohorts,
    deterministic_candidate_display_sample,
    discounted_rollout_return_rows,
    discover_rollout_store_paths,
    exact_policy_role_rows,
    mask_combination_rows,
    oracle_headroom_evidence,
    paired_policy_comparison_rows,
    reconstruction_endpoint_rows,
    reconstruction_endpoint_summary_rows,
    reconstruction_metric_summary_rows,
    rollout_endpoint_metric_summary,
    rollout_header_summary,
    rollout_step_objective_rows,
    rollout_store_inventory_rows,
    rollout_tree_summary_rows,
    root_relative_candidate_rows,
    selected_candidate_rank_rows,
    selected_depth_preview,
    selected_depth_summary_rows,
    store_invariant_rows,
    suspicious_rollout_rows,
    target_audit_rows,
    temporal_metric_summary_rows,
    validity_waterfall_rows,
)
from aria_nbv.rollouts.zarr_store import write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records


def test_candidate_group_summary_rejects_unsupported_field() -> None:
    with pytest.raises(ValueError, match="Unsupported candidate group field"):
        candidate_group_summary_rows(cast(Any, object()), group_by=cast(Any, "not-supported"))


def test_rollout_store_inventory_rows_report_current_stale_and_unreadable_stores(tmp_path) -> None:
    """Inventory rows should diagnose stores before current-schema deep inspection."""

    current = write_rollout_zarr_store(
        tmp_path / "current.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=41)[:1],
    )
    stale_path = tmp_path / "stale.zarr"
    stale_root = zarr.open_group(stale_path, mode="w")
    stale_root.attrs["schema_version"] = "0.6-rollout-core"
    stale_root.create_group("rollouts").create_array("rollout_row_id", data=np.arange(2, dtype=np.int64))
    stale_root.create_group("steps").create_array("step_row_id", data=np.arange(4, dtype=np.int64))
    stale_root.create_group("candidates").create_array("candidate_row_id", data=np.arange(12, dtype=np.int64))
    unreadable_path = tmp_path / "unreadable.zarr"
    unreadable_path.mkdir()
    (unreadable_path / "not-a-zarr-store.txt").write_text("broken", encoding="utf-8")

    rows = rollout_store_inventory_rows([stale_path, unreadable_path, current.store_dir])
    by_name = {str(row["name"]): row for row in rows}

    assert by_name["current.zarr"]["schema_status"] == "current"
    assert by_name["current.zarr"]["validation_ok"] is True
    assert by_name["current.zarr"]["validation_status"] == "ok"
    assert by_name["current.zarr"]["observed_rollouts"] == current.num_rollouts
    assert by_name["current.zarr"]["validator_rollouts"] == current.num_rollouts
    assert by_name["current.zarr"]["required_groups_missing"] == 0

    assert by_name["stale.zarr"]["schema_status"] == "stale"
    assert by_name["stale.zarr"]["validation_ok"] is False
    assert by_name["stale.zarr"]["validation_status"] == "failed"
    assert by_name["stale.zarr"]["observed_rollouts"] == 2
    assert by_name["stale.zarr"]["observed_steps"] == 4
    assert by_name["stale.zarr"]["observed_candidates"] == 12
    assert by_name["stale.zarr"]["validator_rollouts"] == 0
    assert "Unsupported rollout Zarr schema_version" in str(by_name["stale.zarr"]["first_error"])

    assert by_name["unreadable.zarr"]["schema_status"] == "unreadable"
    assert by_name["unreadable.zarr"]["validation_ok"] is False
    assert by_name["unreadable.zarr"]["validation_status"] == "failed"
    assert by_name["unreadable.zarr"]["validation_error_count"] == 1
    assert by_name["unreadable.zarr"]["first_error"]


def test_rollout_store_inventory_can_skip_deep_validation_for_interactive_discovery(tmp_path) -> None:
    current = write_rollout_zarr_store(
        tmp_path / "current.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=42)[:1],
    )

    row = rollout_store_inventory_rows([current.store_dir], validate=False)[0]

    assert row["schema_status"] == "current"
    assert row["validation_ok"] is None
    assert row["validation_status"] == "unknown"
    assert row["observed_candidates"] == current.num_candidates


def test_discover_rollout_store_paths_returns_zarr_directories(tmp_path) -> None:
    """Discovery should recursively find candidate Zarr directories only."""

    first = tmp_path / "nested" / "a.zarr"
    second = tmp_path / "b.zarr"
    first.mkdir(parents=True)
    second.mkdir()
    (tmp_path / "not_zarr.txt").write_text("skip", encoding="utf-8")

    paths = discover_rollout_store_paths(tmp_path)

    assert set(paths) == {first.resolve(), second.resolve()}


def test_rollout_inspection_helpers_join_candidates_targets_and_groups(tmp_path) -> None:
    """Audit helpers should expose decoded rollout QA rows without changing store data."""

    records = build_rollout_records(horizon=1, num_samples=6, seed=43)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)

    candidates = candidate_audit_rows(reader)
    assert len(candidates) == result.num_candidates
    assert candidate_audit_rows(reader, limit=0) == []
    first = candidates[0]
    assert first["candidate_row_id"] == 0
    assert first["scene"] == "fixture_box"
    assert first["position"] == "forward_local"
    assert first["mixture"] != ""
    assert first["target_root_gain"] != first["target_rri"]
    assert "motion_step_length_m" in first
    assert first["coordinate_frame"] == "root-centered ARIA world (RIGHT_HAND_Z_UP)"
    assert first["units"] == "m"

    target_rows = target_audit_rows(reader)
    assert len(target_rows) == 1
    target = target_rows[0]
    assert target["target_id"] == "fixture-target-0"
    assert target["effective_support"] == pytest.approx(12.0)
    assert target["visibility_score"] == pytest.approx(0.8)
    assert target["gt_match_status"] == "matched"

    waterfall = validity_waterfall_rows(reader)
    assert waterfall[0]["stage"] == "full shell"
    assert waterfall[0]["count"] == result.num_candidates
    assert waterfall[-1]["stage"] == "selected"

    by_position = candidate_group_summary_rows(reader, group_by="position")
    assert by_position == [
        {
            "position": "forward_local",
            "total": result.num_candidates,
            "actor_valid": int(reader.array("candidates/actor_action_mask").sum()),
            "actor_valid_fraction": pytest.approx(
                float(reader.array("candidates/actor_action_mask").sum()) / result.num_candidates
            ),
            "q_train": int(reader.array("candidates/q_train_mask").sum()),
            "selected": int(reader.array("candidates/selected_mask").sum()),
            "mean_target_root_gain": pytest.approx(float(np.nanmean(reader.array("candidates/target_root_gain")))),
        }
    ]
    flow = candidate_flow_rows(reader)
    assert {row["root_denominator"] for row in flow} == {result.num_candidates}
    assert sum(row["count"] for row in flow if row["source_stage"] == "root") == result.num_candidates


def test_rollout_inspection_suspicious_queries_find_injected_anomalies(tmp_path) -> None:
    """Suspicious-row predicates should find low fanout, missing labels, and motion outliers."""

    records = build_rollout_records(horizon=1, num_samples=6, seed=44)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    root = zarr.open_group(result.store_dir, mode="a")

    root["steps/num_valid_candidates"][0] = np.asarray(0, dtype=np.int32)
    actor_valid = np.asarray(root["candidates/actor_action_mask"], dtype=np.bool_).reshape(-1)
    first_valid = int(np.flatnonzero(actor_valid)[0])
    root["candidates/target_root_gain"][first_valid] = np.asarray(np.nan, dtype=np.float32)
    selected = np.asarray(root["candidates/selected_mask"], dtype=np.bool_).reshape(-1)
    selected_row = int(np.flatnonzero(selected)[0])
    root["candidate_diagnostics/motion_step_length_m"][selected_row] = np.asarray(99.0, dtype=np.float32)

    rows = suspicious_rollout_rows(
        RolloutZarrStoreReader(result.store_dir),
        config=RolloutSuspiciousQueryConfig(min_valid_candidates=2, max_step_distance_m=1.0),
    )
    kinds = {str(row["kind"]) for row in rows}

    assert "low_valid_fanout" in kinds
    assert "valid_candidate_missing_label" in kinds
    assert "selected_motion_outlier" in kinds


def test_rollout_step_objective_rows_expose_existing_objective_and_sampling_fields(tmp_path) -> None:
    """Per-step rows should join objectives and selected-action provenance from existing arrays."""

    records = build_rollout_records(horizon=2, num_samples=6, seed=45)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)

    rows = rollout_step_objective_rows(reader, rollout_row_id=0)

    assert [row["step_index"] for row in rows] == [0, 1]
    assert rows[0]["policy"] == "oracle_greedy"
    assert rows[0]["chain_id"] == 0
    assert rows[0]["marginal_target_rri"] == pytest.approx(rows[0]["cumulative_target_rri"])
    assert rows[1]["marginal_target_rri"] == pytest.approx(
        float(rows[1]["cumulative_target_rri"]) - float(rows[0]["cumulative_target_rri"])
    )
    assert rows[0]["selected_target_rri"] == pytest.approx(rows[0]["marginal_target_rri"])
    assert rows[0]["selected_target_root_gain"] is not None
    assert rows[0]["selected_position"] == "forward_local"
    assert rows[0]["selected_strategy"] != ""
    assert rows[0]["selected_mixture"] != ""
    assert rows[0]["selected_sampler_probability"] == pytest.approx(1.0 / float(rows[0]["num_candidates"]))
    assert rows[0]["selected_probability"] is not None
    assert rows[0]["selected_entropy"] is not None
    assert rows[0]["num_candidates"] >= 6
    assert rows[0]["num_valid_candidates"] <= rows[0]["num_candidates"]
    temporal = temporal_metric_summary_rows(
        reader,
        metric="cumulative_target_root_gain",
        group_fields=("policy",),
    )
    assert [row["step_index"] for row in temporal] == [0, 1]
    assert all(row["total_count"] == row["finite_count"] + row["missing_count"] for row in temporal)


def test_temporal_metric_summary_rows_use_exact_finite_only_linear_statistics() -> None:
    """Temporal summaries should expose exact counts and deterministic linear quantiles."""

    step_rows = [
        {"policy": "a", "step_index": 0, "selected_target_root_gain": value} for value in (0.0, 10.0, np.nan, np.inf)
    ] + [
        {"policy": "a", "step_index": 1, "selected_target_root_gain": None},
        {"policy": "b", "step_index": 0, "selected_target_root_gain": -2.0},
    ]

    rows = temporal_metric_summary_rows(
        step_rows,
        metric="selected_target_root_gain",
        group_fields=("policy",),
    )

    assert rows == [
        {
            "metric": "selected_target_root_gain",
            "units": "fraction",
            "step_index": 0,
            "policy": "a",
            "total_count": 4,
            "finite_count": 2,
            "missing_count": 2,
            "median": 5.0,
            "q25": 2.5,
            "q75": 7.5,
            "mean": 5.0,
            "min": 0.0,
            "max": 10.0,
        },
        {
            "metric": "selected_target_root_gain",
            "units": "fraction",
            "step_index": 1,
            "policy": "a",
            "total_count": 1,
            "finite_count": 0,
            "missing_count": 1,
            "median": None,
            "q25": None,
            "q75": None,
            "mean": None,
            "min": None,
            "max": None,
        },
        {
            "metric": "selected_target_root_gain",
            "units": "fraction",
            "step_index": 0,
            "policy": "b",
            "total_count": 1,
            "finite_count": 1,
            "missing_count": 0,
            "median": -2.0,
            "q25": -2.0,
            "q75": -2.0,
            "mean": -2.0,
            "min": -2.0,
            "max": -2.0,
        },
    ]
    assert all(row["total_count"] == row["finite_count"] + row["missing_count"] for row in rows)


def test_temporal_metric_summary_rows_validate_metrics_and_grouping_vocabulary() -> None:
    """Temporal grouping should distinguish supported factual and selected-action fields."""

    rows = [
        {
            "step_index": 0,
            "num_valid_candidates": 3,
            "selected_position": "forward_local",
        }
    ]

    assert (
        temporal_metric_summary_rows(
            rows,
            metric="valid_fanout",
            group_fields=("selected_position",),
        )[0]["median"]
        == 3.0
    )
    with pytest.raises(ValueError, match="Unsupported temporal metric"):
        temporal_metric_summary_rows(rows, metric="not_a_metric")
    with pytest.raises(ValueError, match="Unsupported temporal group field"):
        temporal_metric_summary_rows(rows, metric="valid_fanout", group_fields=("scene",))


def test_rollout_endpoint_metric_summary_uses_one_factual_endpoint_per_rollout() -> None:
    """Endpoint statistics must retain mixed horizons and weight rollouts equally."""

    rows: list[dict[str, object]] = []
    for rollout_row_id, endpoint in enumerate((0.0, 0.0, 0.0, 0.0, 100.0)):
        rows.extend(
            [
                {
                    "rollout_row_id": rollout_row_id,
                    "policy": "large_group",
                    "step_index": 0,
                    "selected_target_root_gain": -1.0,
                },
                {
                    "rollout_row_id": rollout_row_id,
                    "policy": "large_group",
                    "step_index": 1,
                    "selected_target_root_gain": endpoint,
                },
            ]
        )
    rows.extend(
        [
            {
                "rollout_row_id": 5,
                "policy": "small_group",
                "step_index": 1,
                "selected_target_root_gain": 100.0,
            },
            {
                "rollout_row_id": 6,
                "policy": "short_horizon",
                "step_index": 0,
                "selected_target_root_gain": 50.0,
            },
            {
                "rollout_row_id": 7,
                "policy": "missing_endpoint",
                "step_index": 0,
                "selected_target_root_gain": 25.0,
            },
            {
                "rollout_row_id": 7,
                "policy": "missing_endpoint",
                "step_index": 1,
                "selected_target_root_gain": np.nan,
            },
        ]
    )

    summary = rollout_endpoint_metric_summary(rows, metric="selected_target_root_gain")

    assert summary == {
        "metric": "selected_target_root_gain",
        "units": "fraction",
        "total_count": 8,
        "finite_count": 7,
        "missing_count": 1,
        "median": 0.0,
    }
    grouped = temporal_metric_summary_rows(rows, metric="selected_target_root_gain", group_fields=("policy",))
    global_max_depth = max(int(row["step_index"]) for row in grouped)
    misleading_median = np.median(
        [float(row["median"]) for row in grouped if row["step_index"] == global_max_depth and row["median"] is not None]
    )
    assert misleading_median == 50.0


def test_rollout_header_summary_requires_proven_reference_denominators(tmp_path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=451)[:1],
    )
    reader = RolloutZarrStoreReader(result.store_dir)

    unavailable = rollout_header_summary(reader)
    assert unavailable["reference_scene_fraction"] is None
    assert unavailable["reference_coverage_reason"] == "manifest provenance does not declare a reference denominator"
    assert unavailable["physical_bytes_per_rollout"] == pytest.approx(
        float(unavailable["physical_store_bytes"]) / float(result.num_rollouts)
    )
    assert unavailable["physical_bytes_per_candidate"] == pytest.approx(
        float(unavailable["physical_store_bytes"]) / float(result.num_candidates)
    )

    payload = copy.deepcopy(reader.manifest())
    payload["manifest"]["source_coverage"]["reference_scene_count"] = 5
    payload["manifest"]["source_coverage"]["reference_source_row_count"] = 4
    available = rollout_header_summary(reader, manifest_payload=payload)
    assert available["reference_scene_covered"] == 1
    assert available["reference_scene_gap"] == 4
    assert available["reference_scene_fraction"] == pytest.approx(0.2)
    assert available["reference_source_row_gap"] == 3
    assert available["reference_source_row_fraction"] == pytest.approx(0.25)


def test_reconstruction_and_discounted_return_rows_use_factual_steps() -> None:
    rows = [
        {
            "rollout_row_id": 0,
            "scene": "scene-a",
            "policy": "oracle_greedy",
            "horizon": 3,
            "step_index": index,
            "selected_target_root_gain": gain,
            "cumulative_target_root_gain": cumulative,
            "selected_target_rri": gain / 10.0,
            "cumulative_target_rri": cumulative / 10.0,
            "selected_probability": 0.5,
            "selected_entropy": 0.25,
        }
        for index, (gain, cumulative) in enumerate(((1.0, 1.0), (2.0, 3.0), (3.0, 6.0)))
    ]
    rows.append(
        {
            **rows[0],
            "rollout_row_id": 1,
            "policy": "short",
            "horizon": 1,
            "selected_target_root_gain": np.nan,
            "cumulative_target_root_gain": 4.0,
        }
    )

    endpoints = reconstruction_endpoint_rows(rows)
    assert [row["step_index"] for row in endpoints] == [2, 0]
    summaries = reconstruction_endpoint_summary_rows(rows)
    assert all(row["total_count"] == row["finite_count"] + row["missing_count"] for row in summaries)
    metrics = reconstruction_metric_summary_rows(rows)
    selected = next(row for row in metrics if row["metric"] == "selected_target_root_gain")
    assert selected["endpoint_total_count"] == 2
    assert selected["endpoint_finite_count"] == 1

    gamma_one = discounted_rollout_return_rows(
        rows[:3],
        return_semantics="cumulative_target_root_gain",
        discount_gamma=1.0,
    )
    gamma_half = discounted_rollout_return_rows(
        rows[:3],
        return_semantics="cumulative_target_root_gain",
        discount_gamma=0.5,
    )
    assert gamma_one["rows"][0]["discounted_return"] == pytest.approx(6.0)
    assert gamma_half["rows"][0]["discounted_return"] == pytest.approx(2.75)
    assert gamma_one["rows"][0]["discounted_return"] != endpoints[0]["cumulative_target_root_gain"] + 1.0
    assert discounted_rollout_return_rows(rows, return_semantics="other", discount_gamma=1.0) == {
        "available": False,
        "reason": "unsupported return_semantics='other'",
        "rows": [],
    }


def test_oracle_headroom_uses_exact_roles_and_raw_denominators() -> None:
    invariant = {
        "source_sample_key": "sample-a",
        "source_sample_index": 2,
        "target_id": "target-a",
        "target_protocol": "v1_observed",
        "horizon": 3,
        "acquisition_budget_steps": 3,
        "candidate_config": "candidate-hash",
        "oracle_config": "oracle-hash",
        "manifest_sha256": "manifest-hash",
        "writer_config_hash": "writer-hash",
        "scene": "scene-a",
        "temperature": np.nan,
        "random_seed": -1,
    }
    rows = [
        {
            **invariant,
            "policy": policy,
            "branch_schedule": schedule,
            "branch_factor": branch_factor,
            "beam_width": beam_width,
            "rollout_recipe": recipe,
            "final_cumulative_target_root_gain": value,
        }
        for policy, schedule, branch_factor, beam_width, recipe, value in (
            ("oracle_greedy", "oracle_greedy", 1, 1, "one", 6.0),
            ("oracle_greedy", "oracle_lookahead", 4, 2, "look", 10.0),
            ("learned_one_step", "learned_one_step", 1, 1, "learned", 4.0),
            ("q_h", "q_h", 1, 1, "qh", 7.0),
        )
    ]

    evidence = oracle_headroom_evidence(rows)
    included = {row["contrast"]: row for row in evidence["contrast_rows"] if row["status"] == "included"}
    assert included["delta_look"]["value"] == pytest.approx(4.0)
    assert included["delta_Q"]["value"] == pytest.approx(3.0)
    assert included["eta_Q"]["headroom_denominator"] == pytest.approx(6.0)
    assert included["eta_Q"]["value"] == pytest.approx(0.5)
    assert all(
        row["eligible_count"] == row["included_count"] + row["excluded_count"] for row in evidence["summary_rows"]
    )
    assert included["delta_look"]["role_treatments"]["oracle_lookahead"]["branch_schedule"] == "oracle_lookahead"

    alias_only = [{**rows[0], "policy": "unsupported", "branch_schedule": "unsupported", "rollout_recipe": "q_h"}]
    assert exact_policy_role_rows(alias_only) == []


def test_oracle_headroom_excludes_duplicate_roles_and_weak_eta_only() -> None:
    invariant = {
        "source_sample_key": "sample-a",
        "source_sample_index": 2,
        "target_id": "target-a",
        "target_protocol": "v1_observed",
        "horizon": 3,
        "acquisition_budget_steps": 3,
        "candidate_config": "candidate-hash",
        "oracle_config": "oracle-hash",
        "manifest_sha256": "manifest-hash",
        "writer_config_hash": "writer-hash",
        "temperature": np.nan,
        "random_seed": -1,
        "branch_factor": 1,
        "beam_width": 1,
        "rollout_recipe": "recipe",
    }
    weak_rows = [
        {
            **invariant,
            "policy": "oracle_greedy",
            "branch_schedule": "oracle_greedy",
            "final_cumulative_target_root_gain": 2.0,
        },
        {
            **invariant,
            "policy": "oracle_greedy",
            "branch_schedule": "oracle_lookahead",
            "final_cumulative_target_root_gain": 1.0,
        },
        {
            **invariant,
            "policy": "learned_one_step",
            "branch_schedule": "learned_one_step",
            "final_cumulative_target_root_gain": 1.0,
        },
        {**invariant, "policy": "q_h", "branch_schedule": "q_h", "final_cumulative_target_root_gain": 1.5},
    ]
    weak = oracle_headroom_evidence(weak_rows)
    by_contrast = {row["contrast"]: row for row in weak["contrast_rows"]}
    assert by_contrast["delta_look"]["status"] == "included"
    assert by_contrast["delta_Q"]["status"] == "included"
    assert by_contrast["eta_Q"]["status"] == "excluded"
    assert by_contrast["eta_Q"]["exclusion_reason"] == "nonpositive_or_weak_headroom"

    duplicate = oracle_headroom_evidence(
        weak_rows
        + [
            {
                **weak_rows[1],
                "branch_schedule": "oracle_lookahead_diverse",
                "rollout_recipe": "diverse",
            }
        ]
    )
    duplicate_by_contrast = {row["contrast"]: row for row in duplicate["contrast_rows"]}
    assert duplicate_by_contrast["delta_look"]["exclusion_reason"] == "duplicate_role:oracle_lookahead"


def test_candidate_evidence_preserves_cohorts_and_state_then_scene_macros() -> None:
    def row(
        candidate_row_id: int,
        *,
        cohort: str,
        scene: str,
        state: int,
        actor: bool,
        selected: bool,
        probability: float,
    ) -> dict[str, object]:
        return {
            "candidate_row_id": candidate_row_id,
            "generation_cohort_id": cohort,
            "generation_cohort": f'{{"cohort":"{cohort}"}}',
            "scene": scene,
            "rollout_row_id": state,
            "step_row_id": state,
            "mixture": "forward",
            "actor_action": actor,
            "oracle_label": actor,
            "q_train": actor,
            "selected": selected,
            "sampler_probability": probability,
            "path_collision": False,
            "path_min_clearance_m": 1.0,
        }

    rows = [
        row(0, cohort="a", scene="s1", state=0, actor=True, selected=True, probability=0.25),
        row(1, cohort="a", scene="s1", state=0, actor=True, selected=False, probability=0.25),
        row(2, cohort="a", scene="s1", state=1, actor=False, selected=False, probability=0.25),
        row(3, cohort="a", scene="s1", state=1, actor=False, selected=False, probability=0.25),
        row(4, cohort="a", scene="s2", state=2, actor=True, selected=True, probability=1.0),
        row(5, cohort="b", scene="s3", state=3, actor=False, selected=False, probability=1.0),
    ]

    composition = candidate_composition_rows(rows)
    assert [candidate["generation_cohort_id"] for candidate in composition] == ["a", "b"]
    cohort_a = composition[0]
    assert cohort_a["allocated_count"] == 5
    assert cohort_a["actor_valid_count"] == 3
    assert cohort_a["macro_actor_valid_rate"] == pytest.approx(0.75)
    assert cohort_a["aggregation"] == "state_then_scene_macro"

    calibration = candidate_proposal_calibration_rows(rows)
    assert [candidate["generation_cohort_id"] for candidate in calibration] == ["a", "b"]
    assert calibration[0]["empirical_frequency"] == pytest.approx(1.0)
    assert calibration[0]["proposal_mass"] == pytest.approx(1.0)
    assert calibration[0]["selected_share"] == pytest.approx(1.0)
    assert calibration[0]["selection_enrichment"] == pytest.approx(1.0)

    collision = candidate_collision_support_rows(rows)[0]
    assert collision["available"] is True
    assert collision["collision_rate"] == pytest.approx(0.0)
    unavailable = candidate_collision_support_rows([{**rows[0], "path_collision": None, "path_min_clearance_m": None}])[
        0
    ]
    assert unavailable["available"] is False
    assert unavailable["collision_rate"] is None

    first = deterministic_candidate_display_sample(rows, max_rows=3)
    second = deterministic_candidate_display_sample(reversed(rows), max_rows=3)
    assert [item["candidate_row_id"] for item in first["rows"]] == [item["candidate_row_id"] for item in second["rows"]]
    assert first["population_count"] == 6
    assert first["display_count"] == 3
    assert first["display_only"] is True
    with pytest.raises(ValueError, match="Unsupported candidate group field"):
        candidate_composition_rows(rows, group_by=cast(Any, "unsupported"))


class _NarrowCandidateFlowReader:
    """Fail-closed reader that exposes only the approved categorical flow surface."""

    def __init__(self) -> None:
        self.requested: list[str] = []
        self._arrays = {
            "rollouts/rollout_row_id": np.asarray([10, 11], dtype=np.int64),
            "rollouts/policy_id": np.asarray([0, 1], dtype=np.int32),
            "dictionaries/policy": np.frombuffer(b'["greedy", "softmax"]', dtype=np.uint8),
            "candidates/rollout_row_id": np.asarray([10, 10, 10, 11, 11, 11], dtype=np.int64),
            "candidates/step_index": np.asarray([0, 0, 1, 0, 1, 1], dtype=np.int16),
            "candidates/mixture_id": np.asarray([0, 0, -1, 1, 1, 1], dtype=np.int32),
            "candidates/position_id": np.asarray([0, 1, -1, 0, 1, 1], dtype=np.int32),
            "candidates/strategy_id": np.asarray([0, 1, -1, 0, 1, 1], dtype=np.int32),
            "candidates/actor_action_mask": np.asarray([True, True, False, True, False, True]),
            "candidates/selected_mask": np.asarray([True, False, True, False, False, True]),
            "candidates/primary_invalid_reason": np.asarray([0, 0, 1, 0, 6, 0], dtype=np.uint16),
        }

    def array(self, path: str) -> np.ndarray:
        self.requested.append(path)
        if path not in self._arrays:
            raise AssertionError(f"candidate flow accessed forbidden array: {path}")
        return self._arrays[path]

    def manifest(self) -> dict[str, object]:
        return {
            "manifest": {
                "generation": {
                    "writer_config": {
                        "candidate_mixture": {
                            "components": [{"name": "forward"}, {"name": "lateral"}],
                        }
                    }
                }
            }
        }


def test_candidate_flow_rows_are_narrow_conservative_and_preserve_violations() -> None:
    """The default provenance flow should conserve candidates without heavy audit reads."""

    reader = _NarrowCandidateFlowReader()
    rows = candidate_flow_rows(reader)

    assert rows == candidate_flow_rows(_NarrowCandidateFlowReader())
    assert {row["root_denominator"] for row in rows} == {6}
    assert {row["store_candidate_count"] for row in rows} == {6}
    assert all(row["fraction_of_root"] == pytest.approx(row["count"] / 6.0) for row in rows)
    assert sum(row["count"] for row in rows if row["source_stage"] == "root") == 6
    assert sum(row["count"] for row in rows if row["target_stage"] == "candidate_outcome") == 6
    assert {row["source_stage"] for row in rows} | {row["target_stage"] for row in rows} == {
        "root",
        "proposal",
        "actor_validity",
        "candidate_outcome",
    }
    assert not any(row["source_stage"] in {"mixture", "position", "orientation"} for row in rows)
    proposal_labels = {
        str(row["target_label"]) for row in rows if row["source_stage"] == "root" and row["target_stage"] == "proposal"
    }
    assert proposal_labels
    assert all("center=" in label and "view=" in label for label in proposal_labels)
    assert any(row["target_label"] == "selection_contract_violation" and row["count"] == 1 for row in rows)
    assert any(row["target_label"] == "invalid: PATH_SEGMENT_COLLISION" and row["count"] == 1 for row in rows)
    assert not any("oracle" in str(value) or "q_train" in str(value) for row in rows for value in row.values())
    assert set(reader.requested) == {
        "rollouts/rollout_row_id",
        "rollouts/policy_id",
        "dictionaries/policy",
        "candidates/rollout_row_id",
        "candidates/step_index",
        "candidates/mixture_id",
        "candidates/position_id",
        "candidates/strategy_id",
        "candidates/actor_action_mask",
        "candidates/selected_mask",
        "candidates/primary_invalid_reason",
    }

    incoming: dict[str, int] = {}
    outgoing: dict[str, int] = {}
    for row in rows:
        outgoing[str(row["source_id"])] = outgoing.get(str(row["source_id"]), 0) + int(row["count"])
        incoming[str(row["target_id"])] = incoming.get(str(row["target_id"]), 0) + int(row["count"])
    for node_id in incoming.keys() & outgoing.keys():
        assert incoming[node_id] == outgoing[node_id]


def test_candidate_flow_rows_apply_policy_and_depth_filters_to_the_root_denominator() -> None:
    """Policy and depth filters should be applied before all flow fractions are computed."""

    rows = candidate_flow_rows(
        _NarrowCandidateFlowReader(),
        policies=("softmax",),
        step_indices=(1,),
    )

    assert {row["root_denominator"] for row in rows} == {2}
    assert {row["store_candidate_count"] for row in rows} == {6}
    assert sum(row["count"] for row in rows if row["source_stage"] == "root") == 2
    assert not any(row["target_label"] == "selection_contract_violation" for row in rows)


def test_rollout_tree_summary_rows_group_selected_branch_provenance(tmp_path) -> None:
    """Tree summaries should aggregate selected-step routing without reading dense payloads."""

    records = build_rollout_records(horizon=2, num_samples=6, seed=45)[:2]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)

    rows = rollout_tree_summary_rows(reader)

    assert rows
    assert sum(int(row["selected_steps"]) for row in rows) == result.num_steps
    first = rows[0]
    assert first["policy"]
    assert first["step_label"].startswith("step ")
    assert first["selected_position"]
    assert first["selected_strategy"]
    assert first["selected_mixture"]
    assert first["mean_valid_fanout"] is not None
    assert first["mean_invalid_fraction"] is not None


def test_selected_depth_summary_rows_are_bounded_and_join_step_context(tmp_path) -> None:
    """Selected-depth inspection should summarize dense rows through rollout inspection helpers."""

    records = build_rollout_records(horizon=2, num_samples=6, seed=46)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)

    rows = selected_depth_summary_rows(reader, rollout_row_id=0, limit=1)
    assert selected_depth_summary_rows(reader, rollout_row_id=0, limit=0) == []

    assert len(rows) == 1
    row = rows[0]
    assert row["rollout_row_id"] == 0
    assert row["step_index"] == 0
    assert row["step_row_id"] == 0
    assert row["candidate_row_id"] == row["selected_candidate_row_id"]
    assert row["available"] is True
    assert row["valid_fraction"] == pytest.approx(1.0)
    assert row["finite_fraction"] == pytest.approx(1.0)
    assert row["depth_min_m"] == pytest.approx(1.0)
    assert row["depth_max_m"] == pytest.approx(1.0)
    assert row["depth_mean_m"] == pytest.approx(1.0)
    assert row["image_height"] == 240
    assert row["image_width"] == 240
    assert row["focal_x_px"] == pytest.approx(120.0)
    assert row["principal_y_px"] == pytest.approx(120.0)


def test_selected_depth_summary_rows_report_disabled_store_without_dense_scan(tmp_path) -> None:
    """Disabled selected-depth stores should expose explicit unavailable rows."""

    records = build_rollout_records(horizon=1, num_samples=6, seed=48)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records, selected_depth_enabled=False)
    reader = RolloutZarrStoreReader(result.store_dir)

    rows = selected_depth_summary_rows(reader)

    assert len(rows) == result.num_steps
    assert rows[0]["available"] is False
    assert rows[0]["valid_fraction"] is None
    assert "selected_depth_enabled=false" in str(rows[0]["warning"])


def test_selected_depth_preview_returns_one_bounded_image_payload(tmp_path) -> None:
    """Selected-depth previews should read one selected step and downsample for app plotting."""

    records = build_rollout_records(horizon=1, num_samples=6, seed=49)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)

    preview = selected_depth_preview(reader, step_row_id=0, max_size=24)

    assert preview["available"] is True
    assert preview["step_row_id"] == 0
    assert preview["candidate_row_id"] == reader.array("steps/selected_candidate_row_id")[0]
    assert preview["depth_m"].shape == (24, 24)
    assert preview["valid_mask"].shape == (24, 24)
    assert np.isfinite(preview["depth_m"]).all()
    assert preview["valid_mask"].all()
    assert preview["image_size_hw"] == (240, 240)


def test_mask_combinations_preserve_selected_rows_outside_q_train(tmp_path) -> None:
    """Selection is an actor decision, not a sequential stage after the training mask."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=50)[:1],
    )
    root = zarr.open_group(result.store_dir, mode="a")
    selected_row = int(np.flatnonzero(np.asarray(root["candidates/selected_mask"], dtype=np.bool_))[0])
    root["candidates/q_train_mask"][selected_row] = np.asarray(False, dtype=np.bool_)

    rows = mask_combination_rows(RolloutZarrStoreReader(result.store_dir))
    selected_without_training = next(row for row in rows if row["selected"] is True and row["q_train"] is False)

    assert selected_without_training["actor_action"] is True
    assert selected_without_training["count"] == 1
    assert selected_without_training["contract_valid"] is True
    assert selected_without_training["denominator"] == result.num_candidates
    assert selected_without_training["fraction_of_all"] == pytest.approx(1.0 / result.num_candidates)


def test_store_invariants_expose_mask_depth_target_and_q_h_contracts(tmp_path) -> None:
    """Invariant evidence should name the persisted contracts rather than hide them in validation text."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=2, num_samples=6, seed=51)[:1],
    )
    reader = RolloutZarrStoreReader(result.store_dir)

    rows = store_invariant_rows(reader, manifest=reader.manifest())
    assert store_invariant_rows(reader, manifest_payload=reader.manifest()) == rows
    by_id = {str(row["invariant_id"]): row for row in rows}

    assert by_id["schema_manifest"]["status"] == "PASS"
    assert by_id["selected_actor_mask"]["status"] == "PASS"
    assert by_id["q_train_supervision"]["status"] == "PASS"
    assert by_id["selected_depth_alignment"]["data_role"] == "oracle/evaluation"
    assert by_id["target_eval_alignment"]["data_role"] == "oracle/evaluation"
    assert by_id["target_protocol_lineage"]["status"] == "PASS"
    assert by_id["q_h_padding"]["status"] == "PASS"
    assert by_id["q_h_selected_transition"]["status"] == "PASS"
    assert by_id["q_h_factual_consistency"]["status"] == "PASS"
    assert "q_h/td_reward" in by_id["q_h_selected_transition"]["source_fields"]


def test_store_invariants_fail_selected_actor_mask_without_reclassifying_q_train(tmp_path) -> None:
    """A selected invalid action is a violation, while selected-not-q-train remains allowed."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=52)[:1],
    )
    root = zarr.open_group(result.store_dir, mode="a")
    selected_row = int(np.flatnonzero(np.asarray(root["candidates/selected_mask"], dtype=np.bool_))[0])
    root["candidates/actor_action_mask"][selected_row] = np.asarray(False, dtype=np.bool_)
    root["candidates/q_train_mask"][selected_row] = np.asarray(False, dtype=np.bool_)

    by_id = {str(row["invariant_id"]): row for row in store_invariant_rows(RolloutZarrStoreReader(result.store_dir))}

    assert by_id["selected_actor_mask"]["status"] == "FAIL"
    assert by_id["selected_actor_mask"]["violation_count"] == 1
    assert by_id["q_train_supervision"]["status"] == "PASS"


def test_comparable_policy_cohorts_gate_on_exact_scientific_keys(tmp_path) -> None:
    """Policy comparison should use matched source, target, budget, and generator lineage."""

    records = build_rollout_records(horizon=2, num_samples=6, seed=53)
    for record in records[1:]:
        record.lineage.source = copy.deepcopy(records[0].lineage.source)
        record.lineage.target = copy.deepcopy(records[0].lineage.target)
    result = write_rollout_zarr_store(tmp_path / "matched.zarr", records)

    projection = comparable_policy_cohorts(RolloutZarrStoreReader(result.store_dir))

    assert projection["eligible"] is True
    assert len(projection["eligible_cohort_rows"]) == 1
    assert projection["eligible_cohort_rows"][0]["comparison_count"] == 3
    assert projection["mismatch_rows"] == []
    assert "candidate_config" in projection["key_fields"]
    assert "horizon" in projection["key_fields"]

    mismatched_records = build_rollout_records(horizon=2, num_samples=6, seed=54)[:2]
    mismatched_records[1].lineage.source = copy.deepcopy(mismatched_records[0].lineage.source)
    mismatched_records[1].lineage.target = copy.deepcopy(mismatched_records[0].lineage.target)
    mismatched_records[1].lineage.policy.candidate_config_hash = "different-candidate-config"
    mismatch_result = write_rollout_zarr_store(tmp_path / "mismatched.zarr", mismatched_records)

    blocked = comparable_policy_cohorts(RolloutZarrStoreReader(mismatch_result.store_dir))

    assert blocked["eligible"] is False
    assert blocked["eligible_cohort_rows"] == []
    assert blocked["mismatch_rows"]
    assert "candidate_config" in blocked["mismatch_rows"][0]["mismatched_fields"]


def test_paired_policy_comparison_rows_are_deterministic_and_paired(tmp_path) -> None:
    """Paired summaries should bootstrap cohort deltas deterministically once three matches exist."""

    records = []
    base_records = build_rollout_records(horizon=1, num_samples=6, seed=55)[:2]
    for source_row_id in range(3):
        source_records = copy.deepcopy(base_records)
        for record in source_records:
            record.lineage.source = copy.deepcopy(source_records[0].lineage.source)
            record.lineage.source.source_row_id = source_row_id
            record.lineage.source.source_sample_index = source_row_id
            record.lineage.source.source_sample_key = f"fixture:paired:{source_row_id}"
            record.lineage.source.source_shard_row = source_row_id
            record.lineage.target = copy.deepcopy(source_records[0].lineage.target)
            record.lineage.target.target_row_id = source_row_id
            record.lineage.target.target_id = f"fixture-target-paired-{source_row_id}"
            record.lineage.target.matched_gt_target_row_id = 100 + source_row_id
            record.lineage.target.matched_gt_target_id = f"fixture-gt-target-paired-{source_row_id}"
        records.extend(source_records)
    result = write_rollout_zarr_store(tmp_path / "paired.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)

    first = paired_policy_comparison_rows(reader, bootstrap_samples=256, seed=7)
    second = paired_policy_comparison_rows(reader, bootstrap_samples=256, seed=7)

    assert first == second
    assert len(first) == 2
    assert {row["metric"] for row in first} == {
        "final_cumulative_target_rri",
        "final_cumulative_target_root_gain",
    }
    assert all(row["matched_cohort_count"] == 3 for row in first)
    assert all(row["policy_pair"] for row in first)
    assert all(row["median_paired_delta"] == row["paired_delta_median"] for row in first)
    assert all(row["bootstrap_ci_low"] is not None for row in first)
    assert all(row["bootstrap_ci_high"] is not None for row in first)


def test_selected_candidate_rank_rows_keep_negative_rewards_distinct_from_invalidity(tmp_path) -> None:
    """Regret ranks finite valid rewards even when the selected reward is negative."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=8, seed=58)[:1],
    )
    root = zarr.open_group(result.store_dir, mode="a")
    selected_row = int(np.flatnonzero(np.asarray(root["candidates/selected_mask"], dtype=np.bool_))[0])
    valid_rows = np.flatnonzero(np.asarray(root["candidates/actor_action_mask"], dtype=np.bool_))
    alternative_row = int(next(row for row in valid_rows.tolist() if row != selected_row))
    root["candidates/target_root_gain"][selected_row] = np.asarray(-0.25, dtype=np.float32)
    root["candidates/target_root_gain"][alternative_row] = np.asarray(0.75, dtype=np.float32)
    root["candidates/target_rri"][selected_row] = np.asarray(-0.5, dtype=np.float32)
    root["candidates/target_rri"][alternative_row] = np.asarray(0.5, dtype=np.float32)

    row = selected_candidate_rank_rows(RolloutZarrStoreReader(result.store_dir))[0]

    assert row["selected_actor_valid"] is True
    assert row["selected_reward_negative"] is True
    assert row["selected_rank"] > 1
    assert row["target_rri_rank"] > 1
    assert float(row["best_valid_target_root_gain"]) >= 0.75
    assert row["regret_to_best"] == pytest.approx(
        float(row["best_valid_target_root_gain"]) - float(row["selected_target_root_gain"])
    )


def test_selected_candidate_rank_rows_expose_softmax_policy_and_exact_rri_rank(tmp_path) -> None:
    """Selected-step evidence should distinguish policy mechanics from target-RRI rank."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=8, seed=61),
    )
    reader = RolloutZarrStoreReader(result.store_dir)
    softmax = next(row for row in selected_candidate_rank_rows(reader) if row["policy"] == "temperature_softmax")
    root = zarr.open_group(result.store_dir, mode="a")
    step_ids = np.asarray(root["candidates/step_row_id"], dtype=np.int64)
    actor_valid = np.asarray(root["candidates/actor_action_mask"], dtype=np.bool_)
    selected = np.asarray(root["candidates/selected_mask"], dtype=np.bool_)
    step_rows = np.flatnonzero((step_ids == int(softmax["step_row_id"])) & actor_valid)
    selected_row = int(np.flatnonzero((step_ids == int(softmax["step_row_id"])) & selected)[0])
    alternatives = [int(row) for row in step_rows.tolist() if int(row) != selected_row]
    assert len(alternatives) >= 3

    root["candidates/target_rri"][step_rows] = np.asarray(0.0, dtype=np.float32)
    root["candidates/selection_logits"][step_rows] = np.asarray(-1.0, dtype=np.float32)
    root["candidates/target_rri"][selected_row] = np.asarray(1.0, dtype=np.float32)
    root["candidates/selection_logits"][selected_row] = np.asarray(1.0, dtype=np.float32)
    for value, row in zip((3.0, 2.0), alternatives[:2], strict=True):
        root["candidates/target_rri"][row] = np.asarray(value, dtype=np.float32)
        root["candidates/selection_logits"][row] = np.asarray(value, dtype=np.float32)
    root["candidates/target_rri"][alternatives[2]] = np.asarray(1.0, dtype=np.float32)
    root["candidates/selection_logits"][alternatives[2]] = np.asarray(1.0, dtype=np.float32)

    ranked = next(
        row
        for row in selected_candidate_rank_rows(RolloutZarrStoreReader(result.store_dir))
        if row["step_row_id"] == softmax["step_row_id"]
    )

    assert ranked["temperature"] == pytest.approx(1.0)
    assert ranked["score_source"] == "target_root_gain"
    assert ranked["selected_probability"] is not None
    assert ranked["selection_entropy"] is not None
    assert ranked["selection_score_rank"] == 3
    assert ranked["target_rri_rank"] == 3
    assert ranked["rank_denominator"] == len(step_rows)
    assert ranked["target_rri_rank_label"] == f"3 / {len(step_rows)}"


def test_selected_candidate_rank_rows_mark_all_invalid_or_missing_rri_unavailable(tmp_path) -> None:
    """Invalid shells and missing selected RRI must not receive synthetic ranks."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=62)[:1],
    )
    root = zarr.open_group(result.store_dir, mode="a")
    step_row_id = int(np.asarray(root["steps/step_row_id"], dtype=np.int64)[0])
    step_rows = np.flatnonzero(np.asarray(root["candidates/step_row_id"], dtype=np.int64) == step_row_id)
    root["candidates/actor_action_mask"][step_rows] = np.asarray(False, dtype=np.bool_)
    selected_row = int(np.flatnonzero(np.asarray(root["candidates/selected_mask"], dtype=np.bool_))[0])
    root["candidates/target_rri"][selected_row] = np.asarray(np.nan, dtype=np.float32)

    row = selected_candidate_rank_rows(RolloutZarrStoreReader(result.store_dir))[0]

    assert row["selected_actor_valid"] is False
    assert row["target_rri_rank"] is None
    assert row["selection_score_rank"] is None
    assert row["rank_denominator"] == 0
    assert row["target_rri_rank_label"] == "unavailable"


def test_root_relative_candidate_rows_use_root_centered_z_up_world_metres(tmp_path) -> None:
    """Geometry projection should never expose cross-scene absolute centers as comparison axes."""

    records = build_rollout_records(horizon=1, num_samples=6, seed=59)[:1]
    root_tensor = records[0].evaluated.result.root_pose_world.tensor().clone()
    root_tensor[9:12] = root_tensor.new_tensor([1.0, 2.0, 3.0])
    records[0].evaluated.result.root_pose_world = records[0].evaluated.result.root_pose_world.__class__(root_tensor)
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)

    rows = root_relative_candidate_rows(reader, rollout_row_id=0)
    first = rows[0]
    world_pose = np.asarray(reader.array("candidates/pose_world_cam")[0], dtype=np.float32)
    root_pose = np.asarray(reader.array("rollouts/root_pose_world")[0], dtype=np.float32)

    assert len(rows) == result.num_candidates
    assert first["coordinate_frame"] == "root-centered ARIA world (RIGHT_HAND_Z_UP)"
    assert first["units"] == "m"
    assert first["root_relative_x_m"] == pytest.approx(float(world_pose[9] - root_pose[9]))
    assert first["root_relative_y_m"] == pytest.approx(float(world_pose[10] - root_pose[10]))
    assert first["root_relative_z_m"] == pytest.approx(float(world_pose[11] - root_pose[11]))
    assert "center_x" not in first


def test_failure_triage_emits_exact_mask_violation_rows(tmp_path) -> None:
    """Hard mask violations should carry exact rollout, step, and candidate identifiers."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=60)[:1],
    )
    root = zarr.open_group(result.store_dir, mode="a")
    selected_row = int(np.flatnonzero(np.asarray(root["candidates/selected_mask"], dtype=np.bool_))[0])
    root["candidates/actor_action_mask"][selected_row] = np.asarray(False, dtype=np.bool_)
    root["candidates/q_train_mask"][selected_row] = np.asarray(False, dtype=np.bool_)

    failures = suspicious_rollout_rows(RolloutZarrStoreReader(result.store_dir))
    violation = next(row for row in failures if row["kind"] == "selected_actor_mask_violation")

    assert violation["severity"] == "error"
    assert violation["rollout_row_id"] == 0
    assert violation["step_row_id"] == 0
    assert violation["candidate_row_id"] == int(root["candidates/candidate_row_id"][selected_row])
