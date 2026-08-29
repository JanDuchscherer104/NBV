"""Rollout inspection helper tests."""

# ruff: noqa: S101

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest
import torch
import zarr
from efm3d.aria.pose import PoseTW

pytest.importorskip("efm3d")

import aria_nbv.rollouts.inspection as inspection_module
from aria_nbv.rollouts import RolloutZarrStoreReader
from aria_nbv.rollouts.inspection import (
    RolloutSuspiciousQueryConfig,
    _decision_relative_vector,
    _iter_candidate_state_chunks,
    _selected_path_lengths,
    candidate_audit_rows,
    candidate_collision_support_rows,
    candidate_composition_rows,
    candidate_flow_rows,
    candidate_group_summary_rows,
    candidate_population_evidence,
    candidate_proposal_calibration_rows,
    candidate_selection_pooled_summary_rows,
    candidate_selection_sequence_rows,
    candidate_selection_temporal_summary_rows,
    candidate_selection_transition_rows,
    candidate_sequence_return_summary_rows,
    comparable_policy_cohorts,
    deterministic_candidate_display_sample,
    discounted_rollout_return_rows,
    discover_rollout_store_paths,
    exact_policy_role_rows,
    mask_combination_rows,
    oracle_headroom_evidence,
    paired_policy_comparison_rows,
    pairwise_finite_pearson,
    proposal_support_geometry,
    reconstruction_endpoint_rows,
    reconstruction_endpoint_summary_rows,
    reconstruction_metric_summary_rows,
    rollout_endpoint_metric_summary,
    rollout_header_summary,
    rollout_step_objective_rows,
    rollout_store_inventory_rows,
    rollout_trajectory_geometry,
    rollout_tree_summary_rows,
    root_relative_candidate_rows,
    s2_target_direction_histogram,
    selected_candidate_rank_rows,
    selected_depth_preview,
    selected_depth_summary_rows,
    store_invariant_rows,
    suspicious_rollout_rows,
    target_audit_rows,
    temporal_metric_summary_rows,
    validity_waterfall_rows,
)
from aria_nbv.rollouts.read_model import target_rows as read_target_rows
from aria_nbv.rollouts.zarr_store import write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records


def _reader_stub() -> RolloutZarrStoreReader:
    return cast(RolloutZarrStoreReader, SimpleNamespace())


def _zarr_array(root: zarr.Group, path: str) -> zarr.Array[Any]:
    return cast(zarr.Array[Any], root[path])


def _pose_tensor(pose: PoseTW) -> torch.Tensor:
    to_tensor: Callable[[], Any] = pose.tensor
    return cast(torch.Tensor, to_tensor())


def test_candidate_population_propagates_callback_type_error_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"rows": 0}

    def audit_reader(_reader: Any, *, row_callback: Any) -> None:
        calls["rows"] += 1
        row_callback({"candidate_row_id": 1})

    def failing_consume(_self: Any, _row: dict[str, Any]) -> None:
        raise TypeError("callback-internal failure")

    monkeypatch.setattr(inspection_module._CandidatePopulationAccumulator, "consume", failing_consume)

    with pytest.raises(TypeError, match="callback-internal failure"):
        candidate_population_evidence(_reader_stub(), audit_reader=audit_reader)
    assert calls["rows"] == 1


def test_pairwise_finite_pearson_keeps_pair_local_support_and_degenerate_reason() -> None:
    result = pairwise_finite_pearson({"left": [1.0, 2.0, np.inf], "right": [2.0, 4.0, 8.0]}, ("left", "right"))
    assert result.counts.tolist() == [[2, 2], [2, 3]]
    assert result.has_finite_off_diagonal
    assert "n=2" in result.reasons[("left", "right")]


def test_runtime_storage_statistics_does_not_fabricate_zero_candidate_ratio(tmp_path: Path) -> None:
    (tmp_path / "payload").write_bytes(b"payload")
    stats = inspection_module.runtime_storage_statistics(tmp_path, candidate_count=0)
    assert stats["bytes_per_candidate"] is None
    assert stats["bytes_per_candidate_reason"] == "unavailable: no persisted candidate rows"


def test_selected_path_lengths_match_scalar_ordered_paths_and_empty_rollouts(tmp_path: Path) -> None:
    """Batched path reduction preserves stable selected-step ordering exactly."""

    result = write_rollout_zarr_store(
        tmp_path / "selected-paths.zarr", build_rollout_records(horizon=2, num_samples=6, seed=712)[:2]
    )
    root = zarr.open_group(result.store_dir, mode="a")
    rollout_ids = np.asarray(_zarr_array(root, "rollouts/rollout_row_id"), dtype=np.int64).reshape(-1)
    candidate_rollout_ids = np.asarray(_zarr_array(root, "candidates/rollout_row_id"), dtype=np.int64).reshape(-1)
    candidate_steps = _zarr_array(root, "candidates/step_index")
    selected = _zarr_array(root, "candidates/selected_mask")
    candidate_poses = _zarr_array(root, "candidates/pose_world_cam")
    root_poses = _zarr_array(root, "rollouts/root_pose_world")

    first_positions = np.flatnonzero(candidate_rollout_ids == rollout_ids[0])[:3]
    assert first_positions.size == 3
    selected[:] = np.asarray(False, dtype=np.bool_)
    selected[first_positions] = np.asarray(True, dtype=np.bool_)
    candidate_steps[first_positions] = np.asarray([1, 0, 1], dtype=np.int16)
    root_pose = np.asarray(root_poses[0], dtype=np.float32)
    root_pose[9:12] = np.asarray([0.0, 0.0, 0.0], dtype=np.float32)
    root_poses[0] = root_pose
    poses = np.asarray(candidate_poses[first_positions], dtype=np.float32)
    poses[:, 9:12] = np.asarray([[0.0, 3.0, 4.0], [0.0, 3.0, 0.0], [0.0, 3.0, 16.0]], dtype=np.float32)
    candidate_poses[first_positions] = poses

    reader = RolloutZarrStoreReader(result.store_dir)
    actual = _selected_path_lengths(reader)
    expected: list[float] = []
    for rollout_row, rollout_id in enumerate(rollout_ids):
        indices = np.flatnonzero(np.asarray(selected, dtype=np.bool_) & (candidate_rollout_ids == int(rollout_id)))
        ordered = indices[np.argsort(np.asarray(candidate_steps)[indices], kind="stable")]
        points = [
            np.asarray(root_poses[rollout_row])[9:12],
            *[np.asarray(candidate_poses[index])[9:12] for index in ordered],
        ]
        expected.append(
            float(sum(np.linalg.norm(points[index + 1] - points[index]) for index in range(len(points) - 1)))
        )

    assert actual == pytest.approx(expected)
    assert actual.tolist() == pytest.approx([19.0, 0.0])


def test_selected_path_lengths_ignore_orphaned_selected_rows_without_rollouts() -> None:
    """A malformed empty rollout table keeps the historical empty result."""

    arrays = {
        "rollouts/rollout_row_id": np.asarray([], dtype=np.int64),
        "rollouts/root_pose_world": np.empty((0, 12), dtype=np.float32),
        "candidates/rollout_row_id": np.asarray([99], dtype=np.int64),
        "candidates/step_index": np.asarray([0], dtype=np.int64),
        "candidates/selected_mask": np.asarray([True], dtype=np.bool_),
        "candidates/pose_world_cam": np.zeros((1, 12), dtype=np.float32),
    }
    reader = cast(RolloutZarrStoreReader, SimpleNamespace(array=arrays.__getitem__))

    assert _selected_path_lengths(reader).tolist() == []


def test_geometry_projections_keep_complete_shells_and_factual_selected_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "geometry.zarr",
        build_rollout_records(horizon=2, num_samples=6, seed=731)[:1],
    )
    reader = RolloutZarrStoreReader(result.store_dir)
    target_center = np.asarray([0.5, 0.0, 0.5], dtype=np.float32)
    target = read_target_rows(reader)[0]
    target_pose = np.asarray(target.pose_world_object, dtype=np.float32).copy()
    target_pose[9:12] = target_center
    target = replace(target, center_world=target_center, pose_world_object=target_pose)
    monkeypatch.setattr("aria_nbv.rollouts.inspection.target_rows", lambda _reader: (target,))

    proposal = proposal_support_geometry(reader, max_candidates=10_000)
    trajectory = rollout_trajectory_geometry(reader)

    assert proposal.view == "proposal_support"
    assert proposal.points
    assert all(point.role == "candidate" for point in proposal.points)
    assert all(point.normalization_distance_m > 0 for point in proposal.points)
    assert trajectory.view == "rollout_trajectory"
    assert [point.role for point in trajectory.points] == ["root", "selected_action", "selected_action"]
    assert [point.path_order for point in trajectory.points] == [0, 1, 2]


def test_target_s2_histogram_uses_object_coordinates_and_geometric_obb_scale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real selected path lands on S² after target-frame rotation and OBB normalization."""

    result = write_rollout_zarr_store(
        tmp_path / "target-s2.zarr",
        build_rollout_records(horizon=2, num_samples=6, seed=734)[:1],
    )
    reader = RolloutZarrStoreReader(result.store_dir)
    target = read_target_rows(reader)[0]
    target_rotation = np.asarray([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32)
    target_pose = np.asarray(target.pose_world_object, dtype=np.float32).copy()
    target_pose[:9] = target_rotation.reshape(-1)
    target = replace(
        target,
        extents=np.asarray([1.0, 4.0, 9.0], dtype=np.float32),
        pose_world_object=target_pose,
    )
    monkeypatch.setattr("aria_nbv.rollouts.inspection.target_rows", lambda _reader: (target,))

    histogram = s2_target_direction_histogram(reader, azimuth_bins=12, elevation_bins=6, projection_limit=10)
    rollout = inspection_module.rollout_at(reader, 0)
    first_selected = inspection_module._selected_pose(inspection_module._bounded_geometry_steps(reader, rollout)[0])
    root = inspection_module._geometry_pose(rollout.root_pose_world, role="test root")
    scale = inspection_module._target_obb_geometric_mean_scale(target.extents)
    expected_movement = target_rotation.T @ (first_selected[9:12] - root[9:12]) / scale
    expected_movement /= np.linalg.norm(expected_movement)
    expected_view = target_rotation.T @ first_selected[:9].reshape(3, 3)[:, 2]
    expected_view /= np.linalg.norm(expected_view)

    assert scale == pytest.approx(0.5 * 36.0 ** (1.0 / 3.0))
    assert histogram.rollout_count == 1
    assert histogram.movement_count == histogram.view_direction_count == 2
    assert int(histogram.movement_counts.sum()) == 2
    assert int(histogram.view_direction_counts.sum()) == 2
    assert np.allclose(histogram.movement_projection[0], expected_movement)
    assert histogram.movement_projection_normalized_lengths[0] == pytest.approx(
        np.linalg.norm(target_rotation.T @ (first_selected[9:12] - root[9:12]) / scale)
    )
    assert np.allclose(histogram.view_direction_projection[0], expected_view)
    assert histogram.source_sample_count == 1
    assert histogram.source_snippet_count == 1
    assert histogram.source_scene_count == 1
    assert histogram.target_count == 1
    assert histogram.selected_step_count == 2
    assert histogram.frustum_count == 2
    assert histogram.frustum_missing_calibration_count == 0
    assert histogram.frustum_mean_fov_solid_angle_sr is not None
    assert 0.0 <= float(histogram.frustum_mean_target_surface_fraction_approx) <= 0.5
    assert 0.0 <= float(histogram.frustum_union_target_surface_fraction_approx) <= 1.0
    assert histogram.movement_projection_rollout_row_ids.tolist() == [rollout.rollout_row_id] * 2
    assert histogram.movement_projection_step_indices.tolist() == [0, 1]


def test_target_s2_histogram_rejects_nonpositive_obb_axes() -> None:
    """A target OBB must provide one finite positive scale per object axis."""

    with pytest.raises(ValueError, match="strictly positive"):
        inspection_module._target_obb_geometric_mean_scale(np.asarray([1.0, 0.0, 2.0]))


def test_target_surface_frustum_uses_camera_translation_and_front_facing_support() -> None:
    """A frustum footprint tests target-surface points, not orientation vectors alone."""

    calibration = inspection_module._SelectedFrustumCalibration(
        candidate_row_id=0,
        focal_px=np.asarray([1.0, 1.0]),
        principal_point_px=np.asarray([1.0, 1.0]),
        image_size_hw=(2, 2),
    )
    directions = np.asarray([[0.0, 0.0, -1.0], [0.0, 0.0, 1.0]], dtype=np.float64)

    footprint = inspection_module._target_surface_frustum_mask(
        directions,
        target_scale_m=1.0,
        camera_center_target=np.asarray([0.0, 0.0, -3.0]),
        camera_to_target=np.eye(3),
        calibration=calibration,
    )

    assert footprint.tolist() == [True, False]
    assert inspection_module._pinhole_frustum_solid_angle_sr(calibration) == pytest.approx(1.7285900744)


def test_image_edge_coordinates_use_half_pixel_boundaries() -> None:
    """Frustum masks and corner rays share the continuous pixel-edge convention."""

    assert inspection_module._image_edge_coordinates(2) == (-0.5, 1.5)
    with pytest.raises(ValueError, match="positive integers"):
        inspection_module._image_edge_coordinates(0)


def test_selected_frustum_calibrations_keep_valid_rows_and_address_bad_rows() -> None:
    """One malformed calibration row excludes itself without discarding valid rows."""

    group = {
        "step_row_id": np.asarray([10, 11]),
        "candidate_row_id": np.asarray([100, 101]),
        "focal_px": np.asarray([[1.0, 1.0], [np.nan, 1.0]]),
        "principal_point_px": np.asarray([[0.5, 0.5], [0.5, 0.5]]),
        "image_size_hw": np.asarray([[2, 2], [2, 2]]),
    }

    class Root:
        attrs = {"selected_depth_enabled": True}

        def __getitem__(self, key: str) -> Any:
            assert key == "selected_depth"
            return group

    issues: list[inspection_module.GeometryIssue] = []

    calibrations = inspection_module._selected_frustum_calibrations(SimpleNamespace(root=Root()), issues=issues)

    assert sorted(calibrations) == [10]
    assert [(issue.code, issue.step_row_id) for issue in issues] == [("invalid_selected_frustum_calibration_row", 11)]


def test_target_surface_frustum_equal_area_fraction_converges_to_visible_spherical_cap() -> None:
    """A sufficiently wide camera recovers the analytic front-facing cap fraction."""

    calibration = inspection_module._SelectedFrustumCalibration(
        candidate_row_id=0,
        focal_px=np.asarray([1.0, 1.0]),
        principal_point_px=np.asarray([1.0, 1.0]),
        image_size_hw=(2, 2),
    )
    directions = inspection_module._s2_bin_center_directions(180, 360)

    footprint = inspection_module._target_surface_frustum_mask(
        directions,
        target_scale_m=1.0,
        camera_center_target=np.asarray([0.0, 0.0, -3.0]),
        camera_to_target=np.eye(3),
        calibration=calibration,
    )

    # The 90-degree pinhole contains the whole apparent sphere.  A camera at
    # distance D sees the outward-facing cap d_z < -r/D, whose S² area fraction
    # is (1-r/D)/2.  Uniform azimuth/z bins make the discrete mean consistent.
    assert float(np.mean(footprint)) == pytest.approx(1.0 / 3.0, abs=0.005)


def test_target_s2_histogram_does_not_fabricate_frusta_without_calibration(tmp_path: Path) -> None:
    """Legacy stores retain direction evidence while calibrated support stays unavailable."""

    result = write_rollout_zarr_store(
        tmp_path / "target-s2-no-depth.zarr",
        build_rollout_records(horizon=2, num_samples=6, seed=735)[:1],
        selected_depth_enabled=False,
    )

    histogram = s2_target_direction_histogram(RolloutZarrStoreReader(result.store_dir))

    assert histogram.frustum_count == 0
    assert histogram.frustum_missing_calibration_count == histogram.selected_step_count == 2
    assert int(histogram.frustum_counts.sum()) == 0
    assert histogram.frustum_projection.shape == (0, 3)
    assert histogram.frustum_mean_fov_solid_angle_sr is None
    assert histogram.frustum_mean_target_surface_fraction_approx is None
    assert histogram.frustum_union_target_surface_fraction_approx is None


def test_geometry_projection_bounds_candidate_reads_to_referenced_shells(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "geometry-bounded.zarr",
        build_rollout_records(horizon=2, num_samples=6, seed=732)[:1],
    )
    reader = RolloutZarrStoreReader(result.store_dir)
    target_center = np.asarray([0.5, 0.0, 0.5], dtype=np.float32)
    target = read_target_rows(reader)[0]
    target_pose = np.asarray(target.pose_world_object, dtype=np.float32).copy()
    target_pose[9:12] = target_center
    target = replace(target, center_world=target_center, pose_world_object=target_pose)
    monkeypatch.setattr("aria_nbv.rollouts.inspection.target_rows", lambda _reader: (target,))
    original_array = reader.array

    def reject_candidate_array(path: str) -> Any:
        if path.startswith("candidates/"):
            raise AssertionError(f"geometry must use bounded Zarr handles, not reader.array({path!r})")
        return original_array(path)

    monkeypatch.setattr(reader, "array", reject_candidate_array)
    assert proposal_support_geometry(reader, max_candidates=10_000).points


def test_geometry_projection_caps_before_the_first_shell_when_limit_is_smaller(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A small bound never lets the first complete candidate shell escape the limit."""

    result = write_rollout_zarr_store(
        tmp_path / "geometry-first-shell-limit.zarr",
        build_rollout_records(horizon=2, num_samples=6, seed=733)[:1],
    )
    reader = RolloutZarrStoreReader(result.store_dir)
    target_center = np.asarray([0.5, 0.0, 0.5], dtype=np.float32)
    target = read_target_rows(reader)[0]
    target_pose = np.asarray(target.pose_world_object, dtype=np.float32).copy()
    target_pose[9:12] = target_center
    target = replace(target, center_world=target_center, pose_world_object=target_pose)
    monkeypatch.setattr("aria_nbv.rollouts.inspection.target_rows", lambda _reader: (target,))

    proposal = proposal_support_geometry(reader, max_candidates=1)

    assert len(proposal.points) <= 1
    assert proposal.points == ()
    assert proposal.truncated is True
    assert any(issue.code == "candidate_limit_reached" for issue in proposal.issues)


