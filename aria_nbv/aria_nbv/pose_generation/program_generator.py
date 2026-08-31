"""Shipped candidate-program interpreter behind the final generation interface."""

from __future__ import annotations

from collections.abc import Callable
from types import MappingProxyType
from typing import Any, cast

import torch
from efm3d.aria.pose import PoseTW

from .candidate_errors import (
    CandidateAlignmentCorruptionError,
    CandidateBackendFailureError,
    CandidateGenerationError,
    CandidateNumericalDegeneracyError,
    CandidateRequestMismatchError,
    InvalidCandidateProgramError,
)
from .candidate_generation import CandidateViewGenerator, CandidateViewGeneratorConfig
from .candidate_interface import (
    AdmissionEvidence,
    CandidateMeasurements,
    CandidateRequest,
    CandidateSet,
    CandidateTable,
    CriterionEvidence,
    CriterionReasonRevision,
    CriterionSourceRoleRevision,
    EvidenceAvailability,
    _LegacyProjectionGroup,
    _LegacyProjectionVariant,
)
from .candidate_mixture import candidate_position_id, candidate_strategy_id
from .candidate_program import CenterFamily, GazeFamily
from .sampling_keys import CandidateSubstreamRevision, derive_shipped_component_seed
from .types import CandidateContext, CandidatePositionMode, ViewDirectionMode

_DEFAULT_TARGET_ORBIT_ANGLES_DEG = (-6.0, 6.0, -10.0, 10.0, -14.0, 14.0, -18.0, 18.0, -22.0, 22.0, -26.0, 26.0)


def _pose_tensor(pose: PoseTW) -> torch.Tensor:
    """Cross the untyped EFM pose boundary with a typed tensor result."""

    accessor: Callable[[], Any] = pose.tensor
    return cast(torch.Tensor, accessor())


class ProgramCandidateGenerator:
    """Interpret literal candidate programs using the shipped numerical kernels."""

    def generate(self, request: CandidateRequest) -> CandidateSet:
        """Generate a canonical attempted shell directly from typed request facts."""

        request.validate_for_generate()
        if request.random_key.revision is not CandidateSubstreamRevision.SHIPPED_V1:
            raise InvalidCandidateProgramError(
                f"Unsupported candidate substream revision: {request.random_key.revision}."
            )
        admission = request.program.admission
        needs_query = admission.min_distance_to_mesh_m > 0 or (
            admission.ensure_collision_free and admission.step_clearance_m > 0
        )
        if needs_query and request.scene.prepared_mesh_query is None:
            raise CandidateRequestMismatchError(
                "Candidate admission requires one composition-owned prepared_mesh_query."
            )
        if not needs_query and request.scene.prepared_mesh_query is not None:
            raise CandidateRequestMismatchError(
                "Prepared mesh query must be omitted when all query-dependent admission is disabled."
            )
        contexts: list[CandidateContext] = []
        metadata: list[tuple[str, str, str, str, int, int, int | None]] = []
        total_rows = sum(group.center_count * len(group.gaze_variants) for group in request.program.groups)
        target = (
            None
            if request.actor_target is None
            else request.actor_target.descriptor.center_world_tensor(dtype=request.scene.dtype).to(
                device=request.scene.device
            )
        )

        for group_index, group in enumerate(request.program.groups):
            primary_seed = _primary_seed(request, group_index)
            primary_context: CandidateContext | None = None
            for variant_index, variant in enumerate(group.gaze_variants):
                config = _runtime_config(request, group_index, variant_index, target)
                generator = CandidateViewGenerator(config, mesh_query=request.scene.prepared_mesh_query)
                seed = primary_seed
                if variant_index > 0 and seed is not None:
                    paired_name = f"{group.legacy_seed_component_name}__paired_{variant.legacy_paired_view_mode_value}"
                    seed = derive_shipped_component_seed(seed, paired_name)
                try:
                    if primary_context is None:
                        context = generator._generate_context(  # noqa: SLF001 - transitional shipped interpreter seam.
                            reference_pose=request.conditioning.reference_pose_world,
                            gt_mesh=request.scene.gt_mesh,
                            mesh_verts=request.scene.mesh_verts,
                            mesh_faces=request.scene.mesh_faces,
                            camera_calib_template=request.scene.camera_calibration,
                            occupancy_extent=request.scene.occupancy_extent_world,
                            seed=seed,
                        )
                        primary_context = context
                    else:
                        context = generator._generate_context_from_centers(  # noqa: SLF001
                            reference_pose=request.conditioning.reference_pose_world,
                            centers_world=primary_context.centers_world,
                            offsets_ref=primary_context.shell_offsets_ref,
                            gt_mesh=request.scene.gt_mesh,
                            mesh_verts=request.scene.mesh_verts,
                            mesh_faces=request.scene.mesh_faces,
                            camera_calib_template=request.scene.camera_calibration,
                            occupancy_extent=request.scene.occupancy_extent_world,
                            seed=seed,
                        )
                except CandidateGenerationError:
                    raise
                except (ArithmeticError, ValueError) as error:
                    raise CandidateNumericalDegeneracyError(
                        f"Candidate numerical generation failed for {group.semantic_group_id!r}."
                    ) from error
                except (ImportError, RuntimeError) as error:
                    raise CandidateBackendFailureError(
                        f"Candidate backend failed for {group.semantic_group_id!r}."
                    ) from error
                contexts.append(context)
                family_id = f"{group.semantic_group_id}/{variant.semantic_variant_id}"
                metadata.append(
                    (
                        group.semantic_group_id,
                        group.center.family.value,
                        variant.gaze.family.value,
                        family_id,
                        group_index,
                        variant_index if len(group.gaze_variants) > 1 else -1,
                        seed,
                    )
                )

        return _assemble_candidate_set(request, contexts, metadata, target, total_rows)


