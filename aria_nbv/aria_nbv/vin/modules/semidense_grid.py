"""Semidense projection-grid encoders for VIN scorers.

This module owns reusable `torch.nn.Module` blocks that transform per-candidate
screen-space semidense projection grids into compact feature vectors. The
geometry helper `aria_nbv.vin.geometry.semidense_projection.build_projection_grid`
constructs the deterministic grid; the encoder defined here owns the learnable
convolutional projection used by the active VIN v3 scorer.
"""

from __future__ import annotations

import torch
from pydantic import Field
from torch import Tensor, nn

from ...utils import TargetConfig
from ..geometry.semidense_projection import build_projection_grid
from ..geometry.semidense_schema import SEMIDENSE_GRID_CHANNELS


class SemidenseGridEncoder(nn.Sequential):
    """Encode semidense projection grids with a small convolutional head.

    The class subclasses `torch.nn.Sequential` intentionally: when assigned to
    `VinModelV3.semidense_cnn`, learnable parameters keep the historical
    checkpoint keys `semidense_cnn.0.*`, `semidense_cnn.2.*`, and
    `semidense_cnn.6.*`. Do not wrap the layers in a child module unless a
    checkpoint migration is planned.
    """

    def __init__(self, config: "SemidenseGridEncoderConfig") -> None:
        """Build the projection-grid encoder.

        Args:
            config: Config-as-factory object that owns grid size, hidden
                channel width, and output feature dimension.
        """
        channels = int(config.channels)
        out_dim = int(config.out_dim)
        super().__init__(
            nn.Conv2d(SEMIDENSE_GRID_CHANNELS, channels, kernel_size=3, padding=1),
            nn.GELU(),
            nn.Conv2d(channels, channels, kernel_size=3, padding=1),
            nn.GELU(),
            nn.AdaptiveAvgPool2d((2, 2)),
            nn.Flatten(),
            nn.Linear(channels * 4, out_dim),
        )
        self.config = config

    def encode_projection_features(
        self,
        proj_data: dict[str, Tensor],
        *,
        batch_size: int,
        num_candidates: int,
        device: torch.device,
        dtype: torch.dtype,
    ) -> Tensor:
        """Return one CNN feature vector per batch/candidate projection.

        Args:
            proj_data: Projection output from
                `aria_nbv.vin.geometry.semidense_projection.project_points_to_candidate_cameras`.
            batch_size: Batch size ``B``.
            num_candidates: Number of candidate cameras ``Nq``.
            device: Device for the intermediate projection grid.
            dtype: Floating point dtype for the grid and returned features.

        Returns:
            ``Tensor["B Nq F"]`` where ``F`` is `SemidenseGridEncoderConfig.out_dim`.
        """
        num_cams = int(proj_data["num_cams"].item())
        grid = build_projection_grid(
            proj_data,
            device=device,
            dtype=dtype,
            grid_size=int(self.config.grid_size),
        )
        feats = self(grid)
        if batch_size == 1 and num_cams == num_candidates:
            return feats.view(1, num_candidates, -1)
        return feats.view(batch_size, num_candidates, -1)


class SemidenseGridEncoderConfig(TargetConfig[SemidenseGridEncoder]):
    """Configure the VIN semidense projection-grid CNN."""

    @property
    def target_type(self) -> type[SemidenseGridEncoder]:
        """Factory target for `BaseConfig.setup_target`."""
        return SemidenseGridEncoder

    grid_size: int = Field(default=24, gt=0)
    """Spatial side length of the deterministic projection grid."""

    channels: int = Field(default=8, gt=0)
    """Hidden channel width for the convolutional layers."""

    out_dim: int = Field(default=16, gt=0)
    """Output feature dimension per candidate projection."""


__all__ = ["SemidenseGridEncoder", "SemidenseGridEncoderConfig"]
