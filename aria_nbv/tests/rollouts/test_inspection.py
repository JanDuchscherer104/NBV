"""Rollout inspection helper tests."""

# ruff: noqa: S101

from __future__ import annotations

import copy
from dataclasses import replace

import numpy as np
import pytest
import zarr

pytest.importorskip("efm3d")

from aria_nbv.rollouts import RolloutZarrStoreReader
from aria_nbv.rollouts.inspection import (
    RolloutSuspiciousQueryConfig,
    candidate_audit_rows,
    candidate_evidence_availability_rows,
    candidate_family_composition_rows,
    candidate_flow_rows,
    candidate_geometry_evidence_rows,
    candidate_group_summary_rows,
    candidate_plot_availability_rows,
    candidate_proposal_calibration_rows,
    candidate_selection_family_rows,
    candidate_selection_rank_family_rows,
    comparable_policy_cohorts,
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


def test_rollout_header_summary_keeps_coverage_and_split_denominators_distinct(tmp_path, monkeypatch) -> None:
    records = build_rollout_records(horizon=2, num_samples=6, seed=43)
    source_locations = (
        ("scene-a", "snippet-a", "train"),
        ("scene-a", "snippet-b", "val"),
        ("scene-b", "snippet-c", "test"),
    )
    records = [
        replace(
            record,
            lineage=replace(
                record.lineage,
                source=replace(
                    record.lineage.source,
                    scene_id=scene_id,
                    snippet_id=snippet_id,
                    split=split,
                ),
            ),
        )
        for record, (scene_id, snippet_id, split) in zip(records, source_locations, strict=True)
    ]
    written = write_rollout_zarr_store(tmp_path / "header.zarr", records)
    reader = RolloutZarrStoreReader(written.store_dir)
    array_calls: list[str] = []
    reader_array = reader.array

    def tracked_array(name: str):
        array_calls.append(name)
        return reader_array(name)

    monkeypatch.setattr(reader, "array", tracked_array)

    summary = rollout_header_summary(reader)

    assert array_calls == [
        "targets/target_row_id",
        "targets/target_valid_mask",
        "targets/gt_label_valid_mask",
        "rollouts/target_row_id",
        "rollouts/scene_id",
        "dictionaries/scene",
        "rollouts/split_id",
        "dictionaries/split",
    ]
    assert summary["source_scenes"] == 2
    assert summary["source_rows"] == 3
    assert summary["reference_scene_count"] == 100
    assert summary["reference_snippet_count"] == 4_608
    assert summary["source_snippets"] == 3
    assert summary["source_scene_coverage"] == pytest.approx(2 / 100)
    assert summary["source_snippet_coverage"] == pytest.approx(3 / 4_608)
    assert summary["store_bytes"] > 0
    assert summary["store_files"] > 0
    assert summary["bytes_per_rollout"] == pytest.approx(summary["store_bytes"] / written.num_rollouts)
    assert summary["source_split_counts"] == {"test": 1, "train": 1, "val": 1}
    assert summary["rollout_split_counts"] == {"test": 1, "train": 1, "val": 1}
    assert summary["horizon"] == 2
    assert summary["rollouts"] == written.num_rollouts
    assert summary["steps"] == written.num_steps
    assert summary["candidates"] == written.num_candidates
    assert summary["candidate_capacity"] == 12
    assert summary["target_protocol"] == "v0_gt_input"
    assert summary["steps_per_scene"] == 3.0
    assert summary["snippets_per_scene"] == (1, 1.5, 2)
    assert summary["target_tasks"] == 3
    assert summary["actor_valid_targets"] == 3
    assert summary["gt_supervised_targets"] == 3
    assert summary["actor_valid_targets_with_rollouts"] == 3
    assert summary["actor_valid_targets_per_scene"] == (1, 1.5, 2)
    assert summary["actor_valid_targets_with_rollouts_per_scene"] == (1, 1.5, 2)
    assert summary["rollouts_per_source_row"] == 1.0
    assert summary["candidates_per_step"] == 12.0
    assert summary["q_h_return_semantics"]
    assert summary["discount_gamma"] == 1.0

    missing = rollout_header_summary(reader, manifest_payload={"root_attrs": {}, "manifest": {}})
    assert missing["source_scenes"] is None
    assert missing["source_rows"] is None
    assert missing["source_snippets"] is None
    assert missing["source_scene_coverage"] is None
    assert missing["source_snippet_coverage"] is None
    assert missing["source_split_counts"] is None
    assert missing["rollout_split_counts"] == {"test": 1, "train": 1, "val": 1}
    assert missing["steps_per_scene"] is None
    assert missing["snippets_per_scene"] is None
    assert missing["target_tasks"] is None
    assert missing["actor_valid_targets"] is None
    assert missing["actor_valid_targets_with_rollouts"] is None
    assert missing["actor_valid_targets_per_scene"] is None
    assert missing["rollouts_per_source_row"] is None
    assert missing["candidates_per_step"] is None
    assert missing["q_h_return_semantics"] is None
    assert missing["discount_gamma"] is None

    malformed = reader.manifest()
    malformed["manifest"]["source_coverage"] = {"num_source_rows": 0, "scene_counts": {}, "sources": [{}]}
    malformed_summary = rollout_header_summary(reader, manifest_payload=malformed)
    assert malformed_summary["steps_per_scene"] is None
    assert malformed_summary["snippets_per_scene"] is None
    assert malformed_summary["rollouts_per_source_row"] is None


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
    assert first["root_to_target_x_m"] is not None
    assert first["root_to_target_y_m"] is not None
    assert first["generation_cohort_id"]
    assert first["acquisition_budget_steps"] == first["horizon"]
    assert first["candidate_config"] == records[0].lineage.policy.candidate_config_hash
    assert first["rollout_config"] == records[0].lineage.policy.rollout_config_hash
    assert first["branch_schedule"] == (records[0].lineage.policy.branch_schedule_id or "")

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
    assert "evaluation_horizon" in projection["key_fields"]
    assert "acquisition_budget_steps" in projection["key_fields"]
    assert "branch_schedule" not in projection["key_fields"]
    assert "branch_factor" not in projection["key_fields"]
    assert "beam_width" not in projection["key_fields"]

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


def test_oracle_headroom_pairs_persisted_schedule_treatments_and_blocks_invalid_context(tmp_path) -> None:
    """Reader-backed headroom should pair recipes while failing closed on invalid cohorts."""

    template = build_rollout_records(horizon=2, num_samples=6, seed=70)[0]
    one_step = copy.deepcopy(template)
    one_step.rollout_id_prefix = "fixture-oracle-one-step"
    one_step.lineage.policy.branch_schedule_id = "oracle_greedy"
    one_step.lineage.policy.rollout_config_hash = "rollout-config-one-step"
    one_step.evaluated.result.branch_factor = 1
    one_step.evaluated.result.beam_width = None
    lookahead = copy.deepcopy(template)
    lookahead.rollout_id_prefix = "fixture-oracle-lookahead"
    lookahead.lineage.policy.branch_schedule_id = "oracle_lookahead"
    lookahead.lineage.policy.rollout_config_hash = "rollout-config-lookahead"
    lookahead.evaluated.result.branch_factor = 2
    lookahead.evaluated.result.beam_width = 2

    matched = write_rollout_zarr_store(tmp_path / "oracle-matched.zarr", [one_step, lookahead])
    projection = comparable_policy_cohorts(RolloutZarrStoreReader(matched.store_dir))
    evidence = oracle_headroom_evidence(projection)

    assert evidence["evidence_status"] == "diagnostic_proxy"
    assert evidence["metric_source"] == "persisted_cumulative_root_gain"
    assert projection["eligible"] is True
    assert len(projection["eligible_cohort_rows"]) == 1
    assert projection["eligible_cohort_rows"][0]["comparison_count"] == 2
    assert {row["branch_schedule"] for row in projection["cohort_rows"]} == {
        "oracle_greedy",
        "oracle_lookahead",
    }
    assert {row["rollout_config_hash"] for row in projection["cohort_rows"]} == {
        "rollout-config-one-step",
        "rollout-config-lookahead",
    }
    assert len(evidence["oracle_rows"]) == 1
    oracle_blocker = next(row for row in evidence["blocker_rows"] if row["prerequisite"] == "exact oracle cohorts")
    assert oracle_blocker["status"] == "PASS"

    mismatched_lookahead = copy.deepcopy(lookahead)
    mismatched_lookahead.lineage.policy.candidate_config_hash = "different-candidate-config"
    mismatched = write_rollout_zarr_store(
        tmp_path / "oracle-mismatched.zarr",
        [one_step, mismatched_lookahead],
    )
    mismatched_projection = comparable_policy_cohorts(RolloutZarrStoreReader(mismatched.store_dir))
    mismatched_evidence = oracle_headroom_evidence(mismatched_projection)

    assert mismatched_projection["eligible"] is False
    assert "candidate_config" in mismatched_projection["mismatch_rows"][0]["mismatched_fields"]
    assert mismatched_evidence["oracle_rows"] == []

    duplicate_one_step = copy.deepcopy(one_step)
    duplicate_one_step.rollout_id_prefix = "fixture-oracle-one-step-duplicate"
    duplicate_one_step.lineage.policy.rollout_config_hash = "rollout-config-one-step-duplicate"
    ambiguous = write_rollout_zarr_store(
        tmp_path / "oracle-ambiguous.zarr",
        [one_step, duplicate_one_step, lookahead],
    )
    ambiguous_projection = comparable_policy_cohorts(RolloutZarrStoreReader(ambiguous.store_dir))
    ambiguous_evidence = oracle_headroom_evidence(ambiguous_projection)

    assert ambiguous_projection["eligible"] is False
    assert "ambiguous" in str(ambiguous_projection["cohort_summary_rows"][0]["reason"])
    assert ambiguous_evidence["oracle_rows"] == []


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
    assert all(row["evidence_status"] == "diagnostic_proxy" for row in first)
    assert all(row["metric_source"] == "persisted_cumulative_root_gain" for row in first)
    assert all(row["policy_pair"] for row in first)
    assert all(row["median_paired_delta"] == row["paired_delta_median"] for row in first)
    assert all(row["bootstrap_ci_low"] is not None for row in first)
    assert all(row["bootstrap_ci_high"] is not None for row in first)


def test_reconstruction_metric_plan_is_automatic_and_excludes_validity_metrics() -> None:
    rows = [
        {
            "rollout_row_id": 0,
            "step_index": 0,
            "scene": "scene-a",
            "policy": "policy-a",
            "horizon": 2,
            "cumulative_target_root_gain": 0.1,
            "cumulative_target_rri": 0.2,
            "selected_target_root_gain": 0.1,
            "selected_target_rri": 0.2,
            "selected_probability": 0.75,
            "selected_entropy": 0.5,
            "num_valid_candidates": 4,
            "invalid_fraction": 0.5,
        },
        {
            "rollout_row_id": 0,
            "step_index": 1,
            "scene": "scene-a",
            "policy": "policy-a",
            "horizon": 2,
            "cumulative_target_root_gain": 0.4,
            "cumulative_target_rri": 0.6,
            "selected_target_root_gain": 0.3,
            "selected_target_rri": 0.4,
            "selected_probability": None,
            "selected_entropy": 0.25,
            "num_valid_candidates": 2,
            "invalid_fraction": 0.75,
        },
    ]

    summaries = reconstruction_metric_summary_rows(rows)
    metrics = {str(row["metric"]) for row in summaries}
    root_gain = next(row for row in summaries if row["metric"] == "cumulative_target_root_gain")
    probability = next(row for row in summaries if row["metric"] == "selected_probability")

    assert len(summaries) == 6
    assert "valid_fanout" not in metrics
    assert "invalid_fraction" not in metrics
    assert root_gain["row_count"] == 2
    assert root_gain["rollout_count"] == 1
    assert root_gain["mean"] == pytest.approx(0.25)
    assert root_gain["median"] == pytest.approx(0.25)
    assert root_gain["q25"] == pytest.approx(0.175)
    assert root_gain["q75"] == pytest.approx(0.325)
    assert root_gain["endpoint_median"] == pytest.approx(0.4)
    assert probability["finite_count"] == 1
    assert probability["missing_count"] == 1


def test_reconstruction_endpoint_helpers_use_terminal_row_and_policy_horizon() -> None:
    rows = [
        {
            "rollout_row_id": rollout,
            "step_index": step,
            "scene": "scene-a",
            "policy": policy,
            "horizon": 2,
            "cumulative_target_root_gain": value,
        }
        for rollout, policy, step, value in (
            (0, "a", 0, 0.1),
            (0, "a", 1, 0.4),
            (1, "b", 0, 0.2),
            (1, "b", 1, 0.6),
        )
    ]

    endpoints = reconstruction_endpoint_rows(rows)
    summaries = reconstruction_endpoint_summary_rows(rows)

    assert [row["cumulative_target_root_gain"] for row in endpoints] == pytest.approx([0.4, 0.6])
    root_summaries = [row for row in summaries if row["metric"] == "cumulative_target_root_gain"]
    assert {(row["policy"], row["horizon"]) for row in root_summaries} == {("a", 2), ("b", 2)}
    assert all(row["finite_count"] == 1 for row in root_summaries)


def test_exact_policy_roles_do_not_use_fuzzy_identifiers() -> None:
    rows = [
        {"policy": "oracle_greedy", "branch_schedule": "oracle_greedy"},
        {"policy": "oracle_greedy", "branch_schedule": "oracle_lookahead"},
        {"policy": "oracle_greedy", "branch_schedule": "oracle_lookaheadish"},
        {"policy": "my_q_h_policy", "branch_schedule": "q_h"},
    ]

    resolved = exact_policy_role_rows(rows)

    assert [row["semantic_role"] for row in resolved] == ["oracle_one_step", "oracle_lookahead"]


def test_oracle_headroom_uses_only_same_exact_cohort() -> None:
    cohort_key = "exact-cohort"
    base = {
        "cohort_key": cohort_key,
        "cohort_id": "cohort-1",
        "horizon": 3,
        "final_cumulative_target_rri": 0.5,
    }
    rows = [
        {
            **base,
            "policy": "oracle_greedy",
            "branch_schedule": "oracle_greedy",
            "final_cumulative_target_root_gain": 0.4,
        },
        {
            **base,
            "policy": "oracle_greedy",
            "branch_schedule": "oracle_lookahead",
            "final_cumulative_target_root_gain": 0.7,
            "final_cumulative_target_rri": 0.8,
        },
        {
            **base,
            "policy": "learned_one_step",
            "branch_schedule": "learned_one_step",
            "final_cumulative_target_root_gain": 0.2,
        },
        {
            **base,
            "policy": "q_h",
            "branch_schedule": "q_h",
            "final_cumulative_target_root_gain": 0.5,
        },
    ]
    projection = {"cohort_rows": rows, "eligible_cohort_rows": [{"cohort_key": cohort_key}]}

    evidence = oracle_headroom_evidence(projection)

    assert evidence["oracle_rows"][0]["delta_look"] == pytest.approx(0.3)
    assert evidence["oracle_rows"][0]["delta_look_target_rri"] == pytest.approx(0.3)
    assert evidence["qh_rows"][0]["eta_q"] == pytest.approx(0.6)
    assert all(row["status"] == "PASS" for row in evidence["blocker_rows"])


def test_oracle_headroom_blocks_zero_exact_matches() -> None:
    projection = {
        "cohort_rows": [
            {
                "cohort_key": "one",
                "policy": "oracle_greedy",
                "branch_schedule": "oracle_greedy",
                "final_cumulative_target_root_gain": 0.4,
            },
            {
                "cohort_key": "look",
                "policy": "oracle_greedy",
                "branch_schedule": "oracle_lookahead",
                "final_cumulative_target_root_gain": 0.7,
            },
        ],
        "eligible_cohort_rows": [],
    }

    evidence = oracle_headroom_evidence(projection)

    assert evidence["oracle_rows"] == []
    assert evidence["qh_rows"] == []
    assert evidence["role_identifiers"]["oracle_one_step"]
    assert evidence["role_identifiers"]["oracle_lookahead"]
    exact = next(row for row in evidence["blocker_rows"] if row["prerequisite"] == "exact oracle cohorts")
    assert exact == {
        "prerequisite": "exact oracle cohorts",
        "status": "BLOCKED",
        "detail": "zero exact finite matches",
    }


def test_discounted_return_requires_declared_semantics_and_complete_rewards() -> None:
    rows = [
        {"rollout_row_id": 0, "step_index": 0, "selected_target_root_gain": 0.2},
        {"rollout_row_id": 0, "step_index": 1, "selected_target_root_gain": 0.4},
    ]

    evidence = discounted_rollout_return_rows(
        rows,
        return_semantics="cumulative_target_root_gain",
        discount_gamma=0.5,
    )
    blocked = discounted_rollout_return_rows(rows, return_semantics=None, discount_gamma=0.5)

    assert evidence["available"] is True
    assert evidence["rows"][0]["discounted_return"] == pytest.approx(0.4)
    assert blocked["available"] is False


def test_candidate_family_composition_is_lightweight_and_normalizes_selection(tmp_path, monkeypatch) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "candidate-composition.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=71)[:1],
    )
    monkeypatch.setattr(
        "aria_nbv.rollouts.inspection.candidate_audit_rows",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("full candidate audit must stay unloaded")),
    )
    reader = RolloutZarrStoreReader(result.store_dir)

    rows = candidate_family_composition_rows(reader)
    availability = candidate_evidence_availability_rows(reader)

    assert {row["dimension"] for row in rows} == {"policy", "strategy", "position", "mixture", "recipe"}
    assert sum(row["sampled_count"] for row in rows if row["dimension"] == "policy") == result.num_candidates
    recipes = [row for row in rows if row["dimension"] == "recipe"]
    assert sum(row["sampled_count"] for row in recipes) == result.num_candidates
    assert all("mixture=" in str(row["family"]) and "position=" in str(row["family"]) for row in recipes)
    assert all("view=" in str(row["family"]) for row in recipes)
    assert all(0.0 <= float(row["actor_valid_rate"]) <= 1.0 for row in rows)
    assert sum(row["selected_count"] for row in rows if row["dimension"] == "policy") == result.num_steps
    assert {row["evidence"] for row in availability} >= {"proposal calibration", "root-relative geometry"}
    assert all(row["generation_cohort_id"] for row in rows)
    assert all(
        {
            "policy",
            "horizon",
            "acquisition_budget_steps",
            "branch_factor",
            "beam_width",
            "temperature",
            "candidate_config",
            "rollout_config",
            "branch_schedule",
        }.issubset(row)
        for row in rows
    )


