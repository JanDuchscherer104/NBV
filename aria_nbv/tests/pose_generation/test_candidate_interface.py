"""Characterization tests for the final candidate request/result interface."""

# ruff: noqa: S101

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest
import torch
import trimesh
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW

from aria_nbv.geometry import PreparedMeshQuery
from aria_nbv.oracle.pipelines.rollout_dataset import RolloutDatasetWriterConfig
from aria_nbv.pose_generation.candidate_errors import CandidateBackendFailureError
from aria_nbv.pose_generation.candidate_generation import CandidateViewGeneratorConfig
from aria_nbv.pose_generation.candidate_interface import (
    ActorTargetContext,
    AdmissionEvidence,
    CandidateConditioning,
    CandidateRequest,
    CandidateSet,
    GeometrySourceRole,
    PreparedCandidateScene,
    candidate_set_to_legacy_result,
)
from aria_nbv.pose_generation.candidate_mixture import (
    CandidateMixtureComponentConfig,
    CandidateMixtureViewGeneratorConfig,
)
from aria_nbv.pose_generation.candidate_program import (
    CandidateProgramLimits,
    GazeFamily,
    GazeVariantConfig,
    TargetExactGazeConfig,
    compile_candidate_program,
)
from aria_nbv.pose_generation.program_generator import ProgramCandidateGenerator
from aria_nbv.pose_generation.sampling_keys import (
    CandidateSamplingKey,
    CandidateSubstreamRevision,
    derive_shipped_component_seed,
)
from aria_nbv.pose_generation.types import (
    CandidateGenerationRuntimeContext,
    CandidatePositionMode,
    ViewDirectionMode,
)
from aria_nbv.rollouts.replay.policy import derive_rollout_seed
from aria_nbv.targets import TargetDescriptor
from aria_nbv.utils.canonical_binding import CanonicalBindingError, canonical_binding_bytes, canonical_binding_sha256


def _pose(device: torch.device | str = "cpu") -> PoseTW:
    return PoseTW.from_Rt(torch.eye(3, device=device), torch.tensor([0.0, 0.0, 0.0], device=device))


def _camera(device: torch.device | str = "cpu") -> CameraTW:
    return CameraTW.from_surreal(
        width=torch.tensor([64.0], device=device),
        height=torch.tensor([64.0], device=device),
        type_str="Pinhole",
        params=torch.tensor([[60.0, 60.0, 32.0, 32.0]], device=device),
        gain=torch.zeros(1, device=device),
        exposure_s=torch.zeros(1, device=device),
        valid_radius=torch.tensor([64.0], device=device),
        T_camera_rig=PoseTW.from_matrix3x4(torch.eye(3, 4, device=device).unsqueeze(0)),
    )


def _target() -> TargetDescriptor:
    return TargetDescriptor(
        sem_id=1,
        class_name="chair",
        pose_world_object=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 2.0),
        extents_m=(1.0, 1.0, 1.0),
        relative_pose_reference_object=(
            1.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            2.0,
        ),
    )


def _scene(device: torch.device | str = "cpu") -> PreparedCandidateScene:
    resolved_device = torch.device(device)
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    verts = torch.from_numpy(mesh.vertices).to(device=resolved_device, dtype=torch.float32)
    faces = torch.from_numpy(mesh.faces).to(device=resolved_device, dtype=torch.long)
    camera = _camera(resolved_device)
    return PreparedCandidateScene(
        scene_identity="scene-content-sha256",
        source_binding_hash="source-binding-sha256",
        mesh_identity="mesh-content-sha256",
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        prepared_mesh_query=None,
        occupancy_extent_world=torch.tensor([-4.0, 4.0, -4.0, 4.0, -4.0, 4.0], device=resolved_device),
        camera_calibration=camera,
        camera_calibration_hash=canonical_binding_sha256(camera),
        geometry_source_role=GeometrySourceRole.ORACLE_ADMISSION,
        device=resolved_device,
        dtype=torch.float32,
    )


def _actor() -> ActorTargetContext:
    descriptor = _target()
    return ActorTargetContext(
        descriptor=descriptor,
        protocol_version="v1_observed",
        descriptor_hash=canonical_binding_sha256(descriptor),
        source_binding_hash="actor-visible-source-sha256",
    )


def _request(
    config: CandidateMixtureViewGeneratorConfig, *, seed: int, source: str = "rollout_proposal"
) -> CandidateRequest:
    program = compile_candidate_program(config)
    return CandidateRequest.bind(
        program=program,
        conditioning=CandidateConditioning(reference_pose_world=_pose()),
        scene=_scene(),
        actor_target=_actor(),
        random_key=CandidateSamplingKey(CandidateSubstreamRevision.SHIPPED_V1, source, seed),  # type: ignore[arg-type]
    )


def _query_free(config: CandidateMixtureViewGeneratorConfig) -> CandidateMixtureViewGeneratorConfig:
    return config.model_copy(
        update={
            "base": config.base.model_copy(
                update={"min_distance_to_mesh": 0.0, "ensure_collision_free": False, "ensure_free_space": False}
            )
        }
    )


