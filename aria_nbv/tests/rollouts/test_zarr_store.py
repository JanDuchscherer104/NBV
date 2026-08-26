"""Smoke tests for the standalone rollout Zarr replay store."""

# ruff: noqa: S101

from __future__ import annotations

import json

import numpy as np
import pytest
import torch
import zarr

pytest.importorskip("efm3d")

from efm3d.aria.pose import PoseTW

from aria_nbv.oracle.target_rri import TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1
from aria_nbv.oracle.target_selection import TARGET_INVALID_REASON_VERSION
from aria_nbv.rollouts import RolloutZarrStoreConfig, RolloutZarrStoreReader
from aria_nbv.rollouts.info_cli import main as rollouts_info_main
from aria_nbv.rollouts.manifest import ROLLOUT_MANIFEST_FILENAME, RolloutStoreManifestContext
from aria_nbv.rollouts.trace import INVALID_REASON_CODES, INVALID_REASON_VERSION
from aria_nbv.rollouts.zarr_store import (
    ROLLOUT_ZARR_SCHEMA_VERSION,
    validate_rollout_zarr_store,
    write_rollout_zarr_store,
)
from tests.rollout_fixtures import build_rollout_records


def _json_list(reader: RolloutZarrStoreReader, path: str) -> list[str]:
    return json.loads(bytes(reader.array(path).tolist()).decode("utf-8"))


def _steps(record):
    return [record.evaluated.step(0, step.step_index) for step in record.evaluated.result.trajectories[0].steps]


def _mask_target_eval_candidate_rows(step) -> None:
    valid_count = int(step.transition.candidates.mask_valid.detach().cpu().to(dtype=torch.bool).sum().item())
    step.evaluation.evidence.target_eval_candidate_points_world = torch.zeros((valid_count, 2, 3), dtype=torch.float32)
    step.evaluation.evidence.target_eval_candidate_point_lengths = torch.full((valid_count,), 2, dtype=torch.long)


