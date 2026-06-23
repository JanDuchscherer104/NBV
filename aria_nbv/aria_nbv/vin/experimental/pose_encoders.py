"""Pose encoder variants for VIN candidates.

This module centralizes pose-encoding logic that was previously embedded in
`VinModelV2`, allowing different encoders to be selected via configuration.
"""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

import torch
from efm3d.aria.pose import PoseTW
from pydantic import Field, field_validator

from ...utils import TargetConfig
from ..encoders import (
    LearnableFourierFeaturesConfig,
    PoseEncoder,
    PoseEncodingOutput,
    R6dLffPoseEncoder,
    R6dLffPoseEncoderConfig,
)
from .spherical_encoding import ShellShPoseEncoderConfig


class ShellShPoseEncoderAdapter(PoseEncoder):
    """Encode shell descriptors with SH-based encoder.

    Note: The SH descriptor uses only the forward direction and therefore does
    not encode roll about the forward axis. This is acceptable when roll jitter
    is small; use R6D LFF if roll sensitivity is needed.
    """

    def __init__(self, config: "ShellShPoseEncoderAdapterConfig") -> None:
        super().__init__()
        self.config = config
        self.sh_encoder = self.config.sh_encoder.setup_target()
        self.pose_encoder_lff = None

    @property
    def out_dim(self) -> int:
        return int(self.sh_encoder.out_dim)

    def encode(self, pose_rig: PoseTW) -> PoseEncodingOutput:
        """Encode shell pose descriptors with spherical harmonics."""
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
        pose_enc = self.sh_encoder(center_dir, forward_dir, r=radius_m, scalars=view_alignment)
        return PoseEncodingOutput(
            center_m=center_m,
            pose_vec=pose_vec,
            pose_enc=pose_enc,
            center_dir=center_dir,
            forward_dir=forward_dir,
            radius_m=radius_m,
            view_alignment=view_alignment,
        )


class ShellLffPoseEncoder(PoseEncoder):
    """Encode shell descriptors with LFF.

    Note: The shell descriptor uses only the forward direction. Roll about the
    forward axis is not represented; this is acceptable when roll jitter is
    small. Use the R6D encoder if roll needs to be captured.
    """

    def __init__(self, config: "ShellLffPoseEncoderConfig") -> None:
        super().__init__()
        self.config = config
        self.pose_encoder_lff = self.config.pose_encoder_lff.setup_target()

    @property
    def out_dim(self) -> int:
        return int(self.pose_encoder_lff.out_dim)

    def encode(self, pose_rig: PoseTW) -> PoseEncodingOutput:
        """Encode shell pose descriptors in the reference rig frame."""
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
        pose_enc = self.pose_encoder_lff(pose_vec)
        return PoseEncodingOutput(
            center_m=center_m,
            pose_vec=pose_vec,
            pose_enc=pose_enc,
            center_dir=center_dir,
            forward_dir=forward_dir,
            radius_m=radius_m,
            view_alignment=view_alignment,
        )


class ShellLffPoseEncoderConfig(TargetConfig[ShellLffPoseEncoder]):
    """Config for `ShellLffPoseEncoder`."""

    @property
    def target_type(self) -> type[ShellLffPoseEncoder]:
        return ShellLffPoseEncoder

    kind: Literal["shell_lff"] = "shell_lff"
    """Discriminator for pose-encoder selection."""

    pose_encoder_lff: LearnableFourierFeaturesConfig = Field(
        default_factory=lambda: LearnableFourierFeaturesConfig(input_dim=8),
    )
    """LFF encoder for shell pose vectors (input_dim=8)."""

    @field_validator("pose_encoder_lff")
    @classmethod
    def _validate_pose_encoder_lff(
        cls,
        value: LearnableFourierFeaturesConfig,
    ) -> LearnableFourierFeaturesConfig:
        if value.input_dim != 8:
            raise ValueError(
                "pose_encoder_lff.input_dim must be 8 for [u, f, r, s] pose vectors.",
            )
        return value


class ShellShPoseEncoderAdapterConfig(TargetConfig[ShellShPoseEncoderAdapter]):
    """Config for `ShellShPoseEncoderAdapter`."""

    @property
    def target_type(self) -> type[ShellShPoseEncoderAdapter]:
        return ShellShPoseEncoderAdapter

    kind: Literal["shell_sh"] = "shell_sh"
    """Discriminator for pose-encoder selection."""

    sh_encoder: ShellShPoseEncoderConfig = Field(
        default_factory=ShellShPoseEncoderConfig,
    )
    """Spherical-harmonics encoder configuration."""


def infer_pose_vec_groups(pose_vec_dim: int) -> list[tuple[str, slice]]:
    """Infer semantic groups for a pose-encoder input vector.

    Args:
        pose_vec_dim: Size of the pose vector ``D``.

    Returns:
        Ordered list of ``(name, slice)`` entries describing how to split the
        pose vector into semantic groups. Falls back to a single ``pose_vec``
        group when the dimensionality is unknown.
    """
    dim = int(pose_vec_dim)
    if dim == 9:
        return [
            ("translation", slice(0, 3)),
            ("rotation6d", slice(3, 9)),
        ]
    if dim == 8:
        return [
            ("center_dir", slice(0, 3)),
            ("forward_dir", slice(3, 6)),
            ("radius", slice(6, 7)),
            ("view_alignment", slice(7, 8)),
        ]
    return [("pose_vec", slice(0, dim))]


PoseEncoderConfig: TypeAlias = Annotated[
    R6dLffPoseEncoderConfig | ShellLffPoseEncoderConfig | ShellShPoseEncoderAdapterConfig,
    Field(discriminator="kind"),
]


__all__ = [
    "PoseEncoder",
    "PoseEncoderConfig",
    "PoseEncodingOutput",
    "R6dLffPoseEncoder",
    "R6dLffPoseEncoderConfig",
    "ShellLffPoseEncoder",
    "ShellLffPoseEncoderConfig",
    "ShellShPoseEncoderAdapter",
    "ShellShPoseEncoderAdapterConfig",
    "infer_pose_vec_groups",
]
