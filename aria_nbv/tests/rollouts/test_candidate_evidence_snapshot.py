"""Canonical live/stored candidate evidence and plot-model contracts."""

from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import plotly.io as pio
import pytest
import torch
import zarr
from efm3d.aria import CameraTW
from efm3d.aria.pose import PoseTW

from aria_nbv.pose_generation.candidate_interface import (
    ActionOrderRevision,
    AdmissionEvidence,
    CandidateCompletion,
    CandidateMeasurements,
    CandidateSet,
    CandidateTable,
    CriterionEvidence,
    CriterionLocalEvidence,
    CriterionReasonRevision,
    CriterionSourceRoleRevision,
    EvidenceAvailability,
)
from aria_nbv.pose_generation.candidate_program import CompletionMode
from aria_nbv.pose_generation.sampling_keys import CandidateSubstreamRevision
from aria_nbv.rollouts.candidate_evidence import (
    _candidate_evidence_snapshot_from_complete_stored,
    _CompleteStoredCandidateTransport,
)
from aria_nbv.rollouts.candidate_plotting import candidate_support_plot_models
from aria_nbv.rollouts.inspection import (
    CandidateEvidenceSnapshot,
    CandidateFactAvailability,
    CandidateProjectionUnavailableReason,
    CandidateRolloutOverlay,
    candidate_evidence_snapshot_from_live,
    candidate_evidence_snapshot_from_stored,
)
from aria_nbv.rollouts.read_model import rollout_at, rollout_steps, target_rows
from aria_nbv.rollouts.zarr_store import RolloutZarrStoreReader, write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records


def _pose_table(centers: torch.Tensor) -> PoseTW:
    rotation = torch.eye(3).expand(centers.shape[0], 3, 3).clone()
    return PoseTW.from_Rt(rotation, centers)


def _camera_table(count: int) -> CameraTW:
    camera = CameraTW.from_surreal(
        width=torch.tensor([64.0]),
        height=torch.tensor([64.0]),
        type_str="Pinhole",
        params=torch.tensor([[60.0, 60.0, 32.0, 32.0]]),
        gain=torch.zeros(1),
        exposure_s=torch.zeros(1),
        valid_radius=torch.tensor([64.0]),
        T_camera_rig=PoseTW.from_matrix3x4(torch.eye(3, 4).unsqueeze(0)),
    )
    return CameraTW(camera.tensor().expand(count, -1).clone())


