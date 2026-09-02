"""Tests for finite-horizon target-RRI rollout metric helpers."""

# ruff: noqa: S101

from __future__ import annotations

import math

import pytest
import torch

from aria_nbv.rri_metrics.returns import (
    endpoint_log_gain,
    endpoint_target_gain,
    finite_horizon_target_return,
    root_normalized_gain,
    selected_target_reward,
    selected_target_rri,
    summarize_target_rollout_metrics,
    target_point_mesh_error_after,
    target_point_mesh_error_before,
)


def test_selected_target_return_uses_root_gain_with_discount() -> None:
    rows = [
        {"target_root_gain": 0.2},
        {"target_root_gain": 0.3},
        {"target_root_gain": float("nan")},
        {"root_gain": 0.4},
    ]

    assert finite_horizon_target_return(rows, gamma=0.5) == pytest.approx(0.2 + 0.5 * 0.3 + 0.5**3 * 0.4)


def test_selected_target_return_prefers_root_normalized_gain() -> None:
    rows = [
        {"target_root_gain": 0.1, "target_rri": 0.9},
        {"root_gain": 0.2, "rri": 0.8},
    ]

    assert selected_target_reward(rows[0]) == 0.1
    assert finite_horizon_target_return(rows, gamma=0.5) == pytest.approx(0.1 + 0.5 * 0.2)


def test_undiscounted_root_normalized_return_matches_endpoint_gain_without_epsilon_stabilization() -> None:
    rows = [
        {"target_root_gain": 0.3, "target_pm_dist_before": 10.0, "target_pm_dist_after": 7.0},
        {"target_root_gain": 0.3, "target_pm_dist_before": 7.0, "target_pm_dist_after": 4.0},
        {"target_root_gain": 0.3, "target_pm_dist_before": 4.0, "target_pm_dist_after": 1.0},
    ]

    summary = summarize_target_rollout_metrics(rows, gamma=1.0, eps=0.0)

    assert summary.cumulative_return == pytest.approx(0.9)
    assert summary.endpoint_gain == pytest.approx(0.9)


def test_endpoint_and_additive_root_gain_use_distinct_epsilon_denominators() -> None:
    eps = 1e-8
    root_error = torch.tensor(eps / 2, dtype=torch.float64)
    final_error = torch.tensor(0.0, dtype=torch.float64)

    endpoint = endpoint_target_gain(
        [{"target_pm_dist_before": root_error.item(), "target_pm_dist_after": 0.0}],
        eps=eps,
    )
    additive = root_normalized_gain(root_error, final_error, root_error, eps=eps).item()

    assert endpoint == pytest.approx(1 / 3)
    assert additive == pytest.approx(0.5)
    assert endpoint != pytest.approx(additive)


def test_endpoint_gain_uses_direct_point_mesh_error() -> None:
    rows = [
        {"target_pm_dist_before": 10.0, "target_pm_dist_after": 8.0, "target_rri": 0.2},
        {"target_pm_dist_before": 8.0, "target_pm_dist_after": 5.0, "target_rri": 0.375},
    ]

    assert endpoint_target_gain(rows, eps=0.0) == 0.5
    assert endpoint_log_gain(rows, eps=0.0) == math.log(10.0) - math.log(5.0)


def test_endpoint_error_falls_back_to_accuracy_plus_completeness() -> None:
    row = {
        "target_pm_acc_before": 1.5,
        "target_pm_comp_before": 2.5,
        "target_pm_acc_after": 0.5,
        "target_pm_comp_after": 1.0,
    }

    assert target_point_mesh_error_before(row) == 4.0
    assert target_point_mesh_error_after(row) == 1.5


def test_rollout_summary_reports_missing_endpoint_metrics_explicitly() -> None:
    summary = summarize_target_rollout_metrics([{"target_root_gain": 0.1}, {"target_root_gain": 0.2}])

    assert summary.cumulative_return == pytest.approx(0.3)
    assert summary.endpoint_gain is None
    assert summary.log_gain is None
    assert summary.initial_error is None
    assert summary.final_error is None
    assert summary.steps == 2


def test_non_finite_selected_target_rri_is_ignored() -> None:
    assert selected_target_rri({"target_rri": float("inf"), "rri": 0.1}) == 0.1
    assert finite_horizon_target_return([{"target_rri": float("nan")}]) is None


def test_diagnostic_rri_is_never_substituted_for_root_gain_reward() -> None:
    rows = [{"target_rri": 0.2}, {"rri": 0.3}]

    assert selected_target_reward(rows[0]) is None
    assert finite_horizon_target_return(rows) is None
