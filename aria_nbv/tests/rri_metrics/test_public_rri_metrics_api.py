"""Contract tests for the compact ``aria_nbv.rri_metrics`` root API."""

from __future__ import annotations

import aria_nbv.rri_metrics as rri_metrics


def test_rri_metrics_root_exports_stable_core_only() -> None:
    """The package root should not re-export rollout reducers or diagnostics helpers."""

    expected = {
        "DistanceAggregation",
        "DistanceBreakdown",
        "OracleRRI",
        "OracleRRIConfig",
        "RriOrdinalBinner",
        "RriResult",
        "chamfer_point_mesh",
        "chamfer_point_mesh_batched",
        "ordinal_labels_to_levels",
    }
    assert set(rri_metrics.__all__) == expected

    hidden = {
        "CandidateTopKOracleHitMetric",
        "TargetRolloutMetricSummary",
        "candidate_topk_oracle_hit",
        "summarize_target_rollout_metrics",
        "topk_accuracy_from_probs",
    }
    assert hidden.isdisjoint(set(rri_metrics.__all__))
    for name in hidden:
        assert not hasattr(rri_metrics, name)