def _candidate_set() -> CandidateSet:
    centers = torch.tensor([[0.5, 2.0, 0.0], [-0.5, 2.0, 0.25], [0.0, 1.0, 0.0]])
    gaze = torch.tensor([[0.0, 0.0, 1.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]])
    count = centers.shape[0]
    local = CriterionLocalEvidence(
        applicable=torch.ones(count, dtype=torch.bool),
        evaluated=torch.ones(count, dtype=torch.bool),
        passed=torch.tensor([True, False, True]),
        reason_code=torch.tensor([0, 2, 0], dtype=torch.int64),
        margin=torch.tensor([0.5, -0.25, 0.1]),
        source_role=torch.ones(count, dtype=torch.int64),
    )
    admission = AdmissionEvidence(
        mask_valid=torch.tensor([True, False, True]),
        criteria=(
            CriterionEvidence(
                criterion_id="max_step_distance",
                legacy_cumulative_valid=torch.tensor([True, False, True]),
                local=local,
                local_availability=torch.ones(count, dtype=torch.bool),
                reason_revision=CriterionReasonRevision.CANDIDATE_ADMISSION_V1,
                source_role_revision=CriterionSourceRoleRevision.CANDIDATE_ADMISSION_V1,
            ),
        ),
    )
    table = CandidateTable(
        world_poses=_pose_table(centers),
        centers_world=centers,
        gaze_directions_world=gaze,
        reference_pose_world=PoseTW.from_Rt(torch.eye(3), torch.zeros(3)),
        sampling_pose_world=None,
        camera_calibration=_camera_table(count),
        shell_offsets_ref=centers.clone(),
        semantic_group_id=("bearing", "bearing", "orbit"),
        center_family_id=("target_bearing_local", "target_bearing_local", "target_orbit"),
        gaze_family_id=("target_glance", "target_glance", "target_exact"),
        candidate_family_id=("bearing/glance", "bearing/glance", "orbit/exact"),
        center_id=torch.tensor([0, 1, 2], dtype=torch.int64),
        position_pair_id=torch.tensor([0, 1, 2], dtype=torch.int64),
        gaze_variant_id=torch.tensor([0, 0, 0], dtype=torch.int64),
        attempt_round_id=torch.zeros(count, dtype=torch.int64),
        draw_id=torch.tensor([0, 1, 0], dtype=torch.int64),
        proposal_key=("bearing:0", "bearing:1", "orbit:0"),
        proposal_probability=torch.full((count,), 1.0 / count),
        view_residual_yaw_deg=torch.tensor([12.0, -8.0, 25.0]),
        view_residual_pitch_deg=torch.tensor([5.0, -3.0, 10.0]),
        view_jitter_is_bounded=torch.tensor([True, True, False]),
        view_jitter_azimuth_limit_deg=torch.tensor([60.0, 60.0, 0.0]),
        view_jitter_elevation_limit_deg=torch.tensor([30.0, 30.0, 0.0]),
        target_anchor_world=torch.tensor([[0.0, 2.0, 0.0]]).expand(count, 3).clone(),
        target_frame_identity=("", "", "generation-orbit-frame"),
        target_frame_availability=(
            EvidenceAvailability.UNAVAILABLE,
            EvidenceAvailability.UNAVAILABLE,
            EvidenceAvailability.AVAILABLE,
        ),
        measurements=CandidateMeasurements(),
    )
    return CandidateSet(
        attempts=table,
        admission=admission,
        action_indices=torch.tensor([0, 2], dtype=torch.int64),
        completion=CandidateCompletion(CompletionMode.FIXED_ATTEMPTS, count, 2),
        candidate_program_hash="program-hash",
        request_binding_hash="request-hash",
        candidate_substream_revision=CandidateSubstreamRevision.SHIPPED_V1,
        action_order_revision=ActionOrderRevision.ORDERED_HARD_VALID_V1,
    )


def _candidate_set_with_nonfinite_attempt() -> CandidateSet:
    candidate_set = _candidate_set()
    poses = candidate_set.attempts.world_poses.tensor().clone()
    poses[1, 0] = torch.nan
    attempts = replace(
        candidate_set.attempts,
        world_poses=PoseTW(poses),
    )
    return replace(candidate_set, attempts=attempts)


