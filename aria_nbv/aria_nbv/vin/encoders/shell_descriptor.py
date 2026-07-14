"""Shared shell-pose descriptors for VIN candidate encoders.

The shell encoders describe a candidate view by its center direction, optical
axis, radial distance, and view-target alignment in a reference rig frame. This
module owns that geometry in one place so `aria_nbv.vin.encoders.shell_pose`
can expose multiple `torch.nn.Module` encoders without duplicating frame math.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from efm3d.aria.pose import PoseTW
from torch import Tensor


@dataclass(slots=True)
class ShellPoseDescriptor:
    """Canonical shell descriptor for a candidate pose.

    Attributes:
        center_m: ``Tensor["... 3", float32]`` candidate center in the
            reference rig frame, measured in meters.
        center_dir: ``Tensor["... 3", float32]`` unit direction from the
            reference origin to the candidate center.
        forward_dir: ``Tensor["... 3", float32]`` candidate camera optical axis
            expressed in the reference rig frame.
        radius_m: ``Tensor["... 1", float32]`` radial distance ``||center_m||``.
        view_alignment: ``Tensor["... 1", float32]`` dot product
            ``<forward_dir, -center_dir>``; higher values look back toward the
            shell center.
        pose_vec: ``Tensor["... 8", float32]`` concatenated
            ``[center_dir, forward_dir, radius_m, view_alignment]`` vector.
    """

    center_m: Tensor
    """``Tensor["... 3", float32]`` center in reference-frame metres."""

    center_dir: Tensor
    """``Tensor["... 3", float32]`` unit direction from reference origin."""

    forward_dir: Tensor
    """``Tensor["... 3", float32]`` camera ``+Z`` axis in the reference frame."""

    radius_m: Tensor
    """``Tensor["... 1", float32]`` reference-frame radial distance in metres."""

    view_alignment: Tensor
    """``Tensor["... 1", float32]`` forward-to-inward alignment in ``[-1, 1]``."""

    pose_vec: Tensor
    """``Tensor["... 8", float32]`` concatenated shell descriptor."""


def encode_shell_pose_descriptor(pose_rig: PoseTW) -> ShellPoseDescriptor:
    """Build the canonical shell descriptor for poses in a reference frame.

    Args:
        pose_rig: ``PoseTW["... 12"]`` candidate pose expressed in the
            reference rig frame. Its translation defines the shell center
            direction and radius; its rotation defines the candidate optical
            axis through the local ``+Z`` camera-forward convention.

    Returns:
        `ShellPoseDescriptor` containing normalized shell geometry and the
        concatenated 8D pose vector consumed by shell LFF and SH encoders.

    Notes:
        The descriptor intentionally ignores roll about the optical axis. Use
        `aria_nbv.vin.encoders.pose.R6dLffPoseEncoder` when roll sensitivity is
        training-visible.
    """
    center_m = pose_rig.t.to(dtype=torch.float32)
    radius_m = torch.linalg.vector_norm(center_m, dim=-1, keepdim=True)
    center_dir = center_m / (radius_m + 1e-8)

    cam_forward_axis = torch.tensor(
        [0.0, 0.0, 1.0],
        device=center_m.device,
        dtype=torch.float32,
    )
    forward_dir = torch.einsum(
        "...ij,j->...i",
        pose_rig.R.to(dtype=torch.float32),
        cam_forward_axis,
    )
    forward_dir = forward_dir / (torch.linalg.vector_norm(forward_dir, dim=-1, keepdim=True) + 1e-8)
    view_alignment = (forward_dir * (-center_dir)).sum(dim=-1, keepdim=True)
    pose_vec = torch.cat([center_dir, forward_dir, radius_m, view_alignment], dim=-1)
    return ShellPoseDescriptor(
        center_m=center_m,
        center_dir=center_dir,
        forward_dir=forward_dir,
        radius_m=radius_m,
        view_alignment=view_alignment,
        pose_vec=pose_vec,
    )


__all__ = ["ShellPoseDescriptor", "encode_shell_pose_descriptor"]
