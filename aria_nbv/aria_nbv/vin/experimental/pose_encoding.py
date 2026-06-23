"""Experimental pose-encoding utilities not used by VIN-Core."""

from __future__ import annotations

import math

import torch
from pydantic import Field
from torch import Tensor, nn

from ...utils import TargetConfig
from ..encoders import LearnableFourierFeatures, LearnableFourierFeaturesConfig


class FourierFeatures(nn.Module):
    """Fixed/learnable Fourier features for scalar or vector inputs."""

    def __init__(self, config: "FourierFeaturesConfig") -> None:
        super().__init__()
        self.config = config
        self.input_dim = int(self.config.input_dim)
        self.num_frequencies = int(self.config.num_frequencies)
        self.include_input = bool(self.config.include_input)

        weights = torch.randn((self.num_frequencies, self.input_dim)) * float(self.config.init_scale)
        if self.config.learnable:
            self.freq = nn.Parameter(weights)
        else:
            self.register_buffer("freq", weights, persistent=False)

        self._div_term = math.sqrt(float(self.num_frequencies))

    @property
    def output_dim(self) -> int:
        """Return output feature dimension."""

        base = 2 * self.num_frequencies
        if self.include_input:
            base += self.input_dim
        return base

    def forward(self, x: Tensor) -> Tensor:
        """Apply Fourier feature mapping to inputs.

        Args:
            x: ``Tensor["... D", float32]`` input vectors.

        Returns:
            ``Tensor["... output_dim", float32]`` Fourier-encoded features.
        """
        if x.shape[-1] != self.input_dim:
            raise ValueError(f"Expected x[..., {self.input_dim}], got {tuple(x.shape)}.")

        proj = x @ self.freq.T
        fourier = torch.cat([torch.sin(proj), torch.cos(proj)], dim=-1) / self._div_term
        if not self.include_input:
            return fourier
        return torch.cat([x, fourier], dim=-1)


class FourierFeaturesConfig(TargetConfig[FourierFeatures]):
    """Config-as-factory wrapper for `FourierFeatures`."""

    @property
    def target_type(self) -> type[FourierFeatures]:
        return FourierFeatures

    input_dim: int = Field(default=1, gt=0)
    """Input dimensionality."""

    num_frequencies: int = Field(default=6, gt=0)
    """Number of Fourier frequencies."""

    include_input: bool = True
    """Concatenate raw inputs to the Fourier features when True."""

    learnable: bool = True
    """Whether the frequency matrix is learnable."""

    init_scale: float = Field(default=1.0, gt=0.0)
    """Stddev used to initialize the frequency matrix."""


__all__ = [
    "FourierFeatures",
    "FourierFeaturesConfig",
    "LearnableFourierFeatures",
    "LearnableFourierFeaturesConfig",
]
