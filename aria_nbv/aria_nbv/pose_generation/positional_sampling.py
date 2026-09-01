r"""Direction and position sampling utilities for finite candidate generation.

This module samples candidate camera centers in the reference rig frame before
they are transformed into world coordinates. It owns only the center prior:
orientation, feasibility pruning, and candidate-table compaction are handled by
neighboring `pose_generation` modules.

Theory:
    Raw directions are sampled either uniformly on the sphere,
    $u \sim \mathrm{Unif}(\mathbb{S}^2)$, or from a forward-biased
    PowerSpherical distribution,
    $p(u) \propto (1 + e_z^\top u)^\kappa$. Azimuth caps scale
    $\psi=\operatorname{atan2}(u_x,u_z)$ into the configured field
    $\Delta\psi$, while elevation caps map $u_y=\sin\theta$ into
    $[\sin\theta_{\min},\sin\theta_{\max}]$ without rejection. A radius
    $r\sim\mathcal{U}(r_{\min},r_{\max})$ then produces the reference-frame
    offset $o_r=r d_r$ and world center $c_w=T^w_r o_r$.

    Position modes reinterpret the capped direction before the radius is
    applied. `forward_local`, `local_refinement`, and `revisit_backtrack` blend
    toward continuity priors; `target_bearing_local` blends toward the selected
    actor-visible target bearing; `target_orbit` makes balanced partial arcs at
    the current horizontal target standoff; `lateral_target_bypass` combines
    target bearing, signed lateral bypass, and bounded vertical offset. These
    target modes may use actor-visible target centers only, never GT target
    geometry.
"""

from __future__ import annotations

from math import radians
from typing import TYPE_CHECKING

import torch
from power_spherical import HypersphericalUniform, PowerSpherical  # type: ignore[import-untyped]

from ..utils.frames import world_up_tensor
from .config import (
    CenterConfig,
    PowerSphericalConfig,
    SampledCenterConfig,
    TargetOrbitCenterConfig,
    TargetShellCenterConfig,
    TargetShellSupportMode,
    UniformSphereConfig,
)
from .geometry import DEVICE_FWD
from .types import CandidatePositionMode

if TYPE_CHECKING:
    from efm3d.aria.pose import PoseTW