def _primary_seed(request: CandidateRequest, group_index: int) -> int | None:
    group = request.program.groups[group_index]
    root = request.random_key.root_seed
    if root is None or group.legacy_seed_component_name is None:
        return root
    if request.random_key.source == "rollout_proposal":
        return derive_shipped_component_seed(root, group.legacy_seed_component_name)
    if group.legacy_direct_component_index is None:
        raise InvalidCandidateProgramError("Direct-base shipped substreams require a frozen component index.")
    return root + group.legacy_direct_component_index


def _runtime_config(
    request: CandidateRequest, group_index: int, variant_index: int, target: torch.Tensor | None
) -> CandidateViewGeneratorConfig:
    group = request.program.groups[group_index]
    center = group.center
    gaze = group.gaze_variants[variant_index].gaze
    admission = request.program.admission
    view_mode = (
        ViewDirectionMode.TARGET_POINT
        if gaze.family in {GazeFamily.TARGET_EXACT, GazeFamily.TARGET_GLANCE}
        else ViewDirectionMode(gaze.family.value)
    )
    position_mode = CandidatePositionMode(center.family.value)
    needs_position_target = center.family in {
        CenterFamily.TARGET_BEARING_LOCAL,
        CenterFamily.TARGET_ORBIT,
        CenterFamily.LATERAL_TARGET_BYPASS,
    }
    if (needs_position_target or gaze.family in {GazeFamily.TARGET_EXACT, GazeFamily.TARGET_GLANCE}) and target is None:
        raise CandidateRequestMismatchError(f"Candidate family {group.semantic_group_id!r} requires actor_target.")
    # CandidateProgram has already performed the complete closed-schema and
    # numerical validation. Avoid repeating Pydantic authoring validation for
    # every group on every rollout node.
    return CandidateViewGeneratorConfig.model_construct(
        num_samples=group.center_count,
        oversample_factor=1.0,
        align_to_gravity=center.align_to_gravity,
        min_radius=center.min_radius_m,
        max_radius=center.max_radius_m,
        min_elev_deg=center.min_elevation_deg,
        max_elev_deg=center.max_elevation_deg,
        delta_azimuth_deg=center.delta_azimuth_deg,
        sampling_strategy=center.sampling_strategy,
        kappa=center.concentration,
        position_mode=position_mode,
        position_target_point_world=(
            target
            if needs_position_target
            or any(item.legacy_direct_component_index is not None for item in request.program.groups)
            else None
        ),
        target_orbit_angles_deg=getattr(
            center,
            "target_orbit_angles_deg",
            _DEFAULT_TARGET_ORBIT_ANGLES_DEG,
        ),
        min_distance_to_mesh=admission.min_distance_to_mesh_m,
        ensure_collision_free=admission.ensure_collision_free,
        ensure_free_space=admission.ensure_free_space,
        collision_backend=admission.collision_backend,
        ray_subsample=admission.ray_subsample,
        step_clearance=admission.step_clearance_m,
        enforce_motion_realism=admission.enforce_motion_realism,
        max_step_distance_m=admission.max_step_distance_m,
        max_height_delta_m=admission.max_height_delta_m,
        max_backward_step_m=admission.max_backward_step_m,
        max_yaw_delta_deg=admission.max_yaw_delta_deg,
        collect_rule_masks=admission.collect_rule_masks,
        collect_debug_stats=admission.collect_debug_stats,
        verbosity=0,
        device=request.scene.device,
        view_direction_mode=view_mode,
        view_sampling_strategy=getattr(gaze, "sampling_strategy", None),
        view_kappa=getattr(gaze, "concentration", 0.0),
        view_max_azimuth_deg=getattr(gaze, "max_azimuth_deg", 0.0),
        view_max_elevation_deg=getattr(gaze, "max_elevation_deg", 0.0),
        view_roll_jitter_deg=getattr(gaze, "roll_jitter_deg", 0.0),
        view_target_point_world=(
            target if gaze.family in {GazeFamily.TARGET_EXACT, GazeFamily.TARGET_GLANCE} else None
        ),
        seed=None,
    )


