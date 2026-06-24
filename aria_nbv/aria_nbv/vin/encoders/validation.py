"""Validation helpers for VIN encoder configuration objects.

The module keeps encoder-specific invariants next to the encoder package
instead of burying them in model orchestration code. These helpers are intended
for Pydantic validators on scorer configs such as `VinModelV3Config`.
"""

from __future__ import annotations

from .fourier import LearnableFourierFeaturesConfig


def validate_pos_grid_xyz_encoder(
    value: LearnableFourierFeaturesConfig,
) -> LearnableFourierFeaturesConfig:
    """Require a position-grid Fourier encoder to consume XYZ coordinates.

    VIN positional grids are passed as metric 3D coordinates before
    `LearnableFourierFeatures` expands them. The encoder therefore must keep
    `input_dim == 3`; any other input width indicates a config/schema mismatch
    rather than a recoverable runtime condition.
    """
    if value.input_dim != 3:
        raise ValueError("pos_grid_encoder_lff.input_dim must be 3 for XYZ coordinates.")
    return value


__all__ = ["validate_pos_grid_xyz_encoder"]