@pytest.mark.parametrize("source", ["rollout_proposal", "direct_base"])
def test_program_generator_preserves_paired_mixture_values_and_order(source: str) -> None:
    config = CandidateMixtureViewGeneratorConfig.paired_center_gaze_family()
    config = config.model_copy(
        update={
            "base": config.base.model_copy(
                update={
                    "min_distance_to_mesh": 0.0,
                    "ensure_collision_free": False,
                    "ensure_free_space": False,
                    "device": torch.device("cpu"),
                }
            )
        }
    )
    request = _request(config, seed=37, source=source)

    candidate_set = ProgramCandidateGenerator().generate(request)
    projected = candidate_set_to_legacy_result(candidate_set)
    legacy_seed = 37 if source == "rollout_proposal" else None
    legacy_config = (
        config
        if source == "rollout_proposal"
        else config.model_copy(update={"base": config.base.model_copy(update={"seed": 37})})
    )
    legacy = legacy_config.setup_target().generate(
        reference_pose=_pose(),
        gt_mesh=request.scene.gt_mesh,
        mesh_verts=request.scene.mesh_verts,
        mesh_faces=request.scene.mesh_faces,
        camera_calib_template=request.scene.camera_calibration,
        occupancy_extent=request.scene.occupancy_extent_world,
        runtime_context=CandidateGenerationRuntimeContext(descriptor=_target()),
        seed=legacy_seed,
    )

    assert torch.equal(projected.shell_poses.tensor(), legacy.shell_poses.tensor())
    assert torch.equal(projected.views.tensor(), legacy.views.tensor())
    assert torch.equal(projected.mask_valid, legacy.mask_valid)
    assert projected.component_name == legacy.component_name
    assert torch.equal(projected.position_pair_id, legacy.position_pair_id)
    assert torch.equal(projected.gaze_variant_id, legacy.gaze_variant_id)
    assert torch.equal(projected.strategy_id, legacy.strategy_id)
    assert torch.equal(projected.position_id, legacy.position_id)
    assert torch.equal(projected.mixture_id, legacy.mixture_id)
    assert torch.equal(projected.sampler_probability, legacy.sampler_probability)
    assert projected.masks.keys() == legacy.masks.keys()
    for name in projected.masks:
        assert torch.equal(projected.masks[name], legacy.masks[name])
    assert projected.extras.keys() == legacy.extras.keys()
    for name in projected.extras:
        assert torch.equal(projected.extras[name], legacy.extras[name])
    assert torch.equal(candidate_set.action_indices, candidate_set.valid_indices)
    assert candidate_set.attempts.semantic_group_id[0] == "target_forward_pair"
    assert candidate_set.attempts.candidate_family_id[0] == "target_forward_pair/primary"


def test_single_family_projection_preserves_none_compatibility_fields() -> None:
    config = CandidateViewGeneratorConfig(
        num_samples=7,
        oversample_factor=1.0,
        min_distance_to_mesh=0.0,
        ensure_collision_free=False,
        ensure_free_space=False,
        collect_debug_stats=True,
        device="cpu",
        seed=19,
    )
    program = compile_candidate_program(config)
    scene = _scene()
    request = CandidateRequest.bind(
        program=program,
        conditioning=CandidateConditioning(_pose()),
        scene=scene,
        actor_target=None,
        random_key=CandidateSamplingKey(CandidateSubstreamRevision.SHIPPED_V1, "direct_base", 19),
    )

    projected = candidate_set_to_legacy_result(ProgramCandidateGenerator().generate(request))
    legacy = config.setup_target().generate(
        reference_pose=_pose(),
        gt_mesh=scene.gt_mesh,
        mesh_verts=scene.mesh_verts,
        mesh_faces=scene.mesh_faces,
        camera_calib_template=scene.camera_calibration,
        occupancy_extent=scene.occupancy_extent_world,
    )

    assert torch.equal(projected.shell_poses.tensor(), legacy.shell_poses.tensor())
    assert torch.equal(projected.views.tensor(), legacy.views.tensor())
    assert projected.strategy_id is projected.position_id is projected.mixture_id is None
    assert projected.sampler_probability is projected.component_name is None
    assert projected.position_pair_id is projected.gaze_variant_id is None
    assert projected.extras.keys() == legacy.extras.keys()
    for name in projected.extras:
        left = projected.extras[name]
        right = legacy.extras[name]
        if torch.is_tensor(left):
            assert torch.equal(left, right)
        else:
            assert torch.equal(left.tensor(), right.tensor())


