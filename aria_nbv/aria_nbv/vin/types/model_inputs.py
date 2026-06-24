"""Model-input containers shared by VIN scorer implementations.

These dataclasses describe intermediate tensors assembled during VIN forward
passes. They are separate from helper functions so models, diagnostics, and
tests can depend on explicit contracts without importing utility buckets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import torch
from efm3d.aria.pose import PoseTW
from torch import Tensor

if TYPE_CHECKING:
    from ...data_handling import VinSnippetView


@dataclass(slots=True)
class PreparedInputs:
    """Prepared inputs for VIN v3-style forward passes.

    Attributes:
        pose_world_cam: ``PoseTW["B N 12"]`` candidate camera poses in world frame.
        pose_world_rig_ref: ``PoseTW["B 12"]`` reference rig pose in world frame.
        t_world_voxel: ``PoseTW["B 12"]`` world←voxel pose for the EVL voxel grid.
        batch_size: Batch size inferred from candidate poses.
        num_candidates: Number of candidate views per batch item.
        device: Device used for tensors in the forward pass.
        snippet: VIN snippet view with padded semidense evidence.
    """

    pose_world_cam: PoseTW
    """``PoseTW["B N 12"]`` candidate camera poses in world frame."""

    pose_world_rig_ref: PoseTW
    """``PoseTW["B 12"]`` reference rig pose in world frame."""

    t_world_voxel: PoseTW
    """``PoseTW["B 12"]`` world←voxel pose for the EVL voxel grid."""

    batch_size: int
    """Batch size inferred from candidate poses."""

    num_candidates: int
    """Number of candidate views per batch item."""

    device: torch.device
    """Device used for tensors in the forward pass."""

    snippet: VinSnippetView
    """VIN snippet view with padded semidense evidence."""


@dataclass(slots=True)
class PoseFeatures:
    """Pose-related feature tensors for VIN candidate views."""

    pose_enc: Tensor
    """``Tensor["B N E", float32]`` pose encoder output."""

    pose_vec: Tensor
    """``Tensor["B N D", float32]`` pose vector fed into the pose encoder."""

    candidate_center_rig_m: Tensor
    """``Tensor["B N 3", float32]`` candidate centers in the reference rig frame."""


@dataclass(slots=True)
class FieldBundle:
    """Scene-field tensors built from EVL backbone outputs."""

    field_in: Tensor
    """``Tensor["B C_in D H W", float32]`` raw scene field."""

    field: Tensor
    """``Tensor["B C_out D H W", float32]`` projected scene field."""

    aux: dict[str, Tensor]
    """Auxiliary channels, such as normalized counts and occupancy probabilities."""


@dataclass(slots=True)
class GlobalContext:
    """Pose-conditioned global scene context tensors."""

    pos_grid: Tensor
    """``Tensor["B 3 D H W", float32]`` normalized voxel position grid."""

    global_feat: Tensor
    """``Tensor["B N C", float32]`` pose-conditioned global features."""


__all__ = ["FieldBundle", "GlobalContext", "PoseFeatures", "PreparedInputs"]