def test_geometry_contract_rejects_malformed_steps_and_invalid_rotations() -> None:
    valid_pose = np.r_[np.eye(3, dtype=np.float64).reshape(-1), [0.0, 0.0, 0.0]]
    malformed = SimpleNamespace(
        step_row_id=11,
        step_index=1,
        selected_mask=np.asarray([True]),
        candidate_row_ids=np.asarray([4]),
        selected_candidate_row_id=4,
        pose_world_cam=np.asarray([valid_pose]),
    )
    with pytest.raises(ValueError, match="non-contiguous factual step indices"):
        inspection_module._validate_factual_steps(7, (malformed,))

    invalid = valid_pose.copy()
    invalid[0] = 2.0
    with pytest.raises(ValueError, match="invalid rotation"):
        inspection_module._geometry_pose(invalid, role="test pose")


def test_geometry_rig_alignment_is_yaw_only_and_current_scale_is_explicit() -> None:
    rig_rotation = np.asarray([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]])
    root = np.r_[rig_rotation.reshape(-1), [0.0, 0.0, 0.0]]
    target = np.asarray([2.0, 1.0, 3.0])
    basis = inspection_module._proposal_basis(
        root,
        target,
        inspection_module.ProposalAlignment.RIG_FORWARD_Z_UP,
    )
    assert basis is not None
    assert basis[:, 2].tolist() == [0.0, 0.0, 1.0]
    assert np.linalg.norm(basis[:, 0][:2]) == pytest.approx(1.0)
    assert inspection_module._positive_distance(target - root[9:12]) == pytest.approx(np.sqrt(14.0))


def test_candidate_population_owner_census_keeps_selection_domain_surface() -> None:
    """The pooled inspection bundle retains the candidate-choice public owners."""

    assert all(
        callable(owner)
        for owner in (
            candidate_selection_pooled_summary_rows,
            candidate_selection_sequence_rows,
            candidate_selection_temporal_summary_rows,
            candidate_selection_transition_rows,
            candidate_sequence_return_summary_rows,
        )
    )
    bundle = candidate_population_evidence(
        cast(Any, SimpleNamespace()),
        audit_reader=lambda _reader, row_callback: None,
    )
    assert set(bundle["selection_dynamics"]) == {"position", "strategy", "mixture", "position_strategy"}


def test_candidate_selection_dynamics_preserve_state_conditioning_and_terminal_sequences() -> None:
    selected = {
        (0, 0): "forward",
        (0, 1): "side",
        (0, 2): "forward",
        (1, 0): "forward",
        (1, 1): "forward",
        (1, 2): "side",
    }
    forward_mass = {(0, 0): 0.8, (0, 1): 0.3, (0, 2): 0.6, (1, 0): 0.6, (1, 1): 0.6, (1, 2): 0.3}
    terminal_gain = {0: 0.5, 1: 0.1}
    rows: list[dict[str, Any]] = []
    candidate_row_id = 0
    for rollout_row_id in range(2):
        for step_index in range(3):
            for family in ("forward", "side"):
                probability = forward_mass[(rollout_row_id, step_index)]
                if family == "side":
                    probability = 1.0 - probability
                rows.append(
                    {
                        "candidate_row_id": candidate_row_id,
                        "generation_cohort_id": "cohort",
                        "generation_cohort": "{}",
                        "scene": f"scene-{rollout_row_id}",
                        "rollout_row_id": rollout_row_id,
                        "step_row_id": 10 * rollout_row_id + step_index,
                        "step_index": step_index,
                        "policy": "temperature_softmax",
                        "temperature": 2.0,
                        "horizon": 3,
                        "branch_factor": 1,
                        "beam_width": 1,
                        "mixture": family,
                        "position": family,
                        "strategy": "target_point" if family == "forward" else "forward_rig",
                        "invalid_reason": "none",
                        "actor_action": True,
                        "oracle_label": True,
                        "q_train": True,
                        "selected": selected[(rollout_row_id, step_index)] == family,
                        "sampler_probability": 0.5,
                        "selection_probability": probability,
                        "target_root_gain": 0.1,
                        "cumulative_target_root_gain": terminal_gain[rollout_row_id]
                        if step_index == 2
                        else 0.05 * (step_index + 1),
                        "path_collision": False,
                        "path_collision_applicable": True,
                        "path_collision_evaluated": True,
                        "path_min_clearance_m": 1.0,
                    }
                )
                candidate_row_id += 1
    evidence = candidate_population_evidence(
        _reader_stub(), audit_reader=lambda _reader, *, row_callback: [row_callback(row) for row in rows]
    )
    dynamics = evidence["selection_dynamics"]["position"]
    assert len(dynamics) == 12
    one = next(
        row for row in dynamics if row["rollout_row_id"] == 0 and row["step_index"] == 1 and row["family"] == "side"
    )
    assert one["policy_mass"] == pytest.approx(0.7)
    assert one["selected_share"] == pytest.approx(1.0)
    temporal = candidate_selection_temporal_summary_rows(dynamics, metric="policy_mass")
    forward_step_one = next(row for row in temporal if row["step_index"] == 1 and row["family"] == "forward")
    assert forward_step_one["finite_count"] == 2
    assert forward_step_one["median"] == pytest.approx(0.45)
    transitions = candidate_selection_transition_rows(dynamics)
    transition = next(
        row
        for row in transitions
        if row["step_index"] == 1 and row["previous_family"] == "forward" and row["next_family"] == "forward"
    )
    assert transition["context_count"] == 2
    assert transition["expected_policy_mass_mean"] == pytest.approx(0.45)
    assert transition["realized_rate"] == pytest.approx(0.5)
    pooled_rows = [
        {
            **row,
            "generation_cohort_id": f"cohort-{row['rollout_row_id']}",
            "temperature": 0.5 if row["rollout_row_id"] == 0 else 2.0,
        }
        for row in dynamics
    ]
    pooled = candidate_selection_pooled_summary_rows(pooled_rows, metric="policy_mass")
    pooled_forward = next(row for row in pooled if row["step_index"] == 1 and row["family"] == "forward")
    assert pooled_forward["state_count"] == 2
    assert pooled_forward["fraction"] == pytest.approx(0.45)
    pooled_transitions = candidate_selection_transition_rows(pooled_rows, pool_temperatures=True)
    pooled_transition = next(
        row
        for row in pooled_transitions
        if row["step_index"] == 1 and row["previous_family"] == "forward" and row["next_family"] == "forward"
    )
    assert pooled_transition["context_count"] == 2
    assert pooled_transition["expected_policy_mass_mean"] == pytest.approx(0.45)
    assert pooled_transition["temperature"] is None
    assert pooled_transition["pooled_temperatures"] is True
    sequences = candidate_selection_sequence_rows(dynamics)
    summaries = candidate_sequence_return_summary_rows(sequences)
    assert [row["sequence"] for row in sequences] == ["forward → side → forward", "forward → forward → side"]
    assert {row["sequence"]: row["terminal_return_median"] for row in summaries} == {
        "forward → forward → side": pytest.approx(0.1),
        "forward → side → forward": pytest.approx(0.5),
    }
    assert evidence["selection_sequences"]["position"] == sequences
    assert evidence["sequence_returns"]["position"] == summaries


def test_pooled_selection_materializes_families_absent_from_a_temperature_cohort() -> None:
    rows: list[dict[str, Any]] = []

    def add_state(cohort: str, temperature: float, step_index: int, families: tuple[str, ...], selected: str) -> None:
        for family in families:
            rows.append(
                {
                    "group_by": "position",
                    "family": family,
                    "generation_cohort_id": cohort,
                    "generation_cohort": cohort,
                    "scene": cohort,
                    "rollout_row_id": 0,
                    "step_row_id": 10 + step_index,
                    "step_index": step_index,
                    "policy": "temperature_softmax",
                    "temperature": temperature,
                    "horizon": 2,
                    "branch_factor": 1,
                    "beam_width": 1,
                    "candidate_count": len(families),
                    "actor_valid_count": len(families),
                    "family_candidate_count": 1,
                    "family_actor_valid_count": 1,
                    "family_selected_count": int(family == selected),
                    "allocation_share": 1.0 / len(families),
                    "valid_share": 1.0 / len(families),
                    "selected_share": float(family == selected),
                    "policy_mass": 0.25 if family == "side" else 0.75 if len(families) == 2 else 1.0,
                    "probability_available": True,
                    "probability_unavailable_reason": None,
                }
            )

    add_state("hot", 2.0, 0, ("forward", "side"), "forward")
    add_state("hot", 2.0, 1, ("forward", "side"), "side")
    add_state("cold", 0.5, 0, ("forward",), "forward")
    add_state("cold", 0.5, 1, ("forward",), "forward")
    pooled = candidate_selection_pooled_summary_rows(rows, metric="allocation_share")
    side = next(row for row in pooled if row["step_index"] == 1 and row["family"] == "side")
    assert side["state_count"] == 2 and side["numerator"] == 1 and side["denominator"] == 3
    assert side["fraction"] == pytest.approx(1 / 3)
    pooled_policy = candidate_selection_pooled_summary_rows(rows, metric="policy_mass")
    side_policy = next(row for row in pooled_policy if row["step_index"] == 1 and row["family"] == "side")
    assert side_policy["state_count"] == 2 and side_policy["finite_state_count"] == 2
    assert side_policy["fraction"] == pytest.approx(0.125)
    pooled_selected = candidate_selection_pooled_summary_rows(rows, metric="selected_share")
    side_selected = next(row for row in pooled_selected if row["step_index"] == 1 and row["family"] == "side")
    assert side_selected["state_count"] == 2 and side_selected["numerator"] == 1
    assert side_selected["denominator"] == 2 and side_selected["fraction"] == pytest.approx(0.5)
    transitions = candidate_selection_transition_rows(rows, pool_temperatures=True)
    transition = next(
        row
        for row in transitions
        if row["step_index"] == 1 and row["previous_family"] == "forward" and row["next_family"] == "side"
    )
    assert transition["context_count"] == 2 and transition["realized_count"] == 1
    assert transition["realized_rate"] == pytest.approx(0.5)


def test_candidate_selection_probability_failure_closes_policy_mass_only() -> None:
    rows = [
        {
            "candidate_row_id": index,
            "generation_cohort_id": "cohort",
            "generation_cohort": "{}",
            "scene": "scene",
            "rollout_row_id": 0,
            "step_row_id": 0,
            "step_index": 0,
            "policy": "temperature_softmax",
            "temperature": 2.0,
            "horizon": 1,
            "branch_factor": 1,
            "beam_width": 1,
            "mixture": family,
            "position": family,
            "strategy": "target_point",
            "invalid_reason": "none",
            "actor_action": True,
            "oracle_label": True,
            "q_train": True,
            "selected": index == 0,
            "sampler_probability": 0.5,
            "selection_probability": probability,
            "target_root_gain": 0.1,
            "cumulative_target_root_gain": 0.1,
            "path_collision": False,
            "path_collision_applicable": True,
            "path_collision_evaluated": True,
            "path_min_clearance_m": 1.0,
        }
        for index, (family, probability) in enumerate((("forward", 0.8), ("side", None)))
    ]
    evidence = candidate_population_evidence(
        _reader_stub(), audit_reader=lambda _reader, *, row_callback: [row_callback(row) for row in rows]
    )
    dynamics = evidence["selection_dynamics"]["position"]
    assert all(row["policy_mass"] is None for row in dynamics)
    assert all(row["probability_unavailable_reason"] == "incomplete_probability_vector" for row in dynamics)
    assert evidence["calibration"]["position"][0]["proposal_available"] is True
    with pytest.raises(ValueError, match="Unsupported candidate selection metric"):
        candidate_selection_temporal_summary_rows(dynamics, metric="unsupported")


