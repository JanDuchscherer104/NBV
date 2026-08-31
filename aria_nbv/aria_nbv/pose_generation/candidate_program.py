"""Literal bounded programs for finite candidate generation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from math import ceil, isfinite
from numbers import Real
from typing import TYPE_CHECKING, Literal, TypeAlias, cast

from ..utils.canonical_binding import canonical_binding_sha256
from .candidate_errors import InvalidCandidateProgramError
from .types import CandidatePositionMode, CollisionBackend, SamplingStrategy, ViewDirectionMode

if TYPE_CHECKING:
    from .candidate_generation import CandidateViewGeneratorConfig
    from .candidate_mixture import CandidateMixtureComponentConfig, CandidateMixtureViewGeneratorConfig

    LegacyCandidateConfig: TypeAlias = CandidateViewGeneratorConfig | CandidateMixtureViewGeneratorConfig
else:
    LegacyCandidateConfig: TypeAlias = object


class CenterFamily(StrEnum):
    """Closed positional-center families supported by the shipped algorithm."""

    UPPER_BOUND_FREE_SHELL = "upper_bound_free_shell"
    FORWARD_LOCAL = "forward_local"
    TARGET_BEARING_LOCAL = "target_bearing_local"
    TARGET_ORBIT = "target_orbit"
    LATERAL_TARGET_BYPASS = "lateral_target_bypass"
    LOCAL_REFINEMENT = "local_refinement"
    REVISIT_BACKTRACK = "revisit_backtrack"


class GazeFamily(StrEnum):
    """Closed gaze families supported by the shipped algorithm."""

    FORWARD_RIG = "forward_rig"
    RADIAL_AWAY = "radial_away"
    RADIAL_TOWARDS = "radial_towards"
    TARGET_EXACT = "target_exact"
    TARGET_GLANCE = "target_glance"


class CompletionMode(StrEnum):
    """Closed score-independent completion algorithms."""

    FIXED_ATTEMPTS = "fixed_attempts"


@dataclass(frozen=True, slots=True)
class SampledCenterConfig:
    """Literal sampled-center configuration for non-orbit families.

    Attributes:
        family: Closed positional family discriminant.
        sampling_strategy: Random support distribution used for center draws.
        align_to_gravity: Whether sampled offsets use the world-Z-up frame.
        min_radius_m: Inclusive minimum radial offset in metres.
        max_radius_m: Inclusive maximum radial offset in metres.
        min_elevation_deg: Minimum elevation angle in degrees.
        max_elevation_deg: Maximum elevation angle in degrees.
        delta_azimuth_deg: Forward-support azimuth half-width in degrees.
        concentration: Positive directional-distribution concentration.
    """

    family: Literal[
        CenterFamily.UPPER_BOUND_FREE_SHELL,
        CenterFamily.FORWARD_LOCAL,
        CenterFamily.TARGET_BEARING_LOCAL,
        CenterFamily.LATERAL_TARGET_BYPASS,
        CenterFamily.LOCAL_REFINEMENT,
        CenterFamily.REVISIT_BACKTRACK,
    ]
    sampling_strategy: SamplingStrategy
    align_to_gravity: bool
    min_radius_m: float
    max_radius_m: float
    min_elevation_deg: float
    max_elevation_deg: float
    delta_azimuth_deg: float
    concentration: float


@dataclass(frozen=True, slots=True)
class TargetOrbitCenterConfig:
    """Literal bilateral target-orbit center configuration.

    Attributes:
        family: Fixed ``TARGET_ORBIT`` positional discriminant.
        sampling_strategy: Radial/elevation support distribution.
        align_to_gravity: Whether orbit offsets use world-Z-up.
        min_radius_m: Inclusive minimum center radius in metres.
        max_radius_m: Inclusive maximum center radius in metres.
        min_elevation_deg: Minimum elevation angle in degrees.
        max_elevation_deg: Maximum elevation angle in degrees.
        delta_azimuth_deg: Legacy support angle retained for exact parity.
        concentration: Positive directional-distribution concentration.
        target_orbit_angles_deg: Ordered nonzero bilateral orbit angles in degrees.
    """

    family: Literal[CenterFamily.TARGET_ORBIT]
    sampling_strategy: SamplingStrategy
    align_to_gravity: bool
    min_radius_m: float
    max_radius_m: float
    min_elevation_deg: float
    max_elevation_deg: float
    delta_azimuth_deg: float
    concentration: float
    target_orbit_angles_deg: tuple[float, ...]


CenterConfig: TypeAlias = SampledCenterConfig | TargetOrbitCenterConfig


@dataclass(frozen=True, slots=True)
class DirectionalGazeConfig:
    """Literal non-target gaze and residual configuration.

    Attributes:
        family: Closed forward or radial gaze discriminant.
        sampling_strategy: Optional spherical residual distribution.
        concentration: Positive residual-distribution concentration.
        max_azimuth_deg: Bounded residual yaw half-width in degrees; zero is
            uncapped for legacy spherical strategies.
        max_elevation_deg: Bounded residual pitch half-width in degrees; zero
            is uncapped for legacy spherical strategies.
        roll_jitter_deg: Symmetric roll residual limit in degrees.
    """

    family: Literal[GazeFamily.FORWARD_RIG, GazeFamily.RADIAL_AWAY, GazeFamily.RADIAL_TOWARDS]
    sampling_strategy: SamplingStrategy | None
    concentration: float
    max_azimuth_deg: float
    max_elevation_deg: float
    roll_jitter_deg: float


@dataclass(frozen=True, slots=True)
class TargetGlanceGazeConfig:
    """Literal target-glance gaze and residual configuration.

    Attributes:
        family: Fixed ``TARGET_GLANCE`` discriminant.
        sampling_strategy: Optional spherical target-relative residual.
        concentration: Positive residual-distribution concentration.
        max_azimuth_deg: Bounded target-relative yaw half-width in degrees.
        max_elevation_deg: Bounded target-relative pitch half-width in degrees.
        roll_jitter_deg: Symmetric roll residual limit in degrees.
    """

    family: Literal[GazeFamily.TARGET_GLANCE]
    sampling_strategy: SamplingStrategy | None
    concentration: float
    max_azimuth_deg: float
    max_elevation_deg: float
    roll_jitter_deg: float


@dataclass(frozen=True, slots=True)
class TargetExactGazeConfig:
    """Exact target look-at gaze with no residual or clamp parameters.

    Attributes:
        family: Fixed ``TARGET_EXACT`` discriminant.
    """

    family: Literal[GazeFamily.TARGET_EXACT]


GazeConfig: TypeAlias = DirectionalGazeConfig | TargetExactGazeConfig | TargetGlanceGazeConfig


@dataclass(frozen=True, slots=True)
class GazeVariantConfig:
    """One gaze hypothesis evaluated for a group's exact center table.

    Attributes:
        semantic_variant_id: Stable nonempty identity within the group.
        gaze: Closed literal gaze configuration.
        legacy_paired_view_mode_value: Optional shipped paired-mode codec used
            only by the one-way compatibility projection.
    """

    semantic_variant_id: str
    gaze: GazeConfig
    legacy_paired_view_mode_value: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateGroup:
    """One ordered center family and its ordered gaze variants.

    Attributes:
        semantic_group_id: Stable nonempty group identity.
        center_count: Number of center rows sampled exactly once.
        center: Closed literal positional configuration.
        gaze_variants: Ordered gaze variants sharing the center table.
        legacy_seed_component_name: Frozen shipped component seed identity.
        legacy_direct_component_index: Frozen direct-base seed offset.
    """

    semantic_group_id: str
    center_count: int
    center: CenterConfig
    gaze_variants: tuple[GazeVariantConfig, ...]
    legacy_seed_component_name: str | None
    legacy_direct_component_index: int | None


@dataclass(frozen=True, slots=True)
class AdmissionConfig:
    """Literal shipped hard-admission policy.

    Attributes:
        min_distance_to_mesh_m: Minimum endpoint clearance in metres.
        ensure_collision_free: Enable endpoint mesh-clearance admission.
        ensure_free_space: Enable path-segment clearance admission.
        collision_backend: Geometry backend used by clearance criteria.
        ray_subsample: Positive path-ray sampling stride.
        step_clearance_m: Required path clearance in metres.
        enforce_motion_realism: Enable actor-motion bounds.
        max_step_distance_m: Optional maximum translation in metres.
        max_height_delta_m: Optional maximum vertical delta in metres.
        max_backward_step_m: Optional maximum backward delta in metres.
        max_yaw_delta_deg: Optional maximum yaw delta in degrees.
        collect_rule_masks: Retain shipped cumulative masks for compatibility.
        collect_debug_stats: Retain optional diagnostic measurements.
    """

    min_distance_to_mesh_m: float
    ensure_collision_free: bool
    ensure_free_space: bool
    collision_backend: CollisionBackend
    ray_subsample: int
    step_clearance_m: float
    enforce_motion_realism: bool
    max_step_distance_m: float | None
    max_height_delta_m: float | None
    max_backward_step_m: float | None
    max_yaw_delta_deg: float | None
    collect_rule_masks: bool
    collect_debug_stats: bool


@dataclass(frozen=True, slots=True)
class CompletionConfig:
    """Literal score-independent completion policy.

    Attributes:
        mode: Closed completion algorithm.
        attempt_rounds: Number of bounded proposal rounds; shipped V1 is one.
    """

    mode: CompletionMode
    attempt_rounds: int


@dataclass(frozen=True, slots=True)
class CandidateProgramLimits:
    """Resource limits enforced before candidate allocation.

    Attributes:
        max_groups: Maximum ordered center groups.
        max_gaze_variants_per_group: Maximum gaze variants per center table.
        max_attempt_rounds: Maximum score-independent proposal rounds.
        max_attempted_rows: Maximum full attempted-shell row count ``N``.
    """

    max_groups: int = 32
    max_gaze_variants_per_group: int = 8
    max_attempt_rounds: int = 8
    max_attempted_rows: int = 4096


@dataclass(frozen=True, slots=True)
class CandidateProgram:
    """Final immutable program interpreted by candidate generation.

    Attributes:
        schema_version: Closed literal-schema version.
        algorithm_revision: Sampling and admission algorithm revision.
        row_order_revision: Attempted-row ordering revision.
        groups: Ordered immutable center/gaze programs.
        admission: Literal hard-admission policy.
        completion: Literal score-independent completion policy.
        limits: Allocation bounds validated before generation.
        candidate_program_hash: Canonical SHA-256 binding of all literal facts.
    """

    schema_version: str
    algorithm_revision: str
    row_order_revision: str
    groups: tuple[CandidateGroup, ...]
    admission: AdmissionConfig
    completion: CompletionConfig
    limits: CandidateProgramLimits
    candidate_program_hash: str

    def validate(self) -> None:
        """Validate bounds, identities, revisions, and shipped compatibility facts."""

        try:
            _validate(self)
        except (AttributeError, TypeError, ValueError) as error:
            raise InvalidCandidateProgramError(str(error)) from error

    def verified_hash(self) -> str:
        """Recompute the program hash from all literal values."""

        return canonical_binding_sha256(replace(self, candidate_program_hash=""))


def compile_candidate_program(
    authoring: LegacyCandidateConfig, *, limits: CandidateProgramLimits | None = None
) -> CandidateProgram:
    """Expand one resolved shipped config into the final literal schema."""

    from .candidate_generation import CandidateViewGeneratorConfig
    from .candidate_mixture import CandidateMixtureViewGeneratorConfig

    if not isinstance(authoring, (CandidateViewGeneratorConfig, CandidateMixtureViewGeneratorConfig)):
        raise InvalidCandidateProgramError(
            "compile_candidate_program accepts only resolved candidate authoring configs."
        )
    resolved_limits = limits or CandidateProgramLimits()
    groups: tuple[CandidateGroup, ...]
    if isinstance(authoring, CandidateViewGeneratorConfig):
        base = authoring
        groups = (
            _group(
                base,
                f"{base.position_mode.value}_{base.view_direction_mode.value}",
                ceil(float(base.num_samples) * float(base.oversample_factor)),
                base.position_mode,
                base.view_direction_mode,
                None,
                None,
            ),
        )
    else:
        base = authoring.base
        groups = tuple(
            _group(
                _component_base(base, component),
                str(component.name),
                int(component.count),
                cast(CandidatePositionMode, component.position_mode),
                cast(ViewDirectionMode, component.view_mode),
                component.paired_view_mode,
                index,
            )
            for index, component in enumerate(authoring.components)
        )
    program = CandidateProgram(
        schema_version="candidate_program_v1",
        algorithm_revision="shipped_candidate_generation_v1",
        row_order_revision="shipped_component_gaze_order_v1",
        groups=groups,
        admission=_admission(base),
        completion=CompletionConfig(CompletionMode.FIXED_ATTEMPTS, 1),
        limits=resolved_limits,
        candidate_program_hash="",
    )
    program.validate()
    return replace(program, candidate_program_hash=program.verified_hash())


def _component_base(
    base: CandidateViewGeneratorConfig,
    component: CandidateMixtureComponentConfig,
) -> CandidateViewGeneratorConfig:
    updates = {
        "num_samples": int(component.count),
        "oversample_factor": 1.0,
        "position_mode": component.position_mode,
        "view_direction_mode": component.view_mode,
    }
    for name in (
        "sampling_strategy",
        "view_sampling_strategy",
        "min_radius",
        "max_radius",
        "min_elev_deg",
        "max_elev_deg",
        "delta_azimuth_deg",
        "kappa",
        "view_kappa",
        "view_max_azimuth_deg",
        "view_max_elevation_deg",
        "view_roll_jitter_deg",
    ):
        value = getattr(component, name)
        if value is not None:
            updates[name] = value
    return base.model_copy(update=updates)


def _group(
    base: CandidateViewGeneratorConfig,
    name: str,
    count: int,
    position_mode: CandidatePositionMode,
    view_mode: ViewDirectionMode,
    paired_view_mode: ViewDirectionMode | None,
    index: int | None,
) -> CandidateGroup:
    family = CenterFamily(position_mode.value)
    sampling_strategy = SamplingStrategy(base.sampling_strategy)
    center: CenterConfig
    if family is CenterFamily.TARGET_ORBIT:
        center = TargetOrbitCenterConfig(
            family=family,
            target_orbit_angles_deg=tuple(float(x) for x in base.target_orbit_angles_deg),
            sampling_strategy=sampling_strategy,
            align_to_gravity=bool(base.align_to_gravity),
            min_radius_m=float(base.min_radius),
            max_radius_m=float(base.max_radius),
            min_elevation_deg=float(base.min_elev_deg),
            max_elevation_deg=float(base.max_elev_deg),
            delta_azimuth_deg=float(base.delta_azimuth_deg),
            concentration=float(base.kappa),
        )
    else:
        center = SampledCenterConfig(
            family=family,
            sampling_strategy=sampling_strategy,
            align_to_gravity=bool(base.align_to_gravity),
            min_radius_m=float(base.min_radius),
            max_radius_m=float(base.max_radius),
            min_elevation_deg=float(base.min_elev_deg),
            max_elevation_deg=float(base.max_elev_deg),
            delta_azimuth_deg=float(base.delta_azimuth_deg),
            concentration=float(base.kappa),
        )
    variants: tuple[GazeVariantConfig, ...] = (_gaze(base, view_mode, "primary", None),)
    if paired_view_mode is not None:
        variants += (_gaze(base, paired_view_mode, "paired", paired_view_mode.value),)
    return CandidateGroup(name, count, center, variants, name if index is not None else None, index)


def _gaze(
    base: CandidateViewGeneratorConfig,
    mode: ViewDirectionMode,
    variant: str,
    paired: str | None,
) -> GazeVariantConfig:
    family = GazeFamily.TARGET_GLANCE if mode.value == "target_point" else GazeFamily(mode.value)
    sampling = None if base.view_sampling_strategy is None else SamplingStrategy(base.view_sampling_strategy)
    gaze_type = TargetGlanceGazeConfig if family is GazeFamily.TARGET_GLANCE else DirectionalGazeConfig
    return GazeVariantConfig(
        variant,
        gaze_type(
            family,  # type: ignore[arg-type]
            sampling,
            float(cast(float, base.view_kappa)),
            float(cast(float, base.view_max_azimuth_deg)),
            float(cast(float, base.view_max_elevation_deg)),
            float(base.view_roll_jitter_deg),
        ),
        paired,
    )


def _admission(base: CandidateViewGeneratorConfig) -> AdmissionConfig:
    return AdmissionConfig(
        float(base.min_distance_to_mesh),
        bool(base.ensure_collision_free),
        bool(base.ensure_free_space),
        CollisionBackend(base.collision_backend),
        int(base.ray_subsample),
        float(base.step_clearance),
        bool(base.enforce_motion_realism),
        base.max_step_distance_m,
        base.max_height_delta_m,
        base.max_backward_step_m,
        base.max_yaw_delta_deg,
        bool(base.collect_rule_masks),
        bool(base.collect_debug_stats),
    )


def _validate(program: CandidateProgram) -> None:
    limits = program.limits
    hard_limits = CandidateProgramLimits()
    if not isinstance(limits, CandidateProgramLimits) or any(
        isinstance(value, bool) or not isinstance(value, int)
        for value in (
            limits.max_groups,
            limits.max_gaze_variants_per_group,
            limits.max_attempt_rounds,
            limits.max_attempted_rows,
        )
    ):
        raise ValueError("Candidate program limits must be canonical integer values.")
    if any(
        value < 1 or value > hard
        for value, hard in zip(
            (
                limits.max_groups,
                limits.max_gaze_variants_per_group,
                limits.max_attempt_rounds,
                limits.max_attempted_rows,
            ),
            (
                hard_limits.max_groups,
                hard_limits.max_gaze_variants_per_group,
                hard_limits.max_attempt_rounds,
                hard_limits.max_attempted_rows,
            ),
            strict=True,
        )
    ):
        raise ValueError("Candidate program limits may be lowered but not raised above hard caps.")
    if program.schema_version != "candidate_program_v1":
        raise ValueError("Unsupported candidate program schema_version.")
    if program.algorithm_revision != "shipped_candidate_generation_v1":
        raise ValueError("Unsupported candidate algorithm_revision.")
    if program.row_order_revision != "shipped_component_gaze_order_v1":
        raise ValueError("Unsupported candidate row_order_revision.")
    if not isinstance(program.completion, CompletionConfig) or not isinstance(program.completion.mode, CompletionMode):
        raise ValueError("Candidate completion must use a declared typed variant.")
    if isinstance(program.completion.attempt_rounds, bool) or not isinstance(program.completion.attempt_rounds, int):
        raise ValueError("Candidate attempt rounds must be an integer.")
    if program.completion.mode is not CompletionMode.FIXED_ATTEMPTS or program.completion.attempt_rounds != 1:
        raise ValueError("Shipped fixed-attempt generation supports exactly one attempt round.")
    admission = program.admission
    if not isinstance(admission, AdmissionConfig) or not isinstance(admission.collision_backend, CollisionBackend):
        raise ValueError("Candidate admission must use declared typed configuration.")
    for value in (
        admission.ensure_collision_free,
        admission.ensure_free_space,
        admission.enforce_motion_realism,
        admission.collect_rule_masks,
        admission.collect_debug_stats,
    ):
        if not isinstance(value, bool):
            raise ValueError("Candidate admission switches must be boolean.")
    admission_values = (
        admission.min_distance_to_mesh_m,
        admission.step_clearance_m,
        admission.max_step_distance_m,
        admission.max_height_delta_m,
        admission.max_backward_step_m,
        admission.max_yaw_delta_deg,
    )
    if any(value is not None and (not _is_finite_real(value) or value < 0.0) for value in admission_values):
        raise ValueError("Candidate admission distances and limits must be finite and non-negative.")
    if isinstance(admission.ray_subsample, bool) or not isinstance(admission.ray_subsample, int):
        raise ValueError("Candidate ray_subsample must be an integer.")
    if admission.ray_subsample < 1:
        raise ValueError("Candidate ray_subsample must be positive.")
    if admission.max_yaw_delta_deg is not None and admission.max_yaw_delta_deg > 180.0:
        raise ValueError("Candidate maximum yaw delta cannot exceed 180 degrees.")
    if not 1 <= len(program.groups) <= limits.max_groups:
        raise ValueError("Candidate program group count is outside configured limits.")
    if not 1 <= program.completion.attempt_rounds <= limits.max_attempt_rounds:
        raise ValueError("Candidate attempt rounds are outside configured limits.")
    rows = 0
    group_ids: set[str] = set()
    legacy_indices: set[int] = set()
    if len(program.groups) > 1 and any(
        group.legacy_seed_component_name is None or group.legacy_direct_component_index is None
        for group in program.groups
    ):
        raise ValueError("Multi-group shipped programs require frozen legacy names and ordered indices.")
    for group_index, group in enumerate(program.groups):
        if not isinstance(group, CandidateGroup):
            raise ValueError("Candidate groups must use the declared typed schema.")
        if not isinstance(group.center, (SampledCenterConfig, TargetOrbitCenterConfig)):
            raise ValueError("Candidate center config must be a closed center variant.")
        if isinstance(group.center, TargetOrbitCenterConfig) != (group.center.family is CenterFamily.TARGET_ORBIT):
            raise ValueError("Candidate center variant does not match its family discriminant.")
        if not isinstance(group.center.family, CenterFamily) or not isinstance(
            group.center.sampling_strategy, SamplingStrategy
        ):
            raise ValueError("Candidate center enum values must use canonical enum types.")
        if (
            not isinstance(group.semantic_group_id, str)
            or not group.semantic_group_id
            or group.semantic_group_id in group_ids
        ):
            raise ValueError("Candidate semantic group identities must be nonempty and unique.")
        group_ids.add(group.semantic_group_id)
        compatibility = (group.legacy_seed_component_name, group.legacy_direct_component_index)
        if (compatibility[0] is None) != (compatibility[1] is None):
            raise ValueError("Candidate legacy name and direct index must be both present or both absent.")
        if compatibility[1] is not None:
            if not isinstance(compatibility[0], str) or not compatibility[0]:
                raise ValueError("Candidate legacy component names must be nonempty strings.")
            if isinstance(compatibility[1], bool) or not isinstance(compatibility[1], int):
                raise ValueError("Candidate legacy direct indices must be integers.")
            if compatibility[1] != group_index or compatibility[1] in legacy_indices:
                raise ValueError("Candidate legacy direct indices must freeze source-list order.")
            legacy_indices.add(compatibility[1])
        if (
            isinstance(group.center_count, bool)
            or not isinstance(group.center_count, int)
            or group.center_count < 1
            or not 1 <= len(group.gaze_variants) <= limits.max_gaze_variants_per_group
        ):
            raise ValueError("Candidate group size is outside configured limits.")
        if not isinstance(group.center.align_to_gravity, bool):
            raise ValueError("Candidate center gravity alignment must be boolean.")
        values = (
            group.center.min_radius_m,
            group.center.max_radius_m,
            group.center.min_elevation_deg,
            group.center.max_elevation_deg,
            group.center.delta_azimuth_deg,
            group.center.concentration,
        )
        if not all(_is_finite_real(value) for value in values):
            raise ValueError("Candidate program contains nonfinite center values.")
        if group.center.min_radius_m < 0 or group.center.max_radius_m < group.center.min_radius_m:
            raise ValueError("Candidate center radii are invalid.")
        if group.center.min_elevation_deg > group.center.max_elevation_deg:
            raise ValueError("Candidate center elevation interval is invalid.")
        if group.center.concentration < 0.0:
            raise ValueError("Candidate center concentration must be non-negative.")
        if group.center.family is CenterFamily.TARGET_ORBIT:
            angles = group.center.target_orbit_angles_deg
            if (
                group.center_count < 2
                or len(angles) < 2
                or any(not _is_finite_real(value) or value == 0.0 or abs(value) >= 180.0 for value in angles)
                or not any(value < 0 for value in angles)
                or not any(value > 0 for value in angles)
            ):
                raise ValueError(
                    "Target-orbit support requires at least two finite, nonzero, bilateral angles below 180 degrees."
                )
        variant_ids: set[str] = set()
        for variant_index, variant in enumerate(group.gaze_variants):
            if not isinstance(
                variant.gaze,
                (DirectionalGazeConfig, TargetExactGazeConfig, TargetGlanceGazeConfig),
            ):
                raise ValueError("Candidate gaze config must be a closed gaze variant.")
            gaze_variant_matches = (
                (isinstance(variant.gaze, TargetGlanceGazeConfig) and variant.gaze.family is GazeFamily.TARGET_GLANCE)
                or (isinstance(variant.gaze, TargetExactGazeConfig) and variant.gaze.family is GazeFamily.TARGET_EXACT)
                or (
                    isinstance(variant.gaze, DirectionalGazeConfig)
                    and variant.gaze.family
                    in {GazeFamily.FORWARD_RIG, GazeFamily.RADIAL_AWAY, GazeFamily.RADIAL_TOWARDS}
                )
            )
            if not gaze_variant_matches:
                raise ValueError("Candidate gaze variant does not match its family discriminant.")
            sampling_strategy = getattr(variant.gaze, "sampling_strategy", None)
            if not isinstance(variant.gaze.family, GazeFamily) or (
                sampling_strategy is not None and not isinstance(sampling_strategy, SamplingStrategy)
            ):
                raise ValueError("Candidate gaze enum values must use canonical enum types.")
            if (
                not isinstance(variant.semantic_variant_id, str)
                or not variant.semantic_variant_id
                or variant.semantic_variant_id in variant_ids
            ):
                raise ValueError("Candidate gaze variant identities must be nonempty and unique per group.")
            variant_ids.add(variant.semantic_variant_id)
            if variant_index == 0 and variant.legacy_paired_view_mode_value is not None:
                raise ValueError("Primary gaze variants cannot claim paired compatibility identity.")
            if variant_index > 0 and not variant.legacy_paired_view_mode_value:
                raise ValueError("Paired gaze variants require frozen paired-mode compatibility identity.")
            if variant.legacy_paired_view_mode_value is not None and not isinstance(
                variant.legacy_paired_view_mode_value, str
            ):
                raise ValueError("Paired gaze compatibility identity must be a string.")
            if not isinstance(variant.gaze, TargetExactGazeConfig):
                gaze_values = (
                    variant.gaze.concentration,
                    variant.gaze.max_azimuth_deg,
                    variant.gaze.max_elevation_deg,
                    variant.gaze.roll_jitter_deg,
                )
                if not all(_is_finite_real(value) and value >= 0 for value in gaze_values):
                    raise ValueError("Candidate gaze values must be finite and non-negative.")
                if variant.gaze.max_azimuth_deg > 180.0 or variant.gaze.max_elevation_deg > 90.0:
                    raise ValueError("Candidate gaze jitter exceeds spherical yaw/pitch support.")
        rows += group.center_count * len(group.gaze_variants) * program.completion.attempt_rounds
    if rows > limits.max_attempted_rows:
        raise ValueError(f"Candidate program attempts {rows} rows, exceeding {limits.max_attempted_rows}.")


def _is_finite_real(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and isfinite(float(value))


__all__ = [
    "AdmissionConfig",
    "CandidateGroup",
    "CandidateProgram",
    "CandidateProgramLimits",
    "CenterConfig",
    "CenterFamily",
    "CompletionConfig",
    "CompletionMode",
    "GazeConfig",
    "GazeFamily",
    "GazeVariantConfig",
    "DirectionalGazeConfig",
    "SampledCenterConfig",
    "TargetGlanceGazeConfig",
    "TargetExactGazeConfig",
    "TargetOrbitCenterConfig",
    "compile_candidate_program",
]
