"""Tests for torch-native target-rollout metrics."""

# ruff: noqa: S101

from __future__ import annotations

import pytest
import torch

from aria_nbv.rri_metrics import (
    CandidateOrderConsistency,
    CandidateOrderConsistencyMetric,
    CandidatePolicyEntropyMetric,
    CandidateProvenanceShareMetric,
    CandidateTableMetrics,
    CandidateTopKOracleHitMetric,
    FiniteMeanMetric,
    PolicyTableMetrics,
    SelectedActionOracleComparison,
    SelectedActionOracleComparisonMetric,
    SelectedPathCostMetrics,
    SelectedRolloutMetrics,
    candidate_best_value,
    candidate_masked_mean,
    candidate_order_consistency,
    candidate_policy_entropy,
    candidate_provenance_share,
    candidate_topk_oracle_hit,
    discounted_selected_return,
    endpoint_log_gain_tensor,
    endpoint_target_gain_tensor,
    selected_action_oracle_comparison,
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


def test_candidate_policy_entropy_renormalizes_candidate_weights() -> None:
    probabilities = torch.tensor([[2.0, 2.0], [1.0, 3.0]])

    result = candidate_policy_entropy(probabilities)

    assert torch.allclose(result[0], torch.log(torch.tensor(2.0)))
    expected_second = -(0.25 * torch.log(torch.tensor(0.25)) + 0.75 * torch.log(torch.tensor(0.75)))
    assert torch.allclose(result[1], expected_second)


def test_candidate_policy_entropy_ignores_invalid_nonfinite_and_nonpositive_entries() -> None:
    probabilities = torch.tensor([[0.5, float("nan"), -1.0, 0.5], [0.0, float("inf"), 1.0, 1.0]])
    valid = torch.tensor([[True, True, True, False], [True, True, True, True]])

    result = candidate_policy_entropy(probabilities, valid)

    assert torch.allclose(result, torch.tensor([-0.0, torch.log(torch.tensor(2.0))]))


def test_candidate_policy_entropy_returns_nan_for_empty_or_zero_mass_tables() -> None:
    probabilities = torch.tensor([[0.0, float("nan")], [-1.0, 0.0]])

    result = candidate_policy_entropy(probabilities)

    assert torch.isnan(result).all()


def test_candidate_policy_entropy_supports_non_last_candidate_dim() -> None:
    probabilities = torch.tensor([[1.0, 2.0], [1.0, 0.0], [0.0, 2.0]])
    valid = torch.tensor([[True, True], [True, False], [False, True]])

    result = candidate_policy_entropy(probabilities, valid, dim=0)

    assert torch.allclose(result, torch.tensor([torch.log(torch.tensor(2.0)), torch.log(torch.tensor(2.0))]))


def test_candidate_topk_oracle_hit_handles_oracle_ties_and_misses() -> None:
    predicted = torch.tensor([[0.9, 0.1, 0.2], [0.1, 0.2, 0.9]])
    oracle = torch.tensor([[1.0, 1.0, 0.0], [1.0, 1.0, 0.0]])

    result = candidate_topk_oracle_hit(predicted, oracle, top_k=1)

    assert torch.equal(result, torch.tensor([1.0, 0.0]))


def test_candidate_topk_oracle_hit_includes_kth_boundary_ties() -> None:
    predicted = torch.tensor([[0.9, 0.8, 0.8, 0.1]])
    oracle = torch.tensor([[0.0, 0.0, 1.0, 0.0]])

    result = candidate_topk_oracle_hit(predicted, oracle, top_k=2)

    assert torch.equal(result, torch.tensor([1.0]))


def test_candidate_topk_oracle_hit_ignores_invalid_and_nonfinite_oracle_values() -> None:
    predicted = torch.tensor([[0.1, 0.9, 0.8]])
    oracle = torch.tensor([[1.0, float("nan"), 2.0]])
    valid = torch.tensor([[True, True, False]])

    result = candidate_topk_oracle_hit(predicted, oracle, valid, top_k=2)

    assert torch.equal(result, torch.tensor([1.0]))


def test_candidate_topk_oracle_hit_nonfinite_best_prediction_is_miss() -> None:
    predicted = torch.tensor([[float("nan"), 0.9]])
    oracle = torch.tensor([[1.0, 0.0]])

    result = candidate_topk_oracle_hit(predicted, oracle, top_k=1)

    assert torch.equal(result, torch.tensor([0.0]))


def test_candidate_topk_oracle_hit_returns_nan_for_empty_tables() -> None:
    predicted = torch.tensor([[1.0, 0.0], [float("nan"), float("nan")], [0.1, 0.2]])
    oracle = torch.tensor([[float("nan"), float("nan")], [1.0, 0.0], [1.0, 0.0]])
    valid = torch.tensor([[True, True], [True, True], [False, False]])

    result = candidate_topk_oracle_hit(predicted, oracle, valid, top_k=1)

    assert torch.isnan(result).all()


def test_candidate_topk_oracle_hit_validates_shape_and_top_k() -> None:
    with pytest.raises(ValueError, match="top_k"):
        candidate_topk_oracle_hit(torch.tensor([1.0]), torch.tensor([1.0]), top_k=0)

    with pytest.raises(ValueError, match="matching shapes"):
        candidate_topk_oracle_hit(torch.tensor([1.0, 2.0]), torch.tensor([[1.0, 2.0]]))


def test_candidate_topk_oracle_hit_supports_non_last_candidate_dim() -> None:
    predicted = torch.tensor([[0.9, 0.1], [0.8, 0.2], [0.1, 0.3]])
    oracle = torch.tensor([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])

    result = candidate_topk_oracle_hit(predicted, oracle, top_k=2, dim=0)

    assert torch.equal(result, torch.tensor([1.0, 1.0]))


def test_selected_action_oracle_comparison_reports_regret_rank_and_percentile() -> None:
    oracle = torch.tensor([[2.0, 2.0, 1.0], [1.0, 3.0, 2.0]])
    selected = torch.tensor([0, 2])
    valid = torch.ones_like(oracle, dtype=torch.bool)

    result = selected_action_oracle_comparison(oracle, selected, valid)

    assert isinstance(result, SelectedActionOracleComparison)
    assert torch.allclose(result.selected_oracle_regret, torch.tensor([0.0, 1.0]))
    assert torch.allclose(result.selected_oracle_rank, torch.tensor([1.0, 2.0]))
    assert torch.allclose(result.selected_oracle_percentile, torch.tensor([1.0, 0.5]))
    assert torch.equal(result.valid_table, torch.tensor([True, True]))


def test_selected_action_oracle_comparison_masks_uncomparable_tables() -> None:
    oracle = torch.tensor(
        [
            [1.0, 2.0],
            [1.0, float("nan")],
            [float("nan"), float("nan")],
            [1.0, 2.0],
            [1.0, 2.0],
            [1.0, 2.0],
        ],
    )
    selected = torch.tensor([-1.0, 1.0, 0.0, 1.0, 2.0, 0.5])
    valid = torch.tensor(
        [
            [True, True],
            [True, True],
            [True, True],
            [True, False],
            [True, True],
            [True, True],
        ],
    )

    result = selected_action_oracle_comparison(oracle, selected, valid)

    assert torch.isnan(result.selected_oracle_regret).all()
    assert torch.isnan(result.selected_oracle_rank).all()
    assert torch.isnan(result.selected_oracle_percentile).all()
    assert not result.valid_table.any()


def test_selected_action_oracle_comparison_supports_non_last_candidate_dim() -> None:
    oracle = torch.tensor([[1.0, 0.0], [3.0, 1.0], [2.0, 2.0]])
    selected = torch.tensor([1, 2])
    valid = torch.ones_like(oracle, dtype=torch.bool)

    result = selected_action_oracle_comparison(oracle, selected, valid, dim=0)

    assert torch.allclose(result.selected_oracle_regret, torch.tensor([0.0, 0.0]))
    assert torch.allclose(result.selected_oracle_rank, torch.tensor([1.0, 1.0]))
    assert torch.allclose(result.selected_oracle_percentile, torch.tensor([1.0, 1.0]))
    assert torch.equal(result.valid_table, torch.tensor([True, True]))


def test_candidate_provenance_share_reports_radial_backtrack_union() -> None:
    strategy_ids = torch.tensor(
        [
            [1, 2, 0, 3],
            [1, 0, 0, -1],
            [-1, -1, -1, -1],
        ],
        dtype=torch.int64,
    )
    position_ids = torch.tensor(
        [
            [2, 2, 5, 2],
            [1, 5, 1, -1],
            [-1, -1, -1, -1],
        ],
        dtype=torch.int64,
    )
    valid = torch.tensor(
        [
            [True, True, True, False],
            [True, True, True, True],
            [True, True, True, True],
        ],
        dtype=torch.bool,
    )

    result = candidate_provenance_share(
        strategy_ids,
        position_ids,
        strategy_family_ids=(1, 2),
        position_family_ids=(5,),
        valid_mask=valid,
    )

    assert torch.allclose(result, torch.tensor([1.0, 2.0 / 3.0, float("nan")]), equal_nan=True)


def test_candidate_provenance_share_supports_non_last_candidate_dim() -> None:
    strategy_ids = torch.tensor([[1, 0], [2, 0], [0, 0]], dtype=torch.int64)
    position_ids = torch.tensor([[1, 5], [1, 1], [5, 1]], dtype=torch.int64)

    result = candidate_provenance_share(
        strategy_ids,
        position_ids,
        strategy_family_ids=(1, 2),
        position_family_ids=(5,),
        dim=0,
    )

    assert torch.allclose(result, torch.tensor([1.0, 1.0 / 3.0]))


def test_candidate_provenance_share_validates_shapes_and_dim() -> None:
    with pytest.raises(ValueError, match="matching shapes"):
        candidate_provenance_share(torch.tensor([1]), torch.tensor([[1]]), strategy_family_ids=(1,))

    with pytest.raises(ValueError, match="outside tensor rank"):
        candidate_provenance_share(torch.tensor([1]), torch.tensor([1]), strategy_family_ids=(1,), dim=2)


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


def test_candidate_policy_entropy_metric_accumulates_finite_table_entropies() -> None:
    metric = CandidatePolicyEntropyMetric()

    metric.update(
        torch.tensor([[2.0, 2.0], [0.0, float("nan")]]),
        torch.tensor([[True, True], [True, True]]),
    )
    metric.update(torch.tensor([[1.0, 3.0]]))

    result = metric.compute()
    second = -(0.25 * torch.log(torch.tensor(0.25)) + 0.75 * torch.log(torch.tensor(0.75)))

    assert torch.allclose(result, (torch.log(torch.tensor(2.0)) + second) / 2.0)


def test_candidate_policy_entropy_metric_returns_nan_when_all_tables_empty() -> None:
    metric = CandidatePolicyEntropyMetric()

    metric.update(torch.tensor([[0.0, float("nan")]]))

    assert torch.isnan(metric.compute())


def test_candidate_topk_oracle_hit_metric_accumulates_finite_hits() -> None:
    metric = CandidateTopKOracleHitMetric(top_k=1)

    metric.update(
        torch.tensor([[0.9, 0.1], [float("nan"), float("nan")]]),
        torch.tensor([[1.0, 0.0], [1.0, 0.0]]),
    )
    metric.update(torch.tensor([[0.1, 0.9]]), torch.tensor([[1.0, 0.0]]))

    assert torch.allclose(metric.compute(), torch.tensor(0.5))


def test_candidate_topk_oracle_hit_metric_returns_nan_when_all_tables_empty() -> None:
    metric = CandidateTopKOracleHitMetric(top_k=2)

    metric.update(torch.tensor([[float("nan"), float("nan")]]), torch.tensor([[1.0, 0.0]]))

    assert torch.isnan(metric.compute())


def test_selected_action_oracle_comparison_metric_accumulates_comparable_tables() -> None:
    metric = SelectedActionOracleComparisonMetric()

    metric.update(
        torch.tensor([[3.0, 2.0, 1.0], [1.0, 4.0, 2.0], [1.0, 2.0, 3.0]]),
        torch.tensor([0, 2, 5]),
        torch.ones((3, 3), dtype=torch.bool),
    )
    metric.update(
        torch.tensor([[1.0, 2.0]]),
        torch.tensor([0]),
        torch.tensor([[True, True]]),
    )

    result = metric.compute()

    assert torch.allclose(result["selected_oracle_regret"], torch.tensor(1.0))
    assert torch.allclose(result["selected_oracle_rank"], torch.tensor(5.0 / 3.0))
    assert torch.allclose(result["selected_oracle_percentile"], torch.tensor(0.5))
    assert torch.allclose(result["selected_oracle_valid_table_rate"], torch.tensor(3.0 / 4.0))


def test_selected_action_oracle_comparison_metric_returns_nan_when_all_tables_empty() -> None:
    metric = SelectedActionOracleComparisonMetric()

    metric.update(torch.tensor([[float("nan"), float("nan")]]), torch.tensor([0]), torch.tensor([[True, True]]))

    result = metric.compute()

    assert torch.isnan(result["selected_oracle_regret"])
    assert torch.isnan(result["selected_oracle_rank"])
    assert torch.isnan(result["selected_oracle_percentile"])
    assert torch.allclose(result["selected_oracle_valid_table_rate"], torch.tensor(0.0))


def test_selected_action_oracle_comparison_metric_empty_valid_rate_is_zero() -> None:
    metric = SelectedActionOracleComparisonMetric()

    result = metric.compute()

    assert torch.isnan(result["selected_oracle_regret"])
    assert torch.isnan(result["selected_oracle_rank"])
    assert torch.isnan(result["selected_oracle_percentile"])
    assert torch.allclose(result["selected_oracle_valid_table_rate"], torch.tensor(0.0))


def test_candidate_provenance_share_metric_accumulates_valid_tables() -> None:
    metric = CandidateProvenanceShareMetric(strategy_family_ids=(1, 2), position_family_ids=(5,))

    metric.update(
        torch.tensor([[1, 2, 0], [0, 0, 0]], dtype=torch.int64),
        torch.tensor([[2, 2, 5], [1, 5, 1]], dtype=torch.int64),
        torch.tensor([[True, True, True], [True, True, True]], dtype=torch.bool),
    )
    metric.update(
        torch.tensor([[-1, -1]], dtype=torch.int64),
        torch.tensor([[-1, -1]], dtype=torch.int64),
        torch.tensor([[True, True]], dtype=torch.bool),
    )

    assert torch.allclose(metric.compute(), torch.tensor((1.0 + (1.0 / 3.0)) / 2.0))


def test_candidate_provenance_share_metric_requires_a_family() -> None:
    with pytest.raises(ValueError, match="At least one"):
        CandidateProvenanceShareMetric()


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
    assert torch.isnan(result["selected_oracle_regret"])
    assert torch.allclose(result["selected_oracle_valid_table_rate"], torch.tensor(0.0))


def test_policy_table_metrics_report_selected_oracle_columns() -> None:
    metric = PolicyTableMetrics(gamma=1.0, eps=1e-6)

    metric.update(
        torch.tensor([[1.0], [1.0], [1.0]]),
        initial_error=torch.tensor([10.0, 10.0, 10.0]),
        final_error=torch.tensor([5.0, 5.0, 5.0]),
        candidate_values=torch.tensor(
            [
                [3.0, 2.0, 1.0],
                [1.0, 4.0, 2.0],
                [1.0, float("nan"), 3.0],
            ]
        ),
        candidate_valid_mask=torch.tensor(
            [
                [True, True, True],
                [True, True, True],
                [True, False, True],
            ]
        ),
        selected_indices=torch.tensor([0, 2, 1]),
    )

    result = metric.compute()

    assert torch.allclose(result["candidate_valid_rate"], torch.tensor(8.0 / 9.0))
    assert torch.allclose(result["selected_oracle_regret"], torch.tensor((0.0 + 2.0) / 2.0))
    assert torch.allclose(result["selected_oracle_rank"], torch.tensor((1.0 + 2.0) / 2.0))
    assert torch.allclose(result["selected_oracle_percentile"], torch.tensor((1.0 + 0.5) / 2.0))
    assert torch.allclose(result["selected_oracle_valid_table_rate"], torch.tensor(2.0 / 3.0))


def test_policy_table_metrics_require_candidate_pair_for_selected_indices() -> None:
    metric = PolicyTableMetrics()

    with pytest.raises(ValueError, match="selected_indices requires"):
        metric.update(
            torch.tensor([[1.0]]),
            initial_error=torch.tensor([10.0]),
            final_error=torch.tensor([5.0]),
            selected_indices=torch.tensor([0]),
        )


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