def test_candidate_group_summary_rejects_unsupported_field() -> None:
    with pytest.raises(ValueError, match="Unsupported candidate group field"):
        candidate_group_summary_rows(cast(Any, SimpleNamespace()), group_by=cast(Any, "not-supported"))


def test_rollout_store_inventory_rows_report_current_stale_and_unreadable_stores(tmp_path: Path) -> None:
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


def test_rollout_header_summary_reuses_manifest_snapshot_without_statistics_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Header inspection consumes its manifest input and does not compute compact statistics."""

    result = write_rollout_zarr_store(
        tmp_path / "header.zarr", build_rollout_records(horizon=1, num_samples=6, seed=104)[:1]
    )
    reader = RolloutZarrStoreReader(result.store_dir)
    manifest = reader.manifest()
    manifest_calls = 0

    def fail_manifest() -> None:
        nonlocal manifest_calls
        manifest_calls += 1
        raise AssertionError("header summary reopened the manifest")

    monkeypatch.setattr(reader, "manifest", fail_manifest)
    monkeypatch.setattr(
        "aria_nbv.rollouts.inspection.rollout_statistics",
        lambda *_args, **_kwargs: pytest.fail("header summary computed compact statistics"),
    )

    header = rollout_header_summary(reader, manifest_payload=manifest)

    assert manifest_calls == 0
    assert header["rollouts"] == result.num_rollouts


def test_rollout_store_inventory_can_skip_deep_validation_for_interactive_discovery(tmp_path: Path) -> None:
    current = write_rollout_zarr_store(
        tmp_path / "current.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=42)[:1],
    )

    row = rollout_store_inventory_rows([current.store_dir], validate=False)[0]

    assert row["schema_status"] == "current"
    assert row["validation_ok"] is None
    assert row["validation_status"] == "unknown"
    assert row["observed_candidates"] == current.num_candidates


def test_discover_rollout_store_paths_returns_zarr_directories(tmp_path: Path) -> None:
    """Discovery should recursively find candidate Zarr directories only."""

    first = tmp_path / "nested" / "a.zarr"
    second = tmp_path / "b.zarr"
    first.mkdir(parents=True)
    second.mkdir()
    (tmp_path / "not_zarr.txt").write_text("skip", encoding="utf-8")

    paths = discover_rollout_store_paths(tmp_path)

    assert set(paths) == {first.resolve(), second.resolve()}


def test_discover_rollout_store_paths_includes_completed_campaign_shards(tmp_path: Path) -> None:
    """Discovery should include only fully promoted hash-named campaign stores."""

    campaign_root = tmp_path / "rollout_supervision" / "campaigns" / "campaign" / "shards"
    promoted = campaign_root / "work-unit-hash"
    incomplete = campaign_root / "incomplete-work-unit"
    nested_group = promoted / "candidate"
    for path in (promoted, incomplete, nested_group):
        path.mkdir(parents=True)
    for marker in ("zarr.json", "manifest.json", "_SUCCESS.json", "_owner.json"):
        (promoted / marker).write_text("{}", encoding="utf-8")
    (incomplete / "zarr.json").write_text("{}", encoding="utf-8")
    (nested_group / "zarr.json").write_text("{}", encoding="utf-8")

    paths = discover_rollout_store_paths(tmp_path)

    assert promoted.resolve() in paths
    assert incomplete.resolve() not in paths
    assert nested_group.resolve() not in paths


def test_rollout_inspection_helpers_join_candidates_targets_and_groups(tmp_path: Path) -> None:
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
    assert first["target_protocol"] == "v0_gt_input"
    assert first["target_evidence_role"] == "oracle/evaluation"
    assert "decision_relative_x_m" in first
    assert first["view_jitter_is_bounded"] is True
    assert first["view_jitter_yaw_deg"] == pytest.approx(0.0)
    assert first["view_jitter_pitch_deg"] == pytest.approx(0.0)
    assert first["target_view_evaluated"] is False
    assert first["target_in_fov"] is None

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


def test_filtered_nonroot_audit_preserves_previous_selected_reference(tmp_path: Path) -> None:
    records = build_rollout_records(horizon=2, num_samples=6, seed=143)[:1]
    result = write_rollout_zarr_store(tmp_path / "filtered-reference.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)
    full = candidate_audit_rows(reader)
    nonroot = next(row for row in full if int(row["step_index"]) == 1)
    filtered = candidate_audit_rows(reader, step_row_id=int(nonroot["step_row_id"]))
    same = next(row for row in filtered if row["candidate_row_id"] == nonroot["candidate_row_id"])
    assert tuple(same[f"decision_relative_{axis}_m"] for axis in "xyz") == pytest.approx(
        tuple(nonroot[f"decision_relative_{axis}_m"] for axis in "xyz")
    )


def test_decision_relative_vector_uses_previous_selected_pose_and_is_global_invariant() -> None:
    identity = np.eye(3)
    root = np.r_[identity.reshape(-1), [0.0, 0.0, 0.0]]
    selected_rotation = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    selected = np.r_[selected_rotation.reshape(-1), [1.0, 0.0, 0.0]]
    candidate = np.r_[identity.reshape(-1), [1.0, 1.0, 0.0]]

    assert _decision_relative_vector(root, candidate) == pytest.approx([1.0, 1.0, 0.0])
    assert _decision_relative_vector(selected, candidate) == pytest.approx([1.0, 0.0, 0.0])

    yaw = np.deg2rad(37.0)
    global_rotation = np.array([[np.cos(yaw), -np.sin(yaw), 0.0], [np.sin(yaw), np.cos(yaw), 0.0], [0.0, 0.0, 1.0]])
    translation = np.array([4.0, -3.0, 2.0])

    def transform(pose: np.ndarray) -> np.ndarray:
        rotation = pose[:9].reshape(3, 3)
        center = pose[9:12]
        return np.asarray(
            np.r_[(global_rotation @ rotation).reshape(-1), global_rotation @ center + translation],
            dtype=np.float64,
        )

    assert _decision_relative_vector(transform(selected), transform(candidate)) == pytest.approx([1.0, 0.0, 0.0])


def test_decision_relative_vector_fails_closed_without_reference() -> None:
    assert _decision_relative_vector(np.full(12, np.nan), np.zeros(12)) is None


def test_candidate_scientific_state_chunks_bound_raw_retention_and_reject_interleave() -> None:
    rows = [
        {
            "generation_cohort_id": "cohort",
            "scene": "scene",
            "rollout_row_id": rollout,
            "step_row_id": step,
            "candidate_row_id": candidate,
        }
        for rollout in range(12)
        for step in range(3)
        for candidate in range(60)
    ]
    chunks = list(_iter_candidate_state_chunks(rows))
    assert len(chunks) == 36
    assert max(map(len, chunks)) == 60

    interleaved = [rows[0], rows[60], rows[1]]
    with pytest.raises(ValueError, match="interleave"):
        list(_iter_candidate_state_chunks(interleaved))


def test_candidate_geometry_evidence_maps_root_target_and_rightward_lateral() -> None:
    """Target-normalized geometry fixes the frame and preserves right-handed sign."""

    from aria_nbv.rollouts.inspection import candidate_geometry_evidence_rows

    rows = candidate_geometry_evidence_rows(
        [
            {
                "candidate_row_id": 1,
                "root_relative_x_m": 0.0,
                "root_relative_y_m": 0.0,
                "root_relative_z_m": 0.0,
                "root_to_target_x_m": 2.0,
                "root_to_target_y_m": 0.0,
            },
            {
                "candidate_row_id": 2,
                "root_relative_x_m": 2.0,
                "root_relative_y_m": 0.0,
                "root_relative_z_m": 0.0,
                "root_to_target_x_m": 2.0,
                "root_to_target_y_m": 0.0,
            },
            {
                "candidate_row_id": 3,
                "root_relative_x_m": 0.0,
                "root_relative_y_m": 1.0,
                "root_relative_z_m": 0.0,
                "root_to_target_x_m": 2.0,
                "root_to_target_y_m": 0.0,
            },
        ]
    )

    by_id = {row["candidate_row_id"]: row for row in rows}
    assert by_id[1]["target_normalized_forward"] == pytest.approx(0.0)
    assert by_id[1]["target_normalized_lateral"] == pytest.approx(0.0)
    assert by_id[2]["target_normalized_forward"] == pytest.approx(1.0)
    assert by_id[3]["target_normalized_forward"] == pytest.approx(0.0)
    assert by_id[3]["target_normalized_lateral"] == pytest.approx(0.5)
    assert by_id[3]["target_normalized_coordinate_frame"] == ("root=(0,0), target=(1,0), right-handed lateral axis")


def test_candidate_geometry_evidence_keeps_missing_and_degenerate_baselines_unavailable() -> None:
    """Unavailable target geometry is not converted into a fabricated origin."""

    from aria_nbv.rollouts.inspection import candidate_geometry_evidence_rows

    rows = candidate_geometry_evidence_rows(
        [
            {
                "candidate_row_id": 1,
                "root_relative_x_m": 1.0,
                "root_relative_y_m": 1.0,
                "root_relative_z_m": 0.0,
                "root_to_target_x_m": 0.0,
                "root_to_target_y_m": 0.0,
            },
            {
                "candidate_row_id": 2,
                "root_relative_x_m": 1.0,
                "root_relative_y_m": 1.0,
                "root_relative_z_m": 0.0,
                "root_to_target_x_m": None,
                "root_to_target_y_m": None,
            },
        ]
    )

    assert all(row["target_normalized_forward"] is None for row in rows)
    assert all(row["target_normalized_lateral"] is None for row in rows)


def _direction_fixture_rows() -> list[dict[str, Any]]:
    common = {
        "generation_cohort_id": "cohort-a",
        "source_sample_key": "sample-a",
        "target_id": "target-a",
        "target_protocol": "v1_observed",
        "candidate_config": "candidate-a",
        "rollout_config": "rollout-a",
        "branch_schedule": "temperature_softmax",
        "policy": "temperature_softmax",
        "temperature": 1.0,
        "horizon": 8,
        "acquisition_budget_steps": 8,
        "branch_factor": 1,
        "beam_width": 1,
        "scene": "scene-a",
        "position": "forward_local",
        "actor_action": True,
    }
    return [
        {
            **common,
            "candidate_row_id": 0,
            "rollout_row_id": 0,
            "step_row_id": 0,
            "root_relative_x_m": 1.0,
            "root_relative_y_m": 0.0,
            "root_relative_z_m": 0.0,
        },
        {
            **common,
            "candidate_row_id": 1,
            "rollout_row_id": 0,
            "step_row_id": 0,
            "root_relative_x_m": 0.0,
            "root_relative_y_m": 1.0,
            "root_relative_z_m": 0.0,
        },
        {
            **common,
            "candidate_row_id": 2,
            "rollout_row_id": 1,
            "step_row_id": 1,
            "root_relative_x_m": 0.0,
            "root_relative_y_m": 0.0,
            "root_relative_z_m": 1.0,
        },
        {
            **common,
            "candidate_row_id": 3,
            "rollout_row_id": 1,
            "step_row_id": 1,
            "root_relative_x_m": 0.0,
            "root_relative_y": 0.0,
            "root_relative_z_m": 0.0,
        },
    ]


def test_candidate_direction_evidence_uses_complete_equal_area_bins_and_state_scene_macros() -> None:
    """Direction density uses azimuth x sin(elevation) and macro-averages states."""

    from aria_nbv.rollouts.inspection import candidate_direction_evidence

    evidence = candidate_direction_evidence(_direction_fixture_rows())
    density = evidence["density_rows"]
    assert density
    assert {row["evidence"] for row in density} == {"equal_area_direction_density"}
    assert {row["aggregation_level"] for row in density} >= {"state", "scene_macro", "cohort_macro"}
    assert all(row["protocol"]["binning"] == "azimuth x sin(elevation)" for row in density)
    state_rows = [
        row
        for row in density
        if row["aggregation_level"] == "state" and row["available"] and row.get("population") in {None, "all"}
    ]
    state_fractions: dict[tuple[Any, Any], float] = {}
    for row in state_rows:
        state_id = (row.get("rollout_row_id"), row.get("step_row_id"))
        state_fractions[state_id] = state_fractions.get(state_id, 0.0) + float(row["mean_state_fraction"])
    assert set(state_fractions) == {("0", "0"), ("1", "1")}
    assert all(value == pytest.approx(1.0) for value in state_fractions.values())
    assert all(row["azimuth_bin"] >= 0 and row["sin_elevation_bin"] >= 0 for row in density)
    assert evidence["cap_rows"] and evidence["angular_support_rows"]


def test_candidate_direction_evidence_uses_luf_forward_left_up_axes() -> None:
    """Equal-area bins use LUF azimuth atan2(left, forward) and up elevation."""

    from aria_nbv.rollouts.inspection import candidate_direction_evidence

    vectors = {
        "forward": (0.0, 0.0, 1.0),
        "left": (1.0, 0.0, 0.0),
        "up": (0.0, 1.0, 0.0),
    }
    rows = []
    for index, (name, vector) in enumerate(vectors.items()):
        rows.append(
            {
                **_direction_fixture_rows()[0],
                "rollout_row_id": index,
                "step_row_id": index,
                "decision_relative_x_m": vector[0],
                "decision_relative_y_m": vector[1],
                "decision_relative_z_m": vector[2],
                "direction_name": name,
            }
        )

    density = candidate_direction_evidence(rows)["density_rows"]

    occupied = {
        (row["rollout_row_id"], row["azimuth_bin"], row["sin_elevation_bin"])
        for row in density
        if row["aggregation_level"] == "state" and row["population"] == "all" and row["count"] == 1
    }
    assert occupied == {("0", 6, 3), ("1", 9, 3), ("2", 6, 5)}


def test_candidate_direction_evidence_excludes_zero_length_and_missing_directions_from_denominator() -> None:
    """Invalid direction vectors remain explicit missingness, never zero directions."""

    from aria_nbv.rollouts.inspection import candidate_direction_evidence

    evidence = candidate_direction_evidence(_direction_fixture_rows())
    state_rows = [
        row
        for row in evidence["density_rows"]
        if row["aggregation_level"] == "state" and row.get("population") in {None, "all"}
    ]
    assert any(int(row["missing_count"]) > 0 for row in state_rows)
    assert all(row["units"] == "solid-angle fraction" for row in state_rows)


def test_candidate_spatial_support_preserves_zero_radius_and_signed_height() -> None:
    """Spatial support is measured in metres and does not discard the origin."""

    from aria_nbv.rollouts.inspection import candidate_geometry_evidence_rows, candidate_spatial_support_evidence

    rows = candidate_geometry_evidence_rows(
        [
            {
                **_direction_fixture_rows()[0],
                "root_relative_x_m": 0.0,
                "root_relative_y_m": -0.25,
                "root_relative_z_m": 0.0,
                "root_radius_m": 0.0,
            },
            {
                **_direction_fixture_rows()[1],
                "rollout_row_id": 1,
                "step_row_id": 1,
                "root_relative_x_m": 0.5,
                "root_relative_y_m": 0.0,
                "root_relative_z_m": 0.5,
                "root_radius_m": 0.5,
            },
        ]
    )

    evidence = candidate_spatial_support_evidence(rows)
    state_rows = [row for row in evidence if row["aggregation_level"] == "state"]
    origin = next(row for row in state_rows if row["rollout_row_id"] == "0")
    offset = next(row for row in state_rows if row["rollout_row_id"] == "1")
    height = next(row for row in evidence if row["metric"] == "decision_height_m" and row["rollout_row_id"] == "0")
    assert origin["available"] is True
    assert origin["mean"] == pytest.approx(0.0)
    assert origin["zero_radius_policy"] == "included"
    assert offset["mean"] == pytest.approx(np.hypot(0.5, 0.5))
    assert height["mean"] == pytest.approx(-0.25)
    assert height["units"] == "m"


def test_candidate_spatial_support_uses_luf_horizontal_plane_and_truthful_names() -> None:
    """Decision-local horizontal support uses left/forward while height uses up."""

    from aria_nbv.rollouts.inspection import candidate_spatial_support_evidence

    row = {
        **_direction_fixture_rows()[0],
        "decision_relative_x_m": 3.0,
        "decision_relative_y_m": 4.0,
        "decision_relative_z_m": 12.0,
    }

    state_rows = [
        item
        for item in candidate_spatial_support_evidence([row])
        if item["aggregation_level"] == "state" and item["population"] == "all"
    ]
    metrics = {item["metric"]: item for item in state_rows}
    assert set(metrics) == {"decision_horizontal_radius_m", "decision_distance_m", "decision_height_m"}
    assert metrics["decision_horizontal_radius_m"]["mean"] == pytest.approx(np.hypot(3.0, 12.0))
    assert metrics["decision_distance_m"]["mean"] == pytest.approx(13.0)
    assert metrics["decision_height_m"]["mean"] == pytest.approx(4.0)
    assert all(item["position_family"] == "forward_local" for item in state_rows)
    assert all("declared_shell" not in item for item in state_rows)


def test_candidate_target_view_evidence_keeps_unpersisted_visibility_explicit() -> None:
    """Target distance is distinct from unavailable target-view or line-of-sight evidence."""

    from aria_nbv.rollouts.inspection import candidate_target_view_evidence

    rows = [{**_direction_fixture_rows()[0], "target_distance_m": 2.0}]
    evidence = candidate_target_view_evidence(rows)
    distance = next(row for row in evidence if row["evidence"] == "target_distance")
    los = next(row for row in evidence if row["evidence"] == "target_line_of_sight")
    assert distance["available"] is True
    assert distance["units"] == "m"
    assert los["available"] is False
    assert "not persisted" in str(los["reason"])
    assert los["missing_count"] == 1


def test_candidate_motion_support_reports_clearance_and_collision_missingness() -> None:
    """Motion support never substitutes a missing collision evaluation with zero."""

    from aria_nbv.rollouts.inspection import candidate_motion_support_evidence

    rows = [
        {
            **_direction_fixture_rows()[0],
            "motion_step_length_m": 0.2,
            "motion_height_delta_m": -0.1,
            "motion_backward_step_m": 0.0,
            "motion_yaw_delta_deg": 10.0,
            "path_min_clearance_m": None,
            "free_space_margin_m": None,
            "path_collision": None,
        }
    ]
    evidence = candidate_motion_support_evidence(rows)
    clearance = next(row for row in evidence if row["metric"] == "path_min_clearance_m")
    collision = next(row for row in evidence if row["metric"] == "path_collision_rate")
    assert clearance["available"] is False
    assert clearance["missing_count"] == 1
    assert collision["available"] is False
    assert collision["missing_count"] == 1


def test_candidate_population_scientific_support_is_complete_and_sample_size_independent() -> None:
    """Scientific reducers use every audit row; sample_size only bounds display rows."""

    from aria_nbv.rollouts.inspection import candidate_population_evidence

    rows = [
        {
            **_direction_fixture_rows()[0],
            "candidate_row_id": index,
            "root_relative_x_m": float(index + 1),
            "root_relative_y_m": 0.0,
            "root_relative_z_m": 0.0,
            "root_to_target_x_m": 1.0,
            "root_to_target_y_m": 0.0,
        }
        for index in range(4)
    ]

    def audit_reader(_reader: Any, *, row_callback: Any) -> None:
        for row in rows:
            row_callback(row)

    bounded = candidate_population_evidence(_reader_stub(), sample_size=1, audit_reader=audit_reader)
    complete = candidate_population_evidence(_reader_stub(), sample_size=100, audit_reader=audit_reader)
    assert bounded["population_count"] == complete["population_count"] == 4
    assert bounded["sample"]["display_count"] == 1
    assert complete["sample"]["display_count"] == 4
    assert bounded["spatial"] == complete["spatial"]
    assert bounded["direction"] == complete["direction"]


def test_candidate_population_returns_macro_only_scientific_support_by_default() -> None:
    """Complete-store cached evidence cardinality depends on facets, not factual state count."""

    import tracemalloc

    from aria_nbv.rollouts.inspection import candidate_population_evidence

    def project(state_count: int) -> dict[str, Any]:
        rows = [
            {
                **_direction_fixture_rows()[0],
                "candidate_row_id": index,
                "rollout_row_id": index,
                "step_row_id": index,
                "decision_relative_x_m": 0.0,
                "decision_relative_y_m": 0.0,
                "decision_relative_z_m": 1.0,
                "target_distance_m": 1.0,
            }
            for index in range(state_count)
        ]
        return candidate_population_evidence(
            _reader_stub(),
            audit_reader=lambda _reader, *, row_callback: [row_callback(row) for row in rows],
        )

    small = project(2)
    tracemalloc.start()
    large = project(128)
    _current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    for key in ("spatial", "target_view", "motion"):
        assert not any(row["aggregation_level"] == "state" for row in large[key])
        assert len(large[key]) == len(small[key])
    for key in ("density_rows", "cap_rows", "angular_support_rows"):
        assert not any(row["aggregation_level"] == "state" for row in large["direction"][key])
        assert len(large["direction"][key]) == len(small["direction"][key])
    assert peak_bytes < 8 * 1024 * 1024


def test_candidate_population_streaming_macros_match_direct_reducer_statistics() -> None:
    """Online scene/cohort sufficient statistics preserve the direct reducer estimand."""

    from aria_nbv.rollouts.inspection import (
        candidate_direction_evidence,
        candidate_motion_support_evidence,
        candidate_population_evidence,
        candidate_spatial_support_evidence,
        candidate_target_view_evidence,
    )

    rows = []
    for index, (scene, vector, actor_action) in enumerate(
        (
            ("scene-a", (1.0, 0.0, 0.0), True),
            ("scene-a", (0.0, 1.0, 0.0), False),
            ("scene-b", (0.0, 0.0, 1.0), True),
            ("scene-b", (0.0, 0.0, 0.0), False),
        )
    ):
        rows.append(
            {
                **_direction_fixture_rows()[0],
                "candidate_row_id": index,
                "scene": scene,
                "rollout_row_id": index,
                "step_row_id": index,
                "step_index": 0,
                "actor_action": actor_action,
                "selected": True,
                "sampler_probability": 1.0,
                "decision_relative_x_m": vector[0],
                "decision_relative_y_m": vector[1],
                "decision_relative_z_m": vector[2],
                "target_distance_m": 1.0,
                "path_collision_applicable": True,
                "path_collision_evaluated": True,
                "path_collision": False,
                "path_min_clearance_m": 1.0,
                "target_evidence_role": "actor-visible",
            }
        )

    projected = candidate_population_evidence(
        _reader_stub(),
        sample_size=0,
        audit_reader=lambda _reader, *, row_callback: [row_callback(row) for row in rows],
    )

    def assert_statistics(
        actual_rows: list[dict[str, Any]],
        expected_rows: list[dict[str, Any]],
        *,
        key_fields: tuple[str, ...],
        value_fields: tuple[str, ...],
    ) -> None:
        actual = {tuple(row.get(field) for field in key_fields): row for row in actual_rows}
        expected = {
            tuple(row.get(field) for field in key_fields): row
            for row in expected_rows
            if row["aggregation_level"] != "state"
        }
        assert actual.keys() == expected.keys()
        for key, expected_row in expected.items():
            for field in value_fields:
                expected_value = expected_row.get(field)
                actual_value = actual[key].get(field)
                if isinstance(expected_value, float):
                    assert actual_value == pytest.approx(expected_value)
                else:
                    assert actual_value == expected_value

    direction = candidate_direction_evidence(rows)
    common = ("aggregation_level", "generation_cohort_id", "scene", "population")
    assert_statistics(
        projected["direction"]["density_rows"],
        direction["density_rows"],
        key_fields=(*common, "azimuth_bin", "sin_elevation_bin"),
        value_fields=("mean_state_fraction", "count", "total_count", "finite_count", "missing_count"),
    )
    assert_statistics(
        projected["direction"]["cap_rows"],
        direction["cap_rows"],
        key_fields=(*common, "radius_deg"),
        value_fields=("discrepancy", "total_count", "finite_count", "missing_count"),
    )
    assert_statistics(
        projected["direction"]["angular_support_rows"],
        direction["angular_support_rows"],
        key_fields=(*common, "evidence"),
        value_fields=("nearest_neighbor_deg", "covering_radius_deg", "total_count", "finite_count"),
    )
    for name, reducer, facets, values in (
        (
            "spatial",
            candidate_spatial_support_evidence,
            (*common, "position_family", "metric"),
            ("mean", "total_count", "finite_count", "missing_count"),
        ),
        (
            "target_view",
            candidate_target_view_evidence,
            (*common, "evidence"),
            ("mean", "total_count", "finite_count", "missing_count"),
        ),
        (
            "motion",
            candidate_motion_support_evidence,
            (*common, "metric"),
            ("mean", "collision_rate", "total_count", "finite_count", "missing_count"),
        ),
    ):
        assert_statistics(projected[name], reducer(rows), key_fields=facets, value_fields=values)


def test_candidate_population_can_skip_unused_scientific_reducers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Report-style projections never invoke direction/spatial/target-view/motion reducers."""

    import aria_nbv.rollouts.inspection as inspection

    def poison(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("unused scientific reducer was invoked")

    for name in (
        "candidate_direction_evidence",
        "candidate_spatial_support_evidence",
        "candidate_target_view_evidence",
        "candidate_motion_support_evidence",
    ):
        monkeypatch.setattr(inspection, name, poison)
    rows = [{**_direction_fixture_rows()[0], "candidate_row_id": 0}]

    evidence = inspection.candidate_population_evidence(
        _reader_stub(),
        scientific_support=False,
        audit_reader=lambda _reader, *, row_callback: [row_callback(row) for row in rows],
    )

    assert evidence["direction"] == {"density_rows": [], "cap_rows": [], "angular_support_rows": []}
    assert evidence["spatial"] == []
    assert evidence["target_view"] == []
    assert evidence["motion"] == []
    assert evidence["population_count"] == 1


def test_candidate_population_assigns_evidence_roles_per_metric_family() -> None:
    """Actor-visible support and privileged evaluator evidence are never conflated."""

    from aria_nbv.rollouts.inspection import candidate_population_evidence

    row = {
        **_direction_fixture_rows()[0],
        "candidate_row_id": 0,
        "target_evidence_role": "actor-visible",
    }
    evidence = candidate_population_evidence(
        _reader_stub(),
        scientific_support=False,
        audit_reader=lambda _reader, *, row_callback: row_callback(row),
    )

    assert evidence["evidence_roles"] == {
        "direction": "actor-visible",
        "spatial": "actor-visible",
        "motion": "actor-visible",
        "collision": "oracle/evaluation",
        "clearance": "oracle/evaluation",
        "target_view": "actor-visible",
        "geometry": "actor-visible",
        "selection": "actor-visible",
        "sequence_return": "oracle/evaluation",
    }


def test_candidate_direction_evidence_preserves_cohorts_and_all_actor_valid_populations() -> None:
    """Direction support never pools incompatible cohorts or actor populations."""

    from aria_nbv.rollouts.inspection import candidate_direction_evidence

    rows = []
    for cohort, actor_action, scene, rollout_id in (
        ("cohort-a", True, "scene-a", 0),
        ("cohort-a", False, "scene-a", 1),
        ("cohort-b", True, "scene-b", 2),
    ):
        rows.append(
            {
                **_direction_fixture_rows()[0],
                "generation_cohort_id": cohort,
                "actor_action": actor_action,
                "scene": scene,
                "rollout_row_id": rollout_id,
                "root_relative_x_m": 1.0,
            }
        )

    density = candidate_direction_evidence(rows)["density_rows"]
    assert {row["generation_cohort_id"] for row in density if row["aggregation_level"] == "cohort_macro"} == {
        "cohort-a",
        "cohort-b",
    }
    assert {row["population"] for row in density if row["aggregation_level"] == "state"} >= {"all", "actor_valid"}
    assert all(
        row["cohort_macro_population"] in {"all", "actor_valid"} for row in density if "cohort_macro_population" in row
    )


def test_candidate_direction_evidence_retains_zero_actor_valid_states() -> None:
    """A factual state with no valid actions remains in actor-valid denominators."""

    from aria_nbv.rollouts.inspection import candidate_direction_evidence

    rows = [{**_direction_fixture_rows()[0], "actor_action": False, "candidate_row_id": index} for index in range(3)]
    density = candidate_direction_evidence(rows)["density_rows"]
    actor_state = next(
        row for row in density if row["aggregation_level"] == "state" and row["population"] == "actor_valid"
    )
    actor_macro = next(
        row for row in density if row["aggregation_level"] == "cohort_macro" and row["population"] == "actor_valid"
    )
    assert actor_state["state_count"] == 1
    assert actor_state["candidate_total_count"] == 0
    assert actor_macro["state_count"] == 1
    assert actor_macro["defined_state_count"] == 0


def test_bounded_candidate_reducers_are_order_invariant_across_state_blocks() -> None:
    """Bounded replay preserves canonical rows even when factual blocks arrive reversed."""

    from aria_nbv.rollouts.inspection import (
        candidate_direction_evidence,
        candidate_motion_support_evidence,
        candidate_spatial_support_evidence,
        candidate_target_view_evidence,
    )

    canonical = [
        {
            **row,
            "target_distance_m": 1.0,
            "motion_step_length_m": 0.1,
            "motion_height_delta_m": 0.0,
            "motion_backward_step_m": 0.0,
            "motion_yaw_delta_deg": 1.0,
            "free_space_margin_m": 0.2,
            "path_min_clearance_m": 0.3,
            "path_collision_applicable": True,
            "path_collision_evaluated": True,
            "path_collision": False,
        }
        for row in _direction_fixture_rows()
    ]
    canonical[2]["actor_action"] = False
    canonical[3]["actor_action"] = False
    blocks: dict[tuple[Any, Any, Any], list[dict[str, Any]]] = {}
    for row in canonical:
        key = (row["scene"], row["rollout_row_id"], row["step_row_id"])
        blocks.setdefault(key, []).append(row)
    reversed_blocks = [row for block in reversed(list(blocks.values())) for row in block]

    for reducer in (
        candidate_direction_evidence,
        candidate_spatial_support_evidence,
        candidate_target_view_evidence,
        candidate_motion_support_evidence,
    ):
        assert reducer(canonical) == reducer(reversed_blocks)


def test_candidate_direction_evidence_reports_numeric_cap_and_nearest_neighbor_metrics() -> None:
    """Angular support rows contain deterministic discrepancy and separation values."""

    from aria_nbv.rollouts.inspection import candidate_direction_evidence

    rows = _direction_fixture_rows()[:3]
    evidence = candidate_direction_evidence(rows)
    cap = evidence["cap_rows"]
    angular = evidence["angular_support_rows"]
    assert cap and angular
    assert all(row["available"] is True for row in cap + angular)
    assert all("candidate_count" not in row or row["candidate_count"] == len(rows) for row in cap + angular)
    assert any("discrepancy" in row or "value" in row for row in cap)
    assert any("nearest" in str(row).lower() or "separation" in str(row).lower() for row in angular)
    assert any("covering" in str(row).lower() for row in angular)
    assert all(row.get("metric_name") == "distance_from_isotropy" for row in cap)
    assert all(row["protocol"]["null_model"] == "uniform S2" for row in cap)


def test_candidate_spatial_support_reports_3d_distance_shell_and_macro_levels() -> None:
    """Spatial support includes radius, 3-D distance, signed Z, and shell macros."""

    from aria_nbv.rollouts.inspection import candidate_spatial_support_evidence

    rows = [
        {
            **_direction_fixture_rows()[0],
            "generation_cohort_id": "cohort-a",
            "position": "forward_local",
            "root_relative_x_m": 0.0,
            "root_relative_y_m": 0.0,
            "root_relative_z_m": -0.25,
        },
        {
            **_direction_fixture_rows()[0],
            "generation_cohort_id": "cohort-a",
            "position": "backtrack",
            "candidate_row_id": 99,
            "root_relative_x_m": 0.3,
            "root_relative_y_m": 0.4,
            "root_relative_z_m": 0.5,
        },
    ]
    evidence = candidate_spatial_support_evidence(rows)
    assert {row["metric"] for row in evidence} >= {
        "decision_horizontal_radius_m",
        "decision_distance_m",
        "decision_height_m",
    }
    assert {row["aggregation_level"] for row in evidence} >= {"state", "scene_macro", "cohort_macro"}
    assert {row["position_family"] for row in evidence} >= {"forward_local", "backtrack"}
    assert any(row["metric"] == "decision_distance_m" and row["units"] == "m" for row in evidence)


def test_candidate_target_view_exposes_unavailable_fov_and_pixel_evidence() -> None:
    """Missing target-view calibration is explicit rather than inferred from distance."""

    from aria_nbv.rollouts.inspection import candidate_target_view_evidence

    evidence = candidate_target_view_evidence([{**_direction_fixture_rows()[0], "target_distance_m": 2.0}])
    names = {row["evidence"] for row in evidence}
    assert {"target_fov_margin", "target_pixel_margin"} <= names
    for row in evidence:
        if row["evidence"] in {"target_fov_margin", "target_pixel_margin"}:
            assert row["available"] is False
            assert row["missing_count"] == 1


def test_candidate_target_view_summarizes_measured_projection_without_claiming_los() -> None:
    """Camera framing is measurable while scene visibility remains unavailable."""

    from aria_nbv.rollouts.inspection import candidate_target_view_evidence

    rows = [
        {
            **_direction_fixture_rows()[0],
            "target_distance_m": 2.0,
            "target_view_angle_deg": 5.0,
            "target_pixel_margin_px": 12.0,
            "target_in_fov": True,
        },
        {
            **_direction_fixture_rows()[0],
            "candidate_row_id": 2,
            "target_distance_m": 3.0,
            "target_view_angle_deg": 50.0,
            "target_pixel_margin_px": -8.0,
            "target_in_fov": False,
        },
    ]

    state = {
        row["evidence"]: row
        for row in candidate_target_view_evidence(rows)
        if row["aggregation_level"] == "state" and row["population"] == "all"
    }

    assert state["target_view_angle"]["mean"] == pytest.approx(27.5)
    assert state["target_pixel_margin"]["mean"] == pytest.approx(2.0)
    assert state["target_in_fov"]["mean"] == pytest.approx(0.5)
    assert state["target_line_of_sight"]["available"] is False
    assert "not persisted" in str(state["target_line_of_sight"]["reason"])


def test_candidate_motion_support_reports_all_motion_fields_and_collision_applicability_matrix() -> None:
    """Motion diagnostics preserve all persisted fields and four collision states."""

    from aria_nbv.rollouts.inspection import candidate_motion_support_evidence

    rows = []
    for index, (applicable, evaluated, collision) in enumerate(
        ((False, False, None), (True, False, None), (True, True, False), (True, True, True))
    ):
        rows.append(
            {
                **_direction_fixture_rows()[0],
                "candidate_row_id": index,
                "motion_step_length_m": 0.2,
                "motion_height_delta_m": -0.1,
                "motion_backward_step_m": 0.0,
                "motion_yaw_delta_deg": 10.0,
                "free_space_margin_m": 0.3,
                "path_min_clearance_m": 0.1 if evaluated else None,
                "path_collision_applicable": applicable,
                "path_collision_evaluated": evaluated,
                "path_collision": collision,
            }
        )
    evidence = candidate_motion_support_evidence(rows)
    assert {row["metric"] for row in evidence} >= {
        "motion_step_length_m",
        "motion_height_delta_m",
        "motion_backward_step_m",
        "motion_yaw_delta_deg",
        "free_space_margin_m",
        "path_min_clearance_m",
        "path_collision_rate",
    }
    collision_summary = next(row for row in evidence if row["metric"] == "path_collision_rate")
    assert collision_summary["applicable_count"] == 3
    assert collision_summary["evaluated_count"] == 2
    assert collision_summary["collision_count"] == 1


def test_direction_macros_exclude_unavailable_states_instead_of_zero_filling() -> None:
    """A state without finite directions must not dilute a valid state's macro fraction."""

    from aria_nbv.rollouts.inspection import candidate_direction_evidence

    rows = [
        {**_direction_fixture_rows()[0], "rollout_row_id": 0, "root_relative_x_m": 1.0},
        {
            **_direction_fixture_rows()[0],
            "rollout_row_id": 1,
            "root_relative_x_m": 0.0,
            "root_relative_y_m": 0.0,
            "root_relative_z_m": 0.0,
        },
    ]
    density = candidate_direction_evidence(rows)["density_rows"]
    valid_state = next(
        row
        for row in density
        if row["aggregation_level"] == "state"
        and row["rollout_row_id"] == "0"
        and row["azimuth_bin"] == 9
        and row["sin_elevation_bin"] == 3
    )
    assert valid_state["available"] is True
    macro = next(
        row
        for row in density
        if row["aggregation_level"] == "cohort_macro"
        and row["population"] == "all"
        and row["azimuth_bin"] == 9
        and row["sin_elevation_bin"] == 3
    )
    assert macro["mean_state_fraction"] == pytest.approx(1.0)


def test_direction_cap_and_angular_rows_keep_protocol_cohort_and_population_context() -> None:
    """Support diagnostics retain fixed references and the same cohort/population facets."""

    from aria_nbv.rollouts.inspection import candidate_direction_evidence

    rows = [
        {**_direction_fixture_rows()[0], "generation_cohort_id": "cohort-a"},
        {**_direction_fixture_rows()[1], "generation_cohort_id": "cohort-a"},
    ]
    evidence = candidate_direction_evidence(rows)
    cap = evidence["cap_rows"]
    angular = evidence["angular_support_rows"]
    assert {row["population"] for row in cap + angular} >= {"all", "actor_valid"}
    assert {row["generation_cohort_id"] for row in cap + angular} == {"cohort-a"}
    assert {row["aggregation_level"] for row in cap + angular} >= {"state", "scene_macro", "cohort_macro"}
    assert all(row["protocol"]["reference"] == "fixed Fibonacci sphere" for row in cap)
    assert all(row["protocol"]["reference_count"] == 128 for row in cap)
    assert all(row["protocol"]["covering_reference_count"] == 512 for row in angular)
    assert {row["radius_deg"] for row in cap} == {30, 60, 90, 120, 150}


def test_angular_support_singleton_and_antipodal_values_are_geometrically_defined() -> None:
    """Nearest-neighbor and covering diagnostics are computed, not placeholder counts."""

    from aria_nbv.rollouts.inspection import candidate_direction_evidence

    singleton = candidate_direction_evidence(
        [{**_direction_fixture_rows()[0], "root_relative_x_m": 1.0, "root_relative_y_m": 0.0, "root_relative_z_m": 0.0}]
    )["angular_support_rows"]
    singleton_row = next(row for row in singleton if row["aggregation_level"] == "state")
    assert singleton_row["nearest_neighbor_deg"] is None
    assert singleton_row["nearest_neighbor_available"] is False
    assert singleton_row["covering_radius_deg"] == pytest.approx(180.0, abs=1e-6)

    antipodal = candidate_direction_evidence(
        [
            {
                **_direction_fixture_rows()[0],
                "root_relative_x_m": 1.0,
                "root_relative_y_m": 0.0,
                "root_relative_z_m": 0.0,
            },
            {
                **_direction_fixture_rows()[1],
                "root_relative_x_m": -1.0,
                "root_relative_y_m": 0.0,
                "root_relative_z_m": 0.0,
            },
        ]
    )["angular_support_rows"]
    assert any(row.get("nearest_neighbor_deg") == pytest.approx(180.0) for row in antipodal)
    antipodal_row = next(row for row in antipodal if row["aggregation_level"] == "state")
    assert antipodal_row["nearest_neighbor_deg"] == pytest.approx(180.0)
    assert antipodal_row["covering_radius_deg"] == pytest.approx(90.0, abs=2.0)


def test_spatial_macros_preserve_shell_and_population_facets() -> None:
    """Spatial scene/cohort summaries remain separated by persisted shell and population."""

    from aria_nbv.rollouts.inspection import candidate_spatial_support_evidence

    rows = [
        {
            **_direction_fixture_rows()[0],
            "position": "forward_local",
            "root_relative_x_m": 0.1,
            "root_relative_y_m": 0.0,
            "root_relative_z_m": 0.0,
        },
        {
            **_direction_fixture_rows()[1],
            "position": "backtrack",
            "root_relative_x_m": 1.0,
            "root_relative_y_m": 0.0,
            "root_relative_z_m": 0.0,
        },
    ]
    evidence = candidate_spatial_support_evidence(rows)
    macro = [row for row in evidence if row["aggregation_level"] in {"scene_macro", "cohort_macro"}]
    assert {row["position_family"] for row in macro} >= {"forward_local", "backtrack"}
    assert {row["population"] for row in macro} >= {"all", "actor_valid"}
    assert all(row["generation_cohort_id"] == "cohort-a" for row in macro)


def test_direction_and_spatial_cohort_macros_weight_scenes_equally() -> None:
    """Uneven state counts cannot make one scene dominate a cohort macro."""

    from aria_nbv.rollouts.inspection import candidate_direction_evidence, candidate_spatial_support_evidence

    common = {**_direction_fixture_rows()[0], "generation_cohort_id": "cohort-a", "position": "forward_local"}
    rows = [
        {
            **common,
            "scene": "scene-a",
            "rollout_row_id": 0,
            "step_row_id": 0,
            "root_relative_x_m": 1.0,
            "root_relative_y_m": 0.0,
        },
        {
            **common,
            "scene": "scene-a",
            "rollout_row_id": 1,
            "step_row_id": 0,
            "root_relative_x_m": 1.0,
            "root_relative_y_m": 0.0,
        },
        {
            **common,
            "scene": "scene-b",
            "rollout_row_id": 2,
            "step_row_id": 0,
            "root_relative_x_m": 0.0,
            "root_relative_y_m": 1.0,
        },
    ]
    direction = candidate_direction_evidence(rows)["density_rows"]
    x_cell = next(
        row
        for row in direction
        if row["aggregation_level"] == "cohort_macro"
        and row["population"] == "all"
        and row["azimuth_bin"] == 9
        and row["sin_elevation_bin"] == 3
    )
    assert x_cell["mean_state_fraction"] == pytest.approx(0.5)
    assert x_cell["state_count"] == 3
    assert x_cell["candidate_direction_count"] == 3
    assert x_cell["total_count"] == 3
    assert x_cell["finite_count"] + x_cell["missing_count"] == x_cell["total_count"]
    state_rows = [row for row in direction if row["aggregation_level"] == "state" and row["population"] == "all"]
    assert all(row["state_count"] == 1 for row in state_rows)
    spatial = candidate_spatial_support_evidence(
        [
            {**row, "root_relative_x_m": 0.1 if row["scene"] == "scene-a" else 1.0, "root_relative_y_m": 0.0}
            for row in rows
        ]
    )
    distance = next(
        row
        for row in spatial
        if row["aggregation_level"] == "cohort_macro"
        and row["metric"] == "decision_horizontal_radius_m"
        and row["population"] == "all"
    )
    assert distance["mean"] == pytest.approx(0.55)


def test_direction_macro_state_dedup_includes_scene_identity() -> None:
    """Local rollout/step identifiers may repeat across distinct scenes."""

    from aria_nbv.rollouts.inspection import candidate_direction_evidence

    common = {
        **_direction_fixture_rows()[0],
        "generation_cohort_id": "cohort-a",
        "root_relative_x_m": 1.0,
        "root_relative_y_m": 0.0,
    }
    rows = [
        {**common, "scene": scene, "rollout_row_id": 0, "step_row_id": 0, "candidate_row_id": index}
        for scene, index in (("scene-a", 0), ("scene-a", 1), ("scene-b", 2), ("scene-b", 3))
    ]
    density = candidate_direction_evidence(rows)["density_rows"]
    macro = next(
        row
        for row in density
        if row["aggregation_level"] == "cohort_macro"
        and row["population"] == "all"
        and row["azimuth_bin"] == 9
        and row["sin_elevation_bin"] == 3
    )
    assert macro["state_count"] == 2
    assert macro["candidate_direction_count"] == 4
    assert macro["total_count"] == 4
    assert macro["finite_count"] + macro["missing_count"] == 4


def test_support_macros_expose_candidate_and_macro_denominators_without_pooling() -> None:
    """Unequal fan-out and reused local ids retain truthful state/scene facets."""

    from aria_nbv.rollouts.inspection import (
        candidate_direction_evidence,
        candidate_motion_support_evidence,
        candidate_spatial_support_evidence,
        candidate_target_view_evidence,
    )

    common = {**_direction_fixture_rows()[0], "generation_cohort_id": "cohort-a"}
    rows = [
        {
            **common,
            "scene": "scene-a",
            "rollout_row_id": 0,
            "step_row_id": 0,
            "candidate_row_id": 0,
            "target_distance_m": 1.0,
        },
        {
            **common,
            "scene": "scene-a",
            "rollout_row_id": 0,
            "step_row_id": 0,
            "candidate_row_id": 1,
            "target_distance_m": None,
        },
        {
            **common,
            "scene": "scene-b",
            "rollout_row_id": 0,
            "step_row_id": 0,
            "candidate_row_id": 2,
            "root_relative_x_m": 0.0,
            "root_relative_y_m": 0.0,
            "root_relative_z_m": 0.0,
            "target_distance_m": 2.0,
        },
    ]

    spatial = next(
        row
        for row in candidate_spatial_support_evidence(rows)
        if row["aggregation_level"] == "cohort_macro"
        and row["population"] == "all"
        and row["metric"] == "decision_horizontal_radius_m"
    )
    assert spatial["state_count"] == 2
    assert spatial["scene_count"] == 2
    assert spatial["candidate_total_count"] == 3
    assert spatial["candidate_finite_count"] == 3
    assert spatial["candidate_missing_count"] == 0

    target = next(
        row
        for row in candidate_target_view_evidence(rows)
        if row["aggregation_level"] == "cohort_macro"
        and row["population"] == "all"
        and row["evidence"] == "target_distance"
    )
    assert target["state_count"] == 2
    assert target["scene_count"] == 2
    assert target["candidate_total_count"] == 3
    assert target["candidate_finite_count"] == 2
    assert target["candidate_missing_count"] == 1

    direction = next(
        row
        for row in candidate_direction_evidence(rows)["cap_rows"]
        if row["aggregation_level"] == "cohort_macro" and row["population"] == "all" and row["radius_deg"] == 30
    )
    assert direction["state_count"] == 2
    assert direction["scene_count"] == 2
    assert direction["total_count"] == 3
    assert direction["finite_count"] == 2
    assert direction["missing_count"] == 1

    motion = next(
        row
        for row in candidate_motion_support_evidence(rows)
        if row["aggregation_level"] == "cohort_macro"
        and row["population"] == "all"
        and row["metric"] == "path_min_clearance_m"
    )
    assert motion["state_count"] == 2
    assert motion["scene_count"] == 2
    assert motion["candidate_total_count"] == 3
    assert motion["candidate_finite_count"] == 0
    assert motion["candidate_missing_count"] == 3


def test_spatial_and_target_cohort_macros_count_two_states_in_one_scene() -> None:
    """Cohort macros count factual states independently of scene multiplicity."""

    from aria_nbv.rollouts.inspection import candidate_spatial_support_evidence, candidate_target_view_evidence

    common = {**_direction_fixture_rows()[0], "scene": "scene-a", "generation_cohort_id": "cohort-a"}
    rows = [
        {
            **common,
            "rollout_row_id": 0,
            "step_row_id": 0,
            "candidate_row_id": 0,
            "target_distance_m": 1.0,
        },
        {
            **common,
            "rollout_row_id": 1,
            "step_row_id": 1,
            "candidate_row_id": 1,
            "root_relative_x_m": 0.0,
            "root_relative_y_m": 1.0,
            "target_distance_m": 2.0,
        },
    ]

    spatial = next(
        row
        for row in candidate_spatial_support_evidence(rows)
        if row["aggregation_level"] == "cohort_macro"
        and row["population"] == "all"
        and row["metric"] == "decision_horizontal_radius_m"
    )
    target = next(
        row
        for row in candidate_target_view_evidence(rows)
        if row["aggregation_level"] == "cohort_macro"
        and row["population"] == "all"
        and row["evidence"] == "target_distance"
    )
    for summary in (spatial, target):
        assert summary["state_count"] == 2
        assert summary["defined_state_count"] == 2
        assert summary["scene_count"] == 1


def test_support_counts_remain_explicit_when_one_candidate_is_missing_in_one_state() -> None:
    """Support facets count the candidate shell separately from defined states."""

    from aria_nbv.rollouts.inspection import (
        candidate_direction_evidence,
        candidate_spatial_support_evidence,
        candidate_target_view_evidence,
    )

    common = {**_direction_fixture_rows()[0], "generation_cohort_id": "cohort-a"}
    rows = [
        {
            **common,
            "candidate_row_id": 0,
            "root_relative_x_m": 1.0,
            "root_relative_y_m": 0.0,
            "root_relative_z_m": 0.0,
            "target_distance_m": 1.0,
        },
        {
            **common,
            "candidate_row_id": 1,
            "root_relative_x_m": 0.0,
            "root_relative_y_m": 0.0,
            "root_relative_z_m": 0.0,
            "target_distance_m": None,
        },
    ]

    angular = next(
        row
        for row in candidate_direction_evidence(rows)["angular_support_rows"]
        if row["aggregation_level"] == "state" and row["population"] == "all"
    )
    cap = next(
        row
        for row in candidate_direction_evidence(rows)["cap_rows"]
        if row["aggregation_level"] == "state" and row["population"] == "all"
    )
    for row in (cap, angular):
        assert row["candidate_total_count"] == 2
        assert row["candidate_finite_count"] == 1
        assert row["candidate_missing_count"] == 1
        assert row["state_count"] == 1
        assert row["defined_state_count"] == 1

    spatial = next(
        row
        for row in candidate_spatial_support_evidence(rows)
        if row["aggregation_level"] == "cohort_macro"
        and row["population"] == "all"
        and row["metric"] == "decision_horizontal_radius_m"
    )
    target = next(
        row
        for row in candidate_target_view_evidence(rows)
        if row["aggregation_level"] == "cohort_macro"
        and row["population"] == "all"
        and row["evidence"] == "target_distance"
    )
    assert spatial["defined_state_count"] == 1
    assert target["defined_state_count"] == 1


def test_candidate_population_composition_keeps_incompatible_cohorts_faceted() -> None:
    """Family summaries retain exact generation cohorts instead of pooling them."""

    from aria_nbv.rollouts.inspection import candidate_population_evidence

    rows = [
        {**_direction_fixture_rows()[0], "generation_cohort_id": cohort, "candidate_row_id": index}
        for index, cohort in enumerate(("cohort-a", "cohort-b"))
    ]

    evidence = candidate_population_evidence(
        _reader_stub(),
        audit_reader=lambda _reader, *, row_callback: [row_callback(row) for row in rows],
    )
    composition = evidence["composition"]["position"]
    assert {row["generation_cohort_id"] for row in composition} == {"cohort-a", "cohort-b"}
    assert len(composition) == 2


def test_angular_covering_cohort_macro_aggregates_scene_values() -> None:
    """Angular macros aggregate covering radii as scene summaries."""

    from aria_nbv.rollouts.inspection import candidate_direction_evidence

    common = {**_direction_fixture_rows()[0], "generation_cohort_id": "cohort-a"}
    rows = [
        {**common, "scene": "scene-a", "rollout_row_id": 0, "root_relative_x_m": 1.0, "root_relative_y_m": 0.0},
        {**common, "scene": "scene-b", "rollout_row_id": 1, "root_relative_x_m": 1.0, "root_relative_y_m": 0.0},
        {**common, "scene": "scene-b", "rollout_row_id": 1, "root_relative_x_m": -1.0, "root_relative_y_m": 0.0},
    ]
    angular = candidate_direction_evidence(rows)["angular_support_rows"]
    macro = next(row for row in angular if row["aggregation_level"] == "cohort_macro" and row["population"] == "all")
    assert macro["covering_radius_deg"] == pytest.approx(135.0, abs=2.0)


def test_collision_cohort_macro_weights_state_rates_by_scene() -> None:
    """Collision rates use equal-state then equal-scene weighting."""

    from aria_nbv.rollouts.inspection import candidate_motion_support_evidence

    common = {
        **_direction_fixture_rows()[0],
        "generation_cohort_id": "cohort-a",
        "path_collision_applicable": True,
        "path_collision_evaluated": True,
    }
    rows = [
        {**common, "scene": "scene-a", "rollout_row_id": 0, "path_collision": False},
        {**common, "scene": "scene-a", "rollout_row_id": 1, "path_collision": True},
        {**common, "scene": "scene-b", "rollout_row_id": 2, "path_collision": True},
    ]
    collision = candidate_motion_support_evidence(rows)
    macro = next(
        row
        for row in collision
        if row["aggregation_level"] == "cohort_macro"
        and row["metric"] == "path_collision_rate"
        and row["population"] == "all"
    )
    assert macro["collision_rate"] == pytest.approx(0.75)


def test_target_view_and_motion_facets_preserve_cohort_population_and_macro_levels() -> None:
    """Target-view and motion diagnostics use the same state-to-cohort evidence grammar."""

    from aria_nbv.rollouts.inspection import candidate_motion_support_evidence, candidate_target_view_evidence

    rows = [{**_direction_fixture_rows()[0], "target_distance_m": 2.0, "generation_cohort_id": "cohort-a"}]
    target = candidate_target_view_evidence(rows)
    motion = candidate_motion_support_evidence(rows)
    for evidence in (target, motion):
        assert all(row["generation_cohort_id"] == "cohort-a" for row in evidence)
        assert {row["population"] for row in evidence} >= {"all", "actor_valid"}
        assert {row["aggregation_level"] for row in evidence} >= {"state", "scene_macro", "cohort_macro"}


def test_rollout_inspection_suspicious_queries_find_injected_anomalies(tmp_path: Path) -> None:
    """Suspicious-row predicates should find low fanout, missing labels, and motion outliers."""

    records = build_rollout_records(horizon=1, num_samples=6, seed=44)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    root = zarr.open_group(result.store_dir, mode="a")

    _zarr_array(root, "steps/num_valid_candidates")[0] = np.asarray(0, dtype=np.int32)
    actor_valid = np.asarray(_zarr_array(root, "candidates/actor_action_mask"), dtype=np.bool_).reshape(-1)
    first_valid = int(np.flatnonzero(actor_valid)[0])
    _zarr_array(root, "candidates/target_root_gain")[first_valid] = np.asarray(np.nan, dtype=np.float32)
    selected = np.asarray(_zarr_array(root, "candidates/selected_mask"), dtype=np.bool_).reshape(-1)
    selected_row = int(np.flatnonzero(selected)[0])
    _zarr_array(root, "candidate_diagnostics/motion_step_length_m")[selected_row] = np.asarray(99.0, dtype=np.float32)

    rows = suspicious_rollout_rows(
        RolloutZarrStoreReader(result.store_dir),
        config=RolloutSuspiciousQueryConfig(min_valid_candidates=2, max_step_distance_m=1.0),
    )
    kinds = {str(row["kind"]) for row in rows}

    assert "low_valid_fanout" in kinds
    assert "valid_candidate_missing_label" in kinds
    assert "selected_motion_outlier" in kinds


def test_rollout_step_objective_rows_expose_existing_objective_and_sampling_fields(tmp_path: Path) -> None:
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

    rows: list[dict[str, Any]] = []
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


def test_rollout_header_summary_requires_proven_reference_denominators(tmp_path: Path) -> None:
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

    overcovered = copy.deepcopy(payload)
    overcovered["manifest"]["source_coverage"]["reference_scene_count"] = 0
    overcovered["manifest"]["source_coverage"]["reference_source_row_count"] = 0
    rejected = rollout_header_summary(reader, manifest_payload=overcovered)
    assert rejected["reference_scene_covered"] is None
    assert rejected["reference_scene_fraction"] is None
    assert rejected["reference_source_rows_covered"] is None
    assert rejected["reference_source_row_fraction"] is None

    empty = copy.deepcopy(overcovered)
    empty["manifest"]["source_coverage"]["scene_counts"] = {}
    empty["manifest"]["source_coverage"]["num_source_rows"] = 0
    empty_rejected = rollout_header_summary(reader, manifest_payload=empty)
    assert empty_rejected["reference_scene_covered"] is None
    assert empty_rejected["reference_source_rows_covered"] is None
    assert empty_rejected["reference_coverage_reason"] is not None


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
    assert [row["raw_row_id"] for row in evidence["role_rows"]] == list(range(len(rows)))
    assert {row["evidence_status"] for row in evidence["role_rows"]} == {"included"}
    assert len(evidence["role_disposition_rows"]) == len(rows) * 3
    assert all("raw_row_id" in row for row in evidence["role_disposition_rows"])
    assert included["delta_look"]["role_treatments"]["oracle_lookahead"]["branch_schedule"] == "oracle_lookahead"

    alias_only = [{**rows[0], "policy": "unsupported", "branch_schedule": "unsupported", "rollout_recipe": "q_h"}]
    aliased = exact_policy_role_rows(alias_only)
    assert len(aliased) == 1
    assert aliased[0]["semantic_role"] is None
    rejected = oracle_headroom_evidence(alias_only)
    assert len(rejected["malformed_role_rows"]) == 1
    assert rejected["malformed_role_rows"][0]["exclusion_reason"] == "unsupported_role_identifier"
    assert all(row["excluded_count"] == 1 for row in rejected["summary_rows"])


def test_reader_policy_projection_excludes_incomplete_terminal_rollout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import aria_nbv.rollouts.inspection as inspection

    store = zarr.open_group(tmp_path / "headroom-reader.zarr", mode="w")

    def put(path: str, values: Any) -> None:
        store.create_array(path, data=np.asarray(values))

    put("rollouts/rollout_row_id", [0, 1, 2])
    put("rollouts/source_row_id", [0, 0, 0])
    put("rollouts/target_row_id", [0, 0, 0])
    put("rollouts/policy_id", [0, 0, 1])
    put("rollouts/termination_reason", [0, 1, 0])
    put("rollouts/horizon", [1, 1, 1])
    put("rollouts/branch_factor", [1, 1, 1])
    put("rollouts/beam_width", [1, 1, 1])
    put("rollouts/temperature", [np.nan, np.nan, np.nan])
    put("rollouts/random_seed", [-1, -1, -1])
    put("rollouts/chain_id", [0, 1, 2])
    put("rollouts/final_cumulative_target_rri", [1.0, 2.0, 3.0])
    put("rollouts/final_cumulative_target_root_gain", [1.0, 2.0, 3.0])
    put("sources/source_row_id", [0])
    put("sources/sample_key_id", [0])
    put("sources/sample_index", [0])
    put("targets/target_row_id", [0])
    put("targets/target_id", [0])
    for path in (
        "lineage/candidate_config_id",
        "lineage/oracle_config_id",
        "lineage/rollout_config_id",
        "lineage/target_protocol_version_id",
    ):
        put(path, [0, 0, 0])
    put("lineage/branch_schedule_id", [0, 1, 2])
    for name, values in {
        "policy": ["oracle_greedy", "q_h"],
        "source_key": ["sample-a"],
        "target": ["target-a"],
        "config": ["oracle_greedy", "oracle_lookahead", "q_h"],
        "termination_reason": ["completed", "incomplete_rollout"],
    }.items():
        payload = np.frombuffer(json.dumps(values).encode(), dtype=np.uint8)
        put(f"dictionaries/{name}", payload)

    monkeypatch.setattr(inspection, "rollout_at", lambda _reader, _index: SimpleNamespace(scene="scene-a"))
    reader = SimpleNamespace(
        root=store,
        array=lambda path: store[path],
        manifest=lambda: {
            "root_attrs": {"manifest_sha256": "manifest"},
            "manifest": {"generation": {"shard": {"writer_config_hash": "writer"}}},
        },
    )
    evidence = inspection.oracle_headroom_evidence(cast(RolloutZarrStoreReader, reader))
    delta_look = next(row for row in evidence["contrast_rows"] if row["contrast"] == "delta_look")
    assert delta_look["status"] == "excluded"
    assert delta_look["exclusion_reason"] == "incomplete_rollout:oracle_lookahead"
    assert all(
        row["eligible_count"] == row["included_count"] + row["excluded_count"] for row in evidence["summary_rows"]
    )


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


def test_oracle_headroom_malformed_identity_closes_exclusion_arithmetic() -> None:
    row = {
        "source_sample_key": None,
        "source_sample_index": 2,
        "target_id": "target-a",
        "target_protocol": "v1_observed",
        "horizon": 3,
        "acquisition_budget_steps": 3,
        "candidate_config": "candidate-hash",
        "oracle_config": "oracle-hash",
        "manifest_sha256": "manifest-hash",
        "writer_config_hash": "writer-hash",
        "campaign_id": "campaign",
        "plan_hash": "plan",
        "work_unit_hash": "unit",
        "profile_hash": "profile",
        "explicit_target_hash": "target-hash",
        "policy": "oracle_greedy",
        "branch_schedule": "oracle_greedy",
        "branch_factor": 1,
        "beam_width": 1,
        "rollout_recipe": "recipe",
        "final_cumulative_target_root_gain": 1.0,
        "scene": "scene-a",
        "temperature": np.nan,
        "random_seed": -1,
    }
    evidence = oracle_headroom_evidence([row, dict(row)])
    assert len(evidence["malformed_role_rows"]) == 2
    assert [item["raw_row_id"] for item in evidence["role_rows"]] == [0, 1]
    assert len(evidence["role_disposition_rows"]) == 6
    assert all(item["status"] == "excluded" for item in evidence["contrast_rows"])
    assert all(
        item["eligible_count"] == item["included_count"] + item["excluded_count"] for item in evidence["summary_rows"]
    )
    summaries = {item["contrast"]: item for item in evidence["summary_rows"]}
    assert summaries["delta_look"]["excluded_count"] == 2
    assert summaries["delta_Q"]["excluded_count"] == 0
    assert summaries["eta_Q"]["excluded_count"] == 0
    assert {
        item["status"] for item in evidence["role_disposition_rows"] if item["contrast"] in {"delta_Q", "eta_Q"}
    } == {"not_applicable"}

    partial_binding = oracle_headroom_evidence(
        [{**row, "source_sample_key": "sample-a", "campaign_id": "campaign", "plan_hash": None}]
    )
    assert partial_binding["role_rows"][0]["evidence_status"] == "excluded"
    assert "plan_hash" in str(partial_binding["role_rows"][0]["exclusion_reason"])


@pytest.mark.parametrize(
    ("policy", "schedule", "applicable_contrasts"),
    [
        ("oracle_greedy", "oracle_greedy", {"delta_look"}),
        ("oracle_greedy", "oracle_lookahead", {"delta_look", "eta_Q"}),
        ("learned_one_step", "learned_one_step", {"delta_Q", "eta_Q"}),
        ("q_h", "q_h", {"delta_Q", "eta_Q"}),
    ],
)
def test_headroom_role_ledger_conserves_valid_plus_malformed_near_duplicates(
    policy: str,
    schedule: str,
    applicable_contrasts: set[str],
) -> None:
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
        "branch_factor": 1,
        "beam_width": 1,
        "rollout_recipe": "recipe",
    }
    roles = (
        ("oracle_greedy", "oracle_greedy", 6.0),
        ("oracle_greedy", "oracle_lookahead", 10.0),
        ("learned_one_step", "learned_one_step", 4.0),
        ("q_h", "q_h", 7.0),
    )
    rows = [
        {
            **invariant,
            "policy": row_policy,
            "branch_schedule": row_schedule,
            "final_cumulative_target_root_gain": value,
        }
        for row_policy, row_schedule, value in roles
    ]
    malformed = next(row for row in rows if row["policy"] == policy and row["branch_schedule"] == schedule)
    evidence = oracle_headroom_evidence([*rows, {**malformed, "source_sample_key": None}])

    assert [row["raw_row_id"] for row in evidence["role_rows"]] == list(range(5))
    dispositions = evidence["role_disposition_rows"]
    keys = {(int(row["raw_row_id"]), str(row["contrast"])) for row in dispositions}
    assert len(dispositions) == 15
    assert len(keys) == 15
    malformed_dispositions = {str(row["contrast"]): row for row in dispositions if row["raw_row_id"] == 4}
    for contrast, row in malformed_dispositions.items():
        assert row["status"] == ("excluded" if contrast in applicable_contrasts else "not_applicable")