def _assemble_candidate_set(
    request: CandidateRequest,
    contexts: list[CandidateContext],
    metadata: list[tuple[str, str, str, str, int, int, int | None]],
    target: torch.Tensor | None,
    total_rows: int,
) -> CandidateSet:
    is_mixture = any(group.legacy_direct_component_index is not None for group in request.program.groups)
    has_paired_gaze = any(len(group.gaze_variants) > 1 for group in request.program.groups)
    masks = _concat_masks(contexts, is_mixture=is_mixture)
    # Inference tensors intentionally lack mutation counters. Copy only the
    # compact validity axis into a normal tensor so the A=V proof can fail
    # closed on later mutation without transferring values to the host.
    with torch.inference_mode(False):
        valid = torch.cat([context.mask_valid.reshape(-1) for context in contexts])
    poses = PoseTW(torch.cat([_pose_tensor(context.shell_poses).reshape(-1, 12) for context in contexts]))
    centers = torch.cat([context.centers_world for context in contexts])
    offsets = torch.cat([context.shell_offsets_ref for context in contexts])
    semantic_group: list[str] = []
    center_family: list[str] = []
    gaze_family: list[str] = []
    candidate_family: list[str] = []
    center_ids: list[torch.Tensor] = []
    pair_ids: list[torch.Tensor] = []
    gaze_ids: list[torch.Tensor] = []
    draw_ids: list[torch.Tensor] = []
    proposal_keys: list[str] = []
    center_base = 0
    pair_base = 0
    group_center_ids: dict[int, torch.Tensor] = {}
    group_pair_ids: dict[int, torch.Tensor] = {}
    for context, (
        group_name,
        center_name,
        gaze_name,
        family_name,
        group_index,
        gaze_index,
        resolved_seed,
    ) in zip(contexts, metadata, strict=True):
        n = int(context.mask_valid.numel())
        device = context.mask_valid.device
        semantic_group.extend([group_name] * n)
        center_family.extend([center_name] * n)
        gaze_family.extend([gaze_name] * n)
        candidate_family.extend([family_name] * n)
        if has_paired_gaze:
            if group_index not in group_center_ids:
                group_center_ids[group_index] = torch.arange(center_base, center_base + n, device=device)
                center_base += n
            center_ids.append(group_center_ids[group_index])
            if gaze_index < 0:
                pair_ids.append(torch.full((n,), -1, device=device, dtype=torch.long))
            else:
                if group_index not in group_pair_ids:
                    group_pair_ids[group_index] = torch.arange(pair_base, pair_base + n, device=device)
                    pair_base += n
                pair_ids.append(group_pair_ids[group_index])
            gaze_ids.append(torch.full((n,), gaze_index, device=device, dtype=torch.long))
        draw_ids.append(torch.arange(n, device=device))
        proposal_keys.extend(
            f"{request.random_key.revision.value}:{request.random_key.source}:"
            f"{'unkeyed_global_rng' if resolved_seed is None else resolved_seed}:"
            f"{group_name}:{gaze_index}:0:{draw_index}"
            for draw_index in range(n)
        )
    measurement_tensors = MappingProxyType(_concat_measurements(contexts, is_mixture=is_mixture))
    jitter_names = {
        "view_jitter_yaw_deg",
        "view_jitter_pitch_deg",
        "view_jitter_is_bounded",
        "view_jitter_azimuth_limit_deg",
        "view_jitter_elevation_limit_deg",
    }
    measurements = _typed_measurements(
        {name: value for name, value in measurement_tensors.items() if name not in jitter_names}
    )
    if has_paired_gaze:
        center_id = torch.cat(center_ids)
        position_pair_id = torch.cat(pair_ids)
        gaze_variant_id = torch.cat(gaze_ids)
    else:
        center_id = torch.arange(valid.numel(), device=valid.device)
        position_pair_id = torch.full_like(center_id, -1)
        gaze_variant_id = torch.full_like(center_id, -1)
    table = CandidateTable(
        world_poses=poses,
        centers_world=centers,
        gaze_directions_world=poses.R.reshape(-1, 3, 3)[:, :, 2],
        reference_pose_world=contexts[0].reference_pose,
        sampling_pose_world=contexts[0].sampling_pose,
        camera_calibration=contexts[0].camera_calib_template,
        shell_offsets_ref=offsets,
        semantic_group_id=tuple(semantic_group),
        center_family_id=tuple(center_family),
        gaze_family_id=tuple(gaze_family),
        candidate_family_id=tuple(candidate_family),
        center_id=center_id,
        position_pair_id=position_pair_id,
        gaze_variant_id=gaze_variant_id,
        attempt_round_id=torch.zeros(valid.numel(), device=valid.device, dtype=torch.long),
        draw_id=torch.cat(draw_ids),
        proposal_key=tuple(proposal_keys),
        proposal_probability=torch.full((valid.numel(),), 1.0 / total_rows, device=valid.device, dtype=centers.dtype),
        view_residual_yaw_deg=measurement_tensors["view_jitter_yaw_deg"],
        view_residual_pitch_deg=measurement_tensors["view_jitter_pitch_deg"],
        view_jitter_is_bounded=measurement_tensors["view_jitter_is_bounded"],
        view_jitter_azimuth_limit_deg=measurement_tensors["view_jitter_azimuth_limit_deg"],
        view_jitter_elevation_limit_deg=measurement_tensors["view_jitter_elevation_limit_deg"],
        target_anchor_world=(
            torch.full((valid.numel(), 3), float("nan"), device=valid.device, dtype=centers.dtype)
            if target is None
            else target.reshape(1, 3).expand(valid.numel(), 3).clone()
        ),
        target_frame_identity=tuple("" for _ in range(valid.numel())),
        target_frame_availability=tuple(EvidenceAvailability.UNAVAILABLE for _ in range(valid.numel())),
        measurements=measurements,
    )
    legacy_groups = (
        tuple(
            _LegacyProjectionGroup(
                semantic_group_id=group.semantic_group_id,
                position_id=candidate_position_id(group.center.family.value),
                mixture_id=group_index,
                sampler_probability=1.0 / total_rows,
                variants=tuple(
                    _LegacyProjectionVariant(
                        candidate_family_id=f"{group.semantic_group_id}/{variant.semantic_variant_id}",
                        strategy_id=candidate_strategy_id(
                            "target_point"
                            if variant.gaze.family in {GazeFamily.TARGET_EXACT, GazeFamily.TARGET_GLANCE}
                            else variant.gaze.family.value
                        ),
                        component_name=(
                            group.semantic_group_id
                            if variant_index == 0
                            else f"{group.legacy_seed_component_name}__paired_{variant.legacy_paired_view_mode_value}"
                        ),
                    )
                    for variant_index, variant in enumerate(group.gaze_variants)
                ),
            )
            for group_index, group in enumerate(request.program.groups)
        )
        if is_mixture
        else ()
    )
    return CandidateSet._from_fixed_valid(  # noqa: SLF001 - shipped interpreter owns the fixed-attempt proof.
        table,
        AdmissionEvidence(valid, _criterion_evidence(masks)),
        request.program.completion.mode,
        request.program.candidate_program_hash,
        request.request_binding_hash,
        request.random_key.revision,
        legacy_groups,
    )


