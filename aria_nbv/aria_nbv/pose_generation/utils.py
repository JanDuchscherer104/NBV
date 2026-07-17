"""Frame-preserving pose and directional statistics for candidate generation.

Helpers operate on EFM ``PoseTW`` values or explicitly documented LUF
reference-frame vectors. Summary functions detach no state and return plain
statistics suitable for diagnostics and persisted reports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import torch
from efm3d.aria.pose import PoseTW

if TYPE_CHECKING:
    from .types import CandidateSamplingResult


def ensure_unbatched_pose(pose: PoseTW) -> PoseTW:
    """Squeeze a singleton batch from :class:`PoseTW` while preserving unbatched poses."""
    if pose._data.ndim == 2 and pose._data.shape[0] == 1:
        return PoseTW(pose._data.squeeze(0))
    return pose


def project_horizontal(v: torch.Tensor, wup: torch.Tensor) -> torch.Tensor:
    """Project vectors `v` onto the horizontal plane defined by world up `wup`."""
    dot = (v * wup).sum(dim=-1, keepdim=True)
    v_h = v - dot * wup
    return v_h / v_h.norm(dim=-1, keepdim=True).clamp_min(1e-6)


def _axis_stats(x: torch.Tensor) -> dict[str, float]:
    return {
        "min": float(x.min()),
        "max": float(x.max()),
        "mean": float(x.mean()),
        "std": float(x.std(unbiased=False)),
    }


def summarise_offsets_ref(offsets_ref: torch.Tensor) -> dict[str, dict[str, float]]:
    """Summarize radii and angles for LUF offsets ``Tensor[\"N 3\"]`` in metres."""
    r = offsets_ref.norm(dim=-1)
    az = torch.rad2deg(torch.atan2(offsets_ref[:, 0], offsets_ref[:, 2]))
    el = torch.rad2deg(torch.atan2(offsets_ref[:, 1], torch.linalg.norm(offsets_ref[:, (0, 2)], dim=-1) + 1e-8))
    return {"radius_m": _axis_stats(r), "az_deg": _axis_stats(az), "el_deg": _axis_stats(el)}


def summarise_dirs_ref(dirs_ref: torch.Tensor) -> dict[str, dict[str, float]]:
    """Summarize azimuth/elevation of LUF directions ``Tensor[\"N 3\"]``."""
    dirs = dirs_ref / dirs_ref.norm(dim=-1, keepdim=True).clamp_min(1e-8)
    az = torch.rad2deg(torch.atan2(dirs[:, 0], dirs[:, 2]))
    el = torch.rad2deg(torch.asin(dirs[:, 1].clamp(-1.0, 1.0)))
    return {"az_deg": _axis_stats(az), "el_deg": _axis_stats(el)}


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------


def stats_to_markdown_table(stats: dict[str, dict[str, float]], *, header: str | None = None) -> str:
    """Convert nested stats dict into a GitHub-flavoured Markdown table.

    Args:
        stats: Mapping like ``{"radius_m": {"min": .., "max": .., ...}}``.
        header: Optional table title inserted as a preceding bold line.

    Returns:
        Markdown string containing a table with columns ``metric | min | max | mean | std``.
    """

    lines: list[str] = []
    if header:
        lines.append(f"**{header}**")
    lines.append("metric | min | max | mean | std")
    lines.append(":--|--:|--:|--:|--:")
    for key, vals in stats.items():
        lines.append(f"{key} | {vals['min']:.3f} | {vals['max']:.3f} | {vals['mean']:.3f} | {vals['std']:.3f}")
    return "\n".join(lines)


def rejected_pose_tensor(candidates: CandidateSamplingResult) -> torch.Tensor | None:
    """Return rejected candidate poses as a tensor (or None if none rejected)."""
    mask_valid = candidates.mask_valid
    shell_poses = candidates.shell_poses
    if mask_valid is None or shell_poses is None or mask_valid.numel() == 0:
        return None
    shell_tensor = shell_poses.tensor() if hasattr(shell_poses, "tensor") else shell_poses
    if mask_valid.shape[0] != shell_tensor.shape[0]:
        return None
    rejected_mask = ~mask_valid
    if not rejected_mask.any():
        return None
    return shell_tensor[rejected_mask]
