"""Tests for torch-native target-rollout metrics."""

# ruff: noqa: S101

from __future__ import annotations

import torch

from aria_nbv.rri_metrics import (
    candidate_best_value,
    candidate_masked_mean,
    discounted_selected_return,
    endpoint_log_gain_tensor,
    endpoint_target_gain_tensor,
    summarize_selected_rollout_tensors,
)


def test_discounted_selected_return_ignores_invalid_and_nonfinite_rewards() -> None:
    rewards = torch.tensor([[0.2, 0.3, float("nan"), 0.4], [float("nan"), 1.0, 2.0, 3.0]])
    valid = torch.tensor([[True, True, True, True], [False, False, True, False]])

    result = discounted_selected_return(rewards, valid, gamma=0.5)

    assert torch.allclose(result, torch.tensor([0.2 + 0.5 * 0.3 + 0.5**3 * 0.4, 0.5**2 * 2.0]))


def test_discounted_selected_return_returns_nan_for_empty_rows() -> None:
    rewards = torch.tensor([[float("nan"), 1.0]])
    valid = torch.tensor([[False, False]])

    result = discounted_selected_return(rewards, valid)

    assert torch.isnan(result).all()


def test_endpoint_metrics_use_root_error_and_mask_bad_inputs() -> None:
    initial = torch.tensor([10.0, 0.0, float("nan"), -1.0])
    final = torch.tensor([5.0, 0.0, 1.0, 0.5])

    gain = endpoint_target_gain_tensor(initial, final, eps=1e-6)
    log_gain = endpoint_log_gain_tensor(initial, final, eps=1e-6)

    assert torch.isclose(gain[0], torch.tensor(0.5))
    assert torch.isclose(log_gain[0], torch.log(torch.tensor(10.0 + 1e-6)) - torch.log(torch.tensor(5.0 + 1e-6)))
    assert torch.isfinite(gain[1])
    assert torch.isnan(gain[2])
    assert torch.isnan(gain[3])


def test_summarize_selected_rollout_tensors_reports_counts_and_endpoint_mask() -> None:
    rewards = torch.tensor([[0.3, 0.3, 0.3], [1.0, float("nan"), 2.0]])
    initial = torch.tensor([10.0, 0.0])
    final = torch.tensor([1.0, 0.0])
    valid = torch.tensor([[True, True, True], [True, True, False]])

    summary = summarize_selected_rollout_tensors(rewards, initial, final, valid, gamma=1.0, eps=0.0)

    assert torch.allclose(summary.discounted_return, torch.tensor([0.9, 1.0]))
    assert torch.allclose(summary.endpoint_gain, torch.tensor([0.9, float("nan")]), equal_nan=True)
    assert torch.equal(summary.valid_steps, torch.tensor([3, 1]))
    assert torch.equal(summary.valid_endpoint, torch.tensor([True, True]))


def test_candidate_reductions_respect_hard_mask_and_nonfinite_values() -> None:
    values = torch.tensor([[1.0, 2.0, float("nan")], [float("-inf"), 5.0, 4.0], [1.0, 2.0, 3.0]])
    valid = torch.tensor([[True, True, True], [True, False, True], [False, False, False]])

    mean = candidate_masked_mean(values, valid)
    best = candidate_best_value(values, valid)

    assert torch.allclose(mean, torch.tensor([1.5, 4.0, float("nan")]), equal_nan=True)
    assert torch.allclose(best, torch.tensor([2.0, 4.0, float("nan")]), equal_nan=True)