def test_live_and_stored_adapters_are_exactly_equivalent_without_reacquisition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_set = _candidate_set()
    overlay = CandidateRolloutOverlay(horizon=8, factual_step=2, remaining_budget=6, history_coverage=2)
    live = candidate_evidence_snapshot_from_live(
        candidate_set,
        selected_attempt_indices=(2,),
        state_key="rollout:1/step:2",
        overlay=overlay,
        execution_hash="execution-hash",
    )

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=3, seed=7)[:1],
    )
    reader = RolloutZarrStoreReader(result.store_dir)
    rollout = rollout_at(reader, 0)
    step = rollout_steps(reader, rollout)[0]
    target = next(value for value in target_rows(reader) if value.target_row_id == rollout.target_row_id)
    pose_values = candidate_set.attempts.world_poses.tensor().detach().cpu().numpy()
    candidate_fields = (
        "candidate_row_positions",
        "candidate_row_ids",
        "shell_indices",
        "target_rri",
        "target_root_gain",
        "scene_rri",
        "selection_probabilities",
        "mixture_ids",
        "gaze_variant_ids",
        "position_pair_ids",
        "sampler_probabilities",
        "position_ids",
        "position_names",
        "invalid_reason_bitsets",
        "primary_invalid_reason_ids",
        "primary_invalid_reason_names",
        "mesh_distance_m",
        "path_min_clearance_m",
        "motion_step_length_m",
        "target_distance_m",
    )
    sliced = {name: getattr(step, name)[:3] for name in candidate_fields}
    for name in (
        "view_jitter_yaw_deg",
        "view_jitter_pitch_deg",
        "view_jitter_azimuth_limit_deg",
        "view_jitter_elevation_limit_deg",
        "view_jitter_is_bounded",
    ):
        value = getattr(step, name)
        sliced[name] = None if value is None else value[:3]
    step = replace(
        step,
        **sliced,
        num_candidates=3,
        num_valid_candidates=2,
        pose_world_cam=pose_values,
        compact_valid_indices=torch.tensor([0, -1, 1], dtype=torch.int32).numpy(),
        actor_action_mask=torch.tensor([True, False, True]).numpy(),
        selected_mask=torch.tensor([False, False, True]).numpy(),
        selected_local_index=2,
        selected_candidate_row_id=int(sliced["candidate_row_ids"][2]),
        mixture_names=torch.tensor([0, 0, 0]).numpy().astype(str),
    )
    rollout = replace(rollout, root_pose_world=candidate_set.attempts.reference_pose_world.tensor().numpy(), horizon=8)
    target = replace(target, center_world=torch.tensor([0.0, 2.0, 0.0]).numpy())

    def fail_reacquire(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("inspection adapters cannot reacquire geometry")

    monkeypatch.setattr("aria_nbv.geometry.PreparedMeshQuery.acquire", fail_reacquire)
    stored = candidate_evidence_snapshot_from_stored(rollout, step, target)

    assert type(live) is CandidateEvidenceSnapshot
    assert type(stored) is CandidateEvidenceSnapshot
    assert torch.allclose(
        torch.tensor([row.center_target_normalized for row in stored.rows]),
        torch.tensor([row.center_target_normalized for row in live.rows]),
    )
    assert torch.allclose(
        torch.tensor([row.gaze_target_unit for row in stored.rows]),
        torch.tensor([row.gaze_target_unit for row in live.rows]),
    )
    assert tuple(row.hard_valid for row in stored.rows) == tuple(row.hard_valid for row in live.rows)
    assert tuple(row.action for row in stored.rows) == tuple(row.action for row in live.rows)
    assert tuple(row.selected for row in stored.rows) == tuple(row.selected for row in live.rows)
    assert all(row.semantic_lineage_availability is CandidateFactAvailability.LEGACY_MISSING for row in stored.rows)


def test_direct_snapshot_keeps_selection_and_rollout_context_unavailable() -> None:
    snapshot = candidate_evidence_snapshot_from_live(_candidate_set())
    models = candidate_support_plot_models((snapshot,))

    assert snapshot.selected_count is None
    assert all(row.selected is None for row in snapshot.rows)
    assert snapshot.overlay == CandidateRolloutOverlay.unavailable()
    assert all("H/t/budget unavailable" in model.title for model in models)
    survival = models[2].build_figure()
    assert "selected" not in {str(value) for trace in survival.data for value in trace.x}


def test_contract_complete_stored_transport_matches_live_snapshot_and_plots() -> None:
    live = candidate_evidence_snapshot_from_live(
        _candidate_set(),
        selected_attempt_indices=(2,),
        state_key="rollout:1/step:2",
        overlay=CandidateRolloutOverlay(8, 2, 6, 2),
        execution_hash="execution-hash",
    )
    stored = _candidate_evidence_snapshot_from_complete_stored(
        _CompleteStoredCandidateTransport(
            canonical_json=json.dumps(
                asdict(live),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        )
    )

    assert stored == live
    assert candidate_support_plot_models((stored,)) == candidate_support_plot_models((live,))


def test_plot_models_retain_statuses_rotated_frame_horizon_and_jitter_support() -> None:
    snapshot = candidate_evidence_snapshot_from_live(
        _candidate_set(),
        selected_attempt_indices=(2,),
        state_key="rollout:1/step:2",
        overlay=CandidateRolloutOverlay(8, 2, 6, 2),
    )
    ground, support, survival, jitter = candidate_support_plot_models((snapshot,))

    assert all("H=8, t=2, remaining=6" in model.title for model in (ground, support, survival, jitter))
    assert snapshot.rows[0].center_target_normalized == pytest.approx((1.0, -0.25, 0.0))
    assert snapshot.target_target_normalized == pytest.approx((1.0, 0.0, 0.0))
    ground_figure = ground.build_figure()
    statuses = {str(value) for trace in ground_figure.data for value in (trace.name or "").split(", ")}
    assert any("invalid" in value for value in statuses)
    assert any("action" in value for value in statuses)
    assert any("selected" in value for value in statuses)
    support_figure = support.build_figure()
    support_trace_names = {str(trace.name) for trace in support_figure.data}
    assert any("bearing/glance" in name and "action" in name for name in support_trace_names)
    assert any("bearing/glance" in name and "invalid" in name for name in support_trace_names)
    assert any("orbit/exact" in name and "selected" in name for name in support_trace_names)
    assert all(model.build_figure().layout.title.x == 0.5 for model in (ground, support, survival, jitter))
    jitter_figure = jitter.build_figure()
    assert len(jitter_figure.layout.shapes) == 1
    assert jitter_figure.layout.shapes[0].line.dash == "dot"
    assert list(jitter_figure.layout.xaxis.range) == [-180, 180]
    assert list(jitter_figure.layout.yaxis.range) == [-90, 90]
    assert any(annotation.text == "uncapped spherical support" for annotation in jitter_figure.layout.annotations)


def test_candidate_plot_static_export_bytes_are_canonical_and_stable() -> None:
    snapshot = candidate_evidence_snapshot_from_live(
        _candidate_set(), selected_attempt_indices=(2,), state_key="state", overlay=CandidateRolloutOverlay(8, 2, 6)
    )
    previous_template = pio.templates.default
    try:
        pio.templates.default = "plotly_dark"
        payloads = tuple(model.plotly_json for model in candidate_support_plot_models((snapshot,)))
        pio.templates.default = "plotly_white"
        assert payloads == tuple(model.plotly_json for model in candidate_support_plot_models((snapshot,)))
    finally:
        pio.templates.default = previous_template

    assert all(isinstance(json.loads(payload), dict) for payload in payloads)
    assert tuple(hashlib.sha256(payload).hexdigest() for payload in payloads) == (
        "950a1dee3e9653313b93c12c53eee836b6ea28881dd1bbe366b471f5b916da0f",
        "025a9db61cc363c1795946a815b1c6b3b28e767a900ff39c694b512dec9ff5b0",
        "27118664cc8301a9d7a55d55dddf32ed405d7847f89e64460f6c81eb7f956379",
        "3154a08cf1fbd9cb71ef7c273d26bf4d81068acde686d666f5576dfbaa75f3cb",
    )


def test_candidate_plot_report_identity_binds_rendering_options() -> None:
    candidate_set = _candidate_set()
    gaze = candidate_set.attempts.gaze_directions_world.clone()
    gaze[0] = torch.tensor([1.0, 0.0, 0.0])
    candidate_set = replace(candidate_set, attempts=replace(candidate_set.attempts, gaze_directions_world=gaze))
    snapshot = candidate_evidence_snapshot_from_live(candidate_set, selected_attempt_indices=(2,), state_key="state")

    without_directions = candidate_support_plot_models((snapshot,), show_view_directions=False)
    without_directions_again = candidate_support_plot_models((snapshot,), show_view_directions=False)
    with_directions = candidate_support_plot_models((snapshot,), show_view_directions=True)

    assert without_directions == without_directions_again
    assert tuple(model.figure.id for model in without_directions) != tuple(model.figure.id for model in with_directions)


def test_phase_a_selection_count_is_not_silently_promoted_to_factual_selection() -> None:
    direct = candidate_evidence_snapshot_from_live(_candidate_set())

    assert direct.action_count == 2
    assert direct.selected_count is None
    assert all(row.selection_availability is CandidateFactAvailability.UNAVAILABLE for row in direct.rows)


def test_snapshot_projection_and_availability_pairs_fail_closed() -> None:
    snapshot = candidate_evidence_snapshot_from_live(_candidate_set())

    with pytest.raises(ValueError, match="available projection requires"):
        replace(snapshot, projection_frame_identity=None)
    with pytest.raises(ValueError, match="action availability"):
        replace(snapshot.rows[0], action=None)

    rows_without_projection = tuple(
        replace(
            row,
            center_target_normalized=None,
            gaze_target_unit=None,
            projection_availability=CandidateFactAvailability.UNAVAILABLE,
            projection_unavailable_reason=CandidateProjectionUnavailableReason.TARGET_MISSING,
        )
        for row in snapshot.rows
    )
    unavailable = replace(
        snapshot,
        rows=rows_without_projection,
        projection_frame_identity=None,
        target_target_normalized=None,
        projection_frame_availability=CandidateFactAvailability.UNAVAILABLE,
        projection_unavailable_reason=CandidateProjectionUnavailableReason.TARGET_MISSING,
    )
    assert unavailable.projection_unavailable_reason is CandidateProjectionUnavailableReason.TARGET_MISSING
    legacy_missing = replace(
        unavailable,
        rows=tuple(
            replace(
                row,
                projection_availability=CandidateFactAvailability.LEGACY_MISSING,
                projection_unavailable_reason=None,
            )
            for row in unavailable.rows
        ),
        projection_frame_availability=CandidateFactAvailability.LEGACY_MISSING,
        projection_unavailable_reason=None,
    )
    assert legacy_missing.projection_frame_identity is None


def test_live_projection_marks_degenerate_target_bearing_unavailable() -> None:
    candidate_set = _candidate_set()
    attempts = replace(
        candidate_set.attempts,
        target_anchor_world=torch.zeros_like(candidate_set.attempts.target_anchor_world),
        target_frame_identity=("", "", ""),
        target_frame_availability=(EvidenceAvailability.UNAVAILABLE,) * 3,
    )
    snapshot = candidate_evidence_snapshot_from_live(replace(candidate_set, attempts=attempts))

    assert snapshot.projection_frame_availability is CandidateFactAvailability.UNAVAILABLE
    assert snapshot.projection_unavailable_reason is CandidateProjectionUnavailableReason.DEGENERATE_TARGET_BEARING
    assert all(row.center_target_normalized is None for row in snapshot.rows)


def test_live_and_stored_snapshots_retain_nonfinite_attempted_rows(tmp_path: Path) -> None:
    live = candidate_evidence_snapshot_from_live(_candidate_set_with_nonfinite_attempt())

    assert live.attempted_count == 3
    assert live.projection_frame_availability is CandidateFactAvailability.PARTIAL
    assert live.rows[1].world_pose_availability is CandidateFactAvailability.UNAVAILABLE
    assert live.rows[1].projection_unavailable_reason is CandidateProjectionUnavailableReason.POSE_NONFINITE
    assert live.rows[1].center_world_m is None
    assert live.rows[0].center_target_normalized is not None

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=3, seed=23)[:1],
    )
    reader = RolloutZarrStoreReader(result.store_dir)
    rollout = rollout_at(reader, 0)
    step = rollout_steps(reader, rollout)[0]
    target = next(value for value in target_rows(reader) if value.target_row_id == rollout.target_row_id)
    poses = step.pose_world_cam.copy()
    nonselected = int(np.flatnonzero(~step.selected_mask)[0])
    poses[nonselected, 0] = np.nan
    root_center = np.asarray(rollout.root_pose_world).reshape(12)[9:12]
    target = replace(target, center_world=root_center + np.asarray([0.0, 2.0, 0.0], dtype=np.float32))

    stored = candidate_evidence_snapshot_from_stored(rollout, replace(step, pose_world_cam=poses), target)

    assert stored.attempted_count == step.num_candidates
    assert stored.projection_frame_availability is CandidateFactAvailability.PARTIAL
    assert stored.rows[nonselected].world_pose_availability is CandidateFactAvailability.UNAVAILABLE
    assert stored.rows[nonselected].projection_unavailable_reason is CandidateProjectionUnavailableReason.POSE_NONFINITE
    assert any(row.center_target_normalized is not None for row in stored.rows)


