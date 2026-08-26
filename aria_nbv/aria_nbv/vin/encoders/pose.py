"""Pose encoder modules for VIN candidate views.

This module owns the active candidate-pose encoder interface and the R6D plus
learnable Fourier feature implementation used by VIN-Core (v3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

import torch
from efm3d.aria.pose import PoseTW
from pydantic import Field, field_validator
from pytorch3d.transforms import matrix_to_rotation_6d
from torch import Tensor, nn

from ...utils import TargetConfig
from .fourier import LearnableFourierFeatures, LearnableFourierFeaturesConfig


@dataclass(slots=True)
class PoseEncodingOutput:
    """Pose-encoding outputs for a pose expressed in a reference frame.

    Attributes:
        center_m: ``Tensor["... 3", float32]`` translation in the reference frame.
        pose_vec: ``Tensor["... D", float32]`` pose vector fed into the encoder.
        pose_enc: ``Tensor["... E", float32]`` encoded pose embedding.
        center_dir: Optional ``Tensor["... 3", float32]`` unit direction to center.
        forward_dir: Optional ``Tensor["... 3", float32]`` forward direction in ref frame.
        radius_m: Optional ``Tensor["... 1", float32]`` radius ``||t||``.
        view_alignment: Optional ``Tensor["... 1", float32]`` dot ``<f, -u>``.
    """

    center_m: Tensor
    """``Tensor["... 3", float32]`` translation in the reference frame."""

    pose_vec: Tensor
    """``Tensor["... D", float32]`` pose vector fed into the encoder."""

    pose_enc: Tensor
    """``Tensor["... E", float32]`` encoded pose embedding."""

    center_dir: Tensor | None = None
    """``Tensor["... 3", float32]`` unit center direction (optional)."""

    forward_dir: Tensor | None = None
    """``Tensor["... 3", float32]`` forward direction (optional)."""

    radius_m: Tensor | None = None
    """``Tensor["... 1", float32]`` radius ``||t||`` (optional)."""

    view_alignment: Tensor | None = None
    """``Tensor["... 1", float32]`` dot ``<f, -u>`` (optional)."""


class PoseEncoder(nn.Module):
    """Base interface for encoders of poses already in a reference frame."""

    pose_encoder_lff: LearnableFourierFeatures | None
    """Optional LFF submodule for diagnostics (None for SH-only encoders)."""

    @property
    def out_dim(self) -> int:  # pragma: no cover - interface only
        """Return the final pose-embedding feature width."""
        raise NotImplementedError

    def encode(self, pose_rig: PoseTW) -> PoseEncodingOutput:  # pragma: no cover - interface only
        """Encode a pose expressed in the reference frame."""
        raise NotImplementedError


class R6dLffPoseEncoder(PoseEncoder):
    """Encode reference-frame translation and rotation-6D through LFF.

    The representation is continuous for common rotations but is not an
    SE(3)-equivariant map: translation coordinates and rotation-matrix columns
    are interpreted in the caller-supplied reference rig frame.
    """

    def __init__(self, config: "R6dLffPoseEncoderConfig") -> None:
        super().__init__()
        self.config = config
        self.pose_encoder_lff = self.config.pose_encoder_lff.setup_target()

        scale_init = torch.tensor(self.config.pose_scale_init, dtype=torch.float32)
        if self.config.pose_scale_learnable:
            self.pose_scale_log = nn.Parameter(torch.log(scale_init))
        else:
            self.register_buffer("pose_scale_log", torch.log(scale_init), persistent=False)
        self.pose_scale_eps = float(self.config.pose_scale_eps)

    @property
    def out_dim(self) -> int:
        """Return the configured LFF pose-embedding width."""

        return int(self.pose_encoder_lff.out_dim)

    def _pose_scales(self) -> tuple[Tensor, Tensor]:
        scales = self.pose_scale_log.exp() + self.pose_scale_eps
        return scales[0], scales[1]

    def encode(self, pose_rig: PoseTW) -> PoseEncodingOutput:
        """Encode poses in the reference rig frame.

        Args:
            pose_rig: ``PoseTW["... 12"]`` pose in reference rig frame.

        Returns:
            PoseEncodingOutput containing translation, pose vector, and embedding.
        """
        center_m = pose_rig.t.to(dtype=torch.float32)
        r6d = matrix_to_rotation_6d(pose_rig.R.to(dtype=torch.float32))
        scale_t, scale_r = self._pose_scales()
        pose_vec = torch.cat([center_m * scale_t, r6d * scale_r], dim=-1)
        pose_enc = self.pose_encoder_lff(pose_vec)
        return PoseEncodingOutput(center_m=center_m, pose_vec=pose_vec, pose_enc=pose_enc)


class R6dLffPoseEncoderConfig(TargetConfig[R6dLffPoseEncoder]):
    """Configure reference-frame R6D plus LFF pose encoding."""

    @property
    def target_type(self) -> type[R6dLffPoseEncoder]:
        """Factory target for `aria_nbv.utils.base_config.BaseConfig.setup_target`."""
        return R6dLffPoseEncoder

    @property
    def out_dim(self) -> int:
        """Return the complete pose-embedding width seen by consumers.

        The pose encoder delegates feature construction to its LFF carrier.
        This property intentionally exposes the carrier's *emitted* width,
        including an optional raw ``[translation, rotation-6D]`` residual,
        rather than only the learned branch width.
        """

        return int(self.pose_encoder_lff.out_dim)

    kind: Literal["r6d_lff"] = "r6d_lff"
    """Discriminator for pose-encoder selection."""

    pose_encoder_lff: LearnableFourierFeaturesConfig = Field(
        default_factory=lambda: LearnableFourierFeaturesConfig(
            input_dim=9,
            fourier_dim=64,
            hidden_dim=128,
            output_dim=32,
        ),
    )
    """LFF encoder for ``[t, r6d]`` pose vectors (input_dim=9)."""

    pose_scale_init: tuple[Annotated[float, Field(gt=0.0)], Annotated[float, Field(gt=0.0)]] = (1.0, 1.0)
    """Initial per-group scale for translation and rotation (t, r6d)."""

    pose_scale_learnable: bool = True
    """Whether pose scaling parameters are learned."""

    pose_scale_eps: float = Field(default=1e-6, gt=0.0)
    """Numerical epsilon for pose scaling."""

    @field_validator("pose_encoder_lff")
    @classmethod
    def _validate_pose_encoder_lff(
        cls,
        value: LearnableFourierFeaturesConfig,
    ) -> LearnableFourierFeaturesConfig:
        if value.input_dim != 9:
            raise ValueError(
                "pose_encoder_lff.input_dim must be 9 for [t, r6d] pose vectors.",
            )
        return value


__all__ = [
    "PoseEncoder",
    "PoseEncodingOutput",
    "R6dLffPoseEncoder",
    "R6dLffPoseEncoderConfig",
]