def test_one_component_mixture_preserves_mixture_mask_and_extra_asymmetry() -> None:
    base = CandidateViewGeneratorConfig(
        num_samples=5,
        oversample_factor=1.0,
        min_distance_to_mesh=0.0,
        ensure_collision_free=False,
        ensure_free_space=False,
        collect_rule_masks=True,
        collect_debug_stats=True,
        device="cpu",
    )
    config = CandidateMixtureViewGeneratorConfig(
        base=base,
        components=[
            CandidateMixtureComponentConfig(
                name="only_forward",
                count=5,
                view_mode=ViewDirectionMode.FORWARD_RIG,
                position_mode=CandidatePositionMode.FORWARD_LOCAL,
            )
        ],
    )
    request = _request(config, seed=11)

    projected = candidate_set_to_legacy_result(ProgramCandidateGenerator().generate(request))
    legacy = config.setup_target().generate(
        reference_pose=_pose(),
        gt_mesh=request.scene.gt_mesh,
        mesh_verts=request.scene.mesh_verts,
        mesh_faces=request.scene.mesh_faces,
        camera_calib_template=request.scene.camera_calibration,
        occupancy_extent=request.scene.occupancy_extent_world,
        runtime_context=CandidateGenerationRuntimeContext(descriptor=_target()),
        seed=11,
    )

    assert projected.masks.keys() == legacy.masks.keys()
    assert projected.extras.keys() == legacy.extras.keys()
    assert "view_dirs_delta" not in projected.extras
    for name in projected.masks:
        assert torch.equal(projected.masks[name], legacy.masks[name])
    for name in projected.extras:
        assert torch.equal(projected.extras[name], legacy.extras[name])
    assert projected.component_name == legacy.component_name == ("only_forward",) * 5
    assert torch.equal(projected.mixture_id, legacy.mixture_id)
    assert torch.equal(projected.strategy_id, legacy.strategy_id)
    assert torch.equal(projected.position_id, legacy.position_id)
    candidate_set = ProgramCandidateGenerator().generate(request)
    for criterion in candidate_set.admission.criteria:
        assert criterion.local is None
        assert not criterion.local_availability.any()
        assert criterion.reason_revision.value == "unavailable_v1"
        assert criterion.source_role_revision.value == "unavailable_v1"
    assert set(candidate_set.attempts.target_frame_availability) == {"unavailable"}


def test_legacy_projection_rejects_action_subset_of_valid_rows() -> None:
    config = CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(count=5)
    config = config.model_copy(
        update={
            "base": config.base.model_copy(
                update={"min_distance_to_mesh": 0.0, "ensure_collision_free": False, "ensure_free_space": False}
            )
        }
    )
    request = _request(config, seed=3)
    candidate_set = ProgramCandidateGenerator().generate(request)
    narrowed = replace(candidate_set, action_indices=candidate_set.action_indices[:-1])

    with pytest.raises(ValueError, match="fixed-valid generation proof"):
        candidate_set_to_legacy_result(narrowed)


def test_legacy_projection_preserves_partial_and_all_invalid_v_tables() -> None:
    config = _query_free(CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(count=5))
    candidate_set = ProgramCandidateGenerator().generate(_request(config, seed=3))
    compatibility = candidate_set._legacy_projection_groups  # noqa: SLF001
    assert compatibility

    def with_mask(mask: torch.Tensor) -> CandidateSet:
        return CandidateSet._from_fixed_valid(  # noqa: SLF001 - characterization of the owned proof factory.
            candidate_set.attempts,
            AdmissionEvidence(mask, candidate_set.admission.criteria),
            candidate_set.completion.mode,
            candidate_set.candidate_program_hash,
            candidate_set.request_binding_hash,
            candidate_set.candidate_substream_revision,
            compatibility,
        )

    all_rows = with_mask(torch.ones_like(candidate_set.admission.mask_valid))
    partial_mask = torch.tensor([True, False, False, True, False])
    partial = with_mask(partial_mask)
    empty = with_mask(torch.zeros_like(partial_mask))

    full_projected = candidate_set_to_legacy_result(all_rows)
    partial_projected = candidate_set_to_legacy_result(partial)
    empty_projected = candidate_set_to_legacy_result(empty)

    assert torch.equal(partial_projected.views.tensor(), full_projected.views.tensor()[[0, 3]])
    assert partial_projected.mask_valid.tolist() == partial_mask.tolist()
    assert empty_projected.views.tensor().shape[0] == 0
    assert not empty_projected.mask_valid.any()


def test_candidate_set_rejects_malformed_action_and_admission_axes() -> None:
    config = _query_free(CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(count=4))
    config = config.model_copy(
        update={
            "base": config.base.model_copy(
                update={"min_distance_to_mesh": 0.0, "ensure_collision_free": False, "ensure_free_space": False}
            )
        }
    )
    candidate_set = ProgramCandidateGenerator().generate(_request(config, seed=2))

    with pytest.raises(ValueError, match="1-D int64"):
        replace(candidate_set, action_indices=candidate_set.action_indices.float())
    with pytest.raises(ValueError, match="1-D boolean"):
        replace(
            candidate_set,
            admission=AdmissionEvidence(candidate_set.admission.mask_valid.reshape(1, -1), ()),
        )
    out_of_bounds = replace(
        candidate_set,
        action_indices=torch.tensor([candidate_set.completion.attempted_count], dtype=torch.long),
    )
    with pytest.raises(ValueError, match="unique indices into N"):
        out_of_bounds.validate_semantics()


