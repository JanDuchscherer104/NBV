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
    actor-visible target bearing; `lateral_target_bypass` combines target
    bearing, signed lateral bypass, and bounded vertical offset. These target
    modes may use actor-visible target centers only, never GT target geometry.
"""

from __future__ import annotations

from math import ceil
from typing import TYPE_CHECKING

import torch
from power_spherical import HypersphericalUniform, PowerSpherical  # type: ignore[import-untyped]

from .geometry import DEVICE_FWD
from .types import CandidatePositionMode, SamplingStrategy

if TYPE_CHECKING:
    from efm3d.aria.pose import PoseTW

    from .candidate_generation import CandidateViewGeneratorConfig


class PositionSampler:
    """Sample candidate centers around a reference pose."""

    def __init__(self, cfg: CandidateViewGeneratorConfig):
        self.cfg = cfg

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

        cfg = self.cfg
        device = dirs_rig.device
        dtype = dirs_rig.dtype

        x, y, z = dirs_rig.unbind(dim=-1)

        # Azimuth scaling (around +Y). Keep distribution uniform over the target band.
        if cfg.delta_azimuth_deg < 360.0 - 1e-3:
            az_raw = torch.atan2(x, z)  # [-pi, pi]
            scale_az = torch.tensor(cfg.delta_azimuth_rad, device=device, dtype=dtype) / (2 * torch.pi)
            az_scaled = az_raw * scale_az  # now in [-delta/2, delta/2]
            x = torch.sin(az_scaled)
            z = torch.cos(az_scaled)

        # Elevation scaling via y = sin(elev) interval mapping.
        y_min = torch.sin(torch.tensor(cfg.min_elev_rad, device=device, dtype=dtype))
        y_max = torch.sin(torch.tensor(cfg.max_elev_rad, device=device, dtype=dtype))
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
        """Fallback: sample unit vectors via backend-independent CPU noise."""
        dirs = torch.randn(n_draw, 3, device="cpu", dtype=torch.float32).to(self.cfg.device)
        return dirs / dirs.norm(dim=-1, keepdim=True).clamp_min(1e-8)

    def _target_direction_ref(self, reference_pose: PoseTW) -> torch.Tensor:
        """Return normalized actor-visible target bearing in the reference frame."""

        target_world = self.cfg.position_target_point_world
        if target_world is None:
            raise ValueError(f"{self.cfg.position_mode.value} requires position_target_point_world.")
        target_world = torch.as_tensor(target_world, device=self.cfg.device, dtype=torch.float32).reshape(1, 3)
        target_ref = reference_pose.inverse().transform(target_world).reshape(3)
        if torch.linalg.norm(target_ref) < 1e-6:
            target_ref = torch.tensor(DEVICE_FWD, device=self.cfg.device, dtype=torch.float32)
        return target_ref / torch.linalg.norm(target_ref).clamp_min(1e-8)

    def _direction_around(self, base: torch.Tensor, noise: torch.Tensor, *, spread: float) -> torch.Tensor:
        """Blend a base direction with orthogonal noise in the reference frame."""

        base = base.to(device=noise.device, dtype=noise.dtype).reshape(1, 3)
        base = base / base.norm(dim=-1, keepdim=True).clamp_min(1e-8)
        parallel = (noise * base).sum(dim=-1, keepdim=True) * base
        orthogonal = noise - parallel
        dirs = base + float(spread) * orthogonal
        return dirs / dirs.norm(dim=-1, keepdim=True).clamp_min(1e-8)

    def _apply_position_mode(self, dirs_rig: torch.Tensor, reference_pose: PoseTW) -> torch.Tensor:
        """Map raw angular samples to the configured position family."""

        match self.cfg.position_mode:
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
                target_dir = self._target_direction_ref(reference_pose).to(device=dirs_rig.device, dtype=dirs_rig.dtype)
                return self._direction_around(target_dir, dirs_rig, spread=0.4)
            case CandidatePositionMode.LATERAL_TARGET_BYPASS:
                target_dir = self._target_direction_ref(reference_pose).to(device=dirs_rig.device, dtype=dirs_rig.dtype)
                up = torch.tensor([0.0, 1.0, 0.0], device=dirs_rig.device, dtype=dirs_rig.dtype)
                lateral = torch.cross(up, target_dir, dim=0)
                if torch.linalg.norm(lateral) < 1e-6:
                    lateral = torch.tensor([1.0, 0.0, 0.0], device=dirs_rig.device, dtype=dirs_rig.dtype)
                lateral = lateral / lateral.norm().clamp_min(1e-8)
                signs = torch.where(dirs_rig[:, 0] >= 0.0, 1.0, -1.0).to(dtype=dirs_rig.dtype).unsqueeze(1)
                vertical = up.reshape(1, 3) * dirs_rig[:, 1:2].clamp(-0.35, 0.35)
                dirs = 0.55 * target_dir.reshape(1, 3) + signs * 0.85 * lateral.reshape(1, 3) + vertical
                return dirs / dirs.norm(dim=-1, keepdim=True).clamp_min(1e-8)

    def sample(self, reference_pose: PoseTW) -> tuple[torch.Tensor, torch.Tensor]:
        """Draw candidate centers and offsets in reference frame.

        Args:
            reference_pose: ``PoseTW`` reference2world pose used as sampling origin.

        Returns:
            Tuple of ``(centers_world, offsets_ref)`` where both are ``Tensor[N, 3]`` with
            ``N = cfg.num_samples * cfg.oversample_factor``. Offsets are in the reference frame before rotation into world.
        """
        n_draw = ceil(self.cfg.num_samples * self.cfg.oversample_factor)

        # A seed must describe one pose set regardless of the compute backend.
        match self.cfg.sampling_strategy:
            case SamplingStrategy.UNIFORM_SPHERE:
                try:
                    dirs = HypersphericalUniform(dim=3, device="cpu").sample((n_draw,)).to(self.cfg.device)
                except Exception:
                    dirs = self._sample_unit_sphere(n_draw)
            case SamplingStrategy.FORWARD_POWERSPHERICAL:
                mu = torch.tensor(DEVICE_FWD, device="cpu")
                try:
                    dirs = PowerSpherical(
                        mu,
                        torch.tensor(self.cfg.kappa, device="cpu"),
                    ).sample((n_draw,)).to(self.cfg.device)
                except Exception:
                    noise = self._sample_unit_sphere(n_draw)
                    kappa = float(self.cfg.kappa)
                    dirs = (mu.to(self.cfg.device) + noise / max(kappa, 1e-6)).to(dtype=noise.dtype)
        dirs_rig = dirs / dirs.norm(dim=-1, keepdim=True)

        # Work entirely in reference (rig) frame for angle limits.
        dirs_rig = self._scale_into_caps(dirs_rig)
        dirs_rig = self._apply_position_mode(dirs_rig, reference_pose)

        dirs_world = reference_pose.rotate(dirs_rig)
        offsets_rig = dirs_rig

        radii = torch.empty(dirs_world.shape[0], device="cpu", dtype=dirs_world.dtype).uniform_(
            self.cfg.min_radius, self.cfg.max_radius
        ).to(self.cfg.device)
        offsets_rig = offsets_rig * radii[:, None]
        centers_world = reference_pose.transform(offsets_rig)
        return centers_world, offsets_rig


__all__ = [
    "PositionSampler",
]