def test_stored_adapter_retains_persisted_jitter_reasons_and_normalizes_legacy_ids(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=3, seed=11)[:1],
    )
    reader = RolloutZarrStoreReader(result.store_dir)
    rollout = rollout_at(reader, 0)
    step = rollout_steps(reader, rollout)[0]
    target = next(value for value in target_rows(reader) if value.target_row_id == rollout.target_row_id)
    snapshot = candidate_evidence_snapshot_from_stored(rollout, step, target)

    assert all(row.position_pair_id is None and row.gaze_variant_id is None for row in snapshot.rows)
    assert all(row.jitter_availability is CandidateFactAvailability.AVAILABLE for row in snapshot.rows)
    assert all(row.view_jitter_is_bounded is True for row in snapshot.rows)
    assert all(row.legacy_invalid_reason_bitset is not None for row in snapshot.rows)
    assert all(row.legacy_admission_availability is CandidateFactAvailability.AVAILABLE for row in snapshot.rows)

    probabilities = step.sampler_probabilities.copy()
    probabilities[0] = np.nan
    jitter_yaw = step.view_jitter_yaw_deg.copy() if step.view_jitter_yaw_deg is not None else None
    assert jitter_yaw is not None
    jitter_yaw[0] = np.nan
    mesh_distance = step.mesh_distance_m.copy()
    path_clearance = step.path_min_clearance_m.copy()
    motion_step = step.motion_step_length_m.copy()
    target_distance = step.target_distance_m.copy()
    for values in (mesh_distance, path_clearance, motion_step, target_distance):
        values[0] = np.nan
    partial = candidate_evidence_snapshot_from_stored(
        rollout,
        replace(
            step,
            sampler_probabilities=probabilities,
            view_jitter_yaw_deg=jitter_yaw,
            mesh_distance_m=mesh_distance,
            path_min_clearance_m=path_clearance,
            motion_step_length_m=motion_step,
            target_distance_m=target_distance,
        ),
        target,
    )
    assert partial.rows[0].proposal_probability is None
    assert partial.rows[0].proposal_probability_availability is CandidateFactAvailability.UNAVAILABLE
    assert partial.rows[0].jitter_availability is CandidateFactAvailability.UNAVAILABLE
    assert partial.rows[0].legacy_admission_availability is CandidateFactAvailability.PARTIAL

    legacy_missing = candidate_evidence_snapshot_from_stored(
        rollout,
        replace(
            step,
            view_jitter_yaw_deg=None,
            view_jitter_pitch_deg=None,
            view_jitter_azimuth_limit_deg=None,
            view_jitter_elevation_limit_deg=None,
            view_jitter_is_bounded=None,
        ),
        target,
    )
    jitter = candidate_support_plot_models((legacy_missing,))[3].build_figure()
    assert any(
        f"does not contain view-jitter evidence for {step.num_candidates} attempted candidates" in str(annotation.text)
        for annotation in jitter.layout.annotations
    )
    assert jitter.layout.xaxis.visible is False
    assert jitter.layout.yaxis.visible is False