def test_candidate_proposal_calibration_compares_mass_with_empirical_frequency() -> None:
    rows = [
        {"policy": "p", "strategy": "a", "position": "x", "mixture": "m", "sampler_probability": 0.1},
        {"policy": "p", "strategy": "a", "position": "x", "mixture": "m", "sampler_probability": 0.2},
        {"policy": "p", "strategy": "b", "position": "y", "mixture": "n", "sampler_probability": 0.3},
        {"policy": "p", "strategy": "b", "position": "y", "mixture": "n", "sampler_probability": 0.4},
    ]

    calibration = candidate_proposal_calibration_rows(rows)
    strategy_a = next(row for row in calibration if row["dimension"] == "strategy" and row["family"] == "a")

    assert strategy_a["empirical_frequency"] == pytest.approx(0.5)
    assert strategy_a["proposal_mass"] == pytest.approx(0.3)
    assert strategy_a["calibration_gap"] == pytest.approx(0.2)


def test_candidate_reducers_isolate_exact_generation_cohorts() -> None:
    base = {
        "policy": "temperature_softmax",
        "horizon": 2,
        "acquisition_budget_steps": 2,
        "branch_factor": 4,
        "beam_width": 2,
        "temperature": 0.5,
        "candidate_config": "candidate-v1",
        "rollout_config": "rollout-v1",
        "branch_schedule": "4x2",
        "position": "radial",
        "mixture": "target",
        "target_root_gain": 0.2,
    }
    rows = [
        {
            **base,
            "generation_cohort_id": "first",
            "strategy": "a",
            "sampler_probability": 0.9,
            "actor_action": True,
            "selected": True,
        },
        {
            **base,
            "generation_cohort_id": "first",
            "strategy": "b",
            "sampler_probability": 0.1,
            "actor_action": True,
            "selected": False,
        },
        {
            **base,
            "generation_cohort_id": "second",
            "candidate_config": "candidate-v2",
            "strategy": "a",
            "sampler_probability": 0.1,
            "actor_action": True,
            "selected": False,
        },
        {
            **base,
            "generation_cohort_id": "second",
            "candidate_config": "candidate-v2",
            "strategy": "b",
            "sampler_probability": 0.9,
            "actor_action": True,
            "selected": True,
        },
    ]

    calibration = candidate_proposal_calibration_rows(rows)
    strategy_a = {
        row["generation_cohort_id"]: row
        for row in calibration
        if row["dimension"] == "strategy" and row["family"] == "a"
    }
    selection = candidate_selection_family_rows(rows)
    selected_a = {
        row["generation_cohort_id"]: row for row in selection if row["dimension"] == "strategy" and row["family"] == "a"
    }

    assert strategy_a["first"]["proposal_mass"] == pytest.approx(0.9)
    assert strategy_a["second"]["proposal_mass"] == pytest.approx(0.1)
    assert strategy_a["first"]["empirical_frequency"] == pytest.approx(0.5)
    assert strategy_a["second"]["empirical_frequency"] == pytest.approx(0.5)
    assert selected_a["first"]["selected_share_of_valid_availability"] == pytest.approx(1.0)
    assert selected_a["second"]["selected_share_of_valid_availability"] == pytest.approx(0.0)


