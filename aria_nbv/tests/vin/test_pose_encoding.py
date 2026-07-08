"""Unit tests for VIN pose encoders."""

from __future__ import annotations

import pytest
import torch

from aria_nbv.vin.encoders import LearnableFourierFeaturesConfig


def test_learnable_fourier_features_gamma_sets_projection_scale() -> None:
    torch.manual_seed(0)

    gamma = 3.0
    cfg = LearnableFourierFeaturesConfig(
        input_dim=6,
        fourier_dim=1024,
        hidden_dim=32,
        output_dim=16,
        gamma=gamma,
        include_input=False,
    )
    lff = cfg.setup_target()

    # NOTE: The LFF paper uses a Gaussian init with std=gamma for the learned projection.
    # This test guards against accidental gamma^2 scaling, which injects overly high
    # frequencies and destabilizes training.
    assert float(lff.Wr.std().item()) == pytest.approx(gamma, rel=0.05)