def test_candidate_evidence_preserves_cohorts_and_state_then_scene_macros() -> None:
    def row(
        candidate_row_id: int,
        *,
        cohort: str,
        scene: str,
        state: int,
        actor: bool,
        selected: bool,
        probability: float | None,
        mixture: str = "forward",
    ) -> dict[str, Any]:
        return {
            "candidate_row_id": candidate_row_id,
            "generation_cohort_id": cohort,
            "generation_cohort": f'{{"cohort":"{cohort}"}}',
            "scene": scene,
            "rollout_row_id": state,
            "step_row_id": state,
            "mixture": mixture,
            "actor_action": actor,
            "oracle_label": actor,
            "q_train": actor,
            "selected": selected,
            "sampler_probability": probability,
            "path_collision": False,
            "path_collision_applicable": True,
            "path_collision_evaluated": True,
            "path_min_clearance_m": 1.0,
        }

    rows = [
        row(0, cohort="a", scene="s1", state=0, actor=True, selected=True, probability=0.25),
        row(1, cohort="a", scene="s1", state=0, actor=True, selected=False, probability=0.25),
        row(2, cohort="a", scene="s1", state=1, actor=False, selected=False, probability=1 / 3),
        row(3, cohort="a", scene="s1", state=1, actor=False, selected=False, probability=1 / 3),
        row(4, cohort="a", scene="s2", state=2, actor=True, selected=True, probability=1.0),
        row(5, cohort="b", scene="s3", state=3, actor=False, selected=False, probability=1.0),
        row(6, cohort="a", scene="s1", state=0, actor=False, selected=False, probability=0.25, mixture="side"),
        row(7, cohort="a", scene="s1", state=0, actor=False, selected=False, probability=0.25, mixture="side"),
        row(8, cohort="a", scene="s1", state=1, actor=True, selected=False, probability=1 / 3, mixture="side"),
    ]

    composition = candidate_composition_rows(rows)
    assert {(candidate["generation_cohort_id"], candidate["family"]) for candidate in composition} == {
        ("a", "forward"),
        ("a", "side"),
        ("b", "forward"),
    }
    cohort_a = next(
        candidate
        for candidate in composition
        if candidate["generation_cohort_id"] == "a" and candidate["family"] == "forward"
    )
    assert cohort_a["allocated_count"] == 5
    assert cohort_a["actor_valid_count"] == 3
    assert cohort_a["macro_actor_valid_rate"] == pytest.approx(0.75)
    assert cohort_a["aggregation"] == "state_then_scene_macro"

    calibration = candidate_proposal_calibration_rows(rows)
    calibration_a = next(
        candidate
        for candidate in calibration
        if candidate["generation_cohort_id"] == "a" and candidate["family"] == "forward"
    )
    assert calibration_a["population_empirical_frequency"] == pytest.approx(5 / 8)
    assert calibration_a["population_proposal_mass"] == pytest.approx(13 / 18)
    assert calibration_a["empirical_frequency"] == pytest.approx(19 / 24)
    assert calibration_a["proposal_mass"] == pytest.approx(19 / 24)
    assert calibration_a["calibration_gap"] == pytest.approx(0.0)
    assert calibration_a["population_selected_share"] == pytest.approx(1.0)
    assert calibration_a["selected_share"] == pytest.approx(1.0)
    assert calibration_a["state_count"] == 3
    assert calibration_a["scene_count"] == 2
    calibration_side = next(
        candidate
        for candidate in calibration
        if candidate["generation_cohort_id"] == "a" and candidate["family"] == "side"
    )
    assert calibration_side["state_count"] == 3
    assert calibration_side["scene_count"] == 2
    assert calibration_side["empirical_frequency"] == pytest.approx(5 / 24)
    assert calibration_side["proposal_mass"] == pytest.approx(5 / 24)
    assert calibration_side["empirical_denominator"] == 8
    assert calibration_side["proposal_denominator"] == 8
    assert calibration_side["selected_denominator"] == 2
    malformed = [
        row(20, cohort="c", scene="s1", state=0, actor=True, selected=True, probability=0.5),
        row(21, cohort="c", scene="s1", state=0, actor=True, selected=False, probability=None, mixture="side"),
    ]
    malformed_side = next(
        candidate for candidate in candidate_proposal_calibration_rows(malformed) if candidate["family"] == "side"
    )
    assert malformed_side["population_proposal_mass"] is None
    assert malformed_side["proposal_mass"] is None
    assert malformed_side["calibration_gap"] is None

    collision = candidate_collision_support_rows(rows)[0]
    assert collision["available"] is True
    assert collision["collision_rate"] == pytest.approx(0.0)
    assert len(candidate_collision_support_rows(rows)) == 2
    assert collision["generation_cohort_id"] == "a"
    assert collision["candidate_count"] == 8
    unavailable = candidate_collision_support_rows(
        [
            {
                **rows[0],
                "path_collision": None,
                "path_collision_evaluated": False,
                "path_min_clearance_m": None,
            }
        ]
    )[0]
    assert unavailable["available"] is False
    assert unavailable["collision_rate"] is None
    not_applicable = candidate_collision_support_rows(
        [
            {
                **rows[0],
                "path_collision": None,
                "path_collision_applicable": False,
                "path_collision_evaluated": False,
                "path_min_clearance_m": None,
            }
        ]
    )[0]
    assert not_applicable["collision_not_applicable_count"] == 1
    assert not_applicable["collision_unavailable_count"] == 0

    unproved = candidate_collision_support_rows(
        [{key: value for key, value in rows[0].items() if key != "path_collision_evaluated"}]
    )[0]
    assert unproved["collision_evaluated_count"] == 0

    first = deterministic_candidate_display_sample(rows, max_rows=3)
    second = deterministic_candidate_display_sample(reversed(rows), max_rows=3)
    assert [item["candidate_row_id"] for item in first["rows"]] == [item["candidate_row_id"] for item in second["rows"]]
    assert first["population_count"] == 9
    assert first["display_count"] == 3
    assert first["display_only"] is True
    with pytest.raises(ValueError, match="Unsupported candidate group field"):
        candidate_composition_rows(rows, group_by=cast(Any, "unsupported"))