def test_proposal_keys_are_unique_for_unkeyed_paired_groups() -> None:
    config = CandidateMixtureViewGeneratorConfig.paired_center_gaze_family()
    config = config.model_copy(
        update={
            "base": config.base.model_copy(
                update={"min_distance_to_mesh": 0.0, "ensure_collision_free": False, "ensure_free_space": False}
            )
        }
    )
    program = compile_candidate_program(config)
    request = CandidateRequest.bind(
        program=program,
        conditioning=CandidateConditioning(_pose()),
        scene=_scene(),
        actor_target=_actor(),
        random_key=CandidateSamplingKey(CandidateSubstreamRevision.SHIPPED_V1, "direct_base", None),
    )

    keys = ProgramCandidateGenerator().generate(request).attempts.proposal_key

    assert len(keys) == len(set(keys))
    assert all("unkeyed_global_rng" in key for key in keys)


def test_program_limits_reject_before_generation() -> None:
    config = CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(count=8)

    with pytest.raises(ValueError, match="exceeding"):
        compile_candidate_program(config, limits=CandidateProgramLimits(max_attempted_rows=7))


def test_program_validation_rejects_untyped_admission_numerics_and_orbit_support() -> None:
    config = _query_free(CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(count=8))
    program = compile_candidate_program(config)
    bad_admission = replace(program, admission=replace(program.admission, ray_subsample=True))
    bad_center = replace(
        program,
        groups=(replace(program.groups[0], center=replace(program.groups[0].center, min_radius_m="0.1")),),
    )
    orbit_config = CandidateMixtureViewGeneratorConfig(
        base=config.base,
        components=[
            CandidateMixtureComponentConfig(
                name="orbit",
                count=2,
                view_mode=ViewDirectionMode.TARGET_POINT,
                position_mode=CandidatePositionMode.TARGET_ORBIT,
            )
        ],
    )
    orbit = compile_candidate_program(orbit_config)
    bad_orbit = replace(
        orbit,
        groups=(
            replace(
                orbit.groups[0],
                center=replace(orbit.groups[0].center, target_orbit_angles_deg=(0.0, 180.0)),
            ),
        ),
    )

    with pytest.raises(ValueError, match="ray_subsample"):
        bad_admission.validate()
    with pytest.raises(ValueError, match="nonfinite center values"):
        bad_center.validate()
    with pytest.raises(ValueError, match="nonzero, bilateral"):
        bad_orbit.validate()


def test_target_exact_schema_omits_jitter_and_generates_exact_look_at() -> None:
    with pytest.raises(TypeError, match="unexpected keyword"):
        TargetExactGazeConfig(  # type: ignore[call-arg]
            family=GazeFamily.TARGET_EXACT,
            max_azimuth_deg=1.0,
        )
    config = _query_free(CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(count=4))
    program = compile_candidate_program(config)
    group = program.groups[0]
    exact = replace(
        program,
        groups=(
            replace(
                group,
                gaze_variants=(GazeVariantConfig("exact", TargetExactGazeConfig(GazeFamily.TARGET_EXACT)),),
            ),
        ),
        candidate_program_hash="",
    )
    exact = replace(exact, candidate_program_hash=exact.verified_hash())
    request = CandidateRequest.bind(
        program=exact,
        conditioning=CandidateConditioning(_pose()),
        scene=_scene(),
        actor_target=_actor(),
        random_key=CandidateSamplingKey(CandidateSubstreamRevision.SHIPPED_V1, "direct_base", 4),
    )
    missing_target = CandidateRequest.bind(
        program=exact,
        conditioning=CandidateConditioning(_pose()),
        scene=_scene(),
        actor_target=None,
        random_key=CandidateSamplingKey(CandidateSubstreamRevision.SHIPPED_V1, "direct_base", 4),
    )

    with pytest.raises(ValueError, match="requires actor_target"):
        ProgramCandidateGenerator().generate(missing_target)

    candidate_set = ProgramCandidateGenerator().generate(request)
    target_vectors = _actor().descriptor.center_world_tensor() - candidate_set.attempts.centers_world
    expected = target_vectors / target_vectors.norm(dim=-1, keepdim=True)

    assert torch.allclose(candidate_set.attempts.gaze_directions_world, expected)
    assert set(candidate_set.attempts.gaze_family_id) == {GazeFamily.TARGET_EXACT.value}
    assert torch.count_nonzero(candidate_set.attempts.view_residual_yaw_deg) == 0
    assert torch.count_nonzero(candidate_set.attempts.view_residual_pitch_deg) == 0
    # TARGET_EXACT is a zero-width bounded residual. Its typed family identity
    # and bounded flag distinguish it from legacy uncapped zero-limit spheres.
    assert candidate_set.attempts.view_jitter_is_bounded.all()
    assert torch.count_nonzero(candidate_set.attempts.view_jitter_azimuth_limit_deg) == 0
    assert torch.count_nonzero(candidate_set.attempts.view_jitter_elevation_limit_deg) == 0


def test_request_bind_rejects_rollout_substream_without_frozen_component_name() -> None:
    config = CandidateViewGeneratorConfig(
        num_samples=4,
        oversample_factor=1.0,
        min_distance_to_mesh=0.0,
        ensure_collision_free=False,
        ensure_free_space=False,
    )

    with pytest.raises(ValueError, match="frozen legacy component names"):
        CandidateRequest.bind(
            program=compile_candidate_program(config),
            conditioning=CandidateConditioning(_pose()),
            scene=_scene(),
            actor_target=None,
            random_key=CandidateSamplingKey(CandidateSubstreamRevision.SHIPPED_V1, "rollout_proposal", 1),
        )


