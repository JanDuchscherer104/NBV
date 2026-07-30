"""Typed rollout-store read-model tests."""

# ruff: noqa: S101

from __future__ import annotations

from dataclasses import replace

import numpy as np
import zarr

from aria_nbv.rollouts import RolloutZarrStoreReader
from aria_nbv.rollouts.read_model import (
    endpoint_evaluation_unit,
    persisted_pre_treatment_context_sha256,
    rollout_at,
    rollout_by_id,
    rollout_steps,
    root_action_set_identity,
    selected_depth_for_step,
    selected_pose_chain_sha256,
    target_by_id,
    target_rows,
)
from aria_nbv.rollouts.scientific_audit import (
    PolicyMatchIdentity,
    PolicySemanticRole,
    PolicyTreatmentIdentity,
    TreatmentConfigPath,
    named_sha256_context_hash,
    normalize_treatment_configs,
)
from aria_nbv.rollouts.zarr_store import write_rollout_zarr_store
from aria_nbv.targets.protocol import ORACLE_GT_TARGET_SOURCE
from tests.rollout_fixtures import build_rollout_records


def _reader(tmp_path, *, selected_depth_enabled: bool = True) -> RolloutZarrStoreReader:
    records = _anchored_records()
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        records,
        selected_depth_enabled=selected_depth_enabled,
    )
    return RolloutZarrStoreReader(result.store_dir)


def _anchored_records(*, horizon: int = 2):
    records = build_rollout_records(horizon=horizon, num_samples=6, seed=51)[:1]
    result = records[0].evaluated.result
    result.root_time_ns = 1_234_567_890
    result.root_trajectory_index = 7
    result.root_frame_index = 11
    return records


def _reader_for_records(tmp_path, records) -> RolloutZarrStoreReader:
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    return RolloutZarrStoreReader(result.store_dir)


def test_rollout_at_decodes_context_and_orders_steps(tmp_path) -> None:
    reader = _reader(tmp_path)

    rollout = rollout_at(reader, 0)

    by_id = rollout_by_id(reader, 0)
    assert (by_id.row_position, by_id.rollout_row_id) == (rollout.row_position, rollout.rollout_row_id)
    assert np.array_equal(by_id.step_row_positions, rollout.step_row_positions)
    assert (rollout.scene, rollout.snippet, rollout.split, rollout.policy) == (
        "fixture_box",
        "smoke",
        "train",
        "oracle_greedy",
    )
    assert (rollout.horizon, rollout.branch_factor, rollout.beam_width) == (2, 1, -1)
    assert np.isnan(rollout.temperature)
    assert rollout.step_row_positions.tolist() == [0, 1]
    assert [step.step_row_id for step in rollout_steps(reader, rollout)] == [0, 1]


def test_rollout_lookup_rejects_missing_rows_and_rollouts_without_steps(tmp_path) -> None:
    reader = _reader(tmp_path)
    with np.testing.assert_raises(IndexError):
        rollout_at(reader, 1)
    with np.testing.assert_raises(KeyError):
        rollout_by_id(reader, 999)

    writable = zarr.open_group(reader.store_dir, mode="a")
    writable["steps/rollout_row_id"][:] = 999
    with np.testing.assert_raises(ValueError):
        rollout_at(RolloutZarrStoreReader(reader.store_dir), 0)


def test_rollout_steps_preserve_shell_ordered_candidate_columns(tmp_path) -> None:
    reader = _reader(tmp_path)

    step = rollout_steps(reader, rollout_at(reader, 0))[0]

    assert (step.num_candidates, step.num_valid_candidates, step.selected_local_index) == (12, 12, 11)
    assert step.candidate_row_ids.tolist() == list(range(12))
    assert step.shell_indices.tolist() == list(range(12))
    assert step.compact_valid_indices.tolist() == list(range(12))
    assert step.actor_action_mask.all()
    assert np.flatnonzero(step.selected_mask).tolist() == [11]
    assert np.allclose(step.target_rri, np.arange(0.1, 1.3, 0.1, dtype=np.float32))
    assert np.allclose(step.selection_probabilities, [0.0] * 11 + [1.0])
    assert set(step.position_names.tolist()) == {"forward_local"}