def test_rollout_zarr_store_writes_reads_and_validates_records(tmp_path) -> None:
    records = build_rollout_records(horizon=2, num_samples=8, seed=7)
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        records,
        discount_gamma=0.95,
        target_protocol_version="v0_gt_input",
        source_offline_store_version="7",
        split_manifest_hash="fixture-split-manifest",
    )

    assert result.num_rollouts == 3
    assert result.num_steps == 6
    assert result.num_candidates > 0

    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors

    reader = RolloutZarrStoreReader(result.store_dir)
    assert reader.root.attrs["schema_id"] == "aria_nbv.rollout_zarr_q_invalidity"
    assert reader.root.attrs["schema_version"] == ROLLOUT_ZARR_SCHEMA_VERSION
    assert reader.root.attrs["return_semantics"] == "cumulative_target_root_gain"
    assert reader.root.attrs["manifest_path"] == ROLLOUT_MANIFEST_FILENAME
    assert result.manifest_path.exists()
    assert result.manifest_sha256 == reader.root.attrs["manifest_sha256"]
    assert "writer_config" not in reader.root.attrs
    assert "generation_manifest_json" not in reader.root["metadata"]
    manifest_bundle = reader.manifest()
    manifest = manifest_bundle["manifest"]
    assert manifest["schema_version"] == ROLLOUT_ZARR_SCHEMA_VERSION
    assert manifest["counts"]["rollouts"] == result.num_rollouts
    assert manifest["counts"]["steps"] == result.num_steps
    assert manifest["counts"]["candidates"] == result.num_candidates
    assert manifest["counts"]["candidate_diagnostics"] == result.num_candidates
    assert manifest["counts"]["target_eval_crops"] == 0
    assert manifest["counts"]["q_h_states"] == result.num_steps
    assert manifest["generation"]["invocation"]["mode"] == "programmatic"
    assert manifest["source_coverage"]["scene_counts"] == {"fixture_box": 3}
    assert manifest["source_coverage"]["source_shard_counts"] == {"vin-shard-000000": 3}
    assert "splits" not in reader.root
    assert "sources" in reader.root
    assert "q_h" in reader.root
    assert "selected_depth" in reader.root
    assert "candidate_diagnostics" in reader.root
    assert reader.root.attrs["q_h_view_persisted"] is True
    assert reader.root.attrs["q_h_view_role"] == "training_core_derived_cache"
    assert reader.root.attrs["q_h_chunk_states"] == 64
    assert reader.root.attrs["q_h_state_count"] == result.num_steps
    assert set(reader.array("sources/source_row_id").tolist()) == {0, 1, 2}
    assert set(reader.array("rollouts/source_row_id").tolist()) == {0, 1, 2}
    root_pose = reader.array("rollouts/root_pose_world")
    assert root_pose.shape == (result.num_rollouts, 12)
    assert np.isfinite(root_pose).all()
    assert reader.array("rollouts/root_time_ns").shape == (result.num_rollouts,)
    assert reader.array("rollouts/root_trajectory_index").shape == (result.num_rollouts,)
    assert reader.array("rollouts/root_frame_index").shape == (result.num_rollouts,)
    assert reader.array("targets/target_projected_area_pixels").tolist() == [512.0, 512.0, 512.0]
    assert np.allclose(reader.array("targets/target_effective_support_count"), np.asarray([12.0, 12.0, 12.0]))
    assert reader.array("targets/target_semidense_support_count").tolist() == [7, 7, 7]
    assert reader.array("targets/target_evl_support_count").tolist() == [5, 5, 5]
    assert np.allclose(reader.array("targets/target_visibility_score"), np.asarray([0.8, 0.8, 0.8]))
    assert np.allclose(reader.array("targets/target_support_score"), np.asarray([1.0, 1.0, 1.0]))
    assert np.allclose(reader.array("targets/target_deficit_score"), np.asarray([0.9, 0.9, 0.9]))

    deleted_candidate_arrays = {
        "candidate_valid_mask",
        "padded_mask",
        "heavy_diag_available_mask",
        "selection_entropy",
    }
    assert deleted_candidate_arrays.isdisjoint(set(reader.root["candidates"].array_keys()))
    assert "transition_id" not in set(reader.root["steps"].array_keys())
    assert "transition" not in set(reader.root["dictionaries"].array_keys())

    candidate_valid = reader.array("candidates/actor_action_mask")
    selection_probabilities = reader.array("candidates/selection_probabilities")
    assert np.all(selection_probabilities[~candidate_valid] == 0.0)
    assert np.all(reader.array("candidates/selected_mask") <= candidate_valid)
    assert np.array_equal(
        reader.array("candidate_diagnostics/candidate_row_id"),
        reader.array("candidates/candidate_row_id"),
    )
    assert reader.array("candidates/position_id").shape == (result.num_candidates,)
    assert reader.array("candidates/position_pair_id").shape == (result.num_candidates,)
    assert reader.array("candidates/gaze_variant_id").shape == (result.num_candidates,)
    assert np.all(reader.array("candidates/position_pair_id") == -1)
    assert np.all(reader.array("candidates/gaze_variant_id") == -1)
    assert np.array_equal(
        reader.array("candidate_diagnostics/position_id"),
        reader.array("candidates/position_id"),
    )
    assert reader.array("candidate_diagnostics/path_collision_mask").dtype == np.dtype(np.bool_)
    for diagnostic_name in (
        "mesh_distance_m",
        "path_min_clearance_m",
        "free_space_margin_m",
        "motion_step_length_m",
        "motion_height_delta_m",
        "motion_backward_step_m",
        "motion_yaw_delta_deg",
        "target_distance_m",
        "target_bearing_yaw_deg",
    ):
        values = reader.array(f"candidate_diagnostics/{diagnostic_name}")
        assert values.dtype == np.dtype(np.float32)
        assert values.shape == (result.num_candidates,)
    selected_depth = reader.root["selected_depth"]
    assert selected_depth.attrs["enabled"] is True
    assert selected_depth.attrs["codec"] == "blosc:zstd:clevel=5:bitshuffle"
    assert selected_depth.attrs["renderer"] == "Pytorch3DDepthRenderer"
    assert selected_depth.attrs["source_resolution"] == "exact_output_size"
    assert reader.root.attrs["selected_depth_role"] == "selected_successor_state_history"
    assert reader.root.attrs["selected_depth_znear_m"] == pytest.approx(0.001)
    assert reader.root.attrs["selected_depth_zfar_m"] == pytest.approx(20.0)
    assert selected_depth["depth_m"].dtype == np.dtype(np.float16)
    assert selected_depth["valid_mask"].dtype == np.dtype(np.bool_)
    assert selected_depth["depth_m"].shape == (result.num_steps, 240, 240)
    assert selected_depth["valid_mask"].shape == (result.num_steps, 240, 240)
    assert selected_depth["depth_m"].chunks == (min(16, result.num_steps), 240, 240)
    assert np.array_equal(reader.array("selected_depth/step_row_id"), reader.array("steps/step_row_id"))
    assert np.array_equal(
        reader.array("selected_depth/candidate_row_id"),
        reader.array("steps/selected_candidate_row_id"),
    )
    target_eval_crops = reader.root["target_eval_crops"]
    assert target_eval_crops.attrs["enabled"] is False
    assert target_eval_crops.attrs["retention"] == "disabled_training_core"
    assert target_eval_crops.attrs["role"] == "oracle_eval_only"
    assert target_eval_crops.attrs["coordinate_frame"] == "world"
    assert target_eval_crops.attrs["max_points"] == 50_000
    crop_rows = int(target_eval_crops["crop_row_id"].shape[0])
    assert crop_rows == manifest["counts"]["target_eval_crops"]
    assert target_eval_crops["points_world"].shape == (crop_rows, 50_000, 3)
    assert target_eval_crops["mask"].shape == (crop_rows, 50_000)
    assert crop_rows == 0

    q_h = reader.q_h_view()
    q_h_group = reader.root["q_h"]
    assert q_h_group.attrs["view_role"] == "training_core_derived_cache"
    assert q_h_group.attrs["td_semantics"] == "selected_transition_only"
    assert q_h_group.attrs["reward_metric"] == "target_root_gain"
    assert q_h_group.attrs["return_semantics"] == "cumulative_target_root_gain"
    assert q_h_group.attrs["chunk_states"] == 64
    assert q_h_group.attrs["state_count"] == result.num_steps
    assert {
        "one_step_scene_rri",
        "bootstrap_next_step_row_id",
        "terminal_mask",
        "discount",
    }.isdisjoint(set(q_h_group.array_keys()))
    q_candidate_row_id = q_h["candidate_row_id"]
    valid_action_mask = q_h["valid_action_mask"]
    q_train_mask = q_h["q_train_mask"]

    assert np.array_equal(reader.array("q_h/state_step_row_id"), q_h["state_step_row_id"])
    assert set(q_h["source_row_id"].tolist()) == {0, 1, 2}
    assert q_candidate_row_id.shape == valid_action_mask.shape
    assert np.all(q_train_mask <= valid_action_mask)
    assert "q_target_target_rri" not in q_h
    assert "one_step_target_root_gain" in q_h
    assert "position_id" in q_h
    assert "td_reward" in q_h
    assert np.isfinite(q_h["one_step_target_root_gain"][q_train_mask]).all()
    assert np.isfinite(q_h["td_reward"]).all()
    assert np.all(~valid_action_mask[q_candidate_row_id < 0])
    derived_q_h = reader.q_h_view(discount_gamma=0.5)
    assert np.any(derived_q_h["td_discount"] != q_h["td_discount"])
    for name, actual in q_h.items():
        expected = derived_q_h[name]
        if name == "td_discount":
            continue
        if np.issubdtype(actual.dtype, np.floating):
            assert np.allclose(actual, expected, equal_nan=True)
        else:
            assert np.array_equal(actual, expected)


