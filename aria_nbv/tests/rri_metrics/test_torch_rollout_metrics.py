"""Tests for torch-native target-rollout metrics."""

# ruff: noqa: S101

from __future__ import annotations

import pytest
import torch

from aria_nbv.rri_metrics import (
    CandidateOrderConsistency,
    CandidateOrderConsistencyMetric,
    CandidateTableMetrics,
    FiniteMeanMetric,
    PolicyTableMetrics,
    SelectedPathCostMetrics,
    SelectedRolloutMetrics,
    candidate_best_value,
    candidate_masked_mean,
    candidate_order_consistency,
    discounted_selected_return,
    endpoint_log_gain_tensor,
    endpoint_target_gain_tensor,
    selected_path_length_tensor,
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


def test_selected_path_length_tensor_reports_3_4_5_geometry() -> None:
    centers = torch.tensor(
        [
            [0.0, 0.0, 0.0],
            [3.0, 4.0, 0.0],
            [3.0, 4.0, 12.0],
        ]
    )

    result = selected_path_length_tensor(centers)

    assert torch.allclose(result, torch.tensor(17.0))


def test_selected_path_length_tensor_ignores_masked_and_nonfinite_segments() -> None:
    centers = torch.tensor(
        [
            [[0.0, 0.0, 0.0], [3.0, 4.0, 0.0], [6.0, 8.0, 0.0]],
            [[0.0, 0.0, 0.0], [float("nan"), 1.0, 0.0], [0.0, 4.0, 0.0]],
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
        ]
    )
    segment_mask = torch.tensor(
        [
            [True, False],
            [True, True],
            [False, False],
        ]
    )

    result = selected_path_length_tensor(centers, segment_mask)

    assert torch.allclose(result, torch.tensor([5.0, float("nan"), float("nan")]), equal_nan=True)


def test_candidate_order_consistency_inverse_aligns_gather_permutation() -> None:
    scores = torch.tensor([[0.1, 0.9, 0.2], [0.5, 0.4, 0.3]])
    permutation = torch.tensor([[2, 0, 1], [1, 2, 0]])
    shuffled_scores = torch.gather(scores, dim=-1, index=permutation)
    valid = torch.tensor([[True, True, True], [True, True, False]])
    shuffled_valid = torch.gather(valid, dim=-1, index=permutation)

    result = candidate_order_consistency(scores, shuffled_scores, permutation, valid, shuffled_valid)

    assert isinstance(result, CandidateOrderConsistency)
    assert torch.allclose(result.score_mae, torch.zeros(2))
    assert torch.equal(result.top1_match, torch.tensor([True, True]))
    assert torch.equal(result.valid_table, torch.tensor([True, True]))


def test_candidate_order_consistency_ignores_invalid_tail_and_detects_bias() -> None:
    scores = torch.tensor([[0.1, 0.8, 0.2, 99.0], [0.1, 0.2, 0.3, 0.4]])
    permutation = torch.tensor([[3, 1, 0, 2], [2, 1, 0, 3]])
    shuffled_scores = torch.gather(scores, dim=-1, index=permutation)
    shuffled_scores[1] = torch.tensor([0.0, 0.1, 1.0, 0.4])
    valid = torch.tensor([[True, True, True, False], [True, True, True, False]])
    shuffled_valid = torch.gather(valid, dim=-1, index=permutation)

    result = candidate_order_consistency(scores, shuffled_scores, permutation, valid, shuffled_valid)

    assert torch.isclose(result.score_mae[0], torch.tensor(0.0))
    assert result.top1_match[0]
    assert result.score_mae[1] > 0.0
    assert not result.top1_match[1]


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


def test_selected_path_cost_metrics_report_mean_cost_aliases() -> None:
    metric = SelectedPathCostMetrics()

    metric.update(
        torch.tensor(
            [
                [[0.0, 0.0, 0.0], [3.0, 4.0, 0.0], [3.0, 4.0, 12.0]],
                [[0.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 9.0, 0.0]],
            ]
        ),
        torch.tensor([[True, True], [True, False]]),
    )
    metric.update(
        torch.tensor([[[0.0, 0.0, 0.0], [float("nan"), 0.0, 0.0]]]),
        torch.tensor([[True]]),
    )

    result = metric.compute()

    assert torch.allclose(result["path_length_m"], torch.tensor((17.0 + 5.0) / 2.0))
    assert torch.allclose(result["cost"], result["path_length_m"])


def test_selected_path_cost_metrics_return_nan_when_all_paths_invalid() -> None:
    metric = SelectedPathCostMetrics()

    metric.update(torch.tensor([[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]]), torch.tensor([[False]]))

    result = metric.compute()

    assert torch.isnan(result["path_length_m"])
    assert torch.isnan(result["cost"])


def test_candidate_order_consistency_metric_reports_rates() -> None:
    metric = CandidateOrderConsistencyMetric()
    scores = torch.tensor([[0.1, 0.9, 0.2], [0.1, 0.2, 0.3]])
    permutation = torch.tensor([[2, 0, 1], [2, 1, 0]])
    shuffled_scores = torch.gather(scores, dim=-1, index=permutation)
    shuffled_scores[1] = torch.tensor([0.0, 1.0, 0.1])
    valid = torch.tensor([[True, True, True], [True, True, True]])

    metric.update(scores, shuffled_scores, permutation, valid)
    metric.update(
        torch.tensor([[0.1, 0.2]]),
        torch.tensor([[0.2, 0.1]]),
        torch.tensor([[1, 0]]),
        torch.tensor([[False, False]]),
    )

    result = metric.compute()

    assert result["candidate_order_score_mae"] > 0.0
    assert torch.allclose(result["candidate_order_top1_match_rate"], torch.tensor(0.5))
    assert torch.allclose(result["candidate_order_valid_table_rate"], torch.tensor(2.0 / 3.0))


def test_policy_table_metrics_report_proposal_columns() -> None:
    metric = PolicyTableMetrics(gamma=0.5, eps=1e-6)

    metric.update(
        torch.tensor([[1.0, 2.0], [0.5, 0.5]]),
        initial_error=torch.tensor([10.0, 4.0]),
        final_error=torch.tensor([5.0, 2.0]),
        scene_rri=torch.tensor([0.2, 0.4]),
        cost=torch.tensor([3.0, 5.0]),
        runtime=torch.tensor([10.0, 20.0]),
        coverage=torch.tensor([0.6, 0.8]),
        candidate_values=torch.tensor([[1.0, 2.0, 3.0], [5.0, 4.0, 3.0]]),
        candidate_valid_mask=torch.tensor([[True, True, False], [False, True, False]]),
    )

    result = metric.compute()

    for key in ("endpoint_gain", "return_h", "scene_rri", "cost", "invalidity", "runtime", "coverage"):
        assert key in result
    assert torch.allclose(result["endpoint_gain"], torch.tensor(0.5), atol=1e-6)
    assert torch.allclose(result["return_h"], torch.tensor(((1.0 + 0.5 * 2.0) + (0.5 + 0.5 * 0.5)) / 2.0))
    assert torch.allclose(result["scene_rri"], torch.tensor(0.3))
    assert torch.allclose(result["cost"], torch.tensor(4.0))
    assert torch.allclose(result["runtime"], torch.tensor(15.0))
    assert torch.allclose(result["coverage"], torch.tensor(0.7))
    assert torch.allclose(result["invalidity"], torch.tensor(3.0 / 6.0))
    assert torch.allclose(result["candidate_value_mean"], torch.tensor((1.5 + 4.0) / 2.0))
    assert torch.allclose(result["candidate_best_value"], torch.tensor((2.0 + 4.0) / 2.0))


def test_policy_table_metrics_can_derive_cost_from_selected_path() -> None:
    metric = PolicyTableMetrics()

    metric.update(
        torch.tensor([[1.0, 1.0], [1.0, 1.0]]),
        initial_error=torch.tensor([10.0, 10.0]),
        final_error=torch.tensor([5.0, 5.0]),
        scene_rri=torch.tensor([0.2, 0.4]),
        selected_camera_centers_world=torch.tensor(
            [
                [[0.0, 0.0, 0.0], [3.0, 4.0, 0.0], [3.0, 4.0, 12.0]],
                [[0.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 9.0, 0.0]],
            ]
        ),
        selected_path_segment_valid_mask=torch.tensor([[True, True], [True, False]]),
        runtime=torch.tensor([10.0, 20.0]),
        coverage=torch.tensor([0.6, 0.8]),
        candidate_values=torch.tensor([[1.0, 2.0], [3.0, 4.0]]),
        candidate_valid_mask=torch.tensor([[True, False], [True, True]]),
    )

    result = metric.compute()

    assert torch.allclose(result["cost"], torch.tensor((17.0 + 5.0) / 2.0))
    assert torch.allclose(result["invalidity"], torch.tensor(1.0 / 4.0))


def test_policy_table_metrics_prefers_explicit_cost_over_path_cost() -> None:
    metric = PolicyTableMetrics()

    metric.update(
        torch.tensor([[1.0, 1.0]]),
        initial_error=torch.tensor([10.0]),
        final_error=torch.tensor([5.0]),
        scene_rri=torch.tensor([0.2]),
        cost=torch.tensor([2.0]),
        selected_camera_centers_world=torch.tensor([[[0.0, 0.0, 0.0], [3.0, 4.0, 0.0], [3.0, 4.0, 12.0]]]),
        runtime=torch.tensor([10.0]),
        coverage=torch.tensor([0.6]),
        candidate_values=torch.tensor([[1.0, 2.0]]),
        candidate_valid_mask=torch.tensor([[True, True]]),
    )

    result = metric.compute()

    assert torch.allclose(result["cost"], torch.tensor(2.0))


def test_policy_table_metrics_requires_centers_for_path_segment_mask() -> None:
    metric = PolicyTableMetrics()

    with pytest.raises(ValueError, match="selected_path_segment_valid_mask"):
        metric.update(
            torch.tensor([[1.0, 1.0]]),
            initial_error=torch.tensor([10.0]),
            final_error=torch.tensor([5.0]),
            selected_path_segment_valid_mask=torch.tensor([[True, False]]),
        )


def test_policy_table_metrics_ignore_nonfinite_and_masked_entries() -> None:
    metric = PolicyTableMetrics()

    metric.update(
        torch.tensor([[1.0, float("nan")], [2.0, 3.0]]),
        initial_error=torch.tensor([10.0, 8.0]),
        final_error=torch.tensor([5.0, 4.0]),
        selected_valid_mask=torch.tensor([[True, True], [False, True]]),
        scene_rri=torch.tensor([0.2, float("nan"), 0.8]),
        cost=torch.tensor([1.0, 100.0, float("inf")]),
        runtime=torch.tensor([10.0, 20.0, 30.0]),
        coverage=torch.tensor([0.5, 0.9, float("nan")]),
        scalar_valid_mask=torch.tensor([True, False, True]),
        candidate_values=torch.tensor([[100.0, -100.0], [float("nan"), 4.0]]),
        candidate_valid_mask=torch.tensor([[False, True], [False, False]]),
    )

    result = metric.compute()

    assert torch.allclose(result["scene_rri"], torch.tensor(0.5))
    assert torch.allclose(result["cost"], torch.tensor(1.0))
    assert torch.allclose(result["runtime"], torch.tensor(20.0))
    assert torch.allclose(result["coverage"], torch.tensor(0.5))
    assert torch.allclose(result["invalidity"], torch.tensor(3.0 / 4.0))
    assert torch.allclose(result["candidate_value_mean"], torch.tensor(-100.0))
    assert torch.allclose(result["candidate_best_value"], torch.tensor(-100.0))
