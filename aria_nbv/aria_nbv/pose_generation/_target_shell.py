"""Shared target-shell frame, measure, and support-boundary geometry."""

from __future__ import annotations

from math import radians

import torch

from ..utils.frames import world_up_tensor
from .config import ActorFacingCapSupportConfig, TargetShellSupportConfig

_EPS = 1.0e-6


def _actor_direction(
    actor_world: torch.Tensor,
    target_world: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Return actor direction, displacement, and world up on the input device."""

    actor_delta = actor_world.reshape(3) - target_world.reshape(3)
    actor_distance = torch.linalg.norm(actor_delta)
    if actor_distance < _EPS:
        raise ValueError("target_shell requires distinct target and reference centers.")
    world_up = world_up_tensor(device=actor_delta.device, dtype=actor_delta.dtype)
    return actor_delta / actor_distance, actor_delta, world_up


def target_shell_frame(
    actor_world: torch.Tensor,
    target_world: torch.Tensor,
    support: TargetShellSupportConfig,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Return the shared orthonormal support frame in world coordinates.

    Angular boxes use ``(forward, lateral, up)``. Actor-facing caps use
    ``(axis, tangent_a, tangent_b)``. Full-azimuth boxes are rotationally
    invariant and therefore use a deterministic horizontal basis when the
    target-to-actor baseline is vertical.
    """

    actor_direction, actor_delta, world_up = _actor_direction(actor_world, target_world)
    if isinstance(support, ActorFacingCapSupportConfig):
        tangent_a = torch.cross(world_up, actor_direction, dim=0)
        if torch.linalg.norm(tangent_a) < _EPS:
            tangent_a = torch.tensor([1.0, 0.0, 0.0], device=actor_delta.device, dtype=actor_delta.dtype)
        tangent_a = tangent_a / tangent_a.norm().clamp_min(_EPS)
        tangent_b = torch.cross(actor_direction, tangent_a, dim=0)
        return actor_direction, tangent_a, tangent_b

    horizontal = actor_delta - (actor_delta @ world_up) * world_up
    if torch.linalg.norm(horizontal) < _EPS:
        if support.azimuth_half_width_deg < 180.0 - 1.0e-6:
            raise ValueError(
                "restricted target_shell angular support requires a nonzero horizontal target-to-actor bearing."
            )
        forward = torch.tensor([1.0, 0.0, 0.0], device=actor_delta.device, dtype=actor_delta.dtype)
    else:
        forward = horizontal / horizontal.norm()
    lateral = torch.cross(world_up, forward, dim=0)
    return forward, lateral, world_up


def sample_target_shell_directions(
    actor_world: torch.Tensor,
    target_world: torch.Tensor,
    support: TargetShellSupportConfig,
    *,
    count: int,
) -> torch.Tensor:
    """Sample unit directions uniformly under the configured solid-angle measure."""

    axis, basis_a, basis_b = target_shell_frame(actor_world, target_world, support)
    device, dtype = actor_world.device, actor_world.dtype
    if isinstance(support, ActorFacingCapSupportConfig):
        cos_min = torch.cos(torch.tensor(radians(support.half_angle_deg), device=device, dtype=dtype))
        cos_theta = cos_min + torch.rand(count, device=device, dtype=dtype) * (1.0 - cos_min)
        sin_theta = torch.sqrt(torch.clamp(1.0 - cos_theta.square(), min=0.0))
        phi = (torch.rand(count, device=device, dtype=dtype) * 2.0 - 1.0) * torch.pi
        directions_world: torch.Tensor = cos_theta[:, None] * axis[None, :] + sin_theta[:, None] * (
            torch.cos(phi)[:, None] * basis_a[None, :] + torch.sin(phi)[:, None] * basis_b[None, :]
        )
        return directions_world

    azimuth_limit = radians(support.azimuth_half_width_deg)
    azimuth = (torch.rand(count, device=device, dtype=dtype) * 2.0 - 1.0) * azimuth_limit
    sin_elevation_min = torch.sin(torch.tensor(radians(support.elevation_min_deg), device=device, dtype=dtype))
    sin_elevation_max = torch.sin(torch.tensor(radians(support.elevation_max_deg), device=device, dtype=dtype))
    sin_elevation = sin_elevation_min + torch.rand(count, device=device, dtype=dtype) * (
        sin_elevation_max - sin_elevation_min
    )
    cos_elevation = torch.sqrt(torch.clamp(1.0 - sin_elevation.square(), min=0.0))
    return (
        cos_elevation[:, None]
        * (torch.cos(azimuth)[:, None] * axis[None, :] + torch.sin(azimuth)[:, None] * basis_a[None, :])
        + sin_elevation[:, None] * basis_b[None, :]
    )


def target_shell_boundary_directions(
    actor_world: torch.Tensor,
    target_world: torch.Tensor,
    support: TargetShellSupportConfig,
) -> torch.Tensor:
    """Return NaN-separated unit-direction curves for the configured support boundary."""

    axis, basis_a, basis_b = target_shell_frame(actor_world, target_world, support)
    device, dtype = actor_world.device, actor_world.dtype
    if isinstance(support, ActorFacingCapSupportConfig):
        phi = torch.linspace(-torch.pi, torch.pi, steps=181, device=device, dtype=dtype)
        theta = torch.tensor(radians(support.half_angle_deg), device=device, dtype=dtype)
        return torch.cos(theta) * axis[None, :] + torch.sin(theta) * (
            torch.cos(phi)[:, None] * basis_a[None, :] + torch.sin(phi)[:, None] * basis_b[None, :]
        )

    az_min = torch.tensor(-radians(support.azimuth_half_width_deg), device=device, dtype=dtype)
    az_max = -az_min
    el_min = torch.tensor(radians(support.elevation_min_deg), device=device, dtype=dtype)
    el_max = torch.tensor(radians(support.elevation_max_deg), device=device, dtype=dtype)
    az_sweep = torch.linspace(az_min, az_max, steps=121, device=device, dtype=dtype)
    el_sweep = torch.linspace(el_min, el_max, steps=61, device=device, dtype=dtype)

    def directions(azimuth: torch.Tensor, elevation: torch.Tensor) -> torch.Tensor:
        horizontal = torch.cos(azimuth)[:, None] * axis[None, :] + torch.sin(azimuth)[:, None] * basis_a[None, :]
        return torch.cos(elevation)[:, None] * horizontal + torch.sin(elevation)[:, None] * basis_b[None, :]

    edges = (
        directions(az_sweep, torch.full_like(az_sweep, float(el_min.item()))),
        directions(az_sweep, torch.full_like(az_sweep, float(el_max.item()))),
        directions(torch.full_like(el_sweep, float(az_min.item())), el_sweep),
        directions(torch.full_like(el_sweep, float(az_max.item())), el_sweep),
    )
    separator = torch.full((1, 3), torch.nan, device=device, dtype=dtype)
    return torch.cat([torch.cat((edge, separator), dim=0) for edge in edges], dim=0)


def target_shell_support_contains(
    directions_world: torch.Tensor,
    actor_world: torch.Tensor,
    target_world: torch.Tensor,
    support: TargetShellSupportConfig,
    *,
    atol: float = 1.0e-5,
) -> torch.Tensor:
    """Return whether each finite unit direction lies inside the configured support."""

    axis, basis_a, basis_b = target_shell_frame(actor_world, target_world, support)
    finite = torch.isfinite(directions_world).all(dim=-1)
    if isinstance(support, ActorFacingCapSupportConfig):
        threshold = torch.cos(
            torch.tensor(radians(support.half_angle_deg), device=directions_world.device, dtype=directions_world.dtype)
        )
        return finite & ((directions_world @ axis) >= threshold - atol)
    azimuth = torch.rad2deg(torch.atan2(directions_world @ basis_a, directions_world @ axis))
    elevation = torch.rad2deg(torch.asin((directions_world @ basis_b).clamp(-1.0, 1.0)))
    return (
        finite
        & (azimuth.abs() <= support.azimuth_half_width_deg + atol)
        & (elevation >= support.elevation_min_deg - atol)
        & (elevation <= support.elevation_max_deg + atol)
    )