def test_candidate_population_evidence_is_compact_callback_parity_and_order_invariant() -> None:
    rows = [
        {
            "candidate_row_id": index,
            "generation_cohort_id": "cohort",
            "generation_cohort": "{}",
            "scene": "scene",
            "rollout_row_id": index // 2,
            "step_row_id": index // 2,
            "mixture": "forward" if index % 2 else "side",
            "position": "center",
            "strategy": "random",
            "invalid_reason": "none",
            "actor_action": index % 3 != 0,
            "oracle_label": index % 3 != 0,
            "q_train": index % 3 != 0,
            "selected": index == 1,
            "sampler_probability": 0.5,
            "target_root_gain": float(index),
            "path_collision": False,
            "path_collision_applicable": True,
            "path_collision_evaluated": True,
            "path_min_clearance_m": 1.0,
        }
        for index in range(8)
    ]

    class Poison:
        def __iter__(self) -> None:
            raise AssertionError("the callback producer result must not be materialized")

    calls = 0

    def producer(_reader: Any, *, row_callback: Any) -> Any:
        nonlocal calls
        calls += 1
        for row in rows:
            row_callback(row)
        return Poison()

    evidence = candidate_population_evidence(_reader_stub(), audit_reader=producer, sample_size=3)
    assert calls == 1
    assert evidence["population_count"] == len(rows)
    assert len(evidence["sample"]["rows"]) == 3
    assert evidence["composition"]["mixture"] == candidate_composition_rows(rows)
    assert evidence["calibration"]["mixture"] == candidate_proposal_calibration_rows(rows)
    assert evidence["collision"] == candidate_collision_support_rows(rows)
    assert evidence["groups"]["mixture"] == candidate_group_summary_rows(
        _reader_stub(), group_by="mixture", audit_rows=rows
    )

    reversed_evidence = candidate_population_evidence(
        _reader_stub(),
        audit_reader=lambda _reader, *, row_callback: [row_callback(row) for row in reversed(rows)],
        sample_size=3,
    )
    assert [row["candidate_row_id"] for row in evidence["sample"]["rows"]] == [
        row["candidate_row_id"] for row in reversed_evidence["sample"]["rows"]
    ]


