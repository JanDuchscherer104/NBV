r"""Candidate pose generation with modular sampling and pruning rules.

This module implements a clear three-stage pipeline:

1. **Sample** directions + radii around the latest pose using either
   area-uniform or forward-biased spherical distributions in the rig frame.
2. **Construct** roll-free camera poses that look away from the last pose
   while keeping the camera x-axis horizontal in the world frame.
3. **Prune** candidates via rule objects (mesh clearance, collision, free
   space). Rules may optionally emit diagnostics such as per-candidate mesh
   distances.

All poses are expressed as `efm3d.aria.pose.PoseTW` in the VIO world
frame (LUF camera convention: x=left, y=up, z=forward).

`CandidateViewGenerator` returns compact valid views for rendering and keeps the
full sampled shell as masks/diagnostics. Mixture generation should wrap this
single-family generator rather than changing its ordering semantics.

This module owns the single-family generator, its config factory, sampling
orchestration, and assembly of :class:`CandidateSamplingResult`. Direction and
orientation primitives, pruning-rule implementations, mixture concatenation,
rendering, and actor/oracle action selection belong to sibling subsystems.

Theory:
    Sampling uses a physical reference pose and, by default, a gravity-aligned
    sampling pose. Center samples are transformed into world-frame candidate
    poses, then pruned without compacting the full shell. Feasibility is a hard
    mask contract:

    $$
    c_i\in B_{\mathrm{occ}},\qquad
    \min_{x\in\mathcal{M}_{GT}}\lVert c_i-x\rVert_2>d_{\min},
    $$

    with optional motion bounds

    $$
    \lVert o_i\rVert_2\le d_{\max},\quad
    |\Delta h_i|\le h_{\max},\quad
    \max(0,-o_{i,z})\le b_{\max}.
    $$

    Collision, bounds, and motion failures stay in masks and reason codes.
    Invalid candidates are not converted into low-RRI labels.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from math import radians
from typing import Annotated, Any, Literal

import torch
import trimesh  # type: ignore[import-untyped]
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW
from pydantic import AliasChoices, Field, field_validator, model_validator

from ..data_handling import EfmSnippetView
from ..utils import BaseConfig, Console, TargetConfig, Verbosity
from ..utils.frames import rotate_yaw_cw90, world_up_tensor
from .candidate_generation_rules import (
    FreeSpaceRule,
    MinDistanceToMeshRule,
    MotionRealismRule,
    PathCollisionRule,
    Rule,
)
from .orientations import OrientationBuilder
from .positional_sampling import PositionSampler
from .types import (
    CandidateContext,
    CandidateGenerationRuntimeContext,
    CandidatePositionMode,
    CandidateSamplingResult,
    CollisionBackend,
    SamplingStrategy,
    ViewDirectionMode,
)
from .utils import ensure_unbatched_pose


class CandidateViewGeneratorConfig(TargetConfig["CandidateViewGenerator"]):
    """Configuration for sampling and pruning candidate camera poses around a reference frame.

    Encapsulates the radii/angle sampling envelope, orientation jitter options, collision and free-space
    filtering, and logging/debug controls used by `CandidateViewGenerator`.

    The config is a Pydantic boundary: ``device`` and ``verbosity`` are coerced
    through the shared config helpers, omitted ``view_kappa`` inherits
    positional ``kappa`` and omitted per-axis caps keep their field defaults,
    while explicit ``None`` on a view cap selects the shared
    ``view_max_angle_deg`` fallback. ``is_debug`` promotes verbosity to
    ``VERBOSE``. Candidate poses remain physical world/camera geometry in
    metres; display-only CW90 rotations belong to plotting callers.
    """

    @property
    def target_type(self) -> type["CandidateViewGenerator"]:
        """Factory target for `BaseConfig.setup_target`."""
        return CandidateViewGenerator

    camera_label: Literal["rgb", "slaml", "slamr"] = "rgb"
    """Camera index to use for candidate generation."""

    num_samples: int = 60
    """Number of candidate poses requested after pruning."""
    oversample_factor: float = 2.0
    """Multiplicative oversampling factor applied before pruning to offset rejections."""
    max_resamples: int = 2
    """Maximum oversampling rounds if pruning removes too many candidates."""

    align_to_gravity: bool = True
    """If True, use a gravity-aligned copy of the reference pose for sampling.

    This removes pitch/roll from the sampling frame while keeping the reference yaw (forward direction projected
    onto the horizontal plane). It stabilises the sampling shell when the reference pose is strongly tilted
    (e.g., high roll angles).
    """

    min_radius: float = 0.5
    """Inner radius (metres) of the sampling shell around the reference pose."""
    max_radius: float = 1.8
    """Outer radius (metres) of the sampling shell around the reference pose."""

    min_elev_deg: float = -20.0
    """Minimum elevation angle (deg) relative to the world horizontal plane."""
    max_elev_deg: float = 25.0
    """Maximum elevation angle (deg) relative to the world horizontal plane."""
    delta_azimuth_deg: float = 170.0
    """Total azimuth spread (deg) around the reference forward direction; 360 unlocks full sphere."""

    sampling_strategy: SamplingStrategy = SamplingStrategy.UNIFORM_SPHERE
    """Distribution used to draw direction samples in the rig frame."""
    kappa: float = 4.0
    """Concentration parameter for the forward-biased PowerSpherical sampler."""

    position_mode: CandidatePositionMode = CandidatePositionMode.UPPER_BOUND_FREE_SHELL
    """Position-family prior used to sample candidate centers before orientation assignment."""

    position_target_point_world: torch.Tensor | None = None
    """Optional actor-visible world-space target center for target-bearing position modes."""

    min_distance_to_mesh: float = 0.2
    """Minimum clearance (metres) between candidate center and mesh surface."""
    ensure_collision_free: bool = True
    """Reject candidates whose straight path from the reference intersects the mesh."""
    ensure_free_space: bool = True
    """Constrain candidates to lie inside the snippet occupancy AABB."""
    collision_backend: CollisionBackend = CollisionBackend.P3D
    """Backend to use for collision and distance checks."""
    ray_subsample: int = 32
    """Number of samples per ray when using discretised collision checks."""
    step_clearance: float = 0.1
    """Distance threshold (metres) below which discretised collision samples are rejected."""

    enforce_motion_realism: bool = False
    """Whether to reject candidates violating egocentric local-motion bounds."""

    max_step_distance_m: float | None = Field(default=None, gt=0.0)
    """Maximum allowed candidate-center displacement from the reference pose."""

    max_height_delta_m: float | None = Field(default=None, ge=0.0)
    """Maximum absolute world-up displacement from the reference pose."""

    max_backward_step_m: float | None = Field(default=None, ge=0.0)
    """Maximum allowed backward displacement in the reference frame."""

    max_yaw_delta_deg: float | None = Field(default=None, ge=0.0)
    """Maximum allowed candidate forward-axis yaw change from the reference pose."""

    mesh_samples: int | None = None
    """Optional number of mesh samples used by mesh-distance rules when applicable."""

    device: Annotated[torch.device, Field(default="auto")]
    """Torch device on which sampling and rule evaluation run (auto-select CUDA if available)."""
    verbosity: Verbosity = Field(
        default=Verbosity.VERBOSE,
        validation_alias=AliasChoices("verbosity", "verbose"),
        description="Verbosity level for logging.",
    )
    """Verbosity level for logging (0=quiet, 1=normal, 2=verbose)."""
    is_debug: bool = False
    """Enable debug logging and force verbose output when True."""

    collect_rule_masks: bool = False
    """Store per-rule boolean masks in the sampling result for diagnostics."""
    collect_debug_stats: bool = False
    """Allow rules to emit extra tensors (e.g., distances) in ``CandidateSamplingResult.extras``."""

    reference_frame_index: int | None = None
    """Optional camera frame index to use as reference pose; None defaults to the final pose."""

    # View orientation controls
    view_direction_mode: ViewDirectionMode = ViewDirectionMode.RADIAL_AWAY
    """Base orientation strategy for candidates."""

    view_sampling_strategy: SamplingStrategy | None = None
    """Optional view-direction sampler in the base camera frame (legacy path).

    Behaviour:
        - If either ``view_max_azimuth_deg`` or ``view_max_elevation_deg`` is > 0, view jitter is sampled as a
          bounded box in local yaw/pitch regardless of ``view_sampling_strategy``.
        - If both caps are 0, this field controls whether view directions are drawn from a distribution
          (PowerSpherical / uniform sphere) or kept deterministic (``None``).
    """

    view_kappa: float | None = None
    """Concentration for PowerSpherical view sampler; defaults to positional `kappa` when None."""

    view_max_angle_deg: float = Field(default=0.0, ge=0.0)
    """Fallback cap (deg) applied to both azimuth and elevation jitter when per-axis caps are unset."""

    view_max_azimuth_deg: float | None = Field(default=60.0, ge=0.0)
    """Maximum horizontal deviation (deg, +/-) from the base direction."""

    view_max_elevation_deg: float | None = Field(default=30.0, ge=0.0)
    """Maximum vertical deviation (deg, +/-) from the base direction."""

    view_roll_jitter_deg: float = Field(default=0.0, ge=0.0)
    """Symmetric roll jitter (deg) around the sampled forward axis in camera frame."""

    view_target_point_world: torch.Tensor | None = None
    """Optional world-space target for TARGET_POINT mode (shape (3,))."""

    seed: int | None = Field(default=0, ge=0)
    """Optional deterministic seed for candidate sampling.

    Set to ``None`` to keep the current global RNG state (non-deterministic).
    """

    _resolve_device = field_validator("device", mode="before")(BaseConfig._resolve_geometry_device)

    _coerce_verbosity = field_validator("verbosity", mode="before")(BaseConfig._coerce_verbosity)

    @model_validator(mode="after")
    def set_debug(self) -> CandidateViewGeneratorConfig:
        """Resolve debug verbosity and inherited view-jitter defaults.

        ``view_kappa=None`` inherits the positional ``kappa``. Explicit
        ``None`` on either per-axis view cap selects ``view_max_angle_deg``;
        omitting those fields instead preserves their distinct 60/30-degree
        field defaults. This normalization happens once during model
        construction so generator code can consume concrete values without
        branch-dependent defaults.
        """
        if self.is_debug:
            object.__setattr__(self, "verbosity", Verbosity.VERBOSE)
        if self.view_kappa is None:
            object.__setattr__(self, "view_kappa", self.kappa)
        if self.view_max_azimuth_deg is None:
            object.__setattr__(self, "view_max_azimuth_deg", self.view_max_angle_deg)
        if self.view_max_elevation_deg is None:
            object.__setattr__(self, "view_max_elevation_deg", self.view_max_angle_deg)
        return self

    @property
    def min_elev_rad(self) -> float:
        """Return the lower candidate elevation bound in radians."""
        return radians(self.min_elev_deg)

    @property
    def max_elev_rad(self) -> float:
        """Return the upper candidate elevation bound in radians."""
        return radians(self.max_elev_deg)

    @property
    def delta_azimuth_rad(self) -> float:
        """Return the candidate azimuth span in radians."""
        return radians(self.delta_azimuth_deg)


def _gravity_align_pose(reference_pose: PoseTW, *, eps: float = 1e-6) -> PoseTW:
    """Return a gravity-aligned variant of ``reference_pose`` with identical translation.

    The aligned pose uses the VIO world-up axis (see `aria_nbv.utils.frames.world_up_tensor`) and keeps
    the reference yaw by projecting the original forward axis onto the horizontal plane. This effectively removes
    pitch and roll so azimuth/elevation sampling caps behave as intended even when the reference camera is tilted.

    Args:
        reference_pose: ``PoseTW`` with shape ``(12,)`` or ``(1,12)`` (world<-reference).
        eps: Numerical stability guard for near-degenerate projections.

    Returns:
        ``PoseTW`` world<-reference pose with gravity-aligned rotation and unchanged translation.
    """
    reference_pose = ensure_unbatched_pose(reference_pose)
    r_wr = reference_pose.R  # (..., 3, 3)
    t_w = reference_pose.t  # (..., 3)
    device = r_wr.device
    dtype = r_wr.dtype

    wup = world_up_tensor(device=device, dtype=dtype)  # (3,)

    fwd_w = r_wr[..., :, 2]  # (..., 3)
    fwd_h = fwd_w - (fwd_w * wup).sum(dim=-1, keepdim=True) * wup
    fwd_norm = fwd_h.norm(dim=-1, keepdim=True)

    left_w = r_wr[..., :, 0]  # (..., 3)
    left_h = left_w - (left_w * wup).sum(dim=-1, keepdim=True) * wup
    left_norm = left_h.norm(dim=-1, keepdim=True)

    # Expand world-up to match batch dimensions of the pose axes.
    wup_exp = wup
    while wup_exp.ndim < fwd_h.ndim:
        wup_exp = wup_exp.unsqueeze(0)
    wup_exp = wup_exp.expand_as(fwd_h)

    # Fallback when forward is near-parallel to gravity: derive forward from left×up.
    left_unit = left_h / left_norm.clamp_min(eps)
    fwd_from_left = torch.cross(left_unit, wup_exp, dim=-1)
    fwd_from_left = fwd_from_left / fwd_from_left.norm(dim=-1, keepdim=True).clamp_min(
        eps,
    )

    use_fallback = fwd_norm < eps
    fwd_unit = fwd_h / fwd_norm.clamp_min(eps)
    z_w = torch.where(use_fallback, fwd_from_left, fwd_unit)

    # Final fallback when both forward/left projections are degenerate.
    degenerate = z_w.norm(dim=-1, keepdim=True) < eps
    if degenerate.any():
        alt = torch.tensor([1.0, 0.0, 0.0], device=device, dtype=dtype)
        alt = alt - (alt * wup).sum() * wup
        alt = alt / alt.norm().clamp_min(eps)
        alt_exp = alt
        while alt_exp.ndim < z_w.ndim:
            alt_exp = alt_exp.unsqueeze(0)
        alt_exp = alt_exp.expand_as(z_w)
        z_w = torch.where(degenerate, alt_exp, z_w)

    x_w = torch.cross(wup_exp, z_w, dim=-1)
    x_w = x_w / x_w.norm(dim=-1, keepdim=True).clamp_min(eps)
    y_w = torch.cross(z_w, x_w, dim=-1)

    r_new = torch.stack([x_w, y_w, z_w], dim=-1)
    return PoseTW.from_Rt(r_new, t_w)


@contextmanager
def _maybe_seed(seed: int | None, *, device: torch.device) -> Iterator[None]:
    if seed is None:
        yield
        return

    # IMPORTANT: `torch.random.fork_rng(devices=None)` will attempt to snapshot
    # CUDA RNG state and triggers CUDA initialization even when running on CPU.
    # Use an empty list unless we explicitly want to manage CUDA RNG state.
    cuda_devices: list[int] = []
    if device.type == "cuda" and torch.cuda.is_available():
        idx = device.index if device.index is not None else torch.cuda.current_device()
        cuda_devices = [int(idx)]

    with torch.random.fork_rng(devices=cuda_devices, enabled=True):
        torch.manual_seed(int(seed))
        if cuda_devices:
            torch.cuda.manual_seed_all(int(seed))
        yield


class CandidateViewGenerator:
    """Generate candidate `PoseTW` around a reference rig pose using composeable and modular rules.

    This class orchestrates the full candidate generation process:

    * positional sampling via `PositionSampler`,
    * orientation construction via `OrientationBuilder`, and
    * rule-based pruning via `FreeSpaceRule`, `MinDistanceToMeshRule` and `PathCollisionRule`.

    """

    def __init__(self, config: CandidateViewGeneratorConfig):
        self.config = config
        self.console = (
            Console.with_prefix(self.__class__.__name__)
            .set_verbosity(self.config.verbosity)
            .set_debug(self.config.is_debug)
        )
        self._rules: list[Rule] = self._build_default_rules(config)

    # ------------------------------------------------------------------ public
    def generate_from_typed_sample(
        self,
        sample: EfmSnippetView,
        frame_index: int | None = None,
        runtime_context: CandidateGenerationRuntimeContext | None = None,
    ) -> CandidateSamplingResult:
        """Generate candidates using an `EfmSnippetView` sample.

        Args:
            sample: Snippet view with trajectory and mesh.
            frame_index: Optional frame index to extract the reference pose instead of using the final pose.
                0 <= frame_index < F where is the number of frames in the snippet; F = sample.get_camera(self.config.camera_label).num_frames.
            runtime_context: Optional target/runtime context accepted for interface
                compatibility with mixture generators. The single-family
                generator reads target state directly from the config.
        """
        del runtime_context
        device = torch.device(self.config.device)
        occ = sample.get_occupancy_extend()
        self.console.dbg(
            f"Using occupancy extent: (xmin, xmax, ymin, ymax, zmin, zmax) = {occ}",
        )
        occupancy_extent = occ.to(device=device, dtype=torch.float32)
        gt_mesh = sample.mesh
        mesh_verts = sample.mesh_verts
        mesh_faces = sample.mesh_faces

        assert mesh_verts is not None and mesh_faces is not None, "Mesh vertices and faces must be provided."

        cam_view = sample.get_camera(self.config.camera_label)

        if frame_index is None:
            frame_index = self.config.reference_frame_index

        if frame_index is None:
            reference_pose = sample.trajectory.final_pose.to(device=device)
        else:
            cam_idx, traj_idx = cam_view.nearest_traj_indices(
                sample.trajectory.time_ns,
                [frame_index],
                default_last=True,
            )
            if traj_idx.numel() == 0:
                reference_pose = sample.trajectory.final_pose.to(device=device)
            else:
                reference_pose = sample.trajectory.t_world_rig[traj_idx].to(
                    device=device,
                )

        return self.generate(
            reference_pose=reference_pose,
            gt_mesh=gt_mesh,
            mesh_verts=mesh_verts,
            mesh_faces=mesh_faces,
            camera_calib_template=cam_view.calib,
            occupancy_extent=occupancy_extent,
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
        """Sample candidate poses around `reference_pose` and apply pruning rules.

        Samples candidate positions and orientations, wraps them in a `CandidateContext`, runs all configured
        rules, and returns `CandidateSamplingResult`.

        Args:
            reference_pose:
                World<-reference `PoseTW` used as the physical rig pose. When
                ``align_to_gravity`` is enabled, a gravity-aligned copy of this pose
                defines the sampling frame (stored in ``CandidateSamplingResult.sampling_pose``).
            gt_mesh:
                Ground-truth `trimesh.Trimesh` in the world frame for pruning.
            mesh_verts:
                `Tensor['V, 3']` mesh vertices aligned with `gt_mesh`.
            mesh_faces:
                `Tensor['F, 3']` integer vertex indices defining mesh faces.
            camera_calib_template:
                `CameraTW` whose intrinsics/metadata are cloned for each candidate; its pose block is
                overwritten with candidate extrinsics.
            occupancy_extent:
                `Tensor['6']` world-space AABB used by `FreeSpaceRule`.
            runtime_context:
                Optional target/runtime context accepted for interface
                compatibility with mixture generators. The single-family
                generator reads target state directly from the config.

        Returns:
            `CandidateSamplingResult` holding the valid candidate `CameraTW`, reference pose, shell
            poses, masks and optional debug statistics.
        """
        del runtime_context
        device = self.config.device

        reference_pose = rotate_yaw_cw90(
            ensure_unbatched_pose(reference_pose.to(device)),
        )
        sampling_pose = _gravity_align_pose(reference_pose) if self.config.align_to_gravity else reference_pose

        with _maybe_seed(self.config.seed if seed is None else seed, device=torch.device(device)):
            centers_world, offsets_ref = PositionSampler(self.config).sample(
                sampling_pose,
            )
            return self._generate_for_centers(
                reference_pose=reference_pose,
                sampling_pose=sampling_pose,
                centers_world=centers_world,
                offsets_ref=offsets_ref,
                gt_mesh=gt_mesh,
                mesh_verts=mesh_verts,
                mesh_faces=mesh_faces,
                camera_calib_template=camera_calib_template,
                occupancy_extent=occupancy_extent,
                seed=None,
            )

    def generate_from_centers(
        self,
        *,
        reference_pose: PoseTW,
        centers_world: torch.Tensor,
        offsets_ref: torch.Tensor,
        gt_mesh: trimesh.Trimesh,
        mesh_verts: torch.Tensor,
        mesh_faces: torch.Tensor,
        camera_calib_template: CameraTW,
        occupancy_extent: torch.Tensor,
        seed: int | None = None,
    ) -> CandidateSamplingResult:
        """Orient and validate an explicit candidate-centre table.

        This is the paired-proposal seam: several gaze hypotheses may reuse
        exactly the same world-space centers while orientation jitter and hard
        validity remain independently auditable per candidate row.
        """

        device = self.config.device
        prepared_reference = rotate_yaw_cw90(ensure_unbatched_pose(reference_pose.to(device)))
        sampling_pose = _gravity_align_pose(prepared_reference) if self.config.align_to_gravity else prepared_reference
        return self._generate_for_centers(
            reference_pose=prepared_reference,
            sampling_pose=sampling_pose,
            centers_world=centers_world.to(device=device),
            offsets_ref=offsets_ref.to(device=device),
            gt_mesh=gt_mesh,
            mesh_verts=mesh_verts,
            mesh_faces=mesh_faces,
            camera_calib_template=camera_calib_template,
            occupancy_extent=occupancy_extent,
            seed=self.config.seed if seed is None else seed,
        )

    def _generate_for_centers(
        self,
        *,
        reference_pose: PoseTW,
        sampling_pose: PoseTW,
        centers_world: torch.Tensor,
        offsets_ref: torch.Tensor,
        gt_mesh: trimesh.Trimesh,
        mesh_verts: torch.Tensor,
        mesh_faces: torch.Tensor,
        camera_calib_template: CameraTW,
        occupancy_extent: torch.Tensor,
        seed: int | None,
    ) -> CandidateSamplingResult:
        """Build orientations and apply hard rules for prepared centers."""

        device = self.config.device
        with _maybe_seed(seed, device=torch.device(device)):
            shell_poses, view_dirs_delta = OrientationBuilder(self.config).build(
                sampling_pose,
                centers_world,
            )

        candidate_count = centers_world.shape[0]
        if view_dirs_delta is None:
            jitter_yaw_deg = torch.zeros(candidate_count, device=device, dtype=centers_world.dtype)
            jitter_pitch_deg = torch.zeros(candidate_count, device=device, dtype=centers_world.dtype)
        else:
            delta_rotation = view_dirs_delta.R
            delta_forward = delta_rotation[:, :, 2]
            jitter_yaw_deg = torch.rad2deg(torch.atan2(delta_forward[:, 0], delta_forward[:, 2]))
            jitter_pitch_deg = torch.rad2deg(torch.asin(delta_forward[:, 1].clamp(-1.0, 1.0)))
        jitter_debug: dict[str, Any] = {
            "view_jitter_yaw_deg": jitter_yaw_deg,
            "view_jitter_pitch_deg": jitter_pitch_deg,
            "view_jitter_is_bounded": torch.full(
                (candidate_count,),
                bool(
                    self.config.view_sampling_strategy is None
                    or float(self.config.view_max_azimuth_deg) > 0.0
                    or float(self.config.view_max_elevation_deg) > 0.0
                ),
                dtype=torch.bool,
                device=device,
            ),
            "view_jitter_azimuth_limit_deg": torch.full(
                (candidate_count,),
                float(self.config.view_max_azimuth_deg),
                device=device,
            ),
            "view_jitter_elevation_limit_deg": torch.full(
                (candidate_count,),
                float(self.config.view_max_elevation_deg),
                device=device,
            ),
        }
        if view_dirs_delta is not None:
            jitter_debug["view_dirs_delta"] = view_dirs_delta

        ctx = CandidateContext(
            cfg=self.config,
            reference_pose=reference_pose,
            sampling_pose=sampling_pose,
            gt_mesh=gt_mesh,
            mesh_verts=mesh_verts.to(device),
            mesh_faces=mesh_faces.to(device),
            occupancy_extent=occupancy_extent.to(device),
            camera_calib_template=camera_calib_template.to(device),
            shell_poses=shell_poses,
            centers_world=centers_world,
            shell_offsets_ref=offsets_ref,
            mask_valid=torch.ones(
                centers_world.shape[0],
                dtype=torch.bool,
                device=device,
            ),
            debug=jitter_debug,
        )
        if self.config.collect_debug_stats:
            collision_enabled = bool(
                self.config.ensure_collision_free and self.config.step_clearance > 0 and gt_mesh is not None
            )
            ctx.mark_debug("path_collision_applicable_mask", torch.full_like(ctx.mask_valid, collision_enabled))
            ctx.mark_debug("path_collision_evaluated_mask", torch.zeros_like(ctx.mask_valid))
            ctx.mark_debug("path_collision_detected", torch.zeros_like(ctx.mask_valid))
            ctx.mark_debug("path_collision_mask", torch.zeros_like(ctx.mask_valid))
        if self.config.position_target_point_world is not None:
            ctx.mark_debug("target_bearing_yaw_rad", _target_bearing_yaw_rad(ctx))
            ctx.mark_debug("target_distance_m", _target_distance_m(ctx))
            for name, value in _target_view_diagnostics(ctx).items():
                ctx.mark_debug(name, value)

        self._apply_rules(ctx)

        return self._finalise(ctx)

    def _build_default_rules(self, cfg: CandidateViewGeneratorConfig) -> list[Rule]:
        rules: list[Rule] = []
        if cfg.ensure_free_space:
            rules.append(FreeSpaceRule(cfg))
        if cfg.enforce_motion_realism:
            rules.append(MotionRealismRule(cfg))
        if cfg.min_distance_to_mesh > 0:
            rules.append(MinDistanceToMeshRule(cfg))
        if cfg.ensure_collision_free:
            rules.append(PathCollisionRule(cfg))
        return rules

    def _apply_rules(self, ctx: CandidateContext) -> None:
        for rule in self._rules:
            rule(ctx)
            if ctx.cfg.collect_rule_masks:
                ctx.record_mask(rule.__class__.__name__, ctx.mask_valid)

    def _finalise(self, ctx: CandidateContext) -> CandidateSamplingResult:
        mask_valid = ctx.mask_valid
        shell_poses = ctx.shell_poses
        assert shell_poses is not None
        assert shell_poses._data is not None

        poses_world_valid = PoseTW(shell_poses._data[mask_valid])  # world <- cam
        reference_pose = ctx.reference_pose  # world <- ref
        ref_inv = reference_pose.inverse()  # ref <- world
        poses_ref_valid = ref_inv.compose(poses_world_valid)  # ref <- cam

        template_data = _clone_camera_template(
            ctx.camera_calib_template,
            poses_ref_valid._data.shape[0],
            poses_ref_valid._data.device,
        )
        # Store camera pose in the reference frame as cam<-ref.
        poses_cam_ref = poses_ref_valid.inverse()
        template_data[:, CameraTW.T_CAM_RIG_IND] = poses_cam_ref._data

        poses_cam = CameraTW(template_data)

        extras = (
            ctx.debug
            if ctx.cfg.collect_debug_stats
            else {
                name: value
                for name, value in ctx.debug.items()
                if name.startswith(("view_jitter_", "target_view_", "target_pixel_", "target_in_fov_"))
            }
        )
        return CandidateSamplingResult(
            views=poses_cam,
            reference_pose=reference_pose,
            sampling_pose=ctx.sampling_pose,
            mask_valid=mask_valid,
            masks=ctx.rule_masks if ctx.cfg.collect_rule_masks else {},
            shell_poses=shell_poses,
            shell_offsets_ref=ctx.shell_offsets_ref,
            extras=extras,
        )


def _clone_camera_template(
    template: CameraTW,
    n: int,
    device: torch.device,
) -> torch.Tensor:
    """Broadcast a camera template to `n` candidates on the target device."""
    data = template._data
    assert data is not None

    if data.ndim == 1:
        data = data.view(1, -1)
    return data.to(device)[0].unsqueeze(0).expand(n, -1).clone()


def _target_bearing_yaw_rad(ctx: CandidateContext) -> torch.Tensor:
    """Compute world-horizontal candidate-to-target bearing for diagnostics."""

    target = torch.as_tensor(
        ctx.cfg.position_target_point_world,
        device=ctx.centers_world.device,
        dtype=ctx.centers_world.dtype,
    ).reshape(1, 3)
    delta = target - ctx.centers_world
    return torch.atan2(delta[:, 0], delta[:, 2])


def _target_distance_m(ctx: CandidateContext) -> torch.Tensor:
    """Compute candidate-center distance to the actor-visible target point."""

    target = torch.as_tensor(
        ctx.cfg.position_target_point_world,
        device=ctx.centers_world.device,
        dtype=ctx.centers_world.dtype,
    ).reshape(1, 3)
    return torch.linalg.norm(target - ctx.centers_world, dim=1)


def _target_view_diagnostics(ctx: CandidateContext) -> dict[str, torch.Tensor]:
    """Project the actor-visible target centre into every candidate camera.

    The returned tensors are audit-only geometry. ``target_in_fov_mask`` uses
    the exact ``CameraTW`` projection model and valid-radius contract; it does
    not claim scene line of sight or target-surface visibility.
    """

    shell_poses = ctx.shell_poses
    if shell_poses is None:
        return {}
    target_world = torch.as_tensor(
        ctx.cfg.position_target_point_world,
        device=ctx.centers_world.device,
        dtype=ctx.centers_world.dtype,
    ).reshape(1, 3)
    target_cam = shell_poses.inverse().transform(target_world).reshape(-1, 3)
    distance = torch.linalg.norm(target_cam, dim=1).clamp_min(1e-8)
    view_angle_deg = torch.rad2deg(torch.acos((target_cam[:, 2] / distance).clamp(-1.0, 1.0)))

    calibration = CameraTW(
        _clone_camera_template(
            ctx.camera_calib_template,
            ctx.centers_world.shape[0],
            ctx.centers_world.device,
        )
    )
    target_pixel, in_fov = calibration.project(target_cam.unsqueeze(1))
    target_pixel = target_pixel.squeeze(1)
    in_fov = in_fov.squeeze(1)
    size = calibration.size.reshape(-1, 2)
    principal = calibration.c.reshape(-1, 2)
    valid_radius = calibration.valid_radius.reshape(target_pixel.shape[0], -1)
    image_margin = torch.stack(
        (
            target_pixel[:, 0],
            target_pixel[:, 1],
            size[:, 0] - 1.0 - target_pixel[:, 0],
            size[:, 1] - 1.0 - target_pixel[:, 1],
        ),
        dim=1,
    ).amin(dim=1)
    radial_fraction = torch.linalg.norm((target_pixel - principal) / valid_radius.clamp_min(1e-8), dim=1)
    radius_margin = (1.0 - radial_fraction) * valid_radius.amin(dim=1)
    pixel_margin = torch.minimum(image_margin, radius_margin)
    pixel_margin = torch.where(in_fov, pixel_margin, -pixel_margin.abs())

    return {
        "target_view_angle_deg": view_angle_deg,
        "target_pixel_margin_px": pixel_margin,
        "target_in_fov_mask": in_fov,
        "target_view_evaluated_mask": torch.ones_like(in_fov),
    }


__all__ = [
    "CandidateViewGenerator",
    "CandidateViewGeneratorConfig",
    "CandidatePositionMode",
    "CollisionBackend",
    "SamplingStrategy",
]
