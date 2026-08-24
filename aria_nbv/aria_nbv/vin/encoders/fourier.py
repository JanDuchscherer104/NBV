"""Learnable Fourier feature encoders for VIN continuous inputs.

This module provides `LearnableFourierFeatures`, which maps candidate pose
features or normalized voxel XYZ coordinates into a trainable positional
embedding. The implementation follows:

    *Learnable Fourier Features for Multi-Dimensional Spatial Positional Encoding*
    (NeurIPS 2021)

The implementation follows the paper's formulation (learned projection +
sin/cos features + small MLP). For reference, see the public implementation at:
https://github.com/JHLew/Learnable-Fourier-Features
"""

from __future__ import annotations

import math

import torch
from pydantic import Field
from torch import Tensor, nn

from ...utils import TargetConfig


class LearnableFourierFeatures(nn.Module):
    r"""Map continuous coordinates through learned sinusoidal features.

    This module maps continuous inputs $x \\in \\mathbb{R}^D$ into a learned
    feature space by:

    1) learning a projection matrix $W_r$,
    2) applying sinusoidal features, and
    3) mapping them through a small MLP.

    Compared to fixed random Fourier features, the learned projection and the
    MLP allow the encoding to adapt to the downstream task. This is a learned
    coordinate-feature inductive bias; the arbitrary projection and MLP do not
    enforce translation, rotation, or SE(3) equivariance.

    Theory:
        For input $x\in\mathbb R^D$ and an even Fourier width $F$, the learned
        matrix $W_r\in\mathbb R^{F/2\times D}$ produces

        $$
        z(x)=\frac{[\cos(xW_r^T),\sin(xW_r^T)]}{\sqrt F},\qquad
        E(x)=\operatorname{MLP}(z(x)).
        $$

        `include_input=True` returns $[x,E(x)]$; otherwise only $E(x)$ is
        emitted. $W_r$ is initialized from a zero-mean Gaussian scaled by
        `gamma` and is optimized jointly with the downstream model.
    """

    def __init__(self, config: "LearnableFourierFeaturesConfig") -> None:
        super().__init__()
        self.config = config
        self.input_dim = self.config.input_dim
        self.fourier_dim = self.config.fourier_dim
        self.hidden_dim = self.config.hidden_dim
        self.output_dim = self.config.output_dim
        self.include_input = self.config.include_input

        half = self.fourier_dim // 2
        self.Wr = nn.Parameter(torch.randn((half, self.input_dim)) * self.config.gamma)
        self.mlp = nn.Sequential(
            nn.Linear(self.fourier_dim, self.hidden_dim),
            nn.GELU(),
            nn.Linear(self.hidden_dim, self.output_dim),
        )
        self._div_term = math.sqrt(self.fourier_dim)

    @property
    def out_dim(self) -> int:
        """Return the emitted feature dimension, including raw inputs when enabled."""
        return (self.input_dim if self.include_input else 0) + self.output_dim

    def forward(self, x: Tensor) -> Tensor:
        """Encode vectors with the learned projection, sine/cosine map, and MLP.

        Args:
            x: ``Tensor["... D"]`` input vectors with ``D == input_dim``.

        Returns:
            ``Tensor["... E"]`` encoded vectors, optionally concatenated with
            the raw input when `LearnableFourierFeaturesConfig.include_input`
            is enabled.
        """
        if x.shape[-1] != self.input_dim:
            raise ValueError(f"Expected x[..., {self.input_dim}], got {tuple(x.shape)}.")

        xwr = x @ self.Wr.T
        fourier = torch.cat([torch.cos(xwr), torch.sin(xwr)], dim=-1) / self._div_term
        enc = self.mlp(fourier)
        if not self.include_input:
            return enc
        return torch.cat([x, enc], dim=-1)


class LearnableFourierFeaturesConfig(TargetConfig[LearnableFourierFeatures]):
    """Config-as-factory wrapper for `LearnableFourierFeatures`."""

    @property
    def target_type(self) -> type[LearnableFourierFeatures]:
        """Factory target for `aria_nbv.utils.base_config.BaseConfig.setup_target`."""
        return LearnableFourierFeatures

    input_dim: int = Field(default=6, gt=0)
    """Input dimensionality (default: 6 for SE(3) relative pose as translation + so(3) log)."""

    fourier_dim: int = Field(default=128, gt=0, multiple_of=2)
    """Fourier feature dimensionality (must be even)."""

    hidden_dim: int = Field(default=256, gt=0)
    """Hidden dimension of the internal MLP."""

    output_dim: int = Field(default=64, gt=0)
    """Output positional encoding dimensionality (per input vector)."""

    gamma: float = Field(default=1.0, gt=0.0)
    """Initialization scale (paper parameter $\\gamma$)."""

    include_input: bool = False
    """Concatenate raw inputs to the learned encoding when True."""