def test_stored_adapter_rejects_alignment_and_previous_selection_identity_drift(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=2, num_samples=3, seed=13)[:1],
    )
    reader = RolloutZarrStoreReader(result.store_dir)
    rollout = rollout_at(reader, 0)
    first, second = rollout_steps(reader, rollout)
    target = next(value for value in target_rows(reader) if value.target_row_id == rollout.target_row_id)

    with pytest.raises(ValueError, match="align exactly"):
        candidate_evidence_snapshot_from_stored(
            rollout,
            replace(first, sampler_probabilities=first.sampler_probabilities[:-1]),
            target,
        )
    with pytest.raises(ValueError, match="exactly one selected action"):
        candidate_evidence_snapshot_from_stored(
            rollout,
            replace(
                first,
                selected_mask=np.zeros_like(first.selected_mask),
                selected_local_index=-1,
                selected_candidate_row_id=-1,
            ),
            target,
        )
    with pytest.raises(ValueError, match="stored selected identity"):
        candidate_evidence_snapshot_from_stored(
            rollout,
            second,
            target,
            previous_step=replace(first, selected_candidate_row_id=-1),
        )


def test_read_model_synthesizes_missing_legacy_position_pair_ids(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=3, seed=17)[:1],
    )
    root = zarr.open_group(str(result.store_dir), mode="a")
    del root["candidates"]["position_pair_id"]

    reader = RolloutZarrStoreReader(result.store_dir)
    rollout = rollout_at(reader, 0)
    step = rollout_steps(reader, rollout)[0]
    assert np.array_equal(step.position_pair_ids, np.full(step.num_candidates, -1, dtype=np.int64))
    assert step.position_pair_ids_persisted is False
    assert step.gaze_variant_ids_persisted is True


