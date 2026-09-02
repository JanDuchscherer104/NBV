r"""Mixed finite-candidate view generation with full-shell provenance.

The mixture wrapper keeps `CandidateViewGeneratorConfig` backward-compatible
while prebuilding one private leaf runtime per center/gaze combination and
concatenating their full sampled shells. Component counts therefore define the
fixed candidate budget exactly, while each output row retains
`strategy_id`, `mixture_id`, `sampler_probability`, and optional component name.

Ordering is part of the data contract: invalid candidates remain in the
full-shell masks and provenance arrays; compact valid views are recoverable
through `CandidateSamplingResult.candidate_shell_indices()`. Target-point
components require `CandidateGenerationRuntimeContext.target_center_world`
because the thesis V1 actor may condition on observed/predicted target records
but not on GT target geometry.

This module owns mixture-component configs, stable strategy/position ids, and
concatenation of component shells into one provenance-aligned result. Each
component delegates geometric sampling and pruning to
:class:`CandidateViewGenerator`; rendering, RRI labels, and final action
selection remain downstream responsibilities.

Theory:
    The default target-conditioned mixture has 60 full-shell rows:
    `forward_local` 24, `target_bearing_local` 24, and
    `lateral_target_bypass` 12. Richer local-refinement, revisit-backtrack,
    and free-shell components are explicit ablations. Each row records stable `position_id`,
    `strategy_id`, `mixture_id`, component name, and
    `sampler_probability = 1/N`. These provenance arrays let rollout/Q_H
    stores audit which finite-action family produced each candidate without
    changing the compact valid-action contract.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Self

import torch
import trimesh  # type: ignore[import-untyped]
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW
from pydantic import Field, model_validator

from ..data_handling import EfmSnippetView
from ..geometry import PreparedMeshQuery
from ..utils import TargetConfig
from ..utils.seeding import derive_stable_seed
from .candidate_generation import CandidateViewGenerator, CandidateViewGeneratorConfig
from .config import (
    BoxViewJitterConfig,
    CandidateGazeConfig,
    CandidateMixtureComponentConfig,
    CenterConfig,
    SampledCenterConfig,
    SampledCenterMode,
    TargetOrbitCenterConfig,
)
from .types import (
    CandidateGenerationRuntimeContext,
    CandidatePositionMode,
    CandidateSamplingResult,
    SamplingStrategy,
    ViewDirectionMode,
)

_STRATEGY_IDS = {
    ViewDirectionMode.FORWARD_RIG: 0,
    ViewDirectionMode.RADIAL_AWAY: 1,
    ViewDirectionMode.RADIAL_TOWARDS: 2,
    ViewDirectionMode.TARGET_POINT: 3,
}
_POSITION_IDS = {
    CandidatePositionMode.UPPER_BOUND_FREE_SHELL: 0,
    CandidatePositionMode.FORWARD_LOCAL: 1,
    CandidatePositionMode.TARGET_BEARING_LOCAL: 2,
    CandidatePositionMode.LATERAL_TARGET_BYPASS: 3,
    CandidatePositionMode.LOCAL_REFINEMENT: 4,
    CandidatePositionMode.REVISIT_BACKTRACK: 5,
    CandidatePositionMode.TARGET_ORBIT: 6,
}


@dataclass(frozen=True)
class _ComponentRuntime:
    """Prebuilt immutable runtime bundle for one mixture component."""

    component: CandidateMixtureComponentConfig
    generators: tuple[CandidateViewGenerator, ...]


def _derive_component_seed(node_seed: int, component_identity: str) -> int:
    """Derive the established component-local seed without rollout imports."""

    return derive_stable_seed("component", int(node_seed), str(component_identity))


def candidate_strategy_id(strategy: ViewDirectionMode | str) -> int:
    """Return the stable integer provenance id for a view-direction family."""

    return _STRATEGY_IDS[ViewDirectionMode(strategy)]


def candidate_position_id(position_mode: CandidatePositionMode | str) -> int:
    """Return the stable integer provenance id for a position family."""

    return _POSITION_IDS[CandidatePositionMode(position_mode)]


def _center_position_mode(center: CenterConfig) -> CandidatePositionMode:
    """Resolve the existing leaf-generator position mode for one center value."""

    match center:
        case SampledCenterConfig(mode=mode):
            return CandidatePositionMode(mode)
        case TargetOrbitCenterConfig():
            return CandidatePositionMode.TARGET_ORBIT


def _center_position_id(center: CenterConfig) -> int:
    """Resolve stable position provenance for one center value."""

    return candidate_position_id(_center_position_mode(center))


def _default_mixture_base() -> CandidateViewGeneratorConfig:
    """Return the established shared mixed-generator defaults."""

    return CandidateViewGeneratorConfig(
        sampling_strategy=SamplingStrategy.FORWARD_POWERSPHERICAL,
        min_radius=0.25,
        max_radius=1.25,
        min_elev_deg=-12.0,
        max_elev_deg=18.0,
        delta_azimuth_deg=120.0,
        kappa=8.0,
        enforce_motion_realism=True,
        max_step_distance_m=1.0,
        max_height_delta_m=0.25,
        max_backward_step_m=0.25,
        max_yaw_delta_deg=70.0,
        collect_debug_stats=True,
    )


def _sampled_center(
    mode: SampledCenterMode,
    *,
    sampling_strategy: SamplingStrategy = SamplingStrategy.FORWARD_POWERSPHERICAL,
    min_radius_m: float = 0.25,
    max_radius_m: float = 1.25,
    min_elevation_deg: float = -12.0,
    max_elevation_deg: float = 18.0,
    azimuth_width_deg: float = 120.0,
    concentration: float = 8.0,
) -> SampledCenterConfig:
    """Build a complete sampled-center value for an existing family."""

    return SampledCenterConfig(
        mode=mode,
        sampling_strategy=sampling_strategy,
        min_radius_m=min_radius_m,
        max_radius_m=max_radius_m,
        min_elevation_deg=min_elevation_deg,
        max_elevation_deg=max_elevation_deg,
        azimuth_width_deg=azimuth_width_deg,
        concentration=concentration,
    )


def _boxed_gaze(mode: ViewDirectionMode, *, name: str = "primary") -> CandidateGazeConfig:
    """Build one gaze with the nonzero seminar jitter envelope."""

    return CandidateGazeConfig(name=name, mode=mode, jitter=BoxViewJitterConfig())


def _default_mixture_components() -> tuple[CandidateMixtureComponentConfig, ...]:
    """Return the established resolved 24/24/12 mixture in nested form."""

    return (
        CandidateMixtureComponentConfig(
            name="forward_local",
            count=24,
            center=_sampled_center(CandidatePositionMode.FORWARD_LOCAL),
            gazes=(_boxed_gaze(ViewDirectionMode.FORWARD_RIG),),
        ),
        CandidateMixtureComponentConfig(
            name="target_bearing_local",
            count=24,
            center=_sampled_center(CandidatePositionMode.TARGET_BEARING_LOCAL),
            gazes=(_boxed_gaze(ViewDirectionMode.TARGET_POINT),),
        ),
        CandidateMixtureComponentConfig(
            name="lateral_target_bypass",
            count=12,
            center=_sampled_center(CandidatePositionMode.LATERAL_TARGET_BYPASS),
            gazes=(_boxed_gaze(ViewDirectionMode.TARGET_POINT),),
        ),
    )


class CandidateMixtureViewGeneratorConfig(TargetConfig["CandidateMixtureViewGenerator"]):
    """Config-as-factory for fixed-count mixed candidate tables."""

    @property
    def target_type(self) -> type["CandidateMixtureViewGenerator"]:
        """Return the fixed-count mixed candidate generator runtime type."""
        return CandidateMixtureViewGenerator

    base: CandidateViewGeneratorConfig = Field(default_factory=_default_mixture_base)
    """Base generator settings shared by all mixture components."""

    components: tuple[CandidateMixtureComponentConfig, ...] = Field(default_factory=_default_mixture_components)
    """Ordered mixture components. Full-shell row order follows this list."""

    @model_validator(mode="after")
    def _validate_components(self) -> Self:
        if not self.components:
            raise ValueError("candidate mixture requires at least one component")

        component_names = tuple(component.name for component in self.components)
        if len(component_names) != len(set(component_names)):
            raise ValueError("candidate component names must be unique")

        emitted_names: list[str] = []
        for component in self.components:
            if isinstance(component.center, TargetOrbitCenterConfig) and component.count < 2:
                raise ValueError("target-orbit components require at least two centers for bilateral proposals")

            emitted_names.append(component.name)
            emitted_names.extend(f"{component.name}__{gaze.name}" for gaze in component.gazes[1:])

        if len(emitted_names) != len(set(emitted_names)):
            raise ValueError("candidate component/gaze provenance names must be globally unique")
        return self

    @property
    def total_count(self) -> int:
        """Total full-shell candidate budget across mixture components."""

        return sum(component.count * len(component.gazes) for component in self.components)

    @classmethod
    def reviewed_component_templates(
        cls,
        components: list[tuple[str, int]] | tuple[tuple[str, int], ...],
        *,
        existing_components: list[CandidateMixtureComponentConfig]
        | tuple[CandidateMixtureComponentConfig, ...]
        | None = None,
    ) -> list[CandidateMixtureComponentConfig]:
        """Return typed templates for a reviewed campaign component schedule.

        Campaign orchestration supplies the reviewed names and counts; this
        method reuses writer-owned components by name and supplies reviewed
        presets only for absent families. Counts are the campaign allocation;
        all other typed component fields remain owned by their source template.
        """

        names = tuple(name for name, _count in components)
        templates = {
            tuple(component.name for component in preset.components): preset.components
            for preset in (
                cls(),
                cls.rich_local_five_family(),
                cls.radial_target_backtrack_family(),
                cls.upper_bound_free_shell(),
            )
        }
        try:
            preset_components = templates[names]
        except KeyError as exc:
            raise ValueError(f"unsupported reviewed candidate component schedule: {names}") from exc

        existing_by_name: dict[str, CandidateMixtureComponentConfig] = {}
        for component in existing_components or ():
            if component.name in existing_by_name:
                raise ValueError(f"duplicate existing candidate component: {component.name}")
            existing_by_name[component.name] = component

        return [
            existing_by_name.get(name, preset).model_copy(update={"count": count})
            for preset, (name, count) in zip(preset_components, components, strict=True)
        ]

    @classmethod
    def upper_bound_free_shell(cls, *, count: int = 60) -> "CandidateMixtureViewGeneratorConfig":
        """Build the explicit legacy free-shell upper-bound ablation config."""

        return cls(
            base=CandidateViewGeneratorConfig(),
            components=(
                CandidateMixtureComponentConfig(
                    name="upper_bound_free_shell",
                    count=count,
                    center=_sampled_center(
                        CandidatePositionMode.UPPER_BOUND_FREE_SHELL,
                        sampling_strategy=SamplingStrategy.UNIFORM_SPHERE,
                        min_radius_m=0.5,
                        max_radius_m=1.8,
                        min_elevation_deg=-20.0,
                        max_elevation_deg=25.0,
                        azimuth_width_deg=170.0,
                        concentration=4.0,
                    ),
                    gazes=(_boxed_gaze(ViewDirectionMode.RADIAL_AWAY),),
                ),
            ),
        )

    @classmethod
    def rich_local_five_family(cls) -> "CandidateMixtureViewGeneratorConfig":
        """Build the previous five-family local sampler for ablation runs."""

        return cls(
            base=cls().base.model_copy(
                update={
                    "max_step_distance_m": 1.25,
                    "max_height_delta_m": 0.6,
                    "max_backward_step_m": 0.35,
                    "max_yaw_delta_deg": 85.0,
                }
            ),
            components=(
                CandidateMixtureComponentConfig(
                    name="target_bearing_local",
                    count=18,
                    center=_sampled_center(CandidatePositionMode.TARGET_BEARING_LOCAL),
                    gazes=(_boxed_gaze(ViewDirectionMode.TARGET_POINT),),
                ),
                CandidateMixtureComponentConfig(
                    name="forward_local",
                    count=18,
                    center=_sampled_center(CandidatePositionMode.FORWARD_LOCAL),
                    gazes=(_boxed_gaze(ViewDirectionMode.FORWARD_RIG),),
                ),
                CandidateMixtureComponentConfig(
                    name="lateral_target_bypass",
                    count=12,
                    center=_sampled_center(CandidatePositionMode.LATERAL_TARGET_BYPASS),
                    gazes=(_boxed_gaze(ViewDirectionMode.TARGET_POINT),),
                ),
                CandidateMixtureComponentConfig(
                    name="local_refinement",
                    count=6,
                    center=_sampled_center(
                        CandidatePositionMode.LOCAL_REFINEMENT,
                        min_radius_m=0.25,
                        max_radius_m=0.7,
                    ),
                    gazes=(_boxed_gaze(ViewDirectionMode.TARGET_POINT),),
                ),
                CandidateMixtureComponentConfig(
                    name="revisit_backtrack",
                    count=6,
                    center=_sampled_center(
                        CandidatePositionMode.REVISIT_BACKTRACK,
                        min_radius_m=0.25,
                        max_radius_m=0.25,
                    ),
                    gazes=(_boxed_gaze(ViewDirectionMode.FORWARD_RIG),),
                ),
            ),
        )

    @classmethod
    def paired_center_gaze_family(cls) -> "CandidateMixtureViewGeneratorConfig":
        """Build a 60-row sampler with paired target and forward gaze hypotheses."""

        return cls(
            base=cls.rich_local_five_family().base,
            components=(
                CandidateMixtureComponentConfig(
                    name="target_forward_pair",
                    count=12,
                    center=_sampled_center(CandidatePositionMode.TARGET_BEARING_LOCAL),
                    gazes=(
                        _boxed_gaze(ViewDirectionMode.TARGET_POINT),
                        _boxed_gaze(ViewDirectionMode.FORWARD_RIG, name="paired_forward_rig"),
                    ),
                ),
                CandidateMixtureComponentConfig(
                    name="forward_local",
                    count=12,
                    center=_sampled_center(CandidatePositionMode.FORWARD_LOCAL),
                    gazes=(_boxed_gaze(ViewDirectionMode.FORWARD_RIG),),
                ),
                CandidateMixtureComponentConfig(
                    name="lateral_target_bypass",
                    count=12,
                    center=_sampled_center(CandidatePositionMode.LATERAL_TARGET_BYPASS),
                    gazes=(_boxed_gaze(ViewDirectionMode.TARGET_POINT),),
                ),
                CandidateMixtureComponentConfig(
                    name="local_refinement",
                    count=6,
                    center=_sampled_center(
                        CandidatePositionMode.LOCAL_REFINEMENT,
                        min_radius_m=0.25,
                        max_radius_m=0.7,
                    ),
                    gazes=(_boxed_gaze(ViewDirectionMode.TARGET_POINT),),
                ),
                CandidateMixtureComponentConfig(
                    name="revisit_backtrack",
                    count=6,
                    center=_sampled_center(
                        CandidatePositionMode.REVISIT_BACKTRACK,
                        min_radius_m=0.25,
                        max_radius_m=0.25,
                    ),
                    gazes=(_boxed_gaze(ViewDirectionMode.FORWARD_RIG),),
                ),
            ),
        )

    @classmethod
    def radial_target_backtrack_family(cls) -> "CandidateMixtureViewGeneratorConfig":
        """Build the radial/backtrack rollout-diversity sampler.

        This preset mirrors `.configs/build_rollouts_v1_diverse.toml`: most
        rows probe radial-towards, radial-away, and revisit-backtrack action
        families, with a small target-point anchor group for continuity with
        the target-conditioned default sampler. It is a named data-generation
        profile only; `CandidateMixtureViewGeneratorConfig()` keeps the
        historical 60-row default.
        """

        return cls(
            base=CandidateViewGeneratorConfig(
                camera_label="rgb",
                num_samples=48,
                oversample_factor=2.0,
                max_resamples=2,
                align_to_gravity=True,
                min_radius=0.25,
                max_radius=1.1,
                min_elev_deg=-12.0,
                max_elev_deg=18.0,
                delta_azimuth_deg=110.0,
                sampling_strategy=SamplingStrategy.FORWARD_POWERSPHERICAL,
                kappa=8.0,
                min_distance_to_mesh=0.2,
                ensure_collision_free=True,
                ensure_free_space=True,
                collision_backend="pytorch3d",
                ray_subsample=32,
                step_clearance=0.1,
                enforce_motion_realism=True,
                max_step_distance_m=1.25,
                max_height_delta_m=0.35,
                max_backward_step_m=0.45,
                max_yaw_delta_deg=90.0,
                device="cpu",
                verbosity=1,
                collect_rule_masks=True,
                collect_debug_stats=True,
                view_max_angle_deg=0.0,
                view_max_azimuth_deg=60.0,
                view_max_elevation_deg=30.0,
                view_roll_jitter_deg=0.0,
                seed=0,
            ),
            components=(
                CandidateMixtureComponentConfig(
                    name="radial_towards_target_bearing",
                    count=16,
                    center=_sampled_center(
                        CandidatePositionMode.TARGET_BEARING_LOCAL,
                        min_radius_m=0.35,
                        max_radius_m=1.1,
                        azimuth_width_deg=110.0,
                    ),
                    gazes=(_boxed_gaze(ViewDirectionMode.RADIAL_TOWARDS),),
                ),
                CandidateMixtureComponentConfig(
                    name="radial_away_target_bearing",
                    count=16,
                    center=_sampled_center(
                        CandidatePositionMode.TARGET_BEARING_LOCAL,
                        min_radius_m=0.35,
                        max_radius_m=1.1,
                        azimuth_width_deg=110.0,
                    ),
                    gazes=(_boxed_gaze(ViewDirectionMode.RADIAL_AWAY),),
                ),
                CandidateMixtureComponentConfig(
                    name="revisit_backtrack",
                    count=12,
                    center=_sampled_center(
                        CandidatePositionMode.REVISIT_BACKTRACK,
                        min_radius_m=0.25,
                        max_radius_m=0.25,
                        azimuth_width_deg=110.0,
                    ),
                    gazes=(_boxed_gaze(ViewDirectionMode.FORWARD_RIG),),
                ),
                CandidateMixtureComponentConfig(
                    name="target_point_anchor",
                    count=4,
                    center=_sampled_center(
                        CandidatePositionMode.TARGET_BEARING_LOCAL,
                        min_radius_m=0.35,
                        max_radius_m=0.9,
                        azimuth_width_deg=110.0,
                    ),
                    gazes=(_boxed_gaze(ViewDirectionMode.TARGET_POINT),),
                ),
            ),
        )

    @property
    def device(self) -> torch.device:
        """Return the resolved device shared by all mixture components."""

        return self.base.device

    @property
    def camera_label(self) -> str:
        """Base camera label used for typed-snippet generation."""

        return self.base.camera_label


class CandidateMixtureViewGenerator:
    """Generate a fixed-size candidate table from multiple sampling families.

    The generator retains one safely versioned prepared mesh query across
    requests. Each request lends that query to every component as request-local
    state, including paired-view components, without extending its lifetime.
    """

    def __init__(self, config: CandidateMixtureViewGeneratorConfig) -> None:
        self._config = deepcopy(config)
        self._mesh_query: PreparedMeshQuery | None = None
        self._component_runtimes = tuple(
            _ComponentRuntime(
                component=component,
                generators=tuple(
                    CandidateViewGenerator._from_component(
                        self._config.base,
                        center_config=component.center,
                        gaze_config=gaze,
                        center_count=component.count,
                    )
                    for gaze in component.gazes
                ),
            )
            for component in self._config.components
        )

    @property
    def config(self) -> CandidateMixtureViewGeneratorConfig:
        """Return a detached copy of the authoring snapshot used by this runtime."""

        return deepcopy(self._config)

    def generate_from_typed_sample(
        self,
        sample: EfmSnippetView,
        frame_index: int | None = None,
        runtime_context: CandidateGenerationRuntimeContext | None = None,
    ) -> CandidateSamplingResult:
        """Generate mixed candidates from an EFM snippet."""

        device = torch.device(self._config.base.device)
        occ = sample.get_occupancy_extend()
        occupancy_extent = occ.to(device=device, dtype=torch.float32)
        gt_mesh = sample.mesh
        mesh_verts = sample.mesh_verts
        mesh_faces = sample.mesh_faces
        if mesh_verts is None or mesh_faces is None:
            raise ValueError("Candidate mixture generation requires sample.mesh_verts and sample.mesh_faces.")

        cam_view = sample.get_camera(self._config.base.camera_label)
        if frame_index is None:
            frame_index = self._config.base.reference_frame_index
        if frame_index is None:
            reference_pose = sample.trajectory.final_pose.to(device=device)
        else:
            _cam_idx, traj_idx = cam_view.nearest_traj_indices(
                sample.trajectory.time_ns,
                [frame_index],
                default_last=True,
            )
            reference_pose = (
                sample.trajectory.final_pose.to(device=device)
                if traj_idx.numel() == 0
                else sample.trajectory.t_world_rig[traj_idx].to(device=device)
            )

        return self.generate(
            reference_pose=reference_pose,
            gt_mesh=gt_mesh,
            mesh_verts=mesh_verts,
            mesh_faces=mesh_faces,
            camera_calib_template=cam_view.calib,
            occupancy_extent=occupancy_extent,
            runtime_context=runtime_context,
        )

    def generate(
        self,
        *,
        reference_pose: PoseTW,
        gt_mesh: trimesh.Trimesh,
        mesh_verts: torch.Tensor,
        mesh_faces: torch.Tensor,
        camera_calib_template: CameraTW,
        occupancy_extent: torch.Tensor,
        runtime_context: CandidateGenerationRuntimeContext | None = None,
        seed: int | None = None,
    ) -> CandidateSamplingResult:
        """Generate one concatenated full-shell candidate table."""

        component_results: list[CandidateSamplingResult] = []
        component_names: list[str] = []
        mesh_query = None
        if self._config.base.requires_mesh_query:
            mesh_query = PreparedMeshQuery.acquire(
                self._mesh_query,
                mesh_verts,
                mesh_faces,
                device=self._config.device,
                dtype=reference_pose.t.dtype,
                mesh=gt_mesh,
            )
            self._mesh_query = mesh_query if mesh_query.is_persistently_reusable else None

        pair_base = 0

        def append_component(
            result: CandidateSamplingResult,
            *,
            name: str,
            view_mode: ViewDirectionMode,
            position_id: int,
            pair_ids: torch.Tensor | None = None,
            gaze_variant: int = -1,
        ) -> None:
            shell_count = int(result.mask_valid.reshape(-1).shape[0])
            device = result.mask_valid.device
            result.strategy_id = torch.full(
                (shell_count,),
                candidate_strategy_id(view_mode),
                dtype=torch.int64,
                device=device,
            )
            result.position_id = torch.full(
                (shell_count,),
                position_id,
                dtype=torch.int64,
                device=device,
            )
            # Paired variants retain the original serialized component index.
            result.mixture_id = torch.full((shell_count,), component_index, dtype=torch.int64, device=device)
            result.sampler_probability = torch.full(
                (shell_count,),
                1.0 / float(self._config.total_count),
                dtype=torch.float32,
                device=device,
            )
            result.component_name = tuple(name for _ in range(shell_count))
            position_pair_id = (
                torch.full((shell_count,), -1, dtype=torch.int64, device=device)
                if pair_ids is None
                else pair_ids.to(device=device, dtype=torch.int64)
            )
            gaze_variant_id = torch.full((shell_count,), gaze_variant, dtype=torch.int64, device=device)
            result.position_pair_id = position_pair_id
            result.gaze_variant_id = gaze_variant_id
            result.extras["position_pair_id"] = position_pair_id
            result.extras["gaze_variant_id"] = gaze_variant_id
            component_results.append(result)
            component_names.extend([name] * shell_count)

        target_center_world = None if runtime_context is None else runtime_context.target_center_world
        for component_index, runtime in enumerate(self._component_runtimes):
            component = runtime.component
            component_seed = None if seed is None else _derive_component_seed(seed, component.name)
            resolved_component_seed = component_seed
            if resolved_component_seed is None and self._config.base.seed is not None:
                resolved_component_seed = int(self._config.base.seed) + component_index
            primary_result: CandidateSamplingResult | None = None
            pair_ids: torch.Tensor | None = None
            for gaze_index, (gaze, generator) in enumerate(zip(component.gazes, runtime.generators, strict=True)):
                emitted_name = component.name if gaze_index == 0 else f"{component.name}__{gaze.name}"
                gaze_seed = component_seed
                if gaze_index > 0:
                    gaze_seed = (
                        None
                        if resolved_component_seed is None
                        else _derive_component_seed(resolved_component_seed, emitted_name)
                    )
                if primary_result is None:
                    result = generator._generate_impl(
                        reference_pose=reference_pose,
                        gt_mesh=gt_mesh,
                        mesh_verts=mesh_verts,
                        mesh_faces=mesh_faces,
                        camera_calib_template=camera_calib_template,
                        occupancy_extent=occupancy_extent,
                        position_target_center_world=target_center_world,
                        gaze_target_center_world=target_center_world,
                        prepared_mesh_query=mesh_query,
                        seed=gaze_seed if gaze_seed is not None else resolved_component_seed,
                    )
                    primary_result = result
                    if len(component.gazes) > 1:
                        pair_ids = torch.arange(
                            pair_base,
                            pair_base + component.count,
                            dtype=torch.int64,
                            device=result.mask_valid.device,
                        )
                        pair_base += component.count
                else:
                    assert primary_result.shell_offsets_ref is not None
                    result = generator._generate_from_centers_impl(
                        reference_pose=reference_pose,
                        centers_world=primary_result.shell_poses.t.reshape(-1, 3),
                        offsets_ref=primary_result.shell_offsets_ref,
                        gt_mesh=gt_mesh,
                        mesh_verts=mesh_verts,
                        mesh_faces=mesh_faces,
                        camera_calib_template=camera_calib_template,
                        occupancy_extent=occupancy_extent,
                        position_target_center_world=target_center_world,
                        gaze_target_center_world=target_center_world,
                        prepared_mesh_query=mesh_query,
                        seed=gaze_seed,
                    )
                append_component(
                    result,
                    name=emitted_name,
                    view_mode=gaze.mode,
                    position_id=_center_position_id(component.center),
                    pair_ids=pair_ids,
                    gaze_variant=gaze_index if pair_ids is not None else -1,
                )

        return _concat_results(component_results, component_name=tuple(component_names))


def _concat_results(
    results: list[CandidateSamplingResult],
    *,
    component_name: tuple[str, ...],
) -> CandidateSamplingResult:
    if not results:
        raise ValueError("Cannot concatenate an empty candidate-mixture result.")

    first = results[0]
    views = CameraTW(torch.cat([result.views.tensor() for result in results], dim=0))
    shell_poses = PoseTW(torch.cat([result.shell_poses.tensor() for result in results], dim=0))
    mask_valid = torch.cat([result.mask_valid.reshape(-1) for result in results], dim=0)
    shell_offsets = _cat_optional([result.shell_offsets_ref for result in results])
    strategy_id = _cat_required([result.strategy_id for result in results], "strategy_id")
    position_id = _cat_required([result.position_id for result in results], "position_id")
    mixture_id = _cat_required([result.mixture_id for result in results], "mixture_id")
    sampler_probability = _cat_required([result.sampler_probability for result in results], "sampler_probability")
    masks = _concat_masks(results, mask_valid)
    extras = _concat_extras(results)

    return CandidateSamplingResult(
        views=views,
        reference_pose=first.reference_pose,
        mask_valid=mask_valid,
        masks=masks,
        shell_poses=shell_poses,
        shell_offsets_ref=shell_offsets,
        sampling_pose=first.sampling_pose,
        strategy_id=strategy_id,
        position_id=position_id,
        mixture_id=mixture_id,
        sampler_probability=sampler_probability,
        component_name=component_name,
        position_pair_id=_cat_optional([result.position_pair_id for result in results]),
        gaze_variant_id=_cat_optional([result.gaze_variant_id for result in results]),
        extras=extras,
    )


def _cat_optional(values: list[torch.Tensor | None]) -> torch.Tensor | None:
    if any(value is None for value in values):
        return None
    return torch.cat([value for value in values if value is not None], dim=0)


def _cat_required(values: list[torch.Tensor | None], name: str) -> torch.Tensor:
    if any(value is None for value in values):
        raise ValueError(f"Candidate mixture component did not provide {name}.")
    return torch.cat([value for value in values if value is not None], dim=0)


def _concat_masks(results: list[CandidateSamplingResult], mask_valid: torch.Tensor) -> dict[str, torch.Tensor]:
    names = sorted({name for result in results for name in result.masks})
    output: dict[str, torch.Tensor] = {}
    for name in names:
        chunks = []
        for result in results:
            chunks.append(result.masks.get(name, result.mask_valid).reshape(-1))
        output[name] = torch.cat(chunks, dim=0).to(device=mask_valid.device)
    return output


def _concat_extras(results: list[CandidateSamplingResult]) -> dict[str, Any]:
    names = sorted({name for result in results for name, value in result.extras.items() if torch.is_tensor(value)})
    extras: dict[str, Any] = {}
    for name in names:
        template = next(result.extras[name] for result in results if torch.is_tensor(result.extras.get(name)))
        chunks = []
        for result in results:
            value = result.extras.get(name)
            if torch.is_tensor(value):
                chunks.append(value)
                continue
            shell_count = int(result.mask_valid.reshape(-1).shape[0])
            chunks.append(_missing_extra_tensor(template, shell_count=shell_count, device=result.mask_valid.device))
        extras[name] = torch.cat(chunks, dim=0)
    return extras


def _missing_extra_tensor(template: torch.Tensor, *, shell_count: int, device: torch.device) -> torch.Tensor:
    shape = (shell_count, *template.shape[1:])
    if template.dtype == torch.bool:
        return torch.zeros(shape, dtype=template.dtype, device=device)
    if template.dtype.is_floating_point:
        return torch.full(shape, float("nan"), dtype=template.dtype, device=device)
    return torch.full(shape, -1, dtype=template.dtype, device=device)


__all__ = [
    "CandidateMixtureComponentConfig",
    "CandidateMixtureViewGenerator",
    "CandidateMixtureViewGeneratorConfig",
    "candidate_position_id",
    "candidate_strategy_id",
]