@pytest.mark.parametrize(
    ("probabilities", "reason"),
    [
        ([None, 0.5], "incomplete_probability_vector"),
        ([np.nan, 0.5], "incomplete_probability_vector"),
        ([np.inf, 0.5], "incomplete_probability_vector"),
        ([-0.1, 1.1], "negative_probability"),
        ([0.4, 0.4], "probability_not_normalized"),
        ([0.0, 0.0], "nonpositive_probability_sum"),
    ],
)
def test_candidate_population_probability_vectors_fail_closed(probabilities: list[float | None], reason: str) -> None:
    rows = [
        {
            "candidate_row_id": index,
            "generation_cohort_id": "cohort",
            "generation_cohort": "{}",
            "scene": "scene",
            "rollout_row_id": 1,
            "step_row_id": 1,
            "mixture": "forward",
            "position": "center",
            "strategy": "random",
            "invalid_reason": "none",
            "actor_action": True,
            "oracle_label": True,
            "q_train": True,
            "selected": index == 0,
            "sampler_probability": probability,
            "target_root_gain": 0.1,
            "path_collision": False,
            "path_collision_applicable": True,
            "path_collision_evaluated": True,
            "path_min_clearance_m": 1.0,
        }
        for index, probability in enumerate(probabilities)
    ]

    evidence = candidate_population_evidence(
        _reader_stub(),
        audit_reader=lambda _reader, *, row_callback: [row_callback(row) for row in rows],
    )
    calibration = evidence["calibration"]["mixture"][0]
    assert calibration["proposal_available"] is False
    assert reason in str(calibration["proposal_unavailable_reason"])
    assert calibration["population_proposal_mass"] is None
    assert calibration["proposal_mass"] is None


