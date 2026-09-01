r"""Orientation builder for finite candidate camera poses.

This module assigns camera frames after candidate centers have been sampled.
It does not decide whether a candidate is valid; it only constructs base
orientations and optional local jitter.

It provides :class:`OrientationBuilder` plus local yaw, pitch, roll, and
normalization helpers. Candidate positions and actor-visible target context are
supplied by the generator, while pruning rules own feasibility decisions and
renderers own camera projection.

Theory:
    `forward_rig` copies the reference rig rotation, while `radial_away` and
    `radial_towards` align the camera with the reference-candidate ray. In
    `target_point` mode, an actor-visible target center $p_e$ defines a look-at
    frame for candidate center $c_w$:

    $$
    z_w=\operatorname{norm}(p_e-c_w),\quad
    y_w=\operatorname{norm}(u_{\mathrm{up}}-(u_{\mathrm{up}}^\top z_w)z_w),
    \quad x_w=y_w\times z_w.
    $$

    View jitter samples yaw and pitch in the local camera frame,
    $\delta\psi\sim\mathcal{U}(-\psi_{\max},\psi_{\max})$ and
    $\delta\theta\sim\mathcal{U}(-\theta_{\max},\theta_{\max})$, then builds a
    roll-free local forward axis before optional roll jitter is applied.
"""

from __future__ import annotations

import torch
from efm3d.aria.pose import PoseTW
from power_spherical import HypersphericalUniform, PowerSpherical  # type: ignore[import-untyped]

from ..utils import Console, Verbosity
from ..utils.frames import view_axes_from_poses, world_up_tensor
from .config import (
    BoxViewJitterConfig,
    CandidateGazeConfig,
    NoViewJitterConfig,
    SphericalViewJitterConfig,
)
from .geometry import DEVICE_FWD
from .types import SamplingStrategy, ViewDirectionMode


