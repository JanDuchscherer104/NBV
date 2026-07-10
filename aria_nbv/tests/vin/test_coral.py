"""Tests for CORAL utilities."""

# ruff: noqa: S101, D103

import math

import torch

from aria_nbv.vin.ordinal import (
    coral_logits_to_prob,
    coral_loss,
    coral_random_loss,
    ordinal_labels_to_levels,
)


def test_ordinal_label_to_levels() -> None:
    labels = torch.tensor([0, 1, 2, 3], dtype=torch.int64)
    levels = ordinal_labels_to_levels(labels, num_classes=4)
    assert levels.shape == (4, 3)
    assert torch.equal(
        levels,
        torch.tensor(
            [
                [0.0, 0.0, 0.0],  # y=0
                [1.0, 0.0, 0.0],  # y=1
                [1.0, 1.0, 0.0],  # y=2
                [1.0, 1.0, 1.0],  # y=3
            ],
        ),
    )


def test_coral_logits_to_prob_is_distribution() -> None:
    logits = torch.tensor([[2.0, 0.0, -2.0]])  # shape (1, K-1) with K=4
    prob = coral_logits_to_prob(logits)
    assert prob.shape == (1, 4)
    assert torch.all(prob >= 0)
    assert torch.allclose(prob.sum(dim=-1), torch.ones((1,)), atol=1e-6)


def test_coral_loss_scalar() -> None:
    logits = torch.zeros((5, 3), dtype=torch.float32)  # K=4
    labels = torch.tensor([0, 1, 2, 3, 1], dtype=torch.int64)
    loss = coral_loss(logits, labels, num_classes=4, reduction="mean")
    assert loss.ndim == 0
    assert torch.isfinite(loss)


def test_coral_random_loss() -> None:
    assert math.isclose(coral_random_loss(4), 3.0 * math.log(2.0))