def test_endpoint_evaluation_unit_decodes_lineage_pose_order_and_comparator(tmp_path) -> None:
    reader = _reader(tmp_path)
    rollout = rollout_at(reader, 0)
    steps = rollout_steps(reader, rollout)

    unit = endpoint_evaluation_unit(reader, rollout.rollout_row_id)

    assert unit.lineage.source_sample_key == "fixture:smoke:0"
    assert (unit.lineage.source_sample_index, unit.lineage.source_shard_row) == (0, 0)
    assert unit.lineage.source_shard_id == "vin-shard-000000"
    assert unit.lineage.source_offline_store_manifest_hash == "fixture-source-manifest"
    assert unit.lineage.split_manifest_hash == "fixture-split-manifest"
    assert (unit.lineage.split, unit.lineage.scene_id, unit.lineage.snippet_id) == (
        "train",
        "fixture_box",
        "smoke",
    )
    assert (unit.lineage.root_time_ns, unit.lineage.root_trajectory_index, unit.lineage.root_frame_index) == (
        1_234_567_890,
        7,
        11,
    )
    assert unit.lineage.candidate_config_hash
    assert unit.lineage.oracle_config_hash == "fixture-oracle"
    assert unit.lineage.rollout_config_hash
    assert unit.lineage.rollout_seed == 51
    assert unit.lineage.model_checkpoint_hash is None
    assert unit.lineage.selection_rng_state_hash == "fixture-rng"
    assert unit.lineage.target_id == "fixture-target-0"
    assert unit.lineage.target_protocol_version == "v0_gt_input"
    assert unit.pose_chain.step_row_ids == tuple(step.step_row_id for step in steps)
    assert unit.pose_chain.selected_candidate_row_ids == tuple(step.selected_candidate_row_id for step in steps)
    expected = np.stack([step.pose_world_cam[step.selected_local_index] for step in steps])
    np.testing.assert_array_equal(unit.pose_chain.selected_poses_world_cam, expected)
    assert unit.pose_chain.root_pose_world.flags.writeable is False
    assert unit.pose_chain.selected_poses_world_cam.flags.writeable is False
    assert (unit.achieved_steps, unit.budget, unit.termination_reason) == (2, 2, "fixed_horizon")
    assert unit.comparator.gain == float(reader.array("rollouts/final_cumulative_target_root_gain")[0])
    assert (unit.comparator.gamma, unit.comparator.epsilon) == (1.0, 1e-12)
    assert len(selected_pose_chain_sha256(unit.pose_chain)) == 64


def test_root_action_set_hash_is_shell_ordered_and_excludes_policy_outcomes(tmp_path) -> None:
    reader = _reader(tmp_path)
    baseline = root_action_set_identity(reader, 0)
    unit = endpoint_evaluation_unit(reader, 0)

    assert root_action_set_identity(reader, unit) == baseline
    assert (baseline.budget, baseline.candidate_count) == (2, 12)

    root = zarr.open_group(reader.store_dir, mode="a")
    root["candidates/selected_mask"][0] = not bool(root["candidates/selected_mask"][0])
    root["candidates/target_rri"][0] += np.float32(10.0)
    root["candidates/pose_world_cam"][12, 9] += np.float32(1.0)
    assert root_action_set_identity(RolloutZarrStoreReader(reader.store_dir), 0).sha256 == baseline.sha256

    candidates = root["candidates"]
    for name in tuple(candidates.array_keys()):
        values = np.asarray(candidates[name][:12])
        candidates[name][:12] = values[::-1]
    reordered = root_action_set_identity(RolloutZarrStoreReader(reader.store_dir), 0)
    assert reordered.sha256 == baseline.sha256


