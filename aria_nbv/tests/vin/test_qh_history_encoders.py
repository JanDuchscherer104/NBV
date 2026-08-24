"""Unit contracts for modular finite-horizon selected-pose history encoders."""

# ruff: noqa: S101

from __future__ import annotations

import pytest
import torch

from aria_nbv.vin.modules.qh_history_encoders import (
    QhCausalTransformerHistoryEncoderConfig,
    QhMeanPoolHistoryEncoderConfig,
)


def _support(
    *, batch_size: int = 2, steps: int = 4, realized_steps: int | None = None
) -> tuple[torch.Tensor, torch.Tensor]:
    realized = steps if realized_steps is None else realized_steps
    step_mask = torch.arange(steps).unsqueeze(0).expand(batch_size, -1) < realized
    state = torch.arange(steps).view(1, steps, 1)
    history = torch.arange(steps).view(1, 1, steps)
    history_mask = step_mask.unsqueeze(-1) & history.lt(state)
    return history_mask, step_mask


def test_qh_mean_history_reproduces_original_masked_mean_exactly() -> None:
    torch.manual_seed(3)
    features = torch.randn(2, 4, 4, 8)
    history_mask, step_mask = _support()
    encoder = QhMeanPoolHistoryEncoderConfig().setup_target(
        feature_dim=8,
        max_horizon=4,
        dropout=0.0,
    )

    expected = torch.where(history_mask.unsqueeze(-1), features, torch.zeros_like(features)).sum(dim=-2)
    expected /= history_mask.sum(dim=-1, keepdim=True).clamp_min(1)

    assert not encoder.state_dict()
    assert torch.equal(encoder(features, history_mask, step_mask), expected)


def test_qh_ordered_history_changes_when_only_noncurrent_prefix_order_changes() -> None:
    torch.manual_seed(5)
    features = torch.randn(1, 4, 4, 8)
    history_mask, step_mask = _support(batch_size=1)
    permuted = features.clone()
    permuted[:, 3, [0, 1]] = permuted[:, 3, [1, 0]]
    mean = QhMeanPoolHistoryEncoderConfig().setup_target(feature_dim=8, max_horizon=4, dropout=0.0)
    ordered = QhCausalTransformerHistoryEncoderConfig(attention_heads=2).setup_target(
        feature_dim=8,
        max_horizon=4,
        dropout=0.0,
    )
    ordered.eval()

    assert torch.allclose(
        mean(features, history_mask, step_mask),
        mean(permuted, history_mask, step_mask),
        atol=1e-7,
        rtol=1e-7,
    )
    assert not torch.allclose(
        ordered(features, history_mask, step_mask)[:, 3],
        ordered(permuted, history_mask, step_mask)[:, 3],
    )


def test_qh_ordered_history_ignores_numeric_contents_of_padding() -> None:
    torch.manual_seed(7)
    features = torch.randn(2, 4, 4, 8)
    history_mask, step_mask = _support()
    changed = features.clone()
    changed[~history_mask] = 1.0e6
    encoder = QhCausalTransformerHistoryEncoderConfig(attention_heads=2).setup_target(
        feature_dim=8,
        max_horizon=4,
        dropout=0.0,
    )
    encoder.eval()

    assert torch.allclose(
        encoder(features, history_mask, step_mask),
        encoder(changed, history_mask, step_mask),
        atol=1e-6,
        rtol=1e-6,
    )


def test_qh_ordered_history_distinguishes_realized_empty_root_from_padding() -> None:
    features = torch.zeros(1, 4, 4, 8)
    history_mask, step_mask = _support(batch_size=1, realized_steps=2)
    encoder = QhCausalTransformerHistoryEncoderConfig(attention_heads=2).setup_target(
        feature_dim=8,
        max_horizon=4,
        dropout=0.0,
    )
    encoder.eval()
    with torch.no_grad():
        encoder.empty_history.fill_(0.25)

    output = encoder(features, history_mask, step_mask)

    assert torch.isfinite(output[:, 0]).all()
    assert bool(output[:, 0].abs().sum() > 0)
    assert torch.equal(output[:, 2:], torch.zeros_like(output[:, 2:]))


def test_qh_history_encoder_rejects_a_hole_in_realized_prefix() -> None:
    features = torch.zeros(1, 4, 4, 8)
    history_mask, step_mask = _support(batch_size=1)
    history_mask[:, 3, 1] = False
    encoder = QhCausalTransformerHistoryEncoderConfig(attention_heads=2).setup_target(
        feature_dim=8,
        max_horizon=4,
        dropout=0.0,
    )

    with pytest.raises(ValueError, match="complete strictly causal prefix"):
        encoder(features, history_mask, step_mask)


def test_qh_ordered_history_rejects_incompatible_attention_width() -> None:
    with pytest.raises(ValueError, match="divisible"):
        QhCausalTransformerHistoryEncoderConfig(attention_heads=3).setup_target(
            feature_dim=8,
            max_horizon=4,
            dropout=0.0,
        )
