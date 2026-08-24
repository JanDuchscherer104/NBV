r"""Encode reference-frame SE(3) poses with R6D and learned Fourier features.

This module owns the active candidate-pose encoder interface and the R6D plus
learnable Fourier feature implementation used by VIN-Core (v3). A pose
$T_{AB}$ maps coordinates from frame $B$ into frame $A$; its translation
$t_{AB}$ is therefore the origin of $B$ expressed in $A$, in metres.

The active encoder forms

$$
x(T_{AB})=[s_t t_{AB},s_r\operatorname{R6D}(R_{AB})]\in\mathbb R^9,
$$

then passes that vector to :class:`LearnableFourierFeatures`. The positive
translation and rotation scales are independent learned coordinate
preconditioners, not physical units or uncertainty estimates.
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
    r"""Encode reference-frame translation and PyTorch3D rotation-6D through LFF.

    The representation is continuous for common rotations but is not an
    SE(3)-equivariant map: translation coordinates and rotation-matrix entries
    are interpreted in the caller-supplied reference rig frame.

    Theory:
        The two positive group scales are parameterized in log space:

        $$
        s_t=\exp(\alpha_t)+\epsilon,\qquad
        s_r=\exp(\alpha_r)+\epsilon.
        $$

        For a pose $T_{AB}=(R_{AB},t_{AB})$, the encoder input is

        $$
        x=[s_t t_{AB},s_r\operatorname{R6D}(R_{AB})]\in\mathbb R^9.
        $$

        :class:`LearnableFourierFeatures` maps $x$ through a learned projection,
        paired sine/cosine features, and an MLP. The default output width is 32.
        Scaling is shared across every pose encoded by this instance, including
        candidates, targets, and causal history in the finite-horizon scorer.

    Notes:
        $s_t$ and $s_r$ initialize from `pose_scale_init`, normally $(1,1)$.
        They rescale coordinates before feature learning; they do not alter the
        stored :class:`efm3d.aria.pose.PoseTW` or its frame semantics.
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
        r"""Encode poses already expressed in the caller-selected reference frame.

        Args:
            pose_rig: ``PoseTW["... 12"]`` transform $T_{AB}$ into reference
                frame $A$. Translation is metres; rotation is a valid matrix.

        Returns:
            :class:`PoseEncodingOutput` containing $t_{AB}$, the scaled
            nine-vector $[s_t t_{AB},s_r\operatorname{R6D}(R_{AB})]$, and its
            learned Fourier embedding.

        Notes:
            `matrix_to_rotation_6d` owns the exact PyTorch3D R6D convention.
            Callers own the meaning of frames $A$ and $B$; this method performs
            no frame conversion.
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
    r"""Initial positive multipliers $(s_t,s_r)$ for translation and R6D coordinates."""

    pose_scale_learnable: bool = True
    r"""Whether log-scales $(\alpha_t,\alpha_r)$ are learned; false keeps initial scales fixed."""

    pose_scale_eps: float = Field(default=1e-6, gt=0.0)
    r"""Positive $\epsilon$ added after exponentiation in $s=\exp(\alpha)+\epsilon$."""

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
