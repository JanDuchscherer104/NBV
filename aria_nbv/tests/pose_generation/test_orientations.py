"""Unit tests for camera orientation jitter logic.

These tests validate the *local* view-jitter controls in
:class:`aria_nbv.pose_generation.orientations.OrientationBuilder`.
"""

# ruff: noqa: S101, D103, SLF001

from __future__ import annotations

import torch
from efm3d.aria.pose import PoseTW

from aria_nbv.pose_generation import orientations as orientations_module
from aria_nbv.pose_generation.candidate_generation import CandidateViewGeneratorConfig
from aria_nbv.pose_generation.orientations import OrientationBuilder
from aria_nbv.pose_generation.types import ViewDirectionMode


def _ref_pose() -> PoseTW:
    return PoseTW.from_Rt(torch.eye(3), torch.zeros(3))


def _legacy_yaw_pitch_rotation(yaw: torch.Tensor, pitch: torch.Tensor) -> torch.Tensor:
    cy, sy = torch.cos(yaw), torch.sin(yaw)
    cp, sp = torch.cos(pitch), torch.sin(pitch)
    n = yaw.shape[0]

    ry = torch.zeros(n, 3, 3, device=yaw.device, dtype=yaw.dtype)
    ry[:, 0, 0] = cy
    ry[:, 0, 2] = sy
    ry[:, 1, 1] = 1.0
    ry[:, 2, 0] = -sy
    ry[:, 2, 2] = cy

    rx = torch.zeros_like(ry)
    rx[:, 0, 0] = 1.0
    rx[:, 1, 1] = cp
    rx[:, 1, 2] = sp
    rx[:, 2, 1] = -sp
    rx[:, 2, 2] = cp

    return torch.matmul(ry, rx)


def _legacy_roll_rotation(roll: torch.Tensor) -> torch.Tensor:
    n = roll.shape[0]
    cr, sr = torch.cos(roll), torch.sin(roll)
    r_roll = torch.zeros(n, 3, 3, device=roll.device, dtype=roll.dtype)
    r_roll[:, 0, 0] = cr
    r_roll[:, 0, 1] = -sr
    r_roll[:, 1, 0] = sr
    r_roll[:, 1, 1] = cr
    r_roll[:, 2, 2] = 1.0
    return r_roll


def test_view_sampling_disabled_when_jitter_zero() -> None:
    cfg = CandidateViewGeneratorConfig(
        num_samples=1,
        view_max_azimuth_deg=0.0,
        view_max_elevation_deg=0.0,
        view_roll_jitter_deg=0.0,
        view_sampling_strategy=None,
    )

    centers = torch.tensor([[0.0, 0.0, 1.0]])
    poses, delta = OrientationBuilder(cfg).build(_ref_pose(), centers)

    assert delta is None
    assert torch.allclose(poses.R[0], torch.eye(3), atol=1e-6)


def test_target_point_gaze_is_exact_target_direction_even_outside_motion_envelope() -> None:
    reference = PoseTW.from_Rt(
        torch.tensor([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]]),
        torch.zeros(3),
    )
    cfg = CandidateViewGeneratorConfig(
        num_samples=1,
        view_direction_mode=ViewDirectionMode.TARGET_POINT,
        view_target_point_world=torch.tensor([10.0, 10.0, 0.0]),
        max_yaw_delta_deg=30.0,
        min_elev_deg=-12.0,
        max_elev_deg=18.0,
        view_max_azimuth_deg=0.0,
        view_max_elevation_deg=0.0,
    )
    poses, _ = OrientationBuilder(cfg).build(reference, torch.tensor([[1.0, 0.0, 0.0]]))

    forward = poses.R[:, :, 2]
    expected = torch.tensor([9.0, 10.0, 0.0])
    expected = expected / expected.norm()
    assert torch.allclose(forward[0], expected, atol=1e-6)


def test_view_jitter_respects_az_el_limits() -> None:
    max_az, max_el = 10.0, 5.0
    cfg = CandidateViewGeneratorConfig(
        num_samples=64,
        view_direction_mode=ViewDirectionMode.RADIAL_AWAY,
        view_max_azimuth_deg=max_az,
        view_max_elevation_deg=max_el,
    )

    centers = torch.tensor([[0.0, 0.0, 1.0]]).expand(cfg.num_samples, -1)
    poses, delta = OrientationBuilder(cfg).build(_ref_pose(), centers)

    fwd = poses.R[:, :, 2]
    az = torch.atan2(fwd[:, 0], fwd[:, 2])
    el = torch.asin(fwd[:, 1].clamp(-1.0, 1.0))

    assert torch.max(az.abs()) <= torch.deg2rad(torch.tensor(max_az)) + 1e-5
    assert torch.max(el.abs()) <= torch.deg2rad(torch.tensor(max_el)) + 1e-5

    assert delta is not None
    fwd_d = delta.R[:, :, 2]
    az_d = torch.atan2(fwd_d[:, 0], fwd_d[:, 2])
    el_d = torch.asin(fwd_d[:, 1].clamp(-1.0, 1.0))
    assert torch.max(az_d.abs()) <= torch.deg2rad(torch.tensor(max_az)) + 1e-5
    assert torch.max(el_d.abs()) <= torch.deg2rad(torch.tensor(max_el)) + 1e-5


def test_roll_jitter_keeps_forward_fixed() -> None:
    max_roll = 20.0
    cfg = CandidateViewGeneratorConfig(
        num_samples=128,
        view_direction_mode=ViewDirectionMode.RADIAL_AWAY,
        view_sampling_strategy=None,
        view_max_azimuth_deg=0.0,
        view_max_elevation_deg=0.0,
        view_roll_jitter_deg=max_roll,
    )

    centers = torch.tensor([[0.0, 0.0, 1.0]]).expand(cfg.num_samples, -1)
    poses, delta = OrientationBuilder(cfg).build(_ref_pose(), centers)

    assert delta is not None
    fwd = poses.R[:, :, 2]
    expected = torch.tensor([0.0, 0.0, 1.0], device=fwd.device, dtype=fwd.dtype).view(1, 3).expand_as(fwd)
    assert torch.allclose(fwd, expected, atol=1e-6)

    fwd_d = delta.R[:, :, 2]
    assert torch.allclose(fwd_d, expected, atol=1e-6)

    roll = torch.atan2(delta.R[:, 1, 0], delta.R[:, 1, 1])
    assert torch.max(roll.abs()) <= torch.deg2rad(torch.tensor(max_roll)) + 1e-5


def test_yaw_pitch_rotation_matches_legacy() -> None:
    torch.manual_seed(0)
    n = 256
    yaw = (torch.rand(n) - 0.5) * (2.0 * torch.pi)
    pitch = (torch.rand(n) - 0.5) * torch.pi

    expected = _legacy_yaw_pitch_rotation(yaw, pitch)
    got = orientations_module._yaw_pitch_rotation(yaw, pitch)

    assert torch.allclose(got, expected, atol=1e-6)


def test_roll_rotation_matches_legacy() -> None:
    torch.manual_seed(1)
    n = 256
    roll = (torch.rand(n) - 0.5) * (2.0 * torch.pi)

    expected = _legacy_roll_rotation(roll)
    got = orientations_module._roll_rotation(roll)

    assert torch.allclose(got, expected, atol=1e-6)