def test_candidate_geometry_is_root_relative_and_wraps_target_bearing() -> None:
    rows = candidate_geometry_evidence_rows(
        [
            {
                "candidate_row_id": 1,
                "root_relative_x_m": 3.0,
                "root_relative_y_m": 4.0,
                "root_relative_z_m": 5.0,
                "root_to_target_x_m": 4.0,
                "root_to_target_y_m": 3.0,
                "motion_yaw_delta_deg": 170.0,
                "target_bearing_yaw_deg": -170.0,
            },
            {
                "candidate_row_id": 2,
                "root_relative_x_m": -8.0,
                "root_relative_y_m": 6.0,
                "root_relative_z_m": 5.0,
                "root_to_target_x_m": -6.0,
                "root_to_target_y_m": 8.0,
            },
        ]
    )
    row, transformed = rows

    assert row["root_radius_m"] == pytest.approx(5.0)
    assert row["root_azimuth_deg"] == pytest.approx(np.degrees(np.arctan2(4.0, 3.0)))
    assert row["root_elevation_deg"] == pytest.approx(45.0)
    assert row["orientation_to_target_bearing_deg"] == pytest.approx(-20.0)
    assert row["root_target_xy_distance_m"] == pytest.approx(5.0)
    assert row["target_normalized_forward"] == pytest.approx(24.0 / 25.0)
    assert row["target_normalized_lateral"] == pytest.approx(7.0 / 25.0)
    assert transformed["target_normalized_forward"] == pytest.approx(row["target_normalized_forward"])
    assert transformed["target_normalized_lateral"] == pytest.approx(row["target_normalized_lateral"])
    assert "center_x" not in row