def test_request_and_scene_reject_invalid_duration_extent_and_axis_binding() -> None:
    with pytest.raises(ValueError, match="duration"):
        CandidateConditioning(_pose(), action_duration_s=0.0)
    scene = _scene()
    with pytest.raises(ValueError, match="minima"):
        replace(scene, occupancy_extent_world=torch.tensor([4.0, -4.0, -4.0, 4.0, -4.0, 4.0]))
    with pytest.raises(ValueError, match="device/dtype"):
        CandidateRequest.bind(
            program=compile_candidate_program(
                _query_free(CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(count=4))
            ),
            conditioning=CandidateConditioning(PoseTW(_pose().tensor().double())),
            scene=scene,
            actor_target=_actor(),
            random_key=CandidateSamplingKey(CandidateSubstreamRevision.SHIPPED_V1, "direct_base", 1),
        )


def test_program_generator_translates_backend_failure_at_public_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _query_free(CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(count=4))
    monkeypatch.setattr(
        "aria_nbv.pose_generation.program_generator.CandidateViewGenerator._generate_context",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("backend")),
    )

    with pytest.raises(CandidateBackendFailureError, match="backend failed"):
        ProgramCandidateGenerator().generate(_request(config, seed=1))


def test_request_revalidates_program_and_calibration_hashes() -> None:
    request = _request(_query_free(CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(count=4)), seed=1)
    malformed_program = replace(request.program, algorithm_revision="changed")

    with pytest.raises(ValueError, match="Unsupported candidate algorithm_revision"):
        replace(request, program=malformed_program)
    group = request.program.groups[0]
    stale_hash_program = replace(
        request.program,
        groups=(replace(group, center=replace(group.center, max_radius_m=group.center.max_radius_m + 0.1)),),
    )
    with pytest.raises(ValueError, match="program hash"):
        replace(request, program=stale_hash_program)


@pytest.mark.parametrize("name", ["forward_local", "target_forward_pair", "tärgét-é"])
def test_candidate_local_component_seed_matches_shipped_rollout_derivation(name: str) -> None:
    assert derive_shipped_component_seed(17, name) == derive_rollout_seed("component", 17, name)


def test_sampling_keys_reject_undeclared_revision_source_and_boolean_seed() -> None:
    with pytest.raises(ValueError, match="declared"):
        CandidateSamplingKey("future", "direct_base", 1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="source"):
        CandidateSamplingKey(CandidateSubstreamRevision.SHIPPED_V1, "other", 1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="integer"):
        CandidateSamplingKey(CandidateSubstreamRevision.SHIPPED_V1, "direct_base", True)


def test_canonical_binding_is_order_stable_little_endian_and_rejects_nfc_collisions() -> None:
    tensor = torch.tensor([1, 256], dtype=torch.int16)
    assert canonical_binding_sha256({"b": 2, "a": 1}) == canonical_binding_sha256({"a": 1, "b": 2})
    assert canonical_binding_bytes(tensor).endswith(b"\x01\x00\x00\x01")
    with pytest.raises(CanonicalBindingError, match="collide"):
        canonical_binding_bytes({"é": 1, "e\u0301": 2})


