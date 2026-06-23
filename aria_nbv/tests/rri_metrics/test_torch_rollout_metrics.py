"""Tests for torch-native target-rollout metrics."""

# ruff: noqa: S101

from __future__ import annotations

import torch

from aria_nbv.rri_metrics import (
    CandidateTableMetrics,
    FiniteMeanMetric,
    SelectedRolloutMetrics,
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


def test_finite_mean_metric_ignores_nonfinite_and_masked_values() -> None:
    metric = FiniteMeanMetric()

    metric.update(
        torch.tensor([1.0, float("nan"), 3.0, 100.0]),
        torch.tensor([True, True, True, False]),
    )

    assert torch.isclose(metric.compute(), torch.tensor(2.0))
    metric.reset()
    metric.update(torch.tensor([1.0, float("nan")]), torch.tensor([False, True]))
    assert torch.isnan(metric.compute())


def test_selected_rollout_metrics_report_proposal_metrics() -> None:
    metric = SelectedRolloutMetrics(gamma=0.5, eps=1e-6)

    metric.update(
        torch.tensor([[1.0, 2.0], [float("nan"), 4.0]]),
        initial_error=torch.tensor([10.0, 8.0]),
        final_error=torch.tensor([5.0, 4.0]),
        valid_mask=torch.tensor([[True, True], [False, True]]),
    )
    metric.update(
        torch.tensor([[2.0, 0.0]]),
        initial_error=torch.tensor([4.0]),
        final_error=torch.tensor([2.0]),
    )

    result = metric.compute()

    assert torch.allclose(result["return_h"], torch.tensor((2.0 + 2.0 + 2.0) / 3.0))
    assert torch.allclose(result["endpoint_gain"], torch.tensor(0.5), atol=1e-6)
    assert result["endpoint_log_gain"] > 0.0
    assert torch.allclose(result["valid_steps"], torch.tensor((2.0 + 1.0 + 2.0) / 3.0))
    assert torch.allclose(result["valid_endpoint_rate"], torch.tensor(1.0))


def test_selected_rollout_metrics_accept_one_dimensional_rollouts() -> None:
    metric = SelectedRolloutMetrics(gamma=1.0, eps=1e-6)

    metric.update(
        torch.tensor([0.2, 0.3, 0.5]),
        initial_error=torch.tensor([10.0]),
        final_error=torch.tensor([6.0]),
    )

    result = metric.compute()

    assert torch.allclose(result["return_h"], torch.tensor(1.0))
    assert torch.allclose(result["endpoint_gain"], torch.tensor(0.4), atol=1e-6)
    assert torch.allclose(result["valid_steps"], torch.tensor(3.0))


def test_candidate_table_metrics_report_invalidity_and_values() -> None:
    metric = CandidateTableMetrics()

    metric.update(
        torch.tensor([[1.0, 2.0, float("nan")], [5.0, 4.0, 3.0]]),
        torch.tensor([[True, True, True], [False, True, False]]),
    )

    result = metric.compute()

    assert torch.allclose(result["candidate_valid_rate"], torch.tensor(3.0 / 6.0))
    assert torch.allclose(result["candidate_invalid_rate"], torch.tensor(0.5))
    assert torch.allclose(result["candidate_value_mean"], torch.tensor((1.5 + 4.0) / 2.0))
    assert torch.allclose(result["candidate_best_value"], torch.tensor((2.0 + 4.0) / 2.0))
