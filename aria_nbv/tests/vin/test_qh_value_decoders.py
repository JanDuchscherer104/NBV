"""Contracts for modular finite-horizon scalar-value decoders."""

# ruff: noqa: S101

from __future__ import annotations

import pytest
import torch
from pydantic import ValidationError

from aria_nbv.vin.modules.qh_value_decoders import (
    QhCoralValueDecoderConfig,
    QhRegressionValueDecoderConfig,
)


def _features() -> torch.Tensor:
    torch.manual_seed(23)
    return torch.randn(2, 3, 4, 8, requires_grad=True)


def test_regression_decoder_returns_only_scalar_conditional_q() -> None:
    features = _features()
    decoder = QhRegressionValueDecoderConfig().setup_target(
        in_dim=8,
        hidden_dim=16,
        dropout=0.0,
    )

    output = decoder(features)
    output.conditional_q.sum().backward()

    assert output.conditional_q.shape == features.shape[:-1]
    assert output.conditional_q.dtype is torch.float32
    assert output.coral is None
    assert features.grad is not None
    assert bool(features.grad.abs().sum() > 0)


def test_coral_decoder_returns_scalar_q_and_training_thresholds() -> None:
    features = _features()
    config = QhCoralValueDecoderConfig(
        bin_edges=(-0.5, 0.5),
        bin_values=(-1.0, 0.0, 1.0),
        preinit_bias=False,
    )
    decoder = config.setup_target(in_dim=8, hidden_dim=16, dropout=0.0)

    output = decoder(features)
    assert output.coral is not None
    output.conditional_q.sum().backward()

    assert output.conditional_q.shape == features.shape[:-1]
    assert output.coral.logits.shape == (*features.shape[:-1], 2)
    assert output.coral.bin_edges.tolist() == [-0.5, 0.5]
    assert output.coral.bin_values.tolist() == [-1.0, 0.0, 1.0]
    assert bool((output.conditional_q >= -1.0).all())
    assert bool((output.conditional_q <= 1.0).all())
    assert features.grad is not None
    assert bool(features.grad.abs().sum() > 0)
    state = decoder.state_dict()
    assert torch.equal(state["bin_edges"], torch.tensor([-0.5, 0.5]))
    assert torch.equal(state["bin_values"], torch.tensor([-1.0, 0.0, 1.0]))


def test_coral_decoder_is_equivariant_to_candidate_row_permutation() -> None:
    features = _features().detach()
    decoder = QhCoralValueDecoderConfig(
        bin_edges=(-0.5, 0.5),
        bin_values=(-1.0, 0.0, 1.0),
        preinit_bias=False,
    ).setup_target(in_dim=8, hidden_dim=16, dropout=0.0)
    permutation = torch.tensor([2, 0, 3, 1])

    expected = decoder(features)
    actual = decoder(features[:, :, permutation])

    assert expected.coral is not None
    assert actual.coral is not None
    assert torch.allclose(actual.conditional_q, expected.conditional_q[:, :, permutation])
    assert torch.allclose(actual.coral.logits, expected.coral.logits[:, :, permutation])


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (
            {"bin_edges": (0.0,), "bin_values": (-1.0, 0.0, 1.0)},
            "exactly one more",
        ),
        (
            {"bin_edges": (0.0, 0.0), "bin_values": (-1.0, 0.0, 1.0)},
            "strictly increasing",
        ),
        (
            {"bin_edges": (0.0, 1.0), "bin_values": (-1.0, 0.0, 0.0)},
            "strictly increasing",
        ),
        (
            {"bin_edges": (-2.0, 0.5), "bin_values": (-1.0, 0.0, 1.0)},
            "adjacent representatives",
        ),
        (
            {"bin_edges": (float("nan"), 0.5), "bin_values": (-1.0, 0.0, 1.0)},
            "finite",
        ),
    ],
)
def test_coral_config_rejects_ambiguous_or_nonfinite_support(
    config: dict[str, tuple[float, ...]],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        QhCoralValueDecoderConfig(**config)