def test_root_action_set_hash_includes_support_fields_and_rejects_corruption(tmp_path) -> None:
    mutations = (
        ("strategy", "candidates/strategy_id", (0,), np.int32(99), None),
        ("root-pose", "candidates/pose_relative_root", (0, 9), np.float32(0.25), None),
        ("budget", "rollouts/horizon", (0,), np.int32(3), None),
        ("duplicate-shell", "candidates/shell_index", (1,), np.int32(0), "duplicate shell"),
        ("nonfinite-pose", "candidates/pose_world_cam", (0, 0), np.float32(np.nan), "poses must be finite"),
        (
            "nonfinite-probability",
            "candidates/sampler_probability",
            (0,),
            np.float32(np.nan),
            "probabilities must be finite",
        ),
    )
    for name, path, index, value, error in mutations:
        reader = _reader(tmp_path / name)
        baseline = root_action_set_identity(reader, 0).sha256
        zarr.open_group(reader.store_dir, mode="a")[path][index] = value
        mutated = RolloutZarrStoreReader(reader.store_dir)
        if error is None:
            assert root_action_set_identity(mutated, 0).sha256 != baseline
        else:
            with np.testing.assert_raises_regex(ValueError, error):
                root_action_set_identity(mutated, 0)


def test_persisted_context_hash_binds_typed_lineage_target_and_root_identity(tmp_path) -> None:
    reader = _reader(tmp_path)
    unit = endpoint_evaluation_unit(reader, 0)
    target = target_by_id(reader, unit.lineage.target_row_id)
    root_identity = root_action_set_identity(reader, unit)
    assert target is not None

    baseline = persisted_pre_treatment_context_sha256(unit.lineage, target, root_identity)
    assert len(baseline) == 64
    assert (
        persisted_pre_treatment_context_sha256(
            replace(unit.lineage, source_sample_key="different-sample"),
            target,
            root_identity,
        )
        != baseline
    )
    assert (
        persisted_pre_treatment_context_sha256(
            replace(unit.lineage, rollout_seed=unit.lineage.rollout_seed + 1),
            target,
            root_identity,
        )
        != baseline
    )
    assert (
        persisted_pre_treatment_context_sha256(
            replace(unit.lineage, selection_rng_state_hash="different-rng"),
            target,
            root_identity,
        )
        != baseline
    )
    assert (
        persisted_pre_treatment_context_sha256(
            unit.lineage,
            replace(target, primary_invalid_reason_id=target.primary_invalid_reason_id + 1),
            root_identity,
        )
        != baseline
    )
    assert (
        persisted_pre_treatment_context_sha256(
            unit.lineage,
            target,
            replace(root_identity, sha256="f" * 64),
        )
        != baseline
    )


def test_stored_pairing_uses_normalized_configs_not_raw_treatment_hashes(tmp_path) -> None:
    allowlist = (
        TreatmentConfigPath(owner="candidate", json_pointer="/treatment"),
        TreatmentConfigPath(owner="rollout", json_pointer="/treatment"),
    )
    resolved = (
        {
            "candidate": {"treatment": "one-step", "radius_m": 1.0},
            "rollout": {"treatment": "one-step", "budget": 2},
        },
        {
            "candidate": {"treatment": "lookahead", "radius_m": 1.0},
            "rollout": {"treatment": "lookahead", "budget": 2},
        },
        {
            "candidate": {"treatment": "lookahead", "radius_m": 2.0},
            "rollout": {"treatment": "lookahead", "budget": 2},
        },
    )
    normalized = tuple(normalize_treatment_configs(config, allowlist) for config in resolved)

    units = []
    targets = []
    root_identities = []
    for index, configs in enumerate(normalized):
        records = _anchored_records()
        raw_by_owner = {item.name: item.sha256 for item in configs.raw_fingerprints}
        records[0].lineage.policy.candidate_config_hash = raw_by_owner["candidate"]
        records[0].lineage.policy.rollout_config_hash = raw_by_owner["rollout"]
        reader = _reader_for_records(tmp_path / str(index), records)
        unit = endpoint_evaluation_unit(reader, 0)
        target = target_by_id(reader, unit.lineage.target_row_id)
        assert target is not None
        units.append(unit)
        targets.append(target)
        root_identities.append(root_action_set_identity(reader, unit))

    persisted_contexts = tuple(
        persisted_pre_treatment_context_sha256(unit.lineage, target, root_identity)
        for unit, target, root_identity in zip(units, targets, root_identities, strict=True)
    )
    assert units[0].lineage.candidate_config_hash != units[1].lineage.candidate_config_hash
    assert units[0].lineage.rollout_config_hash != units[1].lineage.rollout_config_hash
    assert persisted_contexts[0] == persisted_contexts[1] == persisted_contexts[2]

    def match(index: int, role: PolicySemanticRole) -> PolicyMatchIdentity:
        return PolicyMatchIdentity.derive(
            treatment=PolicyTreatmentIdentity(semantic_role=role, treatment_id=role.value),
            configs=normalized[index],
            root_action_set_sha256=root_identities[index].sha256,
            persisted_context_sha256=persisted_contexts[index],
            raw_asset_context_sha256=named_sha256_context_hash(()),
        )

    one_step = match(0, PolicySemanticRole.ORACLE_ONE_STEP)
    lookahead = match(1, PolicySemanticRole.ORACLE_LOOKAHEAD)
    nonallowlisted = match(2, PolicySemanticRole.ORACLE_LOOKAHEAD)
    assert one_step.exact_match_sha256 == lookahead.exact_match_sha256
    assert lookahead.exact_match_sha256 != nonallowlisted.exact_match_sha256


