"""Integration parity for the canonical candidate adapter and legacy consumers."""

# ruff: noqa: S101

from __future__ import annotations

import numpy as np
import torch

from aria_nbv.pose_generation.candidate_interface import (
    CandidateConditioning,
    CandidateRequest,
    GeometrySourceRole,
    PreparedCandidateScene,
    candidate_set_to_legacy_result,
)
from aria_nbv.pose_generation.candidate_program import compile_candidate_program
from aria_nbv.pose_generation.program_generator import ProgramCandidateGenerator
from aria_nbv.pose_generation.sampling_keys import CandidateSamplingKey, CandidateSubstreamRevision
from aria_nbv.rollouts import RolloutZarrStoreReader
from aria_nbv.rollouts.replay.engine import CounterfactualPoseGenerator
from aria_nbv.rollouts.trace import _candidate_invalid_reasons
from aria_nbv.rollouts.zarr_store import write_rollout_zarr_store
from aria_nbv.utils.canonical_binding import canonical_binding_sha256
from tests.rollout_fixtures import build_rollout_records


class _ProgramLegacyFacade:
    """Test-only bridge proving the outward adapter against legacy consumers."""

    def __init__(self, config) -> None:
        self._program = compile_candidate_program(config)

    def generate(
        self,
        *,
        reference_pose,
        gt_mesh,
        mesh_verts,
        mesh_faces,
        camera_calib_template,
        occupancy_extent,
        runtime_context=None,
        seed=None,
    ):
        del runtime_context
        device = mesh_verts.device
        scene = PreparedCandidateScene(
            scene_identity="fixture-box-scene-v1",
            source_binding_hash="fixture-source-v1",
            mesh_identity="fixture-box-mesh-v1",
            gt_mesh=gt_mesh,
            mesh_verts=mesh_verts,
            mesh_faces=mesh_faces,
            prepared_mesh_query=None,
            occupancy_extent_world=occupancy_extent,
            camera_calibration=camera_calib_template,
            camera_calibration_hash=canonical_binding_sha256(camera_calib_template),
            geometry_source_role=GeometrySourceRole.ORACLE_ADMISSION,
            device=device,
            dtype=mesh_verts.dtype,
        )
        request = CandidateRequest.bind(
            program=self._program,
            conditioning=CandidateConditioning(reference_pose),
            scene=scene,
            actor_target=None,
            random_key=CandidateSamplingKey(
                CandidateSubstreamRevision.SHIPPED_V1,
                "direct_base",
                seed,
            ),
        )
        return candidate_set_to_legacy_result(ProgramCandidateGenerator().generate(request))


def test_program_adapter_preserves_rollout_selection_reasons_and_store_tables(monkeypatch, tmp_path) -> None:
    """Existing selector/reason/store consumers see byte-equivalent legacy facts."""

    legacy_records = build_rollout_records(horizon=2, num_samples=6, seed=91)[:2]
    original_init = CounterfactualPoseGenerator.__init__

    def _init_with_program_adapter(self, config) -> None:
        original_init(self, config)
        self._candidate_generator = _ProgramLegacyFacade(config.candidate_config)

    monkeypatch.setattr(CounterfactualPoseGenerator, "__init__", _init_with_program_adapter)
    adapted_records = build_rollout_records(horizon=2, num_samples=6, seed=91)[:2]

    for legacy_record, adapted_record in zip(legacy_records, adapted_records, strict=True):
        for legacy_trajectory, adapted_trajectory in zip(
            legacy_record.evaluated.result.trajectories,
            adapted_record.evaluated.result.trajectories,
            strict=True,
        ):
            for legacy_step, adapted_step in zip(
                legacy_trajectory.steps,
                adapted_trajectory.steps,
                strict=True,
            ):
                assert adapted_step.selected_shell_index == legacy_step.selected_shell_index
                assert adapted_step.selected_valid_index == legacy_step.selected_valid_index
                assert torch.equal(adapted_step.candidates.views.tensor(), legacy_step.candidates.views.tensor())
                assert torch.equal(adapted_step.candidates.mask_valid, legacy_step.candidates.mask_valid)
                assert adapted_step.candidates.masks.keys() == legacy_step.candidates.masks.keys()
                for name in legacy_step.candidates.masks:
                    assert torch.equal(adapted_step.candidates.masks[name], legacy_step.candidates.masks[name])
                adapted_reasons = _candidate_invalid_reasons(adapted_step.candidates)
                legacy_reasons = _candidate_invalid_reasons(legacy_step.candidates)
                assert all(
                    torch.equal(left, right) for left, right in zip(adapted_reasons, legacy_reasons, strict=True)
                )

    legacy_store = write_rollout_zarr_store(tmp_path / "legacy.zarr", legacy_records)
    adapted_store = write_rollout_zarr_store(tmp_path / "adapted.zarr", adapted_records)
    legacy_reader = RolloutZarrStoreReader(legacy_store.store_dir)
    adapted_reader = RolloutZarrStoreReader(adapted_store.store_dir)
    for group_name in ("steps", "candidates", "candidate_diagnostics", "q_h"):
        legacy_group = legacy_reader.root[group_name]
        adapted_group = adapted_reader.root[group_name]
        array_names = sorted(legacy_group.array_keys())
        assert array_names == sorted(adapted_group.array_keys())
        for name in array_names:
            legacy_array = legacy_group[name]
            adapted_array = adapted_group[name]
            assert adapted_array.dtype == legacy_array.dtype
            assert adapted_array.shape == legacy_array.shape
            assert adapted_array.chunks == legacy_array.chunks
            np.testing.assert_equal(np.asarray(adapted_array), np.asarray(legacy_array))