def test_rollout_zarr_persists_pair_provenance_columns(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=4, seed=17)[:1]
    candidates = _steps(records[0])[0].transition.candidates
    count = int(candidates.mask_valid.numel())
    candidates.position_pair_id = torch.arange(count, dtype=torch.int64)
    candidates.gaze_variant_id = torch.zeros(count, dtype=torch.int64)

    result = write_rollout_zarr_store(
        tmp_path / "paired.zarr",
        records,
        discount_gamma=0.95,
        target_protocol_version="v0_gt_input",
        source_offline_store_version="7",
        split_manifest_hash="fixture-split-manifest",
    )
    reader = RolloutZarrStoreReader(result.store_dir)

    assert reader.array("candidates/position_pair_id")[:count].tolist() == list(range(count))
    assert reader.array("candidates/gaze_variant_id")[:count].tolist() == [0] * count


def test_rollout_zarr_dense_valid_contract_is_proven_by_persisted_support(tmp_path) -> None:
    records = build_rollout_records(horizon=2, num_samples=8, seed=7)
    result = write_rollout_zarr_store(
        tmp_path / "dense-valid.zarr",
        records,
        oracle_query_mode="dense_valid",
        label_support_semantics="equals_action_on_realized_steps_v1",
    )

    reader = RolloutZarrStoreReader(result.store_dir)
    q_h = reader.q_h_view()
    assert reader.root.attrs["oracle_query_mode"] == "dense_valid"
    assert reader.root.attrs["label_support_semantics"] == "equals_action_on_realized_steps_v1"
    assert np.array_equal(q_h["q_train_mask"], q_h["valid_action_mask"])
    validation = reader.validate()
    assert validation.ok, validation.errors


def test_rollout_zarr_dense_valid_contract_rejects_subset_support(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=25)[:1]
    records[0].lineage.target.target_protocol_version = "v1-observed"
    records[0].lineage.target.target_row_id = 11
    records[0].lineage.target.target_id = "target-invalid"
    records[0].lineage.target.target_invalid_reason_bitset = 1 << 10
    records[0].lineage.target.target_primary_invalid_reason = 10
    records[0].lineage.target.gt_match_status = "unmatched_gt"

    with pytest.raises(ValueError, match="dense-valid.*q_train_mask"):
        write_rollout_zarr_store(
            tmp_path / "invalid-dense-valid.zarr",
            records,
            target_protocol_version="v1-observed",
            oracle_query_mode="dense_valid",
            label_support_semantics="equals_action_on_realized_steps_v1",
        )


def test_rollout_zarr_validation_rejects_dense_support_tampering(tmp_path) -> None:
    records = build_rollout_records(horizon=2, num_samples=8, seed=19)
    result = write_rollout_zarr_store(
        tmp_path / "tampered-dense-valid.zarr",
        records,
        oracle_query_mode="dense_valid",
        label_support_semantics="equals_action_on_realized_steps_v1",
    )

    root = zarr.open_group(result.store_dir, mode="a")
    q_train_mask = np.asarray(root["q_h/q_train_mask"][:], dtype=np.bool_)
    tampered_row = tuple(int(index) for index in np.argwhere(q_train_mask)[0])
    root["q_h/q_train_mask"][tampered_row] = False

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("dense-valid q_train_mask" in error for error in validation.errors)


def test_rollout_zarr_rejects_mixed_query_and_support_profiles(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=31)[:1]

    with pytest.raises(ValueError, match="must be declared together"):
        write_rollout_zarr_store(
            tmp_path / "mixed-profile.zarr",
            records,
            oracle_query_mode="dense_valid",
            label_support_semantics="subset_of_action_v1",
        )


def test_rollout_zarr_rejects_stale_schema_version(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=11)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)

    root = zarr.open_group(result.store_dir, mode="a")
    root.attrs["schema_version"] = "0.8-global-target-rows"

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any(
        "0.8-global-target-rows" in error and ROLLOUT_ZARR_SCHEMA_VERSION in error for error in validation.errors
    )


def test_rollout_zarr_can_persist_target_eval_crops_for_audit_profile(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=33)[:1]

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records, target_eval_crops_enabled=True)
    reader = RolloutZarrStoreReader(result.store_dir)

    target_eval_crops = reader.root["target_eval_crops"]
    assert reader.root.attrs["target_eval_crops_enabled"] is True
    assert target_eval_crops.attrs["enabled"] is True
    assert target_eval_crops.attrs["retention"] == "sampled_audit"
    crop_rows = int(target_eval_crops["crop_row_id"].shape[0])
    assert crop_rows >= result.num_steps
    assert target_eval_crops["points_world"].shape == (crop_rows, 50_000, 3)
    assert target_eval_crops["mask"].shape == (crop_rows, 50_000)
    assert np.array_equal(
        np.asarray(target_eval_crops["mask"]).sum(axis=1).astype(np.int32),
        np.asarray(target_eval_crops["lengths"]),
    )
    assert set(np.asarray(target_eval_crops["source_role_id"]).tolist()) == {0, 1}
    assert np.any(np.asarray(target_eval_crops["candidate_row_id"]) == -1)
    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors


