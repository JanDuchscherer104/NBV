"""Tests for prepared relative reconstruction improvement."""

from __future__ import annotations

import pytest
import torch

from aria_nbv.rri_metrics.point_mesh import DistanceBreakdown
from aria_nbv.rri_metrics.rri import RriConfig, compute_rri


def test_compute_rri_returns_directional_diagnostics() -> None:
    before = DistanceBreakdown(
        accuracy=torch.tensor(2.0),
        completeness=torch.tensor(3.0),
        bidirectional=torch.tensor(5.0),
    )
    after = DistanceBreakdown(
        accuracy=torch.tensor([1.0, 2.0]),
        completeness=torch.tensor([1.0, 2.0]),
        bidirectional=torch.tensor([2.0, 4.0]),
    )

    result = compute_rri(before, after)

    assert torch.allclose(result.rri, torch.tensor([0.6, 0.2]))
    assert torch.equal(result.pm_dist_before, torch.tensor([5.0, 5.0]))
    assert torch.equal(result.pm_dist_after, torch.tensor([2.0, 4.0]))


def test_compute_rri_preserves_autograd() -> None:
    before_error = torch.tensor(5.0, requires_grad=True)
    after_error = torch.tensor([2.0, 4.0], requires_grad=True)
    before = DistanceBreakdown(before_error, before_error, before_error)
    after = DistanceBreakdown(after_error, after_error, after_error)

    compute_rri(before, after).rri.sum().backward()

    assert before_error.grad is not None
    assert after_error.grad is not None
    assert torch.isfinite(before_error.grad)
    assert torch.isfinite(after_error.grad).all()


def test_rri_config_requires_positive_epsilon() -> None:
    with pytest.raises(ValueError, match="positive"):
        RriConfig(epsilon=0.0)
