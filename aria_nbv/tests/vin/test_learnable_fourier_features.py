"""Tests for Learnable Fourier Features (LFF) pose encoding."""

# ruff: noqa: S101

from __future__ import annotations

import torch

from aria_nbv.vin.encoders import LearnableFourierFeaturesConfig


def test_lff_wr_init_uses_gamma_scaling() -> None:
    """Projection weights follow the current init `randn * gamma`."""
    gamma = 0.5
    cfg = LearnableFourierFeaturesConfig(
        input_dim=3,
        fourier_dim=8,
        hidden_dim=4,
        output_dim=6,
        gamma=gamma,
    )

    half = cfg.fourier_dim // 2
    torch.manual_seed(0)
    expected = torch.randn((half, cfg.input_dim)) * gamma

    torch.manual_seed(0)
    lff = cfg.setup_target()
    assert torch.allclose(lff.Wr, expected)


def test_lff_include_input_concatenates_raw_inputs() -> None:
    """`include_input=True` prepends the original inputs to the learned encoding."""
    cfg = LearnableFourierFeaturesConfig(
        input_dim=3,
        fourier_dim=8,
        hidden_dim=4,
        output_dim=6,
        include_input=True,
    )
    lff = cfg.setup_target()

    x = torch.randn((2, cfg.input_dim))
    out = lff(x)
    assert out.shape == (2, cfg.input_dim + cfg.output_dim)
    assert torch.allclose(out[:, : cfg.input_dim], x)
