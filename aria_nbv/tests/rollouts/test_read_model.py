"""Typed rollout-store read-model tests."""

# ruff: noqa: S101

from __future__ import annotations

import numpy as np
import zarr

from aria_nbv.rollouts import RolloutZarrStoreReader
from aria_nbv.rollouts.read_model import (
    rollout_at,
    rollout_by_id,
    rollout_rows,
    rollout_steps,
    selected_depth_for_step,
    target_by_id,
    target_rows,
)
from aria_nbv.rollouts.zarr_store import write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records


def _reader(tmp_path, *, selected_depth_enabled: bool = True) -> RolloutZarrStoreReader:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=2, num_samples=6, seed=51)[:1],
        selected_depth_enabled=selected_depth_enabled,
    )
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


def test_rollout_rows_matches_single_row_projection(tmp_path) -> None:
    """The batch projection preserves physical rollout order and factual step order."""

    reader = _reader(tmp_path)
    rows = rollout_rows(reader)
    single = rollout_at(reader, 0)

    assert len(rows) == 1
    assert rows[0].rollout_row_id == single.rollout_row_id
    assert np.array_equal(rows[0].step_row_positions, single.step_row_positions)


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
    with np.testing.assert_raises(ValueError):
        rollout_rows(RolloutZarrStoreReader(reader.store_dir))


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


def test_rollout_steps_reuse_reader_local_candidate_shell_index(tmp_path) -> None:
    """Repeated step projections must not rescan immutable shell metadata."""

    reader = _reader(tmp_path)
    rollout = rollout_at(reader, 0)
    original = reader.array
    calls: dict[str, int] = {}

    def spy(path: str) -> np.ndarray:
        calls[path] = calls.get(path, 0) + 1
        return original(path)

    reader.array = spy  # type: ignore[method-assign]
    first = rollout_steps(reader, rollout)
    expected_positions = first[0].candidate_row_positions.copy()
    first[0].candidate_row_positions[:] = -1
    second = rollout_steps(reader, rollout)

    assert np.array_equal(second[0].candidate_row_positions, expected_positions)
    assert [step.candidate_row_ids.tolist() for step in second] == [step.candidate_row_ids.tolist() for step in first]
    assert calls == {
        "candidates/candidate_row_id": 1,
        "candidates/step_row_id": 1,
        "candidates/shell_index": 1,
    }


def test_candidate_shell_index_caches_empty_candidate_table(tmp_path) -> None:
    """A completed zero-candidate store still has a reusable empty index."""

    reader = _reader(tmp_path)
    calls: dict[str, int] = {}

    def empty_array(path: str) -> np.ndarray:
        calls[path] = calls.get(path, 0) + 1
        dtype = np.int32 if path == "candidates/shell_index" else np.int64
        return np.empty(0, dtype=dtype)

    reader.array = empty_array  # type: ignore[method-assign]
    first = reader.candidate_shell_index()
    second = reader.candidate_shell_index()

    assert first is second
    assert first.candidate_ids.size == 0
    assert first.positions_by_step == {}
    assert calls == {
        "candidates/candidate_row_id": 1,
        "candidates/step_row_id": 1,
        "candidates/shell_index": 1,
    }


def test_target_rows_decode_factual_and_audit_fields(tmp_path) -> None:
    reader = _reader(tmp_path)

    target = target_rows(reader)[0]

    assert (target.target_row_id, target.target_id, target.source) == (0, "fixture-target-0", "gt_obbs_oracle")
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
