"""Private atomic gaze implementations for compiled candidate programs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch
from efm3d.aria.pose import PoseTW

from ._candidate_centers import _CenterBatch
from .candidate_errors import CandidateRequestMismatchError
from .candidate_program import (
    DirectionalGazeConfig,
    GazeFamily,
    GazeVariantConfig,
    TargetExactGazeConfig,
    TargetGlanceGazeConfig,
)
from .orientations import OrientationBuilder
from .types import SamplingStrategy, ViewDirectionMode


@dataclass(frozen=True, slots=True)
class _PoseProposalBatch:
    """One gaze hypothesis over an unchanged center batch."""

    centers: _CenterBatch
    shell_poses: PoseTW
    debug: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _GazeKernelConfig:
    """Resolved facts consumed only by the shipped orientation kernel."""

    verbosity: int
    view_direction_mode: ViewDirectionMode
    view_target_point_world: torch.Tensor | None
    view_sampling_strategy: SamplingStrategy | None
    view_kappa: float
    view_max_azimuth_deg: float
    view_max_elevation_deg: float
    view_roll_jitter_deg: float


def _assign_gaze(
    centers: _CenterBatch,
    variant: GazeVariantConfig,
    *,
    target_world: torch.Tensor | None,
) -> _PoseProposalBatch:
    """Assign one closed gaze variant without copying or resampling centers."""

    gaze = variant.gaze
    needs_target = gaze.family in {GazeFamily.TARGET_EXACT, GazeFamily.TARGET_GLANCE}
    if needs_target and target_world is None:
        raise CandidateRequestMismatchError(
            f"Candidate gaze family {variant.semantic_variant_id!r} requires actor_target."
        )
    config = _gaze_kernel_config(gaze, target_world=target_world)
    shell_poses, view_dirs_delta = OrientationBuilder(config).build(
        centers.sampling_pose,
        centers.centers_world,
    )
    candidate_count = centers.centers_world.shape[0]
    if view_dirs_delta is None:
        jitter_yaw_deg = torch.zeros(
            candidate_count,
            device=centers.centers_world.device,
            dtype=centers.centers_world.dtype,
        )
        jitter_pitch_deg = torch.zeros_like(jitter_yaw_deg)
    else:
        delta_forward = view_dirs_delta.R[:, :, 2]
        jitter_yaw_deg = torch.rad2deg(torch.atan2(delta_forward[:, 0], delta_forward[:, 2]))
        jitter_pitch_deg = torch.rad2deg(torch.asin(delta_forward[:, 1].clamp(-1.0, 1.0)))
    debug: dict[str, Any] = {
        "view_jitter_yaw_deg": jitter_yaw_deg,
        "view_jitter_pitch_deg": jitter_pitch_deg,
        "view_jitter_is_bounded": torch.full(
            (candidate_count,),
            bool(
                config.view_sampling_strategy is None
                or config.view_max_azimuth_deg > 0.0
                or config.view_max_elevation_deg > 0.0
            ),
            dtype=torch.bool,
            device=centers.centers_world.device,
        ),
        "view_jitter_azimuth_limit_deg": torch.full(
            (candidate_count,),
            config.view_max_azimuth_deg,
            device=centers.centers_world.device,
        ),
        "view_jitter_elevation_limit_deg": torch.full(
            (candidate_count,),
            config.view_max_elevation_deg,
            device=centers.centers_world.device,
        ),
    }
    if view_dirs_delta is not None:
        debug["view_dirs_delta"] = view_dirs_delta
    return _PoseProposalBatch(centers, shell_poses, debug)


def _gaze_kernel_config(
    gaze: DirectionalGazeConfig | TargetExactGazeConfig | TargetGlanceGazeConfig,
    *,
    target_world: torch.Tensor | None,
) -> _GazeKernelConfig:
    if isinstance(gaze, TargetExactGazeConfig):
        return _GazeKernelConfig(
            verbosity=0,
            view_direction_mode=ViewDirectionMode.TARGET_POINT,
            view_target_point_world=target_world,
            view_sampling_strategy=None,
            view_kappa=0.0,
            view_max_azimuth_deg=0.0,
            view_max_elevation_deg=0.0,
            view_roll_jitter_deg=0.0,
        )
    view_mode = (
        ViewDirectionMode.TARGET_POINT
        if isinstance(gaze, TargetGlanceGazeConfig)
        else ViewDirectionMode(gaze.family.value)
    )
    return _GazeKernelConfig(
        verbosity=0,
        view_direction_mode=view_mode,
        view_target_point_world=target_world if isinstance(gaze, TargetGlanceGazeConfig) else None,
        view_sampling_strategy=gaze.sampling_strategy,
        view_kappa=gaze.concentration,
        view_max_azimuth_deg=gaze.max_azimuth_deg,
        view_max_elevation_deg=gaze.max_elevation_deg,
        view_roll_jitter_deg=gaze.roll_jitter_deg,
    )


__all__: list[str] = []
