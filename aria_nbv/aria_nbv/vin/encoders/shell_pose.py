"""Shell-pose encoder modules for VIN candidates.

Shell encoders describe a candidate by the direction from the reference pose to
the candidate center, the candidate optical axis, the radial distance, and a
view-target alignment scalar. They are useful for shell-sampled NBV candidates
where roll about the optical axis is not semantically important.
"""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from efm3d.aria.pose import PoseTW
from pydantic import Field, field_validator

from ...utils import TargetConfig
from .fourier import LearnableFourierFeaturesConfig
from .pose import PoseEncoder, PoseEncodingOutput, R6dLffPoseEncoderConfig
from .shell_descriptor import encode_shell_pose_descriptor
from .spherical import ShellShPoseEncoderConfig


class ShellShPoseEncoderAdapter(PoseEncoder):
    """Adapt `ShellShPoseEncoder` to the common pose-encoder interface.

    The adapter accepts `efm3d.aria.pose.PoseTW` poses, derives the canonical
    shell descriptor with `encode_shell_pose_descriptor`, and delegates the
    direction/radius tensors to
    `aria_nbv.vin.encoders.spherical.ShellShPoseEncoder`.
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
        descriptor = encode_shell_pose_descriptor(pose_rig)
        pose_enc = self.sh_encoder(
            descriptor.center_dir,
            descriptor.forward_dir,
            r=descriptor.radius_m,
            scalars=descriptor.view_alignment,
        )
        return PoseEncodingOutput(
            center_m=descriptor.center_m,
            pose_vec=descriptor.pose_vec,
            pose_enc=pose_enc,
            center_dir=descriptor.center_dir,
            forward_dir=descriptor.forward_dir,
            radius_m=descriptor.radius_m,
            view_alignment=descriptor.view_alignment,
        )


class ShellLffPoseEncoder(PoseEncoder):
    """Encode canonical shell descriptors with learned Fourier features.

    The input pose must already be expressed in the reference rig frame. The
    emitted pose vector is ``[center_dir, forward_dir, radius_m,
    view_alignment]`` and has dimension 8.
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
        descriptor = encode_shell_pose_descriptor(pose_rig)
        pose_enc = self.pose_encoder_lff(descriptor.pose_vec)
        return PoseEncodingOutput(
            center_m=descriptor.center_m,
            pose_vec=descriptor.pose_vec,
            pose_enc=pose_enc,
            center_dir=descriptor.center_dir,
            forward_dir=descriptor.forward_dir,
            radius_m=descriptor.radius_m,
            view_alignment=descriptor.view_alignment,
        )


class ShellLffPoseEncoderConfig(TargetConfig[ShellLffPoseEncoder]):
    """Config-as-factory wrapper for `ShellLffPoseEncoder`."""

    @property
    def target_type(self) -> type[ShellLffPoseEncoder]:
        """Factory target for `aria_nbv.utils.base_config.BaseConfig.setup_target`."""
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
    """Config-as-factory wrapper for `ShellShPoseEncoderAdapter`."""

    @property
    def target_type(self) -> type[ShellShPoseEncoderAdapter]:
        """Factory target for `aria_nbv.utils.base_config.BaseConfig.setup_target`."""
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
    "R6dLffPoseEncoderConfig",
    "ShellLffPoseEncoder",
    "ShellLffPoseEncoderConfig",
    "ShellShPoseEncoderAdapter",
    "ShellShPoseEncoderAdapterConfig",
    "infer_pose_vec_groups",
]