def test_candidate_selection_is_normalized_by_actor_valid_family_availability() -> None:
    rows = [
        {
            "policy": "p",
            "strategy": "a",
            "position": "x",
            "mixture": "m",
            "actor_action": True,
            "selected": True,
            "target_root_gain": 0.2,
        },
        {
            "policy": "p",
            "strategy": "a",
            "position": "x",
            "mixture": "m",
            "actor_action": True,
            "selected": False,
            "target_root_gain": 0.4,
        },
        {
            "policy": "p",
            "strategy": "b",
            "position": "x",
            "mixture": "m",
            "actor_action": True,
            "selected": False,
            "target_root_gain": 0.9,
        },
    ]

    strategy = next(
        row for row in candidate_selection_family_rows(rows) if row["dimension"] == "strategy" and row["family"] == "a"
    )

    assert strategy["candidate_count"] == 2
    assert strategy["actor_valid_count"] == 2
    assert strategy["selected_share_of_valid_availability"] == pytest.approx(0.5)
    assert strategy["mean_valid_target_root_gain"] == pytest.approx(0.3)
    assert strategy["valid_availability_share"] == pytest.approx(2.0 / 3.0)
    assert strategy["selected_share"] == pytest.approx(1.0)
    assert strategy["selection_enrichment_vs_valid_availability"] == pytest.approx(1.5)


def test_candidate_rank_rows_join_exact_selected_generation_family() -> None:
    audit = [
        {
            "candidate_row_id": 7,
            "selected": True,
            "strategy": "toward_target",
            "position": "radial",
            "mixture": "target",
        }
    ]
    ranks = [
        {
            "selected_candidate_row_id": 7,
            "selection_score_rank": 1,
            "selected_rank": 2,
            "target_rri_rank": 3,
            "regret_to_best": 0.25,
        }
    ]

    joined = candidate_selection_rank_family_rows(audit, ranks)

    assert joined == [{**ranks[0], "strategy": "toward_target", "position": "radial", "mixture": "target"}]


def test_candidate_plot_availability_reports_missing_fields() -> None:
    blockers = candidate_plot_availability_rows(
        [{"root_relative_x_m": 1.0, "root_relative_y_m": 2.0}],
        [],
    )
    by_name = {row["evidence"]: row for row in blockers}

    assert by_name["root-relative XY"]["available"] is True
    assert by_name["proposal calibration"]["available"] is False
    assert by_name["selection rank / regret"]["available"] is False


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