def test_rollout_zarr_validation_rejects_missing_hot_position_id(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=31)[:1]
    for step in _steps(records[0]):
        step.transition.candidates.position_id = None
        step.transition.candidates.extras.clear()
        n = int(step.transition.candidates.mask_valid.numel())
        step.transition.candidates.extras.update(
            {
                "path_collision_mask": torch.zeros(n, dtype=torch.bool),
                "path_collision_applicable_mask": torch.zeros(n, dtype=torch.bool),
                "path_collision_evaluated_mask": torch.zeros(n, dtype=torch.bool),
            }
        )

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)

    assert np.array_equal(
        reader.array("candidate_diagnostics/candidate_row_id"),
        reader.array("candidates/candidate_row_id"),
    )
    assert np.all(reader.array("candidate_diagnostics/position_id") == -1)
    assert np.all(reader.array("candidates/position_id") == -1)
    assert not reader.array("candidate_diagnostics/path_collision_mask").any()
    for name in (
        "mesh_distance_m",
        "path_min_clearance_m",
        "free_space_margin_m",
        "motion_step_length_m",
        "motion_height_delta_m",
        "motion_backward_step_m",
        "motion_yaw_delta_deg",
        "target_distance_m",
        "target_bearing_yaw_deg",
    ):
        assert np.isnan(reader.array(f"candidate_diagnostics/{name}")).all()

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("position_id" in error for error in validation.errors)


def test_rollout_zarr_validates_path_collision_diagnostics_against_invalidity(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=32)[:1]
    step = _steps(records[0])[0]
    collision_shell_index = 0 if int(step.transition.selected_shell_index) != 0 else 1
    candidate_valid = step.transition.candidates.mask_valid.clone()
    candidate_valid[collision_shell_index] = False
    step.transition.candidates.mask_valid = candidate_valid
    path_mask = torch.zeros_like(candidate_valid, dtype=torch.bool)
    path_mask[collision_shell_index] = True
    step.transition.candidates.masks["PathCollisionRule"] = ~path_mask
    step.transition.candidates.extras["path_collision_mask"] = path_mask
    step.transition.candidates.extras["path_collision_applicable_mask"] = torch.ones_like(path_mask)
    step.transition.candidates.extras["path_collision_evaluated_mask"] = torch.ones_like(path_mask)
    _mask_target_eval_candidate_rows(step)

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors
    reader = RolloutZarrStoreReader(result.store_dir)
    path_bit = 1 << INVALID_REASON_CODES["PATH_SEGMENT_COLLISION"]
    assert int(reader.array("candidates/invalid_reason_bitset")[collision_shell_index]) & path_bit
    assert (
        int(reader.array("candidates/primary_invalid_reason")[collision_shell_index])
        == INVALID_REASON_CODES["PATH_SEGMENT_COLLISION"]
    )

    root = zarr.open_group(result.store_dir, mode="a")
    root["candidates/invalid_reason_bitset"][collision_shell_index] = np.asarray(1, dtype=np.uint32)
    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("PATH_SEGMENT_COLLISION" in error for error in validation.errors)


def test_rollout_zarr_writer_rejects_missing_collision_diagnostics(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=33)[:1]
    step = _steps(records[0])[0]
    for name in (
        "path_collision_mask",
        "path_collision_applicable_mask",
        "path_collision_evaluated_mask",
    ):
        step.transition.candidates.extras.pop(name, None)
    _mask_target_eval_candidate_rows(step)

    with pytest.raises(ValueError, match="required candidate diagnostics"):
        write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)


def test_rollout_zarr_validation_requires_selected_depth_when_enabled(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=9)[:1]
    for step in _steps(records[0]):
        step.evaluation.evidence.selected_depth_m = None
        step.evaluation.evidence.selected_depth_valid_mask = None

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("selected_depth/step_row_id" in error or "selected-depth" in error for error in validation.errors)