def test_canonical_binding_fixtures_freeze_program_request_and_value_types() -> None:
    config = _query_free(CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(count=4))
    program = compile_candidate_program(config)
    request = _request(config, seed=1)

    assert program.candidate_program_hash == "aebbc45068eefcc9885455e3a8b62f7426f4d84472c1a68fc2b4cc0230293450"
    assert request.request_binding_hash == "fa443e7b617a311e3fb7478832a5f480a8c06edac2f7e00ea10b5b1fdb48ec53"
    assert canonical_binding_sha256(torch.tensor([1, 256], dtype=torch.int16)) == (
        "c368cc5e5aaa78cabc8abb59484a7265520ed5cf57fb2d2ba8d76cebdaa827f4"
    )
    assert canonical_binding_sha256(_pose()) == "bd207c1d1d767910e2ff9598a575c1a203500b195390f37257b510c8f8e35683"
    assert canonical_binding_sha256(_camera()) == "7a0ef2aeecea1ce38a8b719f4e73e8ad23bbcce74c577b80dcceb72f4965dd68"
    assert canonical_binding_sha256(CandidateSubstreamRevision.SHIPPED_V1) == (
        "c1983b4d6d7043f1b61d1676903544c8b041b2477690d2c7e0353d78ab5369f8"
    )


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required for device-neutral tensor fixture")
def test_canonical_tensor_value_is_device_neutral() -> None:
    value = torch.tensor([[1.25, -2.5]], dtype=torch.float32)
    assert canonical_binding_bytes(value) == canonical_binding_bytes(value.cuda())


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required for generation parity")
def test_cuda_program_generator_preserves_paired_shell_and_provenance() -> None:
    device = torch.device("cuda")
    config = CandidateMixtureViewGeneratorConfig.paired_center_gaze_family()
    config = config.model_copy(
        update={
            "base": config.base.model_copy(
                update={
                    "min_distance_to_mesh": 0.0,
                    "ensure_collision_free": False,
                    "ensure_free_space": False,
                    "device": device,
                }
            )
        }
    )
    scene = _scene(device)
    request = CandidateRequest.bind(
        program=compile_candidate_program(config),
        conditioning=CandidateConditioning(_pose(device)),
        scene=scene,
        actor_target=_actor(),
        random_key=CandidateSamplingKey(CandidateSubstreamRevision.SHIPPED_V1, "rollout_proposal", 37),
    )

    candidate_set = ProgramCandidateGenerator().generate(request)
    projected = candidate_set_to_legacy_result(candidate_set)
    legacy = config.setup_target().generate(
        reference_pose=_pose(device),
        gt_mesh=scene.gt_mesh,
        mesh_verts=scene.mesh_verts,
        mesh_faces=scene.mesh_faces,
        camera_calib_template=scene.camera_calibration,
        occupancy_extent=scene.occupancy_extent_world,
        runtime_context=CandidateGenerationRuntimeContext(descriptor=_target()),
        seed=37,
    )

    assert torch.equal(projected.shell_poses.tensor(), legacy.shell_poses.tensor())
    assert torch.equal(projected.views.tensor(), legacy.views.tensor())
    assert torch.equal(projected.mask_valid, legacy.mask_valid)
    assert torch.equal(projected.position_pair_id, legacy.position_pair_id)
    assert torch.equal(projected.gaze_variant_id, legacy.gaze_variant_id)
    assert projected.component_name == legacy.component_name
    assert candidate_set.valid_indices.data_ptr() == candidate_set.action_indices.data_ptr()


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required for warm transfer guard")
def test_cuda_warm_generation_does_not_call_host_value_materializers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aria_nbv.pose_generation.candidate_interface as candidate_interface

    device = torch.device("cuda")
    config = _query_free(CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(count=4))
    config = config.model_copy(update={"base": config.base.model_copy(update={"device": device})})
    request = CandidateRequest.bind(
        program=compile_candidate_program(config),
        conditioning=CandidateConditioning(_pose(device)),
        scene=_scene(device),
        actor_target=_actor(),
        random_key=CandidateSamplingKey(CandidateSubstreamRevision.SHIPPED_V1, "direct_base", 5),
    )
    monkeypatch.setattr(
        candidate_interface,
        "canonical_binding_sha256",
        lambda *_args, **_kwargs: pytest.fail("warm canonical encoding"),
    )
    monkeypatch.setattr(torch.Tensor, "cpu", lambda _self: pytest.fail("warm tensor.cpu"))
    monkeypatch.setattr(torch.Tensor, "item", lambda _self: pytest.fail("warm tensor.item"))

    result = ProgramCandidateGenerator().generate(request)

    assert result.completion.attempted_count == 4


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required for a valid alternate execution device")
def test_execution_device_changes_request_binding_without_hashing_mesh_content() -> None:
    request = _request(_query_free(CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(count=4)), seed=1)
    cuda_scene = _scene("cuda")
    cuda_request = CandidateRequest.bind(
        program=request.program,
        conditioning=CandidateConditioning(_pose("cuda")),
        scene=cuda_scene,
        actor_target=request.actor_target,
        random_key=request.random_key,
    )

    assert cuda_request.request_binding_hash != request.request_binding_hash


def test_equal_fresh_conditioning_values_have_process_stable_request_binding() -> None:
    config = CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(count=4)

    assert _request(config, seed=1).request_binding_hash == _request(config, seed=1).request_binding_hash


def test_warm_generation_uses_receipts_without_canonical_reencoding(monkeypatch: pytest.MonkeyPatch) -> None:
    import aria_nbv.pose_generation.candidate_interface as candidate_interface

    config = _query_free(CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(count=4))
    request = _request(config, seed=1)
    monkeypatch.setattr(
        candidate_interface,
        "canonical_binding_sha256",
        lambda *_args, **_kwargs: pytest.fail("warm canonical encoding"),
    )

    result = ProgramCandidateGenerator().generate(request)

    assert result.completion.attempted_count == 4


def test_warm_generation_rejects_mutated_bound_pose_without_rehashing() -> None:
    request = _request(CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(count=4), seed=1)
    request.conditioning.reference_pose_world.tensor().add_(1.0)

    with pytest.raises(ValueError, match="pose changed"):
        ProgramCandidateGenerator().generate(request)


def test_cached_valid_projection_rejects_mutated_admission_mask() -> None:
    config = _query_free(CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(count=4))
    candidate_set = ProgramCandidateGenerator().generate(_request(config, seed=1))
    candidate_set.admission.mask_valid.logical_not_()

    with pytest.raises(ValueError, match="Admission validity changed"):
        _ = candidate_set.valid_indices
    with pytest.raises(ValueError, match="Admission validity changed"):
        candidate_set_to_legacy_result(candidate_set)