def test_endpoint_evaluation_unit_rejects_caller_policy_identity_mismatch(tmp_path) -> None:
    checkpoint_hash = "a" * 64
    records = _anchored_records()
    records[0].lineage.policy.model_checkpoint_hash = checkpoint_hash
    reader = _reader_for_records(tmp_path, records)

    unit = endpoint_evaluation_unit(
        reader,
        0,
        expected_rollout_seed=51,
        expected_model_checkpoint_hash=checkpoint_hash,
        expected_selection_rng_state_hash="fixture-rng",
    )
    assert unit.lineage.model_checkpoint_hash == checkpoint_hash

    mismatches = (
        ("rollout_seed", {"expected_rollout_seed": 52}),
        ("model_checkpoint_hash", {"expected_model_checkpoint_hash": "b" * 64}),
        ("selection_rng_state_hash", {"expected_selection_rng_state_hash": "different-rng"}),
    )
    for label, expected in mismatches:
        with np.testing.assert_raises_regex(ValueError, label):
            endpoint_evaluation_unit(reader, 0, **expected)

    builtin_reader = _reader(tmp_path / "builtin")
    with np.testing.assert_raises_regex(ValueError, "model_checkpoint_hash"):
        endpoint_evaluation_unit(
            builtin_reader,
            0,
            expected_model_checkpoint_hash=checkpoint_hash,
        )


def test_endpoint_evaluation_unit_rejects_missing_lineage_and_root_anchor(tmp_path) -> None:
    mutations = (
        ("source_sample_key", "sources/sample_key_id", -1),
        ("candidate_config_hash", "lineage/candidate_config_id", -1),
        ("rollout_seed", "rollouts/random_seed", -1),
        ("selection_rng_state_hash", "lineage/selection_rng_state_hash_id", -1),
        ("target_id", "targets/target_id", -1),
        ("root_time_ns", "rollouts/root_time_ns", -1),
    )
    for label, path, value in mutations:
        reader = _reader(tmp_path / label)
        zarr.open_group(reader.store_dir, mode="a")[path][0] = value
        with np.testing.assert_raises_regex(ValueError, label):
            endpoint_evaluation_unit(RolloutZarrStoreReader(reader.store_dir), 0)