def test_rollout_zarr_validation_reports_mismatched_selected_depth_shapes(tmp_path) -> None:
    """Malformed depth/mask shapes must return structured validation errors, not broadcast exceptions."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=9)[:1],
    )
    root = zarr.open_group(result.store_dir, mode="a")
    valid_mask = root["selected_depth/valid_mask"]
    valid_mask.resize((valid_mask.shape[0], valid_mask.shape[1] - 1, valid_mask.shape[2]))

    validation = validate_rollout_zarr_store(result.store_dir)

    assert not validation.ok
    assert any("selected_depth/valid_mask shape" in error for error in validation.errors)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("zero_focal", "finite positive pinhole focal"),
        ("nonfinite_principal", "finite pixel coordinates"),
        ("wrong_raster_size", "equal the persisted depth raster size"),
        ("valid_below_clip", "within the declared clip range"),
        ("invalid_nonfill", "declared invalid fill value"),
    ),
)
def test_rollout_zarr_validation_rejects_invalid_selected_camera_depth_contract(
    tmp_path, mutation: str, message: str
) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=9)[:1],
    )
    root = zarr.open_group(result.store_dir, mode="a")
    if mutation == "zero_focal":
        root["selected_depth/focal_px"][0, 0] = 0.0
    elif mutation == "nonfinite_principal":
        root["selected_depth/principal_point_px"][0, 0] = np.inf
    elif mutation == "wrong_raster_size":
        root["selected_depth/image_size_hw"][0] = np.array([120, 240], dtype=np.int32)
    elif mutation == "valid_below_clip":
        root["selected_depth/valid_mask"][0, 0, 0] = True
        root["selected_depth/depth_m"][0, 0, 0] = 0.0
    else:
        root["selected_depth/valid_mask"][0, 0, 0] = False
        root["selected_depth/depth_m"][0, 0, 0] = 1.0

    validation = validate_rollout_zarr_store(result.store_dir)

    assert not validation.ok
    assert any(message in error for error in validation.errors)


def test_rollout_zarr_selected_action_td_fields_align_with_step_rows(tmp_path) -> None:
    records = build_rollout_records(horizon=2, num_samples=6, seed=3)
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)
    q_h = reader.q_h_view()

    step_selected = reader.array("steps/selected_candidate_row_id")
    td_selected = q_h["td_selected_candidate_row_id"]
    td_next = q_h["td_next_step_row_id"]
    td_terminal = q_h["td_terminal_mask"]
    td_discount = q_h["td_discount"]

    assert np.array_equal(td_selected, step_selected)
    assert td_next.shape == td_terminal.shape == td_selected.shape
    assert np.any(~td_terminal)
    assert np.any(td_terminal)
    assert np.all(td_discount[td_terminal] == 0.0)
    assert np.all(td_discount[~td_terminal] > 0.0)


def test_rollout_zarr_requires_explicit_target_root_gain_for_q_training(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=11)[:1]
    for step in _steps(records[0]):
        step.evaluation.labels.metrics.clear()

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)
    q_h = reader.q_h_view()

    assert np.isfinite(reader.array("candidates/selection_logits")).any()
    assert np.isnan(reader.array("candidates/target_rri")).all()
    assert np.isnan(reader.array("candidates/target_root_gain")).all()
    assert not reader.array("candidates/q_train_mask").any()
    assert np.isnan(q_h["one_step_target_rri"]).all()
    assert np.isnan(q_h["one_step_target_root_gain"]).all()
    assert not q_h["q_train_mask"].any()


def test_rollout_zarr_never_backfills_scene_rri_from_generic_rri(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=10)[:1]
    for step in _steps(records[0]):
        generic = torch.arange(step.transition.candidates.mask_valid.shape[0], dtype=torch.float32)
        step.evaluation.labels.metrics.clear()
        step.evaluation.labels.metrics.update(rri=generic, target_rri=generic, target_root_gain=generic + 10.0)

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)
    q_h = reader.q_h_view()

    assert np.isfinite(reader.array("candidates/target_rri")).any()
    assert np.isfinite(reader.array("candidates/target_root_gain")).any()
    assert np.isnan(reader.array("candidates/scene_rri")).all()
    assert "one_step_scene_rri" not in q_h


def test_rollout_zarr_qh_reward_uses_target_root_gain_not_target_rri(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=14)[:1]
    for step in _steps(records[0]):
        full = torch.arange(step.transition.candidates.mask_valid.shape[0], dtype=torch.float32)
        step.evaluation.labels.metrics["target_rri"] = full + 1.0
        step.evaluation.labels.metrics["target_root_gain"] = full + 101.0

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)
    q_h = reader.q_h_view()
    selected_index = int(q_h["selected_candidate_index"][0])

    assert q_h["td_reward"][0] == pytest.approx(q_h["one_step_target_root_gain"][0, selected_index])
    assert q_h["td_reward_target_rri"][0] == pytest.approx(q_h["one_step_target_rri"][0, selected_index])
    assert q_h["td_reward"][0] != pytest.approx(q_h["td_reward_target_rri"][0])


def test_rollout_zarr_masks_invalid_candidate_oracle_labels(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=12)[:1]
    step = _steps(records[0])[0]
    invalid_shell_index = 0 if int(step.transition.selected_shell_index) != 0 else 1
    step.transition.candidates.mask_valid[invalid_shell_index] = False
    step.evaluation.labels.metrics["target_rri"] = torch.arange(
        step.transition.candidates.mask_valid.shape[0], dtype=torch.float32
    )
    step.evaluation.labels.metrics["target_root_gain"] = (
        torch.arange(step.transition.candidates.mask_valid.shape[0], dtype=torch.float32) + 10.0
    )
    valid_count = int(step.transition.candidates.mask_valid.sum().item())
    step.evaluation.evidence.target_eval_candidate_points_world = (
        step.evaluation.evidence.target_eval_candidate_points_world[:valid_count]
    )
    step.evaluation.evidence.target_eval_candidate_point_lengths = (
        step.evaluation.evidence.target_eval_candidate_point_lengths[:valid_count]
    )

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)
    q_h = reader.q_h_view()

    candidate_valid = reader.array("candidates/actor_action_mask")
    assert not candidate_valid[invalid_shell_index]
    assert np.isnan(reader.array("candidates/target_rri")[invalid_shell_index])
    assert np.isnan(reader.array("candidates/target_root_gain")[invalid_shell_index])
    assert not reader.array("candidates/q_train_mask")[invalid_shell_index]
    assert np.isnan(q_h["one_step_target_rri"][0, invalid_shell_index])
    assert np.isnan(q_h["one_step_target_root_gain"][0, invalid_shell_index])
    assert not q_h["q_train_mask"][0, invalid_shell_index]


def test_rollout_zarr_preserves_multi_target_identity_in_qh_view(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=13)[:2]
    records[0].lineage.target.target_row_id = 7
    records[0].lineage.target.target_source_index = None
    records[0].lineage.target.target_id = "target-a"
    records[0].lineage.target.target_selection_policy = "greedy_top_k"
    records[0].lineage.target.target_selection_rank = 0
    records[0].lineage.target.target_selection_score = 0.75
    records[0].lineage.target.target_invalid_reason_bitset = 1
    records[0].lineage.target.target_primary_invalid_reason = 0
    records[0].lineage.target.target_reason_code_version = TARGET_INVALID_REASON_VERSION
    records[0].lineage.target.matched_gt_target_row_id = 70
    records[0].lineage.target.matched_gt_target_id = "gt-target-a"
    records[0].lineage.target.gt_match_iou = 0.8
    records[0].lineage.target.gt_match_score = 0.8
    records[0].lineage.target.gt_match_status = "matched"
    records[1].lineage.target.target_row_id = 9
    records[1].lineage.target.target_source_index = None
    records[1].lineage.target.target_id = "target-b"
    records[1].lineage.target.target_selection_policy = "greedy_top_k"
    records[1].lineage.target.target_selection_rank = 1
    records[1].lineage.target.target_selection_score = 0.5
    records[1].lineage.target.target_invalid_reason_bitset = 1
    records[1].lineage.target.target_primary_invalid_reason = 0
    records[1].lineage.target.target_reason_code_version = TARGET_INVALID_REASON_VERSION
    records[1].lineage.target.matched_gt_target_row_id = None
    records[1].lineage.target.matched_gt_target_id = None
    records[1].lineage.target.gt_match_status = "unmatched_gt"

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)
    q_h = reader.q_h_view()

    target_rows = reader.array("targets/target_row_id")
    target_names = _json_list(reader, "dictionaries/target")
    target_name_ids = reader.array("targets/target_id")

    assert set(target_rows.tolist()) == {0, 1}
    assert {target_names[int(index)] for index in target_name_ids.tolist()} == {"target-a", "target-b"}
    assert set(reader.array("rollouts/target_row_id").tolist()) == {0, 1}
    assert set(q_h["target_row_id"].tolist()) == {0, 1}
    assert reader.array("targets/target_source_index").tolist() == [7, 9]
    assert reader.array("targets/target_selection_rank").tolist() == [0, 1]
    assert np.allclose(reader.array("targets/target_selection_score"), np.asarray([0.75, 0.5], dtype=np.float32))
    assert reader.array("targets/matched_gt_target_row_id").tolist() == [70, -1]
    assert reader.array("targets/gt_label_valid_mask").tolist() == [True, False]
    config_names = _json_list(reader, "dictionaries/config")
    reason_version_ids = reader.array("targets/target_reason_code_version_id")
    assert {config_names[int(index)] for index in reason_version_ids.tolist()} == {TARGET_INVALID_REASON_VERSION}
    match_status = _json_list(reader, "dictionaries/target_match_status")
    status_ids = reader.array("targets/gt_match_status_id")
    assert [match_status[int(index)] for index in status_ids.tolist()] == ["matched", "unmatched_gt"]


def test_rollout_zarr_globalizes_selector_local_target_rows(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=14)[:2]
    for source_row_id, record in enumerate(records):
        record.lineage.source.source_row_id = source_row_id
        record.lineage.source.source_sample_index = source_row_id
        record.lineage.source.snippet_id = f"snippet-{source_row_id}"
        record.lineage.target.target_row_id = 0
        record.lineage.target.target_source_index = 0
        record.lineage.target.target_id = f"scene:snippet-{source_row_id}:target-local-0"
        record.lineage.target.matched_gt_target_id = f"scene:snippet-{source_row_id}:gt-local-0"
        record.lineage.target.matched_gt_target_row_id = 0

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)

    assert reader.array("targets/target_row_id").tolist() == [0, 1]
    assert reader.array("targets/target_source_index").tolist() == [0, 0]
    assert reader.array("rollouts/target_row_id").tolist() == [0, 1]
    target_names = _json_list(reader, "dictionaries/target")
    target_name_ids = reader.array("targets/target_id")
    assert [target_names[int(index)] for index in target_name_ids.tolist()] == [
        "scene:snippet-0:target-local-0",
        "scene:snippet-1:target-local-0",
    ]

    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors


def test_rollout_zarr_validation_rejects_target_rows_shared_across_sources(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=15)[:2]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)

    root = zarr.open_group(result.store_dir, mode="a")
    root["rollouts/target_row_id"][...] = np.asarray([0, 0], dtype=np.int64)

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("multiple source_row_id" in error for error in validation.errors)


def test_rollout_zarr_relative_pose_root_is_pose_transform(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=17)[:1]
    records[0].evaluated.result.root_pose_world = PoseTW(
        torch.tensor(
            [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 2.0, 3.0],
            dtype=torch.float32,
        )
    )

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)

    pose = reader.array("candidates/pose_world_cam")[0]
    relative = reader.array("candidates/pose_relative_root")[0]
    stored_root = reader.array("rollouts/root_pose_world")[0]
    root_pose = records[0].evaluated.result.root_pose_world.tensor().numpy()
    expected = (
        records[0].evaluated.result.root_pose_world.inverse().compose(PoseTW(torch.as_tensor(pose))).tensor().numpy()
    )

    assert np.allclose(stored_root, root_pose, atol=1e-5)
    assert np.allclose(relative, expected, atol=1e-5)
    assert not np.allclose(relative, pose - root_pose, atol=1e-5)


def test_rollout_zarr_records_per_rollout_lineage_and_split(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=19)[:1]
    lineage = records[0].lineage
    lineage.source.split = "train"
    lineage.source.source_cache_version = "source-cache-v2"
    lineage.source.source_offline_store_manifest_hash = "source-manifest"
    lineage.source.split_manifest_hash = "split-manifest"
    lineage.policy.candidate_config_hash = "candidate-cfg"
    lineage.policy.oracle_config_hash = "oracle-cfg"
    lineage.policy.rollout_config_hash = "rollout-cfg"
    lineage.policy.model_checkpoint_hash = "model-ckpt"
    lineage.policy.branch_schedule_id = "branch-schedule"
    lineage.policy.reason_code_version = INVALID_REASON_VERSION
    lineage.policy.selection_rng_state_hash = "rng-state"
    lineage.target.target_protocol_version = "v1-observed"
    lineage.target.target_source = "detected_obbs"
    lineage.target.target_crop_policy = TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1
    lineage.target.target_row_id = 5
    lineage.target.target_id = "target"
    lineage.target.target_selection_policy = "greedy_top_k"
    lineage.target.target_invalid_reason_bitset = 1
    lineage.target.target_primary_invalid_reason = 0
    lineage.target.target_reason_code_version = TARGET_INVALID_REASON_VERSION
    lineage.target.matched_gt_target_row_id = 50
    lineage.target.matched_gt_target_id = "gt-target"
    lineage.target.gt_match_status = "matched"
    for step in _steps(records[0]):
        n = int(step.transition.candidates.mask_valid.shape[0])
        step.transition.candidates.strategy_id = torch.arange(n, dtype=torch.int64) % 4
        step.transition.candidates.position_id = torch.arange(n, dtype=torch.int64) % 3
        step.transition.candidates.mixture_id = torch.arange(n, dtype=torch.int64) % 2
        step.transition.candidates.sampler_probability = torch.full((n,), 1.0 / float(n), dtype=torch.float32)

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        records,
        target_protocol_version="v1-observed",
        source_offline_store_version="vin-offline-v1",
        split_manifest_hash="split-manifest",
    )
    reader = RolloutZarrStoreReader(result.store_dir)

    split_names = _json_list(reader, "dictionaries/split")
    assert "splits" not in reader.root
    assert split_names[int(reader.array("rollouts/split_id")[0])] == "train"
    assert np.array_equal(reader.array("rollouts/source_row_id"), reader.array("sources/source_row_id"))
    assert np.array_equal(reader.array("lineage/rollout_row_id"), reader.array("rollouts/rollout_row_id"))
    for name in (
        "candidate_config_id",
        "oracle_config_id",
        "rollout_config_id",
        "model_checkpoint_id",
        "branch_schedule_id",
        "target_protocol_version_id",
        "target_crop_policy_id",
        "reason_code_version_id",
        "selection_rng_state_hash_id",
    ):
        assert int(reader.array(f"lineage/{name}")[0]) >= 0
    for name in ("source_cache_version_id", "source_offline_store_manifest_hash_id", "split_manifest_hash_id"):
        assert int(reader.array(f"sources/{name}")[0]) >= 0
    source_shards = _json_list(reader, "dictionaries/source_shard")
    assert source_shards[int(reader.array("sources/source_shard_id")[0])] == "vin-shard-000000"
    assert int(reader.array("sources/source_shard_row")[0]) >= 0
    for rollout_owned_name in ("root_pose_world", "policy_id", "target_row_id"):
        assert rollout_owned_name not in reader.root["lineage"]
    for target_owned_name in ("target_selection_policy_id", "matched_gt_target_row_id", "gt_match_status_id"):
        assert target_owned_name not in reader.root["lineage"]
        assert target_owned_name in reader.root["targets"]
    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors


def test_rollout_zarr_rejects_in_range_v1_target_source_even_when_masks_are_false(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=38)[:1]
    records[0].lineage.target.target_protocol_version = "v1-observed"
    records[0].lineage.target.target_source = "detected_obbs"
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records, target_protocol_version="v1-observed")

    root = zarr.open_group(result.store_dir, mode="a")
    encoded = np.frombuffer(json.dumps(["fabricated_actor"]).encode("utf-8"), dtype=np.uint8)
    root["dictionaries/target_source"].resize((encoded.size,))
    root["dictionaries/target_source"][...] = encoded
    root["targets/target_valid_mask"][...] = False
    root["targets/target_invalid_reason_bitset"][...] = 0

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("incompatible with v1_observed" in error for error in validation.errors)


def test_rollout_zarr_rejects_in_range_empty_v0_target_source_even_when_masks_are_false(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=41)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records, target_protocol_version="v0_gt_input")

    root = zarr.open_group(result.store_dir, mode="a")
    encoded = np.frombuffer(json.dumps([""]).encode("utf-8"), dtype=np.uint8)
    root["dictionaries/target_source"].resize((encoded.size,))
    root["dictionaries/target_source"][...] = encoded
    root["targets/target_valid_mask"][...] = False
    root["targets/target_invalid_reason_bitset"][...] = 0
    root["candidates/q_train_mask"][...] = False

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("incompatible with v0_gt_input" in error for error in validation.errors)


def test_rollout_zarr_accepts_admitted_v1_target_source(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=39)[:1]
    records[0].lineage.target.target_protocol_version = "v1-observed"
    records[0].lineage.target.target_source = "detected_obbs"
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records, target_protocol_version="v1-observed")

    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors


def test_rollout_zarr_preserves_v0_oracle_compatible_target_source(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=40)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records, target_protocol_version="v0_gt_input")

    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors


def test_rollout_zarr_rejects_mixed_split_shards(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=20)[:2]
    records[0].lineage.source.split = "train"
    records[1].lineage.source.split = "val"

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("exactly one split" in error for error in validation.errors)


def test_rollout_zarr_validation_requires_vin_source_shard_lineage(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=23)[:1]
    records[0].lineage.source.source_shard_id = None
    records[0].lineage.source.source_shard_row = -1

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("source_shard_id" in error for error in validation.errors)
    assert any("source_shard_row" in error for error in validation.errors)


def test_rollout_zarr_rejects_conflicting_source_row_lineage(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=24)[:2]
    records[0].lineage.source.source_row_id = 0
    records[1].lineage.source.source_row_id = 0
    records[1].lineage.source.source_sample_key = "different-source-row"
    records[1].lineage.source.source_shard_id = "vin-shard-999999"
    records[1].lineage.source.source_shard_row = 99

    with pytest.raises(ValueError, match="Conflicting source lineage"):
        write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)


def test_rollout_zarr_preserves_candidate_mixture_provenance_for_real_stores(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=21)[:1]
    lineage = records[0].lineage
    lineage.source.split = "train"
    lineage.source.source_cache_version = "source-cache-v7"
    lineage.source.source_offline_store_manifest_hash = "source-manifest"
    lineage.source.split_manifest_hash = "split-manifest"
    lineage.policy.candidate_config_hash = "candidate-cfg"
    lineage.policy.oracle_config_hash = "oracle-cfg"
    lineage.policy.rollout_config_hash = "rollout-cfg"
    lineage.policy.reason_code_version = INVALID_REASON_VERSION
    lineage.policy.selection_rng_state_hash = "rng-state"
    lineage.target.target_protocol_version = "v1-observed"
    lineage.target.target_source = "detected_obbs"
    lineage.target.target_crop_policy = TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1
    lineage.target.target_row_id = 3
    lineage.target.target_id = "target"
    lineage.target.target_selection_policy = "greedy_top_k"
    lineage.target.target_invalid_reason_bitset = 1
    lineage.target.target_primary_invalid_reason = 0
    lineage.target.target_reason_code_version = TARGET_INVALID_REASON_VERSION
    lineage.target.matched_gt_target_row_id = 30
    lineage.target.matched_gt_target_id = "gt-target"
    lineage.target.gt_match_status = "matched"
    for step in _steps(records[0]):
        n = int(step.transition.candidates.mask_valid.shape[0])
        step.transition.candidates.strategy_id = torch.arange(n, dtype=torch.int64) % 4
        step.transition.candidates.mixture_id = torch.arange(n, dtype=torch.int64) % 2
        step.transition.candidates.sampler_probability = torch.full((n,), 1.0 / float(n), dtype=torch.float32)

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        records,
        target_protocol_version="v1-observed",
        source_offline_store_version="7",
        split_manifest_hash="split-manifest",
    )
    reader = RolloutZarrStoreReader(result.store_dir)

    actor_rows = reader.array("candidates/actor_action_mask")
    assert np.all(reader.array("candidates/strategy_id")[actor_rows] >= 0)
    assert np.all(reader.array("candidates/position_id")[actor_rows] >= 0)
    assert np.all(reader.array("candidates/mixture_id")[actor_rows] >= 0)
    assert np.isfinite(reader.array("candidates/sampler_probability")[actor_rows]).all()

    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors


def test_rollout_zarr_blocks_q_training_for_target_invalid_records(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=25)[:1]
    records[0].lineage.target.target_protocol_version = "v1-observed"
    records[0].lineage.target.target_row_id = 11
    records[0].lineage.target.target_id = "target-invalid"
    records[0].lineage.target.target_invalid_reason_bitset = 1 << 10
    records[0].lineage.target.target_primary_invalid_reason = 10
    records[0].lineage.target.gt_match_status = "unmatched_gt"

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records, target_protocol_version="v1-observed")
    reader = RolloutZarrStoreReader(result.store_dir)
    q_h = reader.q_h_view()

    assert reader.array("candidates/oracle_label_mask").any()
    assert not reader.array("candidates/q_train_mask").any()
    assert not q_h["q_train_mask"].any()


def test_rollout_zarr_blocks_q_training_when_v1_target_reason_is_missing(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=26)[:1]
    target = records[0].lineage.target
    target.target_protocol_version = "v1_observed"
    target.target_source = "detected_obbs"
    target.target_invalid_reason_bitset = None
    target.gt_match_status = "admitted"
    target.gt_match_iou = 0.7

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        records,
        target_protocol_version="v1_observed",
    )
    reader = RolloutZarrStoreReader(result.store_dir)

    assert reader.array("targets/target_invalid_reason_bitset").tolist() == [0]
    assert reader.array("targets/target_valid_mask").tolist() == [False]
    assert reader.array("targets/gt_label_valid_mask").tolist() == [False]
    assert not reader.array("candidates/q_train_mask").any()
    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors


def test_rollout_zarr_preserves_v0_missing_target_reason_admission(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=27)[:1]
    records[0].lineage.target.target_invalid_reason_bitset = None

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        records,
        target_protocol_version="v0_gt_input",
    )
    reader = RolloutZarrStoreReader(result.store_dir)

    assert reader.array("targets/target_invalid_reason_bitset").tolist() == [1]
    assert reader.array("targets/target_valid_mask").tolist() == [True]
    assert reader.array("targets/gt_label_valid_mask").tolist() == [True]
    assert reader.array("candidates/q_train_mask").any()
    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors


def test_rollout_zarr_rejects_missing_root_lineage(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=23)[:1]

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        records,
        target_protocol_version="v1-observed",
        source_offline_store_version="",
    )

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("source_offline_store_version" in error for error in validation.errors)


def test_rollout_zarr_validation_requires_top_level_manifest(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=29)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    result.manifest_path.unlink()

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("manifest" in error for error in validation.errors)


def test_rollout_zarr_validation_rejects_manifest_hash_mismatch(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=31)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    payload["counts"]["rollouts"] = 999
    result.manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("manifest hash" in error for error in validation.errors)


def test_rollouts_info_cli_prints_manifest_without_validation(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=37)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    capsys.readouterr()

    rollouts_info_main(["--store", str(result.store_dir), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["manifest"]["schema_version"] == ROLLOUT_ZARR_SCHEMA_VERSION
    assert payload["manifest"]["source_coverage"]["num_source_rows"] == 1
    assert "validation" not in payload


def test_rollout_manifest_preserves_cli_toml_and_resolved_config(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=41)[:1]
    config_path = tmp_path / "build_rollouts.toml"
    raw_toml = "max_samples = 1\n"
    config_path.write_text(raw_toml, encoding="utf-8")
    writer_config = RolloutZarrStoreConfig(store_dir=tmp_path / "rollouts.zarr")

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        records,
        manifest_context=RolloutStoreManifestContext.from_cli(
            writer_config=writer_config,
            argv=["nbv-build-rollouts", "--config-path", str(config_path)],
            config_path=config_path,
        ),
    )
    manifest = RolloutZarrStoreReader(result.store_dir).manifest()["manifest"]

    invocation = manifest["generation"]["invocation"]
    assert invocation["mode"] == "cli"
    assert invocation["raw_toml_text"] == raw_toml
    assert invocation["raw_toml_sha256"]
    assert manifest["generation"]["writer_config"]["store_dir"].endswith("rollouts.zarr")
    assert manifest["generation"]["runtime"]["git"]["available"] in {True, False}