def test_inference_mode_generation_retains_a_fixed_valid_projection_proof() -> None:
    config = _query_free(CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(count=4))
    request = _request(config, seed=1)

    with torch.inference_mode():
        candidate_set = ProgramCandidateGenerator().generate(request)
        projected = candidate_set_to_legacy_result(candidate_set)

    assert projected.views.shape[0] == candidate_set.completion.valid_count


def test_candidate_core_has_no_rollout_or_consumer_imports() -> None:
    package = Path(__file__).parents[2] / "aria_nbv" / "pose_generation"
    forbidden = ("rollouts", "oracle", "zarr", "plotly", "streamlit", "rerun", "rri_metrics")
    for name in ("candidate_interface.py", "candidate_program.py", "program_generator.py", "sampling_keys.py"):
        tree = ast.parse((package / name).read_text(encoding="utf-8"), filename=name)
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules.append(node.module)
        assert not any(any(part == owner for part in module.split(".")) for module in modules for owner in forbidden)


def test_pose_generation_public_surface_freezes_canonical_and_legacy_facades() -> None:
    import aria_nbv.pose_generation as pose_generation

    canonical = {
        "CandidateProgram",
        "CandidateRequest",
        "PreparedCandidateScene",
        "CandidateSet",
        "CandidateGenerator",
        "ProgramCandidateGenerator",
        "compile_candidate_program",
        "candidate_set_to_legacy_result",
    }
    compatibility = {
        "CandidateViewGenerator",
        "CandidateMixtureViewGenerator",
        "CandidateSamplingResult",
    }

    assert canonical | compatibility <= set(pose_generation.__all__)
    assert all(hasattr(pose_generation, name) for name in canonical | compatibility)


def test_all_reviewed_program_presets_compile_with_bounded_rows() -> None:
    presets = (
        CandidateMixtureViewGeneratorConfig(),
        CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(),
        CandidateMixtureViewGeneratorConfig.rich_local_five_family(),
        CandidateMixtureViewGeneratorConfig.paired_center_gaze_family(),
        CandidateMixtureViewGeneratorConfig.radial_target_backtrack_family(),
    )
    for config in presets:
        program = compile_candidate_program(config)
        assert program.candidate_program_hash == program.verified_hash()
        assert sum(group.center_count * len(group.gaze_variants) for group in program.groups) <= 4096


def test_active_rollout_writer_tomls_compile_and_generate_with_legacy_parity() -> None:
    config_dir = Path(__file__).parents[3] / ".configs"
    names = (
        "build_rollouts_qh_v0_baseline.toml",
        "build_rollouts_v1_cuda_campaign_writer.toml",
        "build_rollouts_v1_diverse.toml",
        "build_rollouts_v1_lrz.template.toml",
        "build_rollouts_v1_microset.toml",
        "build_rollouts_v1_multihorizon_highgain.toml",
        "build_rollouts_v1_realistic.toml",
        "build_rollouts_v1_smoke.toml",
    )
    for name in names:
        writer = RolloutDatasetWriterConfig.from_toml(config_dir / name)
        config = writer.candidate_mixture.model_copy(
            update={"base": writer.candidate_mixture.base.model_copy(update={"device": torch.device("cpu")})}
        )
        program = compile_candidate_program(config)
        assert program.candidate_program_hash == program.verified_hash()
        scene = _scene()
        needs_query = program.admission.min_distance_to_mesh_m > 0 or (
            program.admission.ensure_collision_free and program.admission.step_clearance_m > 0
        )
        if needs_query:
            scene = replace(
                scene,
                prepared_mesh_query=PreparedMeshQuery(
                    scene.mesh_verts,
                    scene.mesh_faces,
                    device=scene.device,
                    dtype=scene.dtype,
                    mesh=scene.gt_mesh,
                ),
            )
        request = CandidateRequest.bind(
            program=program,
            conditioning=CandidateConditioning(_pose()),
            scene=scene,
            actor_target=_actor(),
            random_key=CandidateSamplingKey(CandidateSubstreamRevision.SHIPPED_V1, "rollout_proposal", 17),
        )

        projected = candidate_set_to_legacy_result(ProgramCandidateGenerator().generate(request))
        legacy = config.setup_target().generate(
            reference_pose=_pose(),
            gt_mesh=scene.gt_mesh,
            mesh_verts=scene.mesh_verts,
            mesh_faces=scene.mesh_faces,
            camera_calib_template=scene.camera_calibration,
            occupancy_extent=scene.occupancy_extent_world,
            runtime_context=CandidateGenerationRuntimeContext(descriptor=_target()),
            seed=17,
        )

        assert torch.equal(projected.shell_poses.tensor(), legacy.shell_poses.tensor()), name
        assert torch.equal(projected.views.tensor(), legacy.views.tensor()), name
        assert torch.equal(projected.mask_valid, legacy.mask_valid), name
        assert projected.component_name == legacy.component_name, name