def test_endpoint_evaluation_unit_rejects_step_and_selection_corruption(tmp_path) -> None:
    mutations = (
        (
            "noncontiguous",
            lambda root: root["steps/step_index"].__setitem__(1, 3),
            "noncontiguous factual step",
        ),
        (
            "zero-selected",
            lambda root: root["candidates/selected_mask"].__setitem__(slice(0, 12), False),
            "exactly one selected",
        ),
        (
            "multiple-selected",
            lambda root: root["candidates/selected_mask"].__setitem__(0, True),
            "exactly one selected",
        ),
        (
            "selected-id",
            lambda root: root["steps/selected_candidate_row_id"].__setitem__(0, 0),
            "ID disagreement",
        ),
        (
            "actor-invalid",
            lambda root: root["candidates/actor_action_mask"].__setitem__(11, False),
            "not actor-valid",
        ),
        (
            "oracle-unlabelled",
            lambda root: root["candidates/oracle_label_mask"].__setitem__(11, False),
            "not oracle-labelled",
        ),
        (
            "nonfinite-pose",
            lambda root: root["candidates/pose_world_cam"].__setitem__((11, 0), np.nan),
            "non-finite",
        ),
    )
    for name, mutate, expected in mutations:
        reader = _reader(tmp_path / name)
        mutate(zarr.open_group(reader.store_dir, mode="a"))
        with np.testing.assert_raises_regex(ValueError, expected):
            endpoint_evaluation_unit(RolloutZarrStoreReader(reader.store_dir), 0)


def test_endpoint_evaluation_unit_enforces_termination_and_permits_root_only_early_stop(tmp_path) -> None:
    fixed_mismatch = _reader(tmp_path / "fixed-mismatch")
    zarr.open_group(fixed_mismatch.store_dir, mode="a")["rollouts/horizon"][0] = 3
    with np.testing.assert_raises_regex(ValueError, "fixed_horizon"):
        endpoint_evaluation_unit(RolloutZarrStoreReader(fixed_mismatch.store_dir), 0)

    early_full_records = _anchored_records()
    early_full_records[0].evaluated.result.trajectories[0].terminated_early = True
    early_full = _reader_for_records(tmp_path / "early-full", early_full_records)
    with np.testing.assert_raises_regex(ValueError, "must be shorter"):
        endpoint_evaluation_unit(early_full, 0)

    incomplete_records = _anchored_records()
    incomplete_records[0].evaluated.result.trajectories[0].steps.pop()
    incomplete = _reader_for_records(tmp_path / "incomplete", incomplete_records)
    with np.testing.assert_raises_regex(ValueError, "incomplete or unknown termination"):
        endpoint_evaluation_unit(incomplete, 0)

    root_only_records = _anchored_records()
    root_only = root_only_records[0].evaluated.result.trajectories[0]
    root_only.steps.clear()
    root_only.terminated_early = True
    root_only_reader = _reader_for_records(tmp_path / "root-only", root_only_records)

    unit = endpoint_evaluation_unit(root_only_reader, 0)

    assert (unit.achieved_steps, unit.budget, unit.termination_reason) == (0, 2, "terminated_early")
    assert unit.pose_chain.selected_poses_world_cam.shape == (0, 12)
    assert unit.comparator.gain == 0.0


def test_target_rows_decode_factual_and_audit_fields(tmp_path) -> None:
    reader = _reader(tmp_path)

    target = target_rows(reader)[0]

    assert (target.target_row_id, target.target_id, target.source) == (
        0,
        "fixture-target-0",
        ORACLE_GT_TARGET_SOURCE,
    )
    assert target.class_name == "fixture_object"
    assert (target.selection_rank, target.selection_score) == (0, 1.0)
    assert target.target_valid is True
    assert target.matched_gt_target_row_id == 100
    assert target.matched_gt_target_id == "fixture-gt-target-0"
    assert target.gt_match_status == "matched"
    np.testing.assert_array_equal(target.center_world, reader.array("targets/target_center_world")[0])
    assert np.allclose(target.extents, [0.4, 0.5, 0.6])
    assert target_by_id(reader, 0) is not None
    assert target_by_id(reader, 999) is None


