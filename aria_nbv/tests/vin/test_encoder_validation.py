"""Tests for VIN encoder configuration validators."""

from __future__ import annotations

import pytest

from aria_nbv.vin.encoders import LearnableFourierFeaturesConfig, validate_pos_grid_xyz_encoder


def test_pos_grid_encoder_validator_accepts_xyz_lff_config() -> None:
    """Position-grid encoders consume metric XYZ coordinates."""
    config = LearnableFourierFeaturesConfig(input_dim=3)

    assert validate_pos_grid_xyz_encoder(config) is config


def test_pos_grid_encoder_validator_rejects_non_xyz_lff_config() -> None:
    """Mis-sized position-grid encoders fail at config validation time."""
    config = LearnableFourierFeaturesConfig(input_dim=6)

    with pytest.raises(ValueError, match="input_dim must be 3"):
        validate_pos_grid_xyz_encoder(config)