def test_candidate_population_mixed_state_probability_error_closes_macro() -> None:
    rows = [
        {
            "candidate_row_id": index,
            "generation_cohort_id": "cohort",
            "generation_cohort": "{}",
            "scene": "scene",
            "rollout_row_id": index // 2,
            "step_row_id": index // 2,
            "mixture": "forward",
            "actor_action": True,
            "oracle_label": True,
            "q_train": True,
            "selected": index == 0,
            "sampler_probability": probability,
            "path_collision": False,
            "path_collision_applicable": True,
            "path_collision_evaluated": True,
            "path_min_clearance_m": 1.0,
        }
        for index, probability in enumerate((0.5, 0.5, 0.8, 0.8))
    ]

    row = candidate_population_evidence(_reader_stub(), audit_reader=lambda _reader: rows)["calibration"]["mixture"][0]

    assert row["proposal_available"] is False
    assert row["population_proposal_mass"] is None
    assert row["proposal_mass"] is None
    assert row["calibration_gap"] is None


def test_public_candidate_calibration_rejects_non_normalized_state_probability() -> None:
    rows = [
        {
            "candidate_row_id": index,
            "generation_cohort_id": "cohort",
            "generation_cohort": "{}",
            "scene": "scene",
            "rollout_row_id": 1,
            "step_row_id": 1,
            "mixture": "forward",
            "actor_action": True,
            "oracle_label": True,
            "q_train": True,
            "selected": index == 0,
            "sampler_probability": 0.8,
        }
        for index in range(2)
    ]

    calibration = candidate_proposal_calibration_rows(rows)[0]

    assert calibration["proposal_available"] is False
    assert "probability_not_normalized" in str(calibration["proposal_unavailable_reason"])
    assert calibration["population_proposal_mass"] is None
    assert calibration["proposal_mass"] is None