def test_selected_depth_masks_invalid_pixels_and_copies_payload(tmp_path) -> None:
    reader = _reader(tmp_path)
    writable = zarr.open_group(reader.store_dir, mode="a")
    writable["selected_depth/depth_m"][0, 0, 0] = 42.0
    writable["selected_depth/valid_mask"][0, 0, 0] = False
    step = rollout_steps(reader, rollout_at(reader, 0))[0]

    depth = selected_depth_for_step(reader, step)

    assert depth.available is True
    assert depth.warning is None
    assert depth.depth_m is not None and depth.depth_m.dtype == np.float32
    assert depth.valid_mask is not None and not bool(depth.valid_mask[0, 0])
    assert np.isnan(depth.depth_m[0, 0])
    assert depth.image_size_hw == (240, 240)
    assert np.allclose(depth.focal_px, [120.0, 120.0])
    assert np.allclose(depth.principal_point_px, [120.0, 120.0])


def test_selected_depth_reports_disabled_store_without_dense_payload(tmp_path) -> None:
    reader = _reader(tmp_path, selected_depth_enabled=False)
    step = rollout_steps(reader, rollout_at(reader, 0))[0]

    depth = selected_depth_for_step(reader, step)

    assert depth.available is False
    assert depth.warning is not None and "selected_depth_enabled=false" in depth.warning
    assert depth.depth_m is None


def test_selected_depth_reports_candidate_mismatch(tmp_path) -> None:
    reader = _reader(tmp_path)
    zarr.open_group(reader.store_dir, mode="a")["selected_depth/candidate_row_id"][0] = 999
    step = rollout_steps(reader, rollout_at(reader, 0))[0]

    depth = selected_depth_for_step(reader, step)

    assert depth.available is False
    assert depth.candidate_row_id == 999
    assert depth.warning is not None and depth.warning.startswith("selected_depth candidate mismatch:")


def test_selected_depth_reports_missing_dense_array(tmp_path) -> None:
    reader = _reader(tmp_path)
    del zarr.open_group(reader.store_dir, mode="a")["selected_depth/depth_m"]
    refreshed = RolloutZarrStoreReader(reader.store_dir)
    step = rollout_steps(refreshed, rollout_at(refreshed, 0))[0]

    depth = selected_depth_for_step(refreshed, step)

    assert depth.available is False
    assert depth.warning is not None and "missing dense array" in depth.warning


def test_selected_depth_reports_duplicate_step_rows(tmp_path) -> None:
    reader = _reader(tmp_path)
    writable = zarr.open_group(reader.store_dir, mode="a")["selected_depth"]
    for name in ("step_row_id", "candidate_row_id"):
        values = np.asarray(writable[name])
        writable[name].resize((values.shape[0] + 1,))
        writable[name][-1] = values[0]
    refreshed = RolloutZarrStoreReader(reader.store_dir)
    step = rollout_steps(refreshed, rollout_at(refreshed, 0))[0]

    depth = selected_depth_for_step(refreshed, step)

    assert depth.available is False
    assert depth.warning is not None and "expected one row" in depth.warning


def test_selected_depth_reports_shape_mismatch(tmp_path) -> None:
    reader = _reader(tmp_path)
    group = zarr.open_group(reader.store_dir, mode="a")["selected_depth"]
    mask = np.asarray(group["valid_mask"])
    del group["valid_mask"]
    group.create_array("valid_mask", data=mask[:, :-1, :])
    refreshed = RolloutZarrStoreReader(reader.store_dir)
    step = rollout_steps(refreshed, rollout_at(refreshed, 0))[0]

    depth = selected_depth_for_step(refreshed, step)

    assert depth.available is False
    assert depth.warning is not None and "shape mismatch" in depth.warning


def test_selected_depth_reports_invalid_camera_metadata(tmp_path) -> None:
    reader = _reader(tmp_path)
    group = zarr.open_group(reader.store_dir, mode="a")["selected_depth"]
    focal = np.asarray(group["focal_px"])
    del group["focal_px"]
    group.create_array("focal_px", data=focal[:, :1])
    refreshed = RolloutZarrStoreReader(reader.store_dir)
    step = rollout_steps(refreshed, rollout_at(refreshed, 0))[0]

    depth = selected_depth_for_step(refreshed, step)

    assert depth.available is False
    assert depth.warning is not None and "camera metadata" in depth.warning
