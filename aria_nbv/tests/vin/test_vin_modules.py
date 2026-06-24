"""Tests for reusable VIN neural modules."""

# ruff: noqa: S101

import torch

from aria_nbv.vin.modules import VinScorerHead, VinScorerHeadConfig, largest_divisor_leq


def test_vin_scorer_head_config_builds_coral_logits() -> None:
    """The public head factory should preserve leading batch and candidate axes."""
    config = VinScorerHeadConfig(hidden_dim=8, num_layers=2, num_classes=5)

    head = config.setup_target(in_dim=6)
    logits = head(torch.randn(2, 3, 6))

    assert isinstance(head, VinScorerHead)
    assert logits.shape == (2, 3, 4)


def test_largest_divisor_leq_returns_valid_group_count() -> None:
    """Normalization configs should resolve to valid GroupNorm group counts."""
    assert largest_divisor_leq(32, 8) == 8
    assert largest_divisor_leq(30, 8) == 6
    assert largest_divisor_leq(7, 8) == 7
    assert largest_divisor_leq(7, 3) == 1