class OrientationBuilder:
    """Construct candidate camera orientations from centers and view settings."""

    def __init__(self, config: CandidateGazeConfig, *, verbosity: Verbosity):
        self.config = config
        self.console = Console.with_prefix(self.__class__.__name__).set_verbose(verbosity)

    def _sample_view_dirs_cam(self, num: int, device: torch.device, dtype: torch.dtype) -> torch.Tensor:
        """Sample camera-forward directions in the base camera frame without rejection.

        Sampling rules (priority order):
        1) If both az/el caps are zero and ``view_sampling_strategy`` is ``None`` → deterministic forward.
        2) If any cap is set → box-uniform in yaw/pitch: yaw ~ U(-az, az), pitch ~ U(-el, el).
           This is cheap, unbiased inside the box, and matches the intent of "small jitter".
        3) Else if a sampling_strategy is set → draw from the chosen distribution (legacy path).
        """

        jitter = self.config.jitter
        if isinstance(jitter, NoViewJitterConfig):
            v = torch.tensor(DEVICE_FWD, device=device, dtype=dtype)
            return v.view(1, 3).expand(num, 3)

        if isinstance(jitter, BoxViewJitterConfig):
            az_limit = torch.deg2rad(torch.tensor(jitter.yaw_half_width_deg, device=device, dtype=dtype))
            el_limit = torch.deg2rad(torch.tensor(jitter.pitch_half_width_deg, device=device, dtype=dtype))
            self.console.dbg(
                f"Sampling view deltas with daz={jitter.yaw_half_width_deg}°, del={jitter.pitch_half_width_deg}°"
            )
            yaw = (torch.rand(num, device=device, dtype=dtype) * 2.0 - 1.0) * az_limit
            pitch = (torch.rand(num, device=device, dtype=dtype) * 2.0 - 1.0) * el_limit
            cos_pitch = torch.cos(pitch)
            dirs = torch.stack(
                [
                    cos_pitch * torch.sin(yaw),
                    torch.sin(pitch),
                    cos_pitch * torch.cos(yaw),
                ],
                dim=-1,
            )
            return _normalise(dirs)

        # 3) Legacy distributions when no caps are provided.
        assert isinstance(jitter, SphericalViewJitterConfig)
        strat = jitter.distribution
        if strat == SamplingStrategy.UNIFORM_SPHERE:
            dist = HypersphericalUniform(dim=3, device=device, dtype=dtype)
        elif strat == SamplingStrategy.FORWARD_POWERSPHERICAL:
            mu = torch.tensor(DEVICE_FWD, device=device, dtype=dtype)
            scale = torch.tensor(jitter.concentration, device=device, dtype=dtype)
            dist = PowerSpherical(loc=mu, scale=scale)
        else:
            v = torch.tensor(DEVICE_FWD, device=device, dtype=dtype)
            return v.view(1, 3).expand(num, 3)

        return _normalise(dist.rsample((num,)))

    def build(
        self,
        reference_pose: PoseTW,
        centers_world: torch.Tensor,
        *,
        target_center_world: torch.Tensor | None,
    ) -> tuple[PoseTW, PoseTW | None]:
        """Construct cam2world candidate poses for given centers.

        Args:
            reference_pose:
                reference2world `PoseTW` used as origin for radial modes and as source of the rig2world
                rotation.
            centers_world:
                `Tensor['N, 3']` candidate camera centers in the world frame.

        Returns:
            `PoseTW` instance encoding cam2world SE(3) transforms for all candidates (length `N`).

        This method takes a reference2world rig pose and world-space candidate centers and returns per-candidate
        `PoseTW` cam2world transforms. It proceeds in two stages:

        1. Construct base poses according to `ViewDirectionMode`:

           * `ViewDirectionMode.FORWARD_RIG`:
             reuse the rig rotation for all candidates and place cameras at `centers_world`.
           * `ViewDirectionMode.RADIAL_AWAY` / `RADIAL_TOWARDS`:
             call `view_axes_from_poses` so that camera optical axes point away from or towards the reference
             pose along the center-reference line, keeping x horizontal.
           * `ViewDirectionMode.TARGET_POINT`:
             build look-at frames for the configured target point, using the world up vector to stabilise roll.

        2. Apply local view jitter:

           * sample camera-frame forward axes via `_sample_view_dirs_cam`,
           * build orthonormal camera bases from these directions,
           * optionally apply roll jitter around the forward axis, and
           * compose the resulting rotations as right-multiplicative deltas with the base cam2world poses.
        """
        cfg = self.config
        device = centers_world.device
        dtype = centers_world.dtype
        n = centers_world.shape[0]

        reference_pose_dev = reference_pose

        match cfg.mode:
            case ViewDirectionMode.FORWARD_RIG:
                r_last = reference_pose_dev.R
                if r_last.ndim == 3:
                    r_last = r_last[0]
                r_base = r_last.unsqueeze(0).expand(n, 3, 3)
                base_poses = PoseTW.from_Rt(r_base, centers_world)
            case ViewDirectionMode.RADIAL_AWAY | ViewDirectionMode.RADIAL_TOWARDS:
                eye = torch.eye(3, device=device, dtype=dtype).expand(n, 3, 3)
                centers_pose = PoseTW.from_Rt(eye, centers_world)
                base_poses = view_axes_from_poses(
                    from_pose=reference_pose_dev,
                    to_pose=centers_pose,
                    look_away=(cfg.mode is ViewDirectionMode.RADIAL_AWAY),
                )

            case ViewDirectionMode.TARGET_POINT:
                if target_center_world is None:
                    raise ValueError("TARGET_POINT mode requires target_center_world.")
                target = target_center_world.to(device=device, dtype=dtype).view(1, 3)
                wup = world_up_tensor(device=device, dtype=dtype)
                v = target - centers_world
                z_world = v / v.norm(dim=-1, keepdim=True).clamp_min(1e-6)
                dot_up = (z_world * wup.view(1, 3)).sum(dim=-1, keepdim=True)
                y_world = wup.view(1, 3) - dot_up * z_world
                y_world = y_world / y_world.norm(dim=-1, keepdim=True).clamp_min(1e-6)
                x_world = torch.cross(y_world, z_world, dim=-1)
                r_base = torch.stack([x_world, y_world, z_world], dim=-1)
                base_poses = PoseTW.from_Rt(r_base, centers_world)

        if isinstance(cfg.jitter, NoViewJitterConfig):
            return base_poses, None

        dirs_cam = self._sample_view_dirs_cam(n, device=device, dtype=dtype)

        z_new = dirs_cam / dirs_cam.norm(dim=-1, keepdim=True).clamp_min(1e-6)
        # Derive yaw/pitch from the jittered forward and build roll-free rotation.
        yaw = torch.atan2(z_new[:, 0], z_new[:, 2])  # around +Y (up)
        pitch = torch.asin(z_new[:, 1].clamp(-1.0, 1.0))  # around +X (left)

        r_delta = _yaw_pitch_rotation(yaw, pitch)

        roll_half_width_deg = (
            cfg.jitter.roll_half_width_deg
            if isinstance(cfg.jitter, BoxViewJitterConfig | SphericalViewJitterConfig)
            else 0.0
        )
        if roll_half_width_deg > 0.0:
            # Jitter is applied as a rotation matrix about the forward axis so the basis stays orthonormal. Adding Gaussian noise to direction vectors would skew/scale them unless you re‑orthogonalise anyway (which is what this code guarantees).
            roll = (2.0 * torch.rand(n, device=device, dtype=dtype) - 1.0) * torch.deg2rad(
                torch.tensor(roll_half_width_deg, device=device, dtype=dtype)
            )
            r_roll = _roll_rotation(roll)
            r_delta = torch.matmul(r_delta, r_roll)

        delta_poses = PoseTW.from_Rt(r_delta, torch.zeros_like(centers_world))
        return base_poses.compose(delta_poses), delta_poses


def _yaw_pitch_rotation(yaw: torch.Tensor, pitch: torch.Tensor) -> torch.Tensor:
    """Build a roll-free rotation matrix for yaw (about +Y) then pitch (about +X)."""
    cy, sy = torch.cos(yaw), torch.sin(yaw)
    cp, sp = torch.cos(pitch), torch.sin(pitch)
    zeros = torch.zeros_like(cy)

    return torch.stack(
        [
            torch.stack([cy, -sy * sp, sy * cp], dim=-1),
            torch.stack([zeros, cp, sp], dim=-1),
            torch.stack([-sy, -cy * sp, cy * cp], dim=-1),
        ],
        dim=-2,
    )


def _roll_rotation(roll: torch.Tensor) -> torch.Tensor:
    """Build a rotation matrix for roll about +Z (forward)."""
    cr, sr = torch.cos(roll), torch.sin(roll)
    zeros = torch.zeros_like(cr)
    ones = torch.ones_like(cr)

    return torch.stack(
        [
            torch.stack([cr, -sr, zeros], dim=-1),
            torch.stack([sr, cr, zeros], dim=-1),
            torch.stack([zeros, zeros, ones], dim=-1),
        ],
        dim=-2,
    )


def _normalise(v: torch.Tensor) -> torch.Tensor:
    return v / v.norm(dim=-1, keepdim=True).clamp_min(torch.finfo(v.dtype).eps)


__all__ = ["OrientationBuilder"]
