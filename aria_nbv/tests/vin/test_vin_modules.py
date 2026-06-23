"""Tests for reusable VIN neural modules."""

# ruff: noqa: S101

import torch

from aria_nbv.vin.modules import VinScorerHead, VinScorerHeadConfig


def test_vin_scorer_head_config_builds_coral_logits() -> None:
    """The public head factory should preserve leading batch and candidate axes."""
    config = VinScorerHeadConfig(hidden_dim=8, num_layers=2, num_classes=5)

    head = config.setup_target(in_dim=6)
    logits = head(torch.randn(2, 3, 6))

    assert isinstance(head, VinScorerHead)
    assert logits.shape == (2, 3, 4)