def _concat_masks(contexts: list[CandidateContext], *, is_mixture: bool) -> dict[str, torch.Tensor]:
    if not is_mixture:
        return dict(contexts[0].rule_masks)
    names = sorted({name for context in contexts for name in context.rule_masks})
    return {
        name: torch.cat([context.rule_masks.get(name, context.mask_valid).reshape(-1) for context in contexts])
        for name in names
    }


def _concat_measurements(contexts: list[CandidateContext], *, is_mixture: bool) -> dict[str, torch.Tensor]:
    selected = [
        {
            name: value
            for name, value in context.debug.items()
            if context.cfg.collect_debug_stats
            or name.startswith(("view_jitter_", "target_view_", "target_pixel_", "target_in_fov_"))
        }
        for context in contexts
    ]
    if not is_mixture:
        return {
            name: value if isinstance(value, torch.Tensor) else _pose_tensor(value)
            for name, value in selected[0].items()
            if isinstance(value, (torch.Tensor, PoseTW))
        }
    names = sorted({name for values in selected for name, value in values.items() if isinstance(value, torch.Tensor)})
    output: dict[str, torch.Tensor] = {}
    for name in names:
        template = cast(
            torch.Tensor,
            next(values[name] for values in selected if isinstance(values.get(name), torch.Tensor)),
        )
        chunks: list[torch.Tensor] = []
        for context, values in zip(contexts, selected, strict=True):
            value = values.get(name)
            if isinstance(value, torch.Tensor):
                chunks.append(value)
            elif template.dtype == torch.bool:
                chunks.append(
                    torch.zeros(
                        (context.mask_valid.numel(), *template.shape[1:]),
                        device=context.mask_valid.device,
                        dtype=template.dtype,
                    )
                )
            elif template.is_floating_point():
                chunks.append(
                    torch.full(
                        (context.mask_valid.numel(), *template.shape[1:]),
                        float("nan"),
                        device=context.mask_valid.device,
                        dtype=template.dtype,
                    )
                )
            else:
                chunks.append(
                    torch.full(
                        (context.mask_valid.numel(), *template.shape[1:]),
                        -1,
                        device=context.mask_valid.device,
                        dtype=template.dtype,
                    )
                )
        output[name] = torch.cat(chunks)
    return output


