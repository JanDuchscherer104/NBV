"""Tests for reusable VIN neural modules."""

# ruff: noqa: S101

import torch

from aria_nbv.vin.modules import (
    SceneFieldProjection,
    SceneFieldProjectionConfig,
    VinScorerHead,
    VinScorerHeadConfig,
    largest_divisor_leq,
)


def test_scene_field_projection_config_builds_numbered_layers() -> None:
    """Scene-field projection should preserve direct Sequential layer keys."""
    projection = SceneFieldProjectionConfig(
        in_channels=6,
        field_dim=30,
        field_gn_groups=8,
    ).setup_target()

    assert isinstance(projection, SceneFieldProjection)
    assert isinstance(projection[0], torch.nn.Conv3d)
    assert projection[0].in_channels == 6
    assert projection[0].out_channels == 30
    assert projection[0].bias is None
    assert isinstance(projection[1], torch.nn.GroupNorm)
    assert projection[1].num_groups == 6
    assert projection[1].num_channels == 30
    assert isinstance(projection[2], torch.nn.GELU)

    out = projection(torch.randn(2, 6, 3, 3, 3))

    assert out.shape == (2, 30, 3, 3, 3)


def test_vin_scorer_head_config_builds_coral_logits() -> None:
    """The public head factory should preserve leading batch and candidate axes."""
    config = VinScorerHeadConfig(hidden_dim=8, num_layers=2, num_classes=5)

    head = config.setup_target(in_dim=6)
    logits = head(torch.randn(2, 3, 6))

    assert isinstance(head, VinScorerHead)
    assert logits.shape == (2, 3, 4)


def test_vin_scorer_head_config_controls_coral_bias_preinit() -> None:
    """The shared head should expose the CORAL bias initialization switch."""
    config = VinScorerHeadConfig(
        hidden_dim=8,
        num_classes=5,
        coral_preinit_bias=False,
    )

    head = config.setup_target(in_dim=6)
    logits = head(torch.randn(2, 6))

    assert logits.shape == (2, 4)
    assert torch.allclose(head.coral.layer.coral_bias, torch.zeros_like(head.coral.layer.coral_bias))


def test_largest_divisor_leq_returns_valid_group_count() -> None:
    """Normalization configs should resolve to valid GroupNorm group counts."""
    assert largest_divisor_leq(32, 8) == 8
    assert largest_divisor_leq(30, 8) == 6
    assert largest_divisor_leq(7, 8) == 7
    assert largest_divisor_leq(7, 3) == 1
