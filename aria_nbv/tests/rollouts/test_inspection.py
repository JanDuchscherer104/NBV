"""Rollout inspection helper tests."""

# ruff: noqa: S101

from __future__ import annotations

import numpy as np
import pytest
import zarr

pytest.importorskip("efm3d")

from aria_nbv.app.panels.stored_rollouts import candidate_rows_for_rollout
from aria_nbv.rollouts import (
    RolloutSuspiciousQueryConfig,
    RolloutZarrStoreReader,
    candidate_audit_rows,
    candidate_group_summary_rows,
    discover_rollout_store_paths,
    rollout_step_objective_rows,
    rollout_store_inventory_rows,
    rollout_tree_summary_rows,
    selected_depth_preview,
    selected_depth_summary_rows,
    suspicious_rollout_rows,
    target_audit_rows,
    validity_waterfall_rows,
    write_rollout_zarr_store,
)
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
    first = candidates[0]
    assert first["candidate_row_id"] == 0
    assert first["scene"] == "fixture_box"
    assert first["position"] == "forward_local"
    assert first["mixture"] != ""
    assert first["target_root_gain"] != first["target_rri"]
    assert "motion_step_length_m" in first
    assert candidate_rows_for_rollout(reader, 0) == candidates

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
