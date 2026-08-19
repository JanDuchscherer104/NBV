r"""Mixed finite-candidate view generation with full-shell provenance.

The mixture wrapper keeps `CandidateViewGeneratorConfig` backward-compatible by
instantiating one normal generator per component, overriding only the component
fields, and concatenating the full sampled shells. Component counts therefore
define the fixed candidate budget exactly, while each output row retains
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

from typing import Any

import torch
import trimesh  # type: ignore[import-untyped]
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW
from pydantic import Field, model_validator

from ..data_handling import EfmSnippetView
from ..utils import BaseConfig, TargetConfig
from .candidate_generation import CandidateViewGenerator, CandidateViewGeneratorConfig
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
}


def candidate_strategy_id(strategy: ViewDirectionMode | str) -> int:
    """Return the stable integer provenance id for a view-direction family."""

    return _STRATEGY_IDS[ViewDirectionMode(strategy)]


def candidate_position_id(position_mode: CandidatePositionMode | str) -> int:
    """Return the stable integer provenance id for a position family."""

    return _POSITION_IDS[CandidatePositionMode(position_mode)]


class CandidateMixtureComponentConfig(BaseConfig):
    """One fixed-count candidate-family component inside a mixture sampler."""

    name: str
    """Human-readable component name retained as row provenance."""

    count: int = Field(ge=1)
    """Number of full-shell candidates sampled by this component."""

    strategy: ViewDirectionMode | None = None
    """Backward-compatible alias for ``view_mode``."""

    view_mode: ViewDirectionMode | None = None
    """View-direction family used as stable candidate-strategy provenance."""

    position_mode: CandidatePositionMode | None = None
    """Position-family prior used to sample candidate centers."""

    sampling_strategy: SamplingStrategy | None = None
    """Optional positional sampling override."""

    view_sampling_strategy: SamplingStrategy | None = None
    """Optional view-direction sampling override."""

    min_radius: float | None = None
    max_radius: float | None = None
    min_elev_deg: float | None = None
    max_elev_deg: float | None = None
    delta_azimuth_deg: float | None = None
    kappa: float | None = None
    view_kappa: float | None = None
    view_max_angle_deg: float | None = None
    view_max_azimuth_deg: float | None = None
    view_max_elevation_deg: float | None = None
    view_roll_jitter_deg: float | None = None

    @model_validator(mode="after")
    def _resolve_modes(self) -> "CandidateMixtureComponentConfig":
        view_mode = self.view_mode if self.view_mode is not None else self.strategy
        if view_mode is None:
            raise ValueError("Candidate mixture components require view_mode or strategy.")
        object.__setattr__(self, "view_mode", view_mode)
        object.__setattr__(self, "strategy", view_mode)
        if self.position_mode is None:
            object.__setattr__(self, "position_mode", CandidatePositionMode.UPPER_BOUND_FREE_SHELL)
        return self


class CandidateMixtureViewGeneratorConfig(TargetConfig["CandidateMixtureViewGenerator"]):
    """Config-as-factory for fixed-count mixed candidate tables."""

    @property
    def target_type(self) -> type["CandidateMixtureViewGenerator"]:
        """Return the fixed-count mixed candidate generator runtime type."""
        return CandidateMixtureViewGenerator

    base: CandidateViewGeneratorConfig = Field(
        default_factory=lambda: CandidateViewGeneratorConfig(
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
    )
    """Base generator settings shared by all mixture components."""

    components: list[CandidateMixtureComponentConfig] = Field(
        default_factory=lambda: [
            CandidateMixtureComponentConfig(
                name="forward_local",
                count=24,
                view_mode=ViewDirectionMode.FORWARD_RIG,
                position_mode=CandidatePositionMode.FORWARD_LOCAL,
                view_max_azimuth_deg=0.0,
                view_max_elevation_deg=0.0,
            ),
            CandidateMixtureComponentConfig(
                name="target_bearing_local",
                count=24,
                view_mode=ViewDirectionMode.TARGET_POINT,
                position_mode=CandidatePositionMode.TARGET_BEARING_LOCAL,
                view_max_azimuth_deg=0.0,
                view_max_elevation_deg=0.0,
            ),
            CandidateMixtureComponentConfig(
                name="lateral_target_bypass",
                count=12,
                view_mode=ViewDirectionMode.TARGET_POINT,
                position_mode=CandidatePositionMode.LATERAL_TARGET_BYPASS,
                view_max_azimuth_deg=0.0,
                view_max_elevation_deg=0.0,
            ),
        ]
    )
    """Ordered mixture components. Full-shell row order follows this list."""

    @model_validator(mode="after")
    def _nonempty_components(self) -> "CandidateMixtureViewGeneratorConfig":
        if not self.components:
            raise ValueError("Candidate mixture requires at least one component.")
        return self

    @property
    def total_count(self) -> int:
        """Total full-shell candidate budget across mixture components."""

        return sum(component.count for component in self.components)

    @classmethod
    def reviewed_component_templates(
        cls,
        components: list[tuple[str, int]] | tuple[tuple[str, int], ...],
        *,
        existing_components: list[CandidateMixtureComponentConfig] | None = None,
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
            components=[
                CandidateMixtureComponentConfig(
                    name="upper_bound_free_shell",
                    count=count,
                    view_mode=ViewDirectionMode.RADIAL_AWAY,
                    position_mode=CandidatePositionMode.UPPER_BOUND_FREE_SHELL,
                )
            ],
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
            components=[
                CandidateMixtureComponentConfig(
                    name="target_bearing_local",
                    count=18,
                    view_mode=ViewDirectionMode.TARGET_POINT,
                    position_mode=CandidatePositionMode.TARGET_BEARING_LOCAL,
                    view_max_azimuth_deg=0.0,
                    view_max_elevation_deg=0.0,
                ),
                CandidateMixtureComponentConfig(
                    name="forward_local",
                    count=18,
                    view_mode=ViewDirectionMode.FORWARD_RIG,
                    position_mode=CandidatePositionMode.FORWARD_LOCAL,
                    view_max_azimuth_deg=0.0,
                    view_max_elevation_deg=0.0,
                ),
                CandidateMixtureComponentConfig(
                    name="lateral_target_bypass",
                    count=12,
                    view_mode=ViewDirectionMode.TARGET_POINT,
                    position_mode=CandidatePositionMode.LATERAL_TARGET_BYPASS,
                    view_max_azimuth_deg=0.0,
                    view_max_elevation_deg=0.0,
                ),
                CandidateMixtureComponentConfig(
                    name="local_refinement",
                    count=6,
                    view_mode=ViewDirectionMode.TARGET_POINT,
                    position_mode=CandidatePositionMode.LOCAL_REFINEMENT,
                    min_radius=0.25,
                    max_radius=0.7,
                    view_max_azimuth_deg=0.0,
                    view_max_elevation_deg=0.0,
                ),
                CandidateMixtureComponentConfig(
                    name="revisit_backtrack",
                    count=6,
                    view_mode=ViewDirectionMode.FORWARD_RIG,
                    position_mode=CandidatePositionMode.REVISIT_BACKTRACK,
                    min_radius=0.25,
                    max_radius=0.25,
                    view_max_azimuth_deg=0.0,
                    view_max_elevation_deg=0.0,
                ),
            ],
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
                view_max_azimuth_deg=0.0,
                view_max_elevation_deg=0.0,
                view_roll_jitter_deg=0.0,
                seed=0,
            ),
            components=[
                CandidateMixtureComponentConfig(
                    name="radial_towards_target_bearing",
                    count=16,
                    view_mode=ViewDirectionMode.RADIAL_TOWARDS,
                    position_mode=CandidatePositionMode.TARGET_BEARING_LOCAL,
                    min_radius=0.35,
                    max_radius=1.1,
                    view_max_azimuth_deg=0.0,
                    view_max_elevation_deg=0.0,
                ),
                CandidateMixtureComponentConfig(
                    name="radial_away_target_bearing",
                    count=16,
                    view_mode=ViewDirectionMode.RADIAL_AWAY,
                    position_mode=CandidatePositionMode.TARGET_BEARING_LOCAL,
                    min_radius=0.35,
                    max_radius=1.1,
                    view_max_azimuth_deg=0.0,
                    view_max_elevation_deg=0.0,
                ),
                CandidateMixtureComponentConfig(
                    name="revisit_backtrack",
                    count=12,
                    view_mode=ViewDirectionMode.FORWARD_RIG,
                    position_mode=CandidatePositionMode.REVISIT_BACKTRACK,
                    min_radius=0.25,
                    max_radius=0.25,
                    view_max_azimuth_deg=0.0,
                    view_max_elevation_deg=0.0,
                ),
                CandidateMixtureComponentConfig(
                    name="target_point_anchor",
                    count=4,
                    view_mode=ViewDirectionMode.TARGET_POINT,
                    position_mode=CandidatePositionMode.TARGET_BEARING_LOCAL,
                    min_radius=0.35,
                    max_radius=0.9,
                    view_max_azimuth_deg=0.0,
                    view_max_elevation_deg=0.0,
                ),
            ],
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
    """Generate a fixed-size candidate table from multiple sampling families."""

    def __init__(self, config: CandidateMixtureViewGeneratorConfig) -> None:
        self.config = config

    def generate_from_typed_sample(
        self,
        sample: EfmSnippetView,
        frame_index: int | None = None,
        runtime_context: CandidateGenerationRuntimeContext | None = None,
    ) -> CandidateSamplingResult:
        """Generate mixed candidates from an EFM snippet."""

        device = torch.device(self.config.base.device)
        occ = sample.get_occupancy_extend()
        occupancy_extent = occ.to(device=device, dtype=torch.float32)
        gt_mesh = sample.mesh
        mesh_verts = sample.mesh_verts
        mesh_faces = sample.mesh_faces
        if mesh_verts is None or mesh_faces is None:
            raise ValueError("Candidate mixture generation requires sample.mesh_verts and sample.mesh_faces.")

        cam_view = sample.get_camera(self.config.base.camera_label)
        if frame_index is None:
            frame_index = self.config.base.reference_frame_index
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
        from ..rollouts.replay.policy import derive_component_seed

        for component_index, component in enumerate(self.config.components):
            component_seed = None if seed is None else derive_component_seed(seed, component.name)
            component_cfg = self._component_config(
                component, component_index, runtime_context=runtime_context, component_seed=component_seed
            )
            result = CandidateViewGenerator(component_cfg).generate(
                reference_pose=reference_pose,
                gt_mesh=gt_mesh,
                mesh_verts=mesh_verts,
                mesh_faces=mesh_faces,
                camera_calib_template=camera_calib_template,
                occupancy_extent=occupancy_extent,
                seed=component_seed,
            )
            shell_count = int(result.mask_valid.reshape(-1).shape[0])
            device = result.mask_valid.device
            result.strategy_id = torch.full(
                (shell_count,),
                candidate_strategy_id(component.view_mode),
                dtype=torch.int64,
                device=device,
            )
            result.position_id = torch.full(
                (shell_count,),
                candidate_position_id(component.position_mode),
                dtype=torch.int64,
                device=device,
            )
            result.mixture_id = torch.full((shell_count,), component_index, dtype=torch.int64, device=device)
            result.sampler_probability = torch.full(
                (shell_count,),
                1.0 / float(self.config.total_count),
                dtype=torch.float32,
                device=device,
            )
            result.component_name = tuple(component.name for _ in range(shell_count))
            component_results.append(result)
            component_names.extend([component.name] * shell_count)

        return _concat_results(component_results, component_name=tuple(component_names))

    def _component_config(
        self,
        component: CandidateMixtureComponentConfig,
        component_index: int,
        *,
        runtime_context: CandidateGenerationRuntimeContext | None,
        component_seed: int | None = None,
    ) -> CandidateViewGeneratorConfig:
        target_point = self.config.base.view_target_point_world
        position_target = self.config.base.position_target_point_world
        if component.view_mode == ViewDirectionMode.TARGET_POINT:
            if runtime_context is None or runtime_context.target_center_world is None:
                raise ValueError("TARGET_POINT candidate components require runtime_context.target_center_world.")
            target_point = torch.as_tensor(runtime_context.target_center_world, dtype=torch.float32).reshape(3)
        if component.position_mode in (
            CandidatePositionMode.TARGET_BEARING_LOCAL,
            CandidatePositionMode.LATERAL_TARGET_BYPASS,
        ):
            if runtime_context is None or runtime_context.target_center_world is None:
                raise ValueError(
                    f"{component.position_mode.value} components require runtime_context.target_center_world."
                )
            position_target = torch.as_tensor(runtime_context.target_center_world, dtype=torch.float32).reshape(3)

        updates: dict[str, Any] = {
            "num_samples": component.count,
            "oversample_factor": 1.0,
            "view_direction_mode": component.view_mode,
            "position_mode": component.position_mode,
            "view_target_point_world": target_point,
            "position_target_point_world": position_target,
        }
        if component_seed is not None:
            updates["seed"] = int(component_seed)
        elif self.config.base.seed is not None:
            updates["seed"] = int(self.config.base.seed) + component_index

        for field_name in (
            "sampling_strategy",
            "view_sampling_strategy",
            "min_radius",
            "max_radius",
            "min_elev_deg",
            "max_elev_deg",
            "delta_azimuth_deg",
            "kappa",
            "view_kappa",
            "view_max_angle_deg",
            "view_max_azimuth_deg",
            "view_max_elevation_deg",
            "view_roll_jitter_deg",
        ):
            value = getattr(component, field_name)
            if value is not None:
                updates[field_name] = value
        return self.config.base.model_copy(update=updates)


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