def test_read_model_rejects_partial_persisted_jitter_bundle(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=3, seed=19)[:1],
    )
    root = zarr.open_group(str(result.store_dir), mode="a")
    del root["candidate_diagnostics"]["view_jitter_pitch_deg"]

    reader = RolloutZarrStoreReader(result.store_dir)
    rollout = rollout_at(reader, 0)
    with pytest.raises(ValueError, match="complete five-array bundle"):
        rollout_steps(reader, rollout)


def test_plot_core_has_no_reader_generator_or_concrete_family_imports() -> None:
    source = (Path(__file__).parents[2] / "aria_nbv/rollouts/candidate_plotting.py").read_text()
    imports = {node.module or "" for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)}
    imports.update(
        alias.name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Import) for alias in node.names
    )

    assert not any(
        forbidden in module
        for module in imports
        for forbidden in ("read_model", "zarr_store", "pose_generation", "candidate_benchmark")
    )


def test_plot_titles_retain_mixed_horizon_range_and_zero_row_support_failure() -> None:
    first = candidate_evidence_snapshot_from_live(
        _candidate_set(),
        state_key="first",
        overlay=CandidateRolloutOverlay(8, 2, 6),
    )
    second = candidate_evidence_snapshot_from_live(
        _candidate_set(),
        state_key="second",
        overlay=CandidateRolloutOverlay(10, 3, 7),
    )
    assert all("H=8…10" in model.title for model in candidate_support_plot_models((first, second)))

    unavailable = replace(
        first,
        rows=(),
        attempted_count=0,
        valid_count=0,
        action_count=0,
        selected_count=None,
        projection_frame_identity=None,
        target_target_normalized=None,
        projection_frame_availability=CandidateFactAvailability.UNAVAILABLE,
        projection_unavailable_reason=CandidateProjectionUnavailableReason.TARGET_MISSING,
    )
    ground = candidate_support_plot_models((unavailable,))[0].build_figure()
    assert any("target_missing" in str(annotation.text) for annotation in ground.layout.annotations)
