"""Geometric contracts for the opt-in target-centric shell center family."""

from __future__ import annotations

from math import cos, radians, sin

import pytest
import torch
from efm3d.aria.pose import PoseTW

from aria_nbv.pose_generation.config import TargetShellCenterConfig, TargetShellSupportMode
from aria_nbv.pose_generation.positional_sampling import PositionSampler
from aria_nbv.utils.frames import world_up_tensor


def _pose_at(center: tuple[float, float, float], device: torch.device) -> PoseTW:
    return PoseTW.from_Rt(
        torch.eye(3, device=device, dtype=torch.float32),
        torch.tensor(center, device=device, dtype=torch.float32),
    )


def _available_devices() -> tuple[torch.device, ...]:
    devices = [torch.device("cpu")]
    if torch.cuda.is_available():
        devices.append(torch.device("cuda"))
    return tuple(devices)


@pytest.mark.parametrize("device", _available_devices(), ids=str)
def test_target_shell_angular_box_respects_radius_and_uniform_solid_angle(device: torch.device) -> None:
    cfg = TargetShellCenterConfig(
        radius_min_m=0.7,
        radius_max_m=1.3,
        support_mode=TargetShellSupportMode.ANGULAR_BOX,
        azimuth_half_width_deg=55.0,
        elevation_min_deg=-20.0,
        elevation_max_deg=35.0,
    )
    sampler = PositionSampler(cfg, device=device)
    reference = _pose_at((2.0, 0.0, 0.0), device)
    target = torch.zeros(3, device=device)

    torch.manual_seed(17)
    centers, offsets = sampler.sample(reference, count=16_384, target_center_world=target)

    target_to_center = centers - target
    radii = torch.linalg.norm(target_to_center, dim=1)
    directions = target_to_center / radii[:, None]
    world_up = world_up_tensor(device=device, dtype=directions.dtype)
    forward = torch.tensor([1.0, 0.0, 0.0], device=device)
    lateral = torch.cross(world_up, forward, dim=0)
    azimuth = torch.rad2deg(torch.atan2(directions @ lateral, directions @ forward))
    sin_elevation = directions @ world_up

    assert centers.shape == offsets.shape == (16_384, 3)
    assert float(radii.min()) >= cfg.radius_min_m - 1e-5
    assert float(radii.max()) <= cfg.radius_max_m + 1e-5
    assert float(azimuth.abs().max()) <= cfg.azimuth_half_width_deg + 1e-4
    assert float(sin_elevation.min()) >= sin(radians(cfg.elevation_min_deg)) - 1e-5
    assert float(sin_elevation.max()) <= sin(radians(cfg.elevation_max_deg)) + 1e-5
    expected_sin_mean = 0.5 * (sin(radians(cfg.elevation_min_deg)) + sin(radians(cfg.elevation_max_deg)))
    assert abs(float(sin_elevation.mean()) - expected_sin_mean) < 0.01
    assert abs(float(azimuth.mean())) < 1.0


@pytest.mark.parametrize("device", _available_devices(), ids=str)
def test_target_shell_actor_facing_cap_is_uniform_in_cosine_and_reproducible(device: torch.device) -> None:
    cfg = TargetShellCenterConfig(
        radius_min_m=1.0,
        radius_max_m=1.0,
        support_mode=TargetShellSupportMode.ACTOR_FACING_CAP,
        cap_half_angle_deg=70.0,
    )
    sampler = PositionSampler(cfg, device=device)
    reference = _pose_at((2.0, -1.0, 1.5), device)
    target = torch.zeros(3, device=device)

    torch.manual_seed(29)
    centers_a, offsets_a = sampler.sample(reference, count=16_384, target_center_world=target)
    torch.manual_seed(29)
    centers_b, offsets_b = sampler.sample(reference, count=16_384, target_center_world=target)

    actor_direction = reference.t.reshape(3) / reference.t.reshape(3).norm()
    directions = torch.nn.functional.normalize(centers_a - target, dim=1)
    cosines = directions @ actor_direction
    cos_min = cos(radians(cfg.cap_half_angle_deg or 0.0))
    assert torch.equal(centers_a, centers_b)
    assert torch.equal(offsets_a, offsets_b)
    assert torch.allclose(torch.linalg.norm(centers_a - target, dim=1), torch.ones(16_384, device=device))
    assert float(cosines.min()) >= cos_min - 1e-5
    assert abs(float(cosines.mean()) - 0.5 * (1.0 + cos_min)) < 0.01


def test_target_shell_degenerate_target_geometry_fails_explicitly() -> None:
    angular = PositionSampler(
        TargetShellCenterConfig(
            radius_min_m=1.0,
            radius_max_m=1.0,
            support_mode=TargetShellSupportMode.ANGULAR_BOX,
        ),
        device=torch.device("cpu"),
    )
    cap = PositionSampler(
        TargetShellCenterConfig(
            radius_min_m=1.0,
            radius_max_m=1.0,
            support_mode=TargetShellSupportMode.ACTOR_FACING_CAP,
            cap_half_angle_deg=45.0,
        ),
        device=torch.device("cpu"),
    )

    with pytest.raises(ValueError, match="distinct target and reference"):
        cap.sample(_pose_at((0.0, 0.0, 0.0), torch.device("cpu")), count=4, target_center_world=torch.zeros(3))
    with pytest.raises(ValueError, match="nonzero horizontal"):
        angular.sample(_pose_at((0.0, 0.0, 2.0), torch.device("cpu")), count=4, target_center_world=torch.zeros(3))

    centers, _ = cap.sample(
        _pose_at((0.0, 0.0, 2.0), torch.device("cpu")),
        count=64,
        target_center_world=torch.zeros(3),
    )
    assert centers.shape == (64, 3)


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"radius_min_m": 2.0, "radius_max_m": 1.0}, "radius_min_m"),
        ({"elevation_min_deg": 20.0, "elevation_max_deg": 10.0}, "elevation_min_deg"),
        (
            {"support_mode": TargetShellSupportMode.UPPER_ANGULAR_BOX, "elevation_min_deg": -1.0},
            "elevation_min_deg >= 0",
        ),
        ({"support_mode": TargetShellSupportMode.ACTOR_FACING_CAP}, "cap_half_angle_deg"),
        ({"cap_half_angle_deg": 30.0}, "valid only"),
        (
            {
                "support_mode": TargetShellSupportMode.ACTOR_FACING_CAP,
                "cap_half_angle_deg": 30.0,
                "azimuth_half_width_deg": 60.0,
            },
            "full-range",
        ),
    ],
)
def test_target_shell_config_rejects_incompatible_support(values: dict[str, object], message: str) -> None:
    defaults: dict[str, object] = {
        "radius_min_m": 1.0,
        "radius_max_m": 1.5,
        "support_mode": TargetShellSupportMode.ANGULAR_BOX,
    }
    with pytest.raises(ValueError, match=message):
        TargetShellCenterConfig(**(defaults | values))