def test_program_generator_consumes_supplied_prepared_query_without_reacquisition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    verts = torch.from_numpy(mesh.vertices).float()
    faces = torch.from_numpy(mesh.faces).long()
    query = PreparedMeshQuery(verts, faces, device="cpu", dtype=torch.float32, mesh=mesh)
    config = CandidateViewGeneratorConfig(
        num_samples=4,
        oversample_factor=1.0,
        min_distance_to_mesh=0.1,
        ensure_collision_free=False,
        ensure_free_space=False,
    )
    program = compile_candidate_program(config)
    scene = PreparedCandidateScene(
        scene_identity="scene",
        source_binding_hash="source",
        mesh_identity="mesh",
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        prepared_mesh_query=query,
        occupancy_extent_world=torch.tensor([-4.0, 4.0, -4.0, 4.0, -4.0, 4.0]),
        camera_calibration=_camera(),
        camera_calibration_hash=canonical_binding_sha256(_camera()),
        geometry_source_role=GeometrySourceRole.ORACLE_ADMISSION,
        device=torch.device("cpu"),
        dtype=torch.float32,
    )
    request = CandidateRequest.bind(
        program=program,
        conditioning=CandidateConditioning(_pose()),
        scene=scene,
        actor_target=None,
        random_key=CandidateSamplingKey(CandidateSubstreamRevision.SHIPPED_V1, "direct_base", 2),
    )
    monkeypatch.setattr(
        PreparedMeshQuery, "acquire", classmethod(lambda cls, *args, **kwargs: pytest.fail("reacquired"))
    )

    result = ProgramCandidateGenerator().generate(request)

    assert result.completion.attempted_count == 4


def test_multi_group_program_shares_one_prepared_query_without_reacquisition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    verts = torch.from_numpy(mesh.vertices).float()
    faces = torch.from_numpy(mesh.faces).long()
    query = PreparedMeshQuery(verts, faces, device="cpu", dtype=torch.float32, mesh=mesh)
    base = CandidateViewGeneratorConfig(
        num_samples=2,
        oversample_factor=1.0,
        min_distance_to_mesh=0.1,
        ensure_collision_free=False,
        ensure_free_space=False,
    )
    config = CandidateMixtureViewGeneratorConfig(
        base=base,
        components=[
            CandidateMixtureComponentConfig(
                name="first",
                count=2,
                view_mode=ViewDirectionMode.FORWARD_RIG,
                position_mode=CandidatePositionMode.FORWARD_LOCAL,
            ),
            CandidateMixtureComponentConfig(
                name="second",
                count=2,
                view_mode=ViewDirectionMode.RADIAL_AWAY,
                position_mode=CandidatePositionMode.REVISIT_BACKTRACK,
            ),
        ],
    )
    camera = _camera()
    scene = PreparedCandidateScene(
        scene_identity="scene",
        source_binding_hash="source",
        mesh_identity="mesh",
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        prepared_mesh_query=query,
        occupancy_extent_world=torch.tensor([-4.0, 4.0, -4.0, 4.0, -4.0, 4.0]),
        camera_calibration=camera,
        camera_calibration_hash=canonical_binding_sha256(camera),
        geometry_source_role=GeometrySourceRole.ORACLE_ADMISSION,
        device=torch.device("cpu"),
        dtype=torch.float32,
    )
    request = CandidateRequest.bind(
        program=compile_candidate_program(config),
        conditioning=CandidateConditioning(_pose()),
        scene=scene,
        actor_target=_actor(),
        random_key=CandidateSamplingKey(CandidateSubstreamRevision.SHIPPED_V1, "rollout_proposal", 2),
    )
    monkeypatch.setattr(
        PreparedMeshQuery, "acquire", classmethod(lambda cls, *args, **kwargs: pytest.fail("reacquired"))
    )

    result = ProgramCandidateGenerator().generate(request)

    assert result.completion.attempted_count == 4


def test_warm_generation_rejects_mutated_prepared_query_source() -> None:
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    verts = torch.from_numpy(mesh.vertices).float()
    faces = torch.from_numpy(mesh.faces).long()
    query = PreparedMeshQuery(verts, faces, device="cpu", dtype=torch.float32, mesh=mesh)
    camera = _camera()
    scene = PreparedCandidateScene(
        scene_identity="scene",
        source_binding_hash="source",
        mesh_identity="mesh",
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        prepared_mesh_query=query,
        occupancy_extent_world=torch.tensor([-4.0, 4.0, -4.0, 4.0, -4.0, 4.0]),
        camera_calibration=camera,
        camera_calibration_hash=canonical_binding_sha256(camera),
        geometry_source_role=GeometrySourceRole.ORACLE_ADMISSION,
        device=torch.device("cpu"),
        dtype=torch.float32,
    )
    config = CandidateViewGeneratorConfig(
        num_samples=4,
        oversample_factor=1.0,
        min_distance_to_mesh=0.1,
        ensure_collision_free=False,
        ensure_free_space=False,
    )
    request = CandidateRequest.bind(
        program=compile_candidate_program(config),
        conditioning=CandidateConditioning(_pose()),
        scene=scene,
        actor_target=None,
        random_key=CandidateSamplingKey(CandidateSubstreamRevision.SHIPPED_V1, "direct_base", 2),
    )
    verts.add_(0.1)

    with pytest.raises(ValueError, match="query sources changed"):
        ProgramCandidateGenerator().generate(request)