def test_headroom_condition_applicability_fails_closed_only_when_applicable() -> None:
    common = {
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
        "campaign_id": "campaign",
        "plan_hash": "plan",
        "work_unit_hash": "unit",
        "profile_hash": "profile",
        "explicit_target_hash": "target-hash",
        "branch_factor": 1,
        "beam_width": 1,
        "rollout_recipe": "oracle",
        "final_cumulative_target_root_gain": 1.0,
        "temperature": np.nan,
        "random_seed": -1,
    }
    rows = [
        {
            **common,
            "policy": "oracle_greedy",
            "branch_schedule": "oracle_greedy",
            "temperature_applicable": False,
            "random_seed_applicable": False,
        },
        {
            **common,
            "policy": "oracle_greedy",
            "branch_schedule": "oracle_lookahead",
            "temperature_applicable": True,
            "random_seed_applicable": False,
        },
    ]
    evidence = oracle_headroom_evidence(rows)
    assert evidence["contrast_rows"][0]["status"] == "excluded"
    assert evidence["contrast_rows"][0]["exclusion_reason"] == "unsupported_semantics"


class _NarrowCandidateFlowReader:
    """Fail-closed reader that exposes only the approved categorical flow surface."""

    def __init__(self) -> None:
        self.requested: list[str] = []
        self._arrays: dict[str, np.ndarray] = {
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
        return np.asarray(self._arrays[path])

    def manifest(self) -> dict[str, Any]:
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
    rows = candidate_flow_rows(cast(RolloutZarrStoreReader, reader))

    assert rows == candidate_flow_rows(cast(RolloutZarrStoreReader, _NarrowCandidateFlowReader()))
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
        cast(RolloutZarrStoreReader, _NarrowCandidateFlowReader()),
        policies=("softmax",),
        step_indices=(1,),
    )

    assert {row["root_denominator"] for row in rows} == {2}
    assert {row["store_candidate_count"] for row in rows} == {6}
    assert sum(row["count"] for row in rows if row["source_stage"] == "root") == 2
    assert not any(row["target_label"] == "selection_contract_violation" for row in rows)


def test_rollout_tree_summary_rows_group_selected_branch_provenance(tmp_path: Path) -> None:
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


def test_selected_depth_summary_rows_are_bounded_and_join_step_context(tmp_path: Path) -> None:
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


def test_selected_depth_summary_rows_report_disabled_store_without_dense_scan(tmp_path: Path) -> None:
    """Disabled selected-depth stores should expose explicit unavailable rows."""

    records = build_rollout_records(horizon=1, num_samples=6, seed=48)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records, selected_depth_enabled=False)
    reader = RolloutZarrStoreReader(result.store_dir)

    rows = selected_depth_summary_rows(reader)

    assert len(rows) == result.num_steps
    assert rows[0]["available"] is False
    assert rows[0]["valid_fraction"] is None
    assert "selected_depth_enabled=false" in str(rows[0]["warning"])


def test_selected_depth_preview_returns_one_bounded_image_payload(tmp_path: Path) -> None:
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


def test_mask_combinations_preserve_selected_rows_outside_q_train(tmp_path: Path) -> None:
    """Selection is an actor decision, not a sequential stage after the training mask."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=50)[:1],
    )
    root = zarr.open_group(result.store_dir, mode="a")
    selected_row = int(np.flatnonzero(np.asarray(_zarr_array(root, "candidates/selected_mask"), dtype=np.bool_))[0])
    _zarr_array(root, "candidates/q_train_mask")[selected_row] = np.asarray(False, dtype=np.bool_)

    rows = mask_combination_rows(RolloutZarrStoreReader(result.store_dir))
    selected_without_training = next(row for row in rows if row["selected"] is True and row["q_train"] is False)

    assert selected_without_training["actor_action"] is True
    assert selected_without_training["count"] == 1
    assert selected_without_training["contract_valid"] is True
    assert selected_without_training["denominator"] == result.num_candidates
    assert selected_without_training["fraction_of_all"] == pytest.approx(1.0 / result.num_candidates)


def test_store_invariants_expose_mask_depth_target_and_q_h_contracts(tmp_path: Path) -> None:
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


def test_store_invariants_fail_selected_actor_mask_without_reclassifying_q_train(tmp_path: Path) -> None:
    """A selected invalid action is a violation, while selected-not-q-train remains allowed."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=52)[:1],
    )
    root = zarr.open_group(result.store_dir, mode="a")
    selected_row = int(np.flatnonzero(np.asarray(_zarr_array(root, "candidates/selected_mask"), dtype=np.bool_))[0])
    _zarr_array(root, "candidates/actor_action_mask")[selected_row] = np.asarray(False, dtype=np.bool_)
    _zarr_array(root, "candidates/q_train_mask")[selected_row] = np.asarray(False, dtype=np.bool_)

    by_id = {str(row["invariant_id"]): row for row in store_invariant_rows(RolloutZarrStoreReader(result.store_dir))}

    assert by_id["selected_actor_mask"]["status"] == "FAIL"
    assert by_id["selected_actor_mask"]["violation_count"] == 1
    assert by_id["q_train_supervision"]["status"] == "PASS"


def test_comparable_policy_cohorts_gate_on_exact_scientific_keys(tmp_path: Path) -> None:
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


def test_paired_policy_comparison_rows_are_deterministic_and_paired(tmp_path: Path) -> None:
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


def test_selected_candidate_rank_rows_keep_negative_rewards_distinct_from_invalidity(tmp_path: Path) -> None:
    """Regret ranks finite valid rewards even when the selected reward is negative."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=8, seed=58)[:1],
    )
    root = zarr.open_group(result.store_dir, mode="a")
    selected_row = int(np.flatnonzero(np.asarray(_zarr_array(root, "candidates/selected_mask"), dtype=np.bool_))[0])
    valid_rows = np.flatnonzero(np.asarray(_zarr_array(root, "candidates/actor_action_mask"), dtype=np.bool_))
    alternative_row = int(next(row for row in valid_rows.tolist() if row != selected_row))
    _zarr_array(root, "candidates/target_root_gain")[selected_row] = np.asarray(-0.25, dtype=np.float32)
    _zarr_array(root, "candidates/target_root_gain")[alternative_row] = np.asarray(0.75, dtype=np.float32)
    _zarr_array(root, "candidates/target_rri")[selected_row] = np.asarray(-0.5, dtype=np.float32)
    _zarr_array(root, "candidates/target_rri")[alternative_row] = np.asarray(0.5, dtype=np.float32)

    row = selected_candidate_rank_rows(RolloutZarrStoreReader(result.store_dir))[0]

    assert row["selected_actor_valid"] is True
    assert row["selected_reward_negative"] is True
    assert row["selected_rank"] > 1
    assert row["target_rri_rank"] > 1
    assert float(row["best_valid_target_root_gain"]) >= 0.75
    assert row["regret_to_best"] == pytest.approx(
        float(row["best_valid_target_root_gain"]) - float(row["selected_target_root_gain"])
    )


def test_selected_candidate_rank_rows_expose_softmax_policy_and_exact_rri_rank(tmp_path: Path) -> None:
    """Selected-step evidence should distinguish policy mechanics from target-RRI rank."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=8, seed=61),
    )
    reader = RolloutZarrStoreReader(result.store_dir)
    softmax = next(row for row in selected_candidate_rank_rows(reader) if row["policy"] == "temperature_softmax")
    root = zarr.open_group(result.store_dir, mode="a")
    step_ids = np.asarray(_zarr_array(root, "candidates/step_row_id"), dtype=np.int64)
    actor_valid = np.asarray(_zarr_array(root, "candidates/actor_action_mask"), dtype=np.bool_)
    selected = np.asarray(_zarr_array(root, "candidates/selected_mask"), dtype=np.bool_)
    step_rows = np.flatnonzero((step_ids == int(softmax["step_row_id"])) & actor_valid)
    selected_row = int(np.flatnonzero((step_ids == int(softmax["step_row_id"])) & selected)[0])
    alternatives = [int(row) for row in step_rows.tolist() if int(row) != selected_row]
    assert len(alternatives) >= 3

    _zarr_array(root, "candidates/target_rri")[step_rows] = np.asarray(0.0, dtype=np.float32)
    _zarr_array(root, "candidates/selection_logits")[step_rows] = np.asarray(-1.0, dtype=np.float32)
    _zarr_array(root, "candidates/target_rri")[selected_row] = np.asarray(1.0, dtype=np.float32)
    _zarr_array(root, "candidates/selection_logits")[selected_row] = np.asarray(1.0, dtype=np.float32)
    for value, row in zip((3.0, 2.0), alternatives[:2], strict=True):
        _zarr_array(root, "candidates/target_rri")[row] = np.asarray(value, dtype=np.float32)
        _zarr_array(root, "candidates/selection_logits")[row] = np.asarray(value, dtype=np.float32)
    _zarr_array(root, "candidates/target_rri")[alternatives[2]] = np.asarray(1.0, dtype=np.float32)
    _zarr_array(root, "candidates/selection_logits")[alternatives[2]] = np.asarray(1.0, dtype=np.float32)

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


def test_selected_candidate_rank_rows_mark_all_invalid_or_missing_rri_unavailable(tmp_path: Path) -> None:
    """Invalid shells and missing selected RRI must not receive synthetic ranks."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=62)[:1],
    )
    root = zarr.open_group(result.store_dir, mode="a")
    step_row_id = int(np.asarray(_zarr_array(root, "steps/step_row_id"), dtype=np.int64)[0])
    step_rows = np.flatnonzero(np.asarray(_zarr_array(root, "candidates/step_row_id"), dtype=np.int64) == step_row_id)
    _zarr_array(root, "candidates/actor_action_mask")[step_rows] = np.asarray(False, dtype=np.bool_)
    selected_row = int(np.flatnonzero(np.asarray(_zarr_array(root, "candidates/selected_mask"), dtype=np.bool_))[0])
    _zarr_array(root, "candidates/target_rri")[selected_row] = np.asarray(np.nan, dtype=np.float32)

    row = selected_candidate_rank_rows(RolloutZarrStoreReader(result.store_dir))[0]

    assert row["selected_actor_valid"] is False
    assert row["target_rri_rank"] is None
    assert row["selection_score_rank"] is None
    assert row["rank_denominator"] == 0
    assert row["target_rri_rank_label"] == "unavailable"


def test_root_relative_candidate_rows_use_root_centered_z_up_world_metres(tmp_path: Path) -> None:
    """Geometry projection should never expose cross-scene absolute centers as comparison axes."""

    records = build_rollout_records(horizon=1, num_samples=6, seed=59)[:1]
    root_tensor = _pose_tensor(records[0].evaluated.result.root_pose_world).clone()
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


def test_failure_triage_emits_exact_mask_violation_rows(tmp_path: Path) -> None:
    """Hard mask violations should carry exact rollout, step, and candidate identifiers."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=60)[:1],
    )
    root = zarr.open_group(result.store_dir, mode="a")
    selected_row = int(np.flatnonzero(np.asarray(_zarr_array(root, "candidates/selected_mask"), dtype=np.bool_))[0])
    _zarr_array(root, "candidates/actor_action_mask")[selected_row] = np.asarray(False, dtype=np.bool_)
    _zarr_array(root, "candidates/q_train_mask")[selected_row] = np.asarray(False, dtype=np.bool_)

    failures = suspicious_rollout_rows(RolloutZarrStoreReader(result.store_dir))
    violation = next(row for row in failures if row["kind"] == "selected_actor_mask_violation")

    assert violation["severity"] == "error"
    assert violation["rollout_row_id"] == 0
    assert violation["step_row_id"] == 0
    persisted_candidate_id = np.asarray(_zarr_array(root, "candidates/candidate_row_id")[selected_row]).item()
    assert violation["candidate_row_id"] == int(persisted_candidate_id)
