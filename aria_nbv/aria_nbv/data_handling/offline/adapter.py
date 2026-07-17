"""Canonical helpers for adapting raw EFM snippets into VIN snippet views.

This module owns the single supported transformation from
`EfmSnippetView` to `VinSnippetView`:
- collapse padded per-frame semidense points,
- optionally cap the collapsed point count,
- pad or truncate to a fixed on-disk/runtime point budget,
- preserve the snippet trajectory needed by VIN models.

The adapter is actor-visible preprocessing. It does not attach oracle RRI,
target matches, GT crops, or candidate labels; those belong to offline writers
or rollout replay generation.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import torch
from efm3d.aria.pose import PoseTW

from ..raw.views import EfmSnippetView, VinSnippetView

DEFAULT_VIN_SNIPPET_PAD_POINTS = 50000


def vin_snippet_cache_config_hash(
    *,
    dataset_config: dict[str, Any] | None,
    include_inv_dist_std: bool,
    include_obs_count: bool,
    semidense_max_points: int | None,
    pad_points: int | None,
) -> str:
    """Hash source and semidense-collapse settings for VIN payload compatibility."""
    payload = {
        "dataset_config": dataset_config,
        "include_inv_dist_std": include_inv_dist_std,
        "include_obs_count": include_obs_count,
        "semidense_max_points": semidense_max_points,
        "pad_points": pad_points,
    }
    serial = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha1(serial.encode("utf-8")).hexdigest()


def collapse_vin_points(
    efm_snippet: EfmSnippetView,
    *,
    device: torch.device,
    max_points: int | None,
    include_inv_dist_std: bool = True,
    include_obs_count: bool = False,
) -> torch.Tensor:
    """Collapse actor-visible MPS points across snippet time for VIN input.

    Returns:
        ``Tensor["K 3+C", float32]`` world-frame points in metres on ``device``.
        Optional columns are inverse distance uncertainty followed by
        observation count; no GT mesh, OBB label, or oracle reward is included.
    """
    extra_dim = int(include_inv_dist_std) + int(include_obs_count)
    points_world = torch.zeros((0, 3 + extra_dim), dtype=torch.float32, device=device)
    try:
        semidense = efm_snippet.semidense
    except Exception:
        semidense = None
    if semidense is None:
        return points_world
    return semidense.collapse_points(
        max_points=max_points,
        include_inv_dist_std=include_inv_dist_std,
        include_obs_count=include_obs_count,
    ).to(device=device, dtype=torch.float32)


def pad_vin_points(
    points_world: torch.Tensor,
    *,
    pad_points: int | None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Pad or truncate VIN point rows while preserving a valid-prefix length.

    Returns:
        Tuple containing ``Tensor["K_pad D", float32]`` points with NaN tail
        padding and ``Tensor["1", int64]`` valid length. Without ``pad_points``,
        ``K_pad`` equals the input row count.
    """
    valid_len = int(points_world.shape[0])
    lengths = torch.tensor([valid_len], device=points_world.device, dtype=torch.int64)
    if pad_points is None:
        return points_world, lengths

    target = int(pad_points)
    if target < 0:
        raise ValueError("pad_points must be >= 0 when provided.")
    if valid_len > target:
        points_world = points_world[:target]
        valid_len = target
    if valid_len < target:
        pad = torch.full(
            (target - valid_len, points_world.shape[1]),
            float("nan"),
            dtype=points_world.dtype,
            device=points_world.device,
        )
        points_world = torch.cat([points_world[:valid_len], pad], dim=0)
    lengths = torch.tensor([valid_len], device=points_world.device, dtype=torch.int64)
    return points_world, lengths


def build_vin_snippet_view(
    efm_snippet: EfmSnippetView,
    *,
    device: torch.device,
    max_points: int | None,
    include_inv_dist_std: bool = True,
    include_obs_count: bool = False,
    pad_points: int | None = None,
) -> VinSnippetView:
    """Build the canonical actor-visible VIN view from an adapted EFM snippet.

    The returned :class:`VinSnippetView` owns collapsed world-frame semidense
    points, a valid-prefix length, and the MPS/EFM world←rig trajectory. Missing
    semidense or trajectory fields yield empty typed tensors; oracle assets are
    intentionally excluded.
    """
    points_world = collapse_vin_points(
        efm_snippet,
        device=device,
        max_points=max_points,
        include_inv_dist_std=include_inv_dist_std,
        include_obs_count=include_obs_count,
    )
    points_world, lengths = pad_vin_points(points_world, pad_points=pad_points)

    traj_world_rig = PoseTW(torch.zeros((0, 12), dtype=torch.float32, device=device))
    try:
        traj_view = efm_snippet.trajectory.to(device=device, dtype=torch.float32)
        traj_world_rig = traj_view.t_world_rig
    except Exception:
        pass

    return VinSnippetView(points_world=points_world, lengths=lengths, t_world_rig=traj_world_rig)


def empty_vin_snippet(
    device: torch.device,
    *,
    extra_dim: int = 1,
    pad_points: int | None = None,
) -> VinSnippetView:
    """Return a shape-valid VIN view with no observed points or trajectory.

    ``points_world`` has logical shape ``Tensor["K_pad 3+C", float32]`` where
    ``C=extra_dim``; ``lengths`` is zero and any fixed-width rows are NaN
    padding. This sentinel carries no GT/oracle information.
    """
    points_world = torch.zeros((0, 3 + int(extra_dim)), dtype=torch.float32, device=device)
    points_world, lengths = pad_vin_points(points_world, pad_points=pad_points)
    return VinSnippetView(
        points_world=points_world,
        lengths=lengths,
        t_world_rig=PoseTW(torch.zeros((0, 12), dtype=torch.float32, device=device)),
    )


__all__ = [
    "DEFAULT_VIN_SNIPPET_PAD_POINTS",
    "build_vin_snippet_view",
    "collapse_vin_points",
    "empty_vin_snippet",
    "pad_vin_points",
    "vin_snippet_cache_config_hash",
]
