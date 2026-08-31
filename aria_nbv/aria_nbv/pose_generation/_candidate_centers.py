"""Private atomic center implementations for compiled candidate programs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import radians
from typing import Any, cast

import torch
from efm3d.aria.pose import PoseTW

from ..utils.frames import rotate_yaw_cw90
from .candidate_errors import CandidateRequestMismatchError
from .candidate_generation import _gravity_align_pose
from .candidate_program import CandidateGroup, CenterFamily, SampledCenterConfig, TargetOrbitCenterConfig
from .positional_sampling import PositionSampler
from .types import CandidatePositionMode, SamplingStrategy
from .utils import ensure_unbatched_pose

_DEFAULT_TARGET_ORBIT_ANGLES_DEG = (-6.0, 6.0, -10.0, 10.0, -14.0, 14.0, -18.0, 18.0, -22.0, 22.0, -26.0, 26.0)


def _pose_to_device(pose: PoseTW, device: torch.device) -> PoseTW:
    """Cross the untyped EFM device-transfer boundary."""

    transfer: Callable[..., Any] = pose.to
    return cast(PoseTW, transfer(device))


@dataclass(frozen=True, slots=True)
class _CenterBatch:
    """One group's exact center tensors shared by every gaze variant."""

    reference_pose: PoseTW
    sampling_pose: PoseTW
    centers_world: torch.Tensor
    offsets_ref: torch.Tensor


@dataclass(frozen=True, slots=True)
class _CenterKernelConfig:
    """Resolved facts consumed only by the shipped positional kernel."""

    num_samples: int
    oversample_factor: float
    device: torch.device
    sampling_strategy: SamplingStrategy
    kappa: float
    min_radius: float
    max_radius: float
    min_elev_rad: float
    max_elev_rad: float
    delta_azimuth_deg: float
    delta_azimuth_rad: float
    position_mode: CandidatePositionMode
    position_target_point_world: torch.Tensor | None
    target_orbit_angles_deg: tuple[float, ...]


def _sample_centers(
    group: CandidateGroup,
    reference_pose_world: PoseTW,
    *,
    target_world: torch.Tensor | None,
    device: torch.device,
) -> _CenterBatch:
    """Sample one center table from a closed center-family configuration."""

    center = group.center
    needs_target = center.family in {
        CenterFamily.TARGET_BEARING_LOCAL,
        CenterFamily.TARGET_ORBIT,
        CenterFamily.LATERAL_TARGET_BYPASS,
    }
    if needs_target and target_world is None:
        raise CandidateRequestMismatchError(
            f"Candidate center family {group.semantic_group_id!r} requires actor_target."
        )
    reference_pose = rotate_yaw_cw90(ensure_unbatched_pose(_pose_to_device(reference_pose_world, device)))
    sampling_pose = _gravity_align_pose(reference_pose) if center.align_to_gravity else reference_pose
    config = _center_kernel_config(group, target_world=target_world, device=device)
    centers_world, offsets_ref = PositionSampler(config).sample(sampling_pose)
    return _CenterBatch(reference_pose, sampling_pose, centers_world, offsets_ref)


def _center_kernel_config(
    group: CandidateGroup,
    *,
    target_world: torch.Tensor | None,
    device: torch.device,
) -> _CenterKernelConfig:
    center = group.center
    orbit_angles = (
        center.target_orbit_angles_deg
        if isinstance(center, TargetOrbitCenterConfig)
        else _DEFAULT_TARGET_ORBIT_ANGLES_DEG
    )
    if not isinstance(center, (SampledCenterConfig, TargetOrbitCenterConfig)):
        raise TypeError(f"Unsupported center config: {type(center).__name__}.")
    return _CenterKernelConfig(
        num_samples=group.center_count,
        oversample_factor=1.0,
        device=device,
        sampling_strategy=center.sampling_strategy,
        kappa=center.concentration,
        min_radius=center.min_radius_m,
        max_radius=center.max_radius_m,
        min_elev_rad=radians(center.min_elevation_deg),
        max_elev_rad=radians(center.max_elevation_deg),
        delta_azimuth_deg=center.delta_azimuth_deg,
        delta_azimuth_rad=radians(center.delta_azimuth_deg),
        position_mode=CandidatePositionMode(center.family.value),
        position_target_point_world=target_world if _needs_target_center(center.family) else None,
        target_orbit_angles_deg=orbit_angles,
    )


def _needs_target_center(family: CenterFamily) -> bool:
    """Return whether a closed center family consumes the actor target."""

    return family in {
        CenterFamily.TARGET_BEARING_LOCAL,
        CenterFamily.TARGET_ORBIT,
        CenterFamily.LATERAL_TARGET_BYPASS,
    }


__all__: list[str] = []