def _criterion_evidence(masks: dict[str, torch.Tensor]) -> tuple[CriterionEvidence, ...]:
    unavailable = torch.zeros_like(next(iter(masks.values()))) if masks else None
    return tuple(
        CriterionEvidence(
            criterion_id=name,
            legacy_cumulative_valid=cumulative_valid,
            local=None,
            local_availability=(unavailable if unavailable is not None else torch.zeros_like(cumulative_valid)),
            reason_revision=CriterionReasonRevision.UNAVAILABLE_V1,
            source_role_revision=CriterionSourceRoleRevision.UNAVAILABLE_V1,
        )
        for name, cumulative_valid in masks.items()
    )


def _typed_measurements(values: dict[str, torch.Tensor]) -> CandidateMeasurements:
    try:
        unknown = values.keys() - CandidateMeasurements.__dataclass_fields__.keys()
        if unknown:
            raise TypeError(f"Undeclared measurements: {sorted(unknown)!r}")
        return CandidateMeasurements(
            view_dirs_delta=values.get("view_dirs_delta"),
            path_collision_applicable_mask=values.get("path_collision_applicable_mask"),
            path_collision_evaluated_mask=values.get("path_collision_evaluated_mask"),
            path_collision_detected=values.get("path_collision_detected"),
            path_collision_mask=values.get("path_collision_mask"),
            path_collision_applicable=values.get("path_collision_applicable"),
            path_collision_evaluated=values.get("path_collision_evaluated"),
            min_distance_to_mesh=values.get("min_distance_to_mesh"),
            path_min_clearance_m=values.get("path_min_clearance_m"),
            motion_step_length_m=values.get("motion_step_length_m"),
            motion_height_delta_m=values.get("motion_height_delta_m"),
            motion_backward_step_m=values.get("motion_backward_step_m"),
            motion_yaw_delta_rad=values.get("motion_yaw_delta_rad"),
            motion_realism_reject_mask=values.get("motion_realism_reject_mask"),
            free_space_margin_m=values.get("free_space_margin_m"),
            target_bearing_yaw_rad=values.get("target_bearing_yaw_rad"),
            target_distance_m=values.get("target_distance_m"),
            target_view_angle_deg=values.get("target_view_angle_deg"),
            target_pixel_margin_px=values.get("target_pixel_margin_px"),
            target_in_fov_mask=values.get("target_in_fov_mask"),
            target_view_evaluated_mask=values.get("target_view_evaluated_mask"),
        )
    except TypeError as error:
        raise CandidateAlignmentCorruptionError("Shipped generator produced an undeclared measurement.") from error


__all__ = ["ProgramCandidateGenerator"]