class PositionSampler:
    """Sample candidate centers around a reference pose."""

    def __init__(self, config: CenterConfig, *, device: torch.device):
        self.config = config
        self.device = device

    @staticmethod
    def _angles_from_dirs_rig(dirs_rig: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Return (azimuth, elevation) for rig-frame unit vectors.

        Azimuth is measured around the rig up-axis (+Y) with 0 aligned to +Z (forward).
        Elevation is measured from the horizontal plane; +90° looks straight up, -90° down.
        """

        az = torch.atan2(dirs_rig[:, 0], dirs_rig[:, 2])  # x vs z in LUF convention
        elev = torch.atan2(dirs_rig[:, 1], torch.linalg.norm(dirs_rig[:, (0, 2)], dim=-1) + 1e-8)
        return az, elev

    def _scale_into_caps(self, dirs_rig: torch.Tensor) -> torch.Tensor:
        """Uniformly scale directions into az/elev caps without rejection.

        Strategy:
        - Azimuth: linear scale from [-pi, pi] to [-delta/2, delta/2] (wrap-friendly).
        - Elevation: linearly map y=sin(elev) from [-1, 1] to [sin(min), sin(max)];
          rescale xz-plane to keep unit norm. This preserves azimuth and avoids pile-up.
        """

        cfg = self.config
        if not isinstance(cfg, SampledCenterConfig):
            raise TypeError("angular caps apply only to sampled centers")
        device = dirs_rig.device
        dtype = dirs_rig.dtype

        x, y, z = dirs_rig.unbind(dim=-1)

        # Azimuth scaling (around +Y). Keep distribution uniform over the target band.
        if cfg.azimuth_width_deg < 360.0 - 1e-3:
            az_raw = torch.atan2(x, z)  # [-pi, pi]
            scale_az = torch.tensor(radians(cfg.azimuth_width_deg), device=device, dtype=dtype) / (2 * torch.pi)
            az_scaled = az_raw * scale_az  # now in [-delta/2, delta/2]
            x = torch.sin(az_scaled)
            z = torch.cos(az_scaled)

        # Elevation scaling via y = sin(elev) interval mapping.
        y_min = torch.sin(torch.tensor(radians(cfg.min_elevation_deg), device=device, dtype=dtype))
        y_max = torch.sin(torch.tensor(radians(cfg.max_elevation_deg), device=device, dtype=dtype))
        # map [-1,1] -> [y_min, y_max]
        y_scaled = y_min + (y + 1.0) * 0.5 * (y_max - y_min)
        xz_norm = torch.linalg.norm(torch.stack([x, z], dim=-1), dim=-1).clamp_min(1e-8)
        xz_scale = torch.sqrt(torch.clamp(1.0 - y_scaled**2, min=0.0)) / xz_norm
        x = x * xz_scale
        z = z * xz_scale
        y = y_scaled

        dirs = torch.stack([x, y, z], dim=-1)
        return dirs / dirs.norm(dim=-1, keepdim=True).clamp_min(1e-8)

    def _sample_unit_sphere(self, n_draw: int) -> torch.Tensor:
        """Fallback: sample unit vectors via normalized Gaussian noise."""
        dirs = torch.randn(n_draw, 3, device=self.device, dtype=torch.float32)
        return dirs / dirs.norm(dim=-1, keepdim=True).clamp_min(1e-8)

    def _target_direction_ref(self, reference_pose: PoseTW, target_center_world: torch.Tensor | None) -> torch.Tensor:
        """Return normalized actor-visible target bearing in the reference frame."""

        target_ref = self._target_point_ref(reference_pose, target_center_world)
        if torch.linalg.norm(target_ref) < 1e-6:
            target_ref = torch.tensor(DEVICE_FWD, device=self.device, dtype=torch.float32)
        return target_ref / torch.linalg.norm(target_ref).clamp_min(1e-8)

    def _target_point_ref(self, reference_pose: PoseTW, target_center_world: torch.Tensor | None) -> torch.Tensor:
        """Return the actor-visible target center in the reference frame."""

        target_world = self._target_point_world(target_center_world)
        return reference_pose.inverse().transform(target_world.reshape(1, 3)).reshape(3)

    def _target_point_world(self, target_center_world: torch.Tensor | None) -> torch.Tensor:
        """Return the actor-visible target center in world coordinates."""

        if target_center_world is None:
            raise ValueError(f"{_position_mode(self.config).value} requires target_center_world.")
        return torch.as_tensor(target_center_world, device=self.device, dtype=torch.float32).reshape(3)

    def _sample_target_orbit(
        self,
        reference_pose: PoseTW,
        n_draw: int,
        target_center_world: torch.Tensor | None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        r"""Sample balanced partial arcs at the current horizontal target standoff.

        For world-horizontal root-to-target bearing $b$, left tangent $l$,
        current standoff $d$, and configured angle $\alpha_i$, the world-frame
        center offset is

        $$o_i = d b - d\cos(\alpha_i)b + d\sin(\alpha_i)l.$$

        Thus every candidate remains $d$ metres from the target in the ground
        plane while the existing motion rules decide which arc steps are
        feasible from the current pose.
        """

        if n_draw < 2:
            raise ValueError("target_orbit requires at least two attempted proposals.")

        root_world = reference_pose.t.reshape(3)
        target_delta_world = self._target_point_world(target_center_world) - root_world
        world_up = world_up_tensor(device=self.device, dtype=torch.float32)
        target_horizontal = target_delta_world - (target_delta_world @ world_up) * world_up
        standoff = torch.linalg.norm(target_horizontal)
        if standoff < 1e-6:
            raise ValueError("target_orbit requires a nonzero horizontal target bearing.")

        bearing = target_horizontal / standoff
        lateral = torch.cross(world_up, bearing, dim=0)
        assert isinstance(self.config, TargetOrbitCenterConfig)
        angles_deg = torch.tensor(self.config.angles_deg, device=self.device, dtype=torch.float32)
        negative = angles_deg[angles_deg < 0.0]
        positive = angles_deg[angles_deg > 0.0]
        pair_indices = torch.arange((n_draw + 1) // 2, device=self.device)
        angles_interleaved = torch.stack(
            (negative[pair_indices % negative.numel()], positive[pair_indices % positive.numel()]),
            dim=1,
        ).reshape(-1)[:n_draw]
        angles_rad = torch.deg2rad(angles_interleaved)
        target_to_candidate = (
            -standoff * torch.cos(angles_rad)[:, None] * bearing[None, :]
            + standoff * torch.sin(angles_rad)[:, None] * lateral[None, :]
        )
        offsets_world = target_horizontal[None, :] + target_to_candidate
        centers_world = root_world[None, :] + offsets_world
        offsets_ref = reference_pose.inverse().rotate(offsets_world)
        return centers_world, offsets_ref

    def _sample_target_shell(
        self,
        reference_pose: PoseTW,
        n_draw: int,
        target_center_world: torch.Tensor | None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        r"""Sample target-relative centers with the configured solid-angle measure.

        Angular boxes use uniform azimuth and uniform ``sin(elevation)`` in a
        world-Z-up target-to-actor frame. Actor-facing caps use uniform cosine
        about the true three-dimensional target-to-actor direction. Radius is
        uniform in metres for every support mode.
        """

        cfg = self.config
        assert isinstance(cfg, TargetShellCenterConfig)
        root_world = reference_pose.t.reshape(3)
        target_world = self._target_point_world(target_center_world)
        actor_delta = root_world - target_world
        actor_distance = torch.linalg.norm(actor_delta)
        if actor_distance < 1e-6:
            raise ValueError("target_shell requires distinct target and reference centers.")
        actor_direction = actor_delta / actor_distance
        world_up = world_up_tensor(device=self.device, dtype=torch.float32)

        if cfg.support_mode is TargetShellSupportMode.ACTOR_FACING_CAP:
            assert cfg.cap_half_angle_deg is not None
            cos_min = torch.cos(torch.tensor(radians(cfg.cap_half_angle_deg), device=self.device))
            cos_theta = cos_min + torch.rand(n_draw, device=self.device) * (1.0 - cos_min)
            sin_theta = torch.sqrt(torch.clamp(1.0 - cos_theta.square(), min=0.0))
            phi = (torch.rand(n_draw, device=self.device) * 2.0 - 1.0) * torch.pi
            basis_a = torch.cross(world_up, actor_direction, dim=0)
            if torch.linalg.norm(basis_a) < 1e-6:
                basis_a = torch.tensor([1.0, 0.0, 0.0], device=self.device)
            basis_a = basis_a / basis_a.norm().clamp_min(1e-8)
            basis_b = torch.cross(actor_direction, basis_a, dim=0)
            directions_world = cos_theta[:, None] * actor_direction[None, :] + sin_theta[:, None] * (
                torch.cos(phi)[:, None] * basis_a[None, :] + torch.sin(phi)[:, None] * basis_b[None, :]
            )
        else:
            horizontal = actor_delta - (actor_delta @ world_up) * world_up
            if torch.linalg.norm(horizontal) < 1e-6:
                raise ValueError("target_shell angular support requires a nonzero horizontal target-to-actor bearing.")
            forward = horizontal / horizontal.norm()
            lateral = torch.cross(world_up, forward, dim=0)
            azimuth_limit = radians(cfg.azimuth_half_width_deg)
            azimuth = (torch.rand(n_draw, device=self.device) * 2.0 - 1.0) * azimuth_limit
            sin_elevation_min = torch.sin(torch.tensor(radians(cfg.elevation_min_deg), device=self.device))
            sin_elevation_max = torch.sin(torch.tensor(radians(cfg.elevation_max_deg), device=self.device))
            sin_elevation = sin_elevation_min + torch.rand(n_draw, device=self.device) * (
                sin_elevation_max - sin_elevation_min
            )
            cos_elevation = torch.sqrt(torch.clamp(1.0 - sin_elevation.square(), min=0.0))
            directions_world = (
                cos_elevation[:, None]
                * (torch.cos(azimuth)[:, None] * forward[None, :] + torch.sin(azimuth)[:, None] * lateral[None, :])
                + sin_elevation[:, None] * world_up[None, :]
            )

        radii = torch.empty(n_draw, device=self.device).uniform_(cfg.radius_min_m, cfg.radius_max_m)
        centers_world = target_world[None, :] + radii[:, None] * directions_world
        offsets_ref = reference_pose.inverse().transform(centers_world)
        return centers_world, offsets_ref

    def _direction_around(self, base: torch.Tensor, noise: torch.Tensor, *, spread: float) -> torch.Tensor:
        """Blend a base direction with orthogonal noise in the reference frame."""

        base = base.to(device=noise.device, dtype=noise.dtype).reshape(1, 3)
        base = base / base.norm(dim=-1, keepdim=True).clamp_min(1e-8)
        parallel = (noise * base).sum(dim=-1, keepdim=True) * base
        orthogonal = noise - parallel
        dirs = base + float(spread) * orthogonal
        return dirs / dirs.norm(dim=-1, keepdim=True).clamp_min(1e-8)

    def _apply_position_mode(
        self,
        dirs_rig: torch.Tensor,
        reference_pose: PoseTW,
        target_center_world: torch.Tensor | None,
    ) -> torch.Tensor:
        """Map raw angular samples to the configured position family."""

        match _position_mode(self.config):
            case CandidatePositionMode.UPPER_BOUND_FREE_SHELL:
                return dirs_rig
            case CandidatePositionMode.FORWARD_LOCAL:
                forward = torch.tensor(DEVICE_FWD, device=dirs_rig.device, dtype=dirs_rig.dtype)
                return self._direction_around(forward, dirs_rig, spread=0.45)
            case CandidatePositionMode.LOCAL_REFINEMENT:
                forward = torch.tensor(DEVICE_FWD, device=dirs_rig.device, dtype=dirs_rig.dtype)
                return self._direction_around(forward, dirs_rig, spread=0.25)
            case CandidatePositionMode.REVISIT_BACKTRACK:
                backward = torch.tensor([0.0, 0.0, -1.0], device=dirs_rig.device, dtype=dirs_rig.dtype)
                return self._direction_around(backward, dirs_rig, spread=0.35)
            case CandidatePositionMode.TARGET_BEARING_LOCAL:
                target_dir = self._target_direction_ref(reference_pose, target_center_world).to(
                    device=dirs_rig.device, dtype=dirs_rig.dtype
                )
                return self._direction_around(target_dir, dirs_rig, spread=0.4)
            case CandidatePositionMode.TARGET_ORBIT:
                raise RuntimeError("target_orbit centers must be sampled by _sample_target_orbit.")
            case CandidatePositionMode.TARGET_SHELL:
                raise RuntimeError("target_shell centers must be sampled by _sample_target_shell.")
            case CandidatePositionMode.LATERAL_TARGET_BYPASS:
                target_dir = self._target_direction_ref(reference_pose, target_center_world).to(
                    device=dirs_rig.device, dtype=dirs_rig.dtype
                )
                up = torch.tensor([0.0, 1.0, 0.0], device=dirs_rig.device, dtype=dirs_rig.dtype)
                lateral = torch.cross(up, target_dir, dim=0)
                if torch.linalg.norm(lateral) < 1e-6:
                    lateral = torch.tensor([1.0, 0.0, 0.0], device=dirs_rig.device, dtype=dirs_rig.dtype)
                lateral = lateral / lateral.norm().clamp_min(1e-8)
                signs = torch.where(dirs_rig[:, 0] >= 0.0, 1.0, -1.0).to(dtype=dirs_rig.dtype).unsqueeze(1)
                vertical = up.reshape(1, 3) * dirs_rig[:, 1:2].clamp(-0.35, 0.35)
                dirs = 0.55 * target_dir.reshape(1, 3) + signs * 0.85 * lateral.reshape(1, 3) + vertical
                return dirs / dirs.norm(dim=-1, keepdim=True).clamp_min(1e-8)

    def sample(
        self,
        reference_pose: PoseTW,
        *,
        count: int,
        target_center_world: torch.Tensor | None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Draw candidate centers and offsets in reference frame.

        Args:
            reference_pose: ``PoseTW`` reference2world pose used as sampling origin.
            count: Exact number of centers to attempt.
            target_center_world: Request-local actor-visible target, when required by the center family.

        Returns:
            Tuple of ``(centers_world, offsets_ref)`` where both are ``Tensor[N, 3]`` with
            ``N = count``. Offsets are in the reference frame before rotation into world.
        """
        n_draw = int(count)

        if isinstance(self.config, TargetOrbitCenterConfig):
            return self._sample_target_orbit(reference_pose, n_draw, target_center_world)
        if isinstance(self.config, TargetShellCenterConfig):
            return self._sample_target_shell(reference_pose, n_draw, target_center_world)

        cfg = self.config
        assert isinstance(cfg, SampledCenterConfig)

        match cfg.distribution:
            case UniformSphereConfig():
                try:
                    dirs = HypersphericalUniform(dim=3, device=self.device).sample((n_draw,))
                except Exception:
                    dirs = self._sample_unit_sphere(n_draw)
            case PowerSphericalConfig(concentration=concentration):
                mu = torch.tensor(DEVICE_FWD, device=self.device)
                try:
                    dirs = PowerSpherical(
                        mu,
                        torch.tensor(concentration, device=self.device),
                    ).sample((n_draw,))
                except Exception as exc:
                    raise RuntimeError(
                        "PowerSpherical position sampling failed for "
                        f"strategy={cfg.distribution.kind!r}, "
                        f"device={str(self.device)!r}, kappa={concentration!r}. "
                        "No alternate distribution was used; verify the sampler dependency, device, and profile values."
                    ) from exc
        dirs_rig = dirs / dirs.norm(dim=-1, keepdim=True)

        # Work entirely in reference (rig) frame for angle limits.
        dirs_rig = self._scale_into_caps(dirs_rig)
        dirs_rig = self._apply_position_mode(dirs_rig, reference_pose, target_center_world)

        dirs_world = reference_pose.rotate(dirs_rig)
        offsets_rig = dirs_rig

        radii = torch.empty(dirs_world.shape[0], device=self.device, dtype=dirs_world.dtype).uniform_(
            cfg.min_radius_m, cfg.max_radius_m
        )
        offsets_rig = offsets_rig * radii[:, None]
        centers_world = reference_pose.transform(offsets_rig)
        return centers_world, offsets_rig


def _position_mode(config: CenterConfig) -> CandidatePositionMode:
    match config:
        case SampledCenterConfig(mode=mode):
            return CandidatePositionMode(mode)
        case TargetOrbitCenterConfig():
            return CandidatePositionMode.TARGET_ORBIT
        case TargetShellCenterConfig():
            return CandidatePositionMode.TARGET_SHELL
        case _:
            raise TypeError(f"unsupported center configuration: {type(config).__name__}")


__all__ = [
    "PositionSampler",
]
