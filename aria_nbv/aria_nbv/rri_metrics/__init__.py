"""Oracle RRI metrics, ordinal labels, and VIN logging utilities.

RRI is computed from point-mesh error before and after adding a candidate view.
The directional components are accuracy (point to mesh) and completeness (mesh
to point); their scalarized sum is used by the current oracle implementation.
For target-aware labels, callers crop points and mesh to the matched target and
must mark empty or ambiguous crops invalid rather than assigning low RRI.

CORAL utilities convert continuous RRI-derived supervision into ordered bins for
VIN-style one-step scoring. Ordinal predictions are ranking/calibration signals,
not geometry metrics by themselves.
"""

from .coral import (
    CoralLayer,
    coral_expected_from_logits,
    coral_logits_to_prob,
    coral_loss,
    coral_random_loss,
)
from .eval_pointclouds import (
    RootEvalPointCloud,
    RriEvaluationPointCloudSource,
    RriRewardMode,
    build_root_eval_pointcloud,
    canonical_fuse_points,
    observed_prefix_frame_indices,
)
from .logging import (
    LabelHistogram,
    Loss,
    Metric,
    RriErrorStats,
    VinMetrics,
    VinMetricsConfig,
    loss_key,
    metric_key,
    topk_accuracy_from_probs,
)
from .metrics import chamfer_point_mesh, chamfer_point_mesh_batched
from .rollout import (
    TargetRolloutMetricSummary,
    endpoint_log_gain,
    endpoint_target_gain,
    finite_horizon_target_return,
    selected_target_reward,
    selected_target_rri,
    summarize_target_rollout_metrics,
    target_point_mesh_error_after,
    target_point_mesh_error_before,
)
from .rri_binning import RriOrdinalBinner, ordinal_labels_to_levels
from .torch_rollout import (
    CandidateOrderConsistency,
    TorchRolloutMetrics,
    candidate_best_value,
    candidate_masked_mean,
    candidate_order_consistency,
    candidate_policy_entropy,
    candidate_topk_oracle_hit,
    discounted_selected_return,
    endpoint_log_gain_tensor,
    endpoint_target_gain_tensor,
    selected_path_length_tensor,
    summarize_selected_rollout_tensors,
)
from .torch_rollout_metrics import (
    CandidateOrderConsistencyMetric,
    CandidatePolicyEntropyMetric,
    CandidateTableMetrics,
    CandidateTopKOracleHitMetric,
    FiniteMeanMetric,
    PolicyTableMetrics,
    SelectedPathCostMetrics,
    SelectedRolloutMetrics,
)
from .types import DistanceAggregation, DistanceBreakdown, RriResult

__all__ = [
    "CoralLayer",
    "CandidateOrderConsistency",
    "CandidateOrderConsistencyMetric",
    "CandidatePolicyEntropyMetric",
    "CandidateTableMetrics",
    "CandidateTopKOracleHitMetric",
    "FiniteMeanMetric",
    "LabelHistogram",
    "Loss",
    "Metric",
    "PolicyTableMetrics",
    "RriErrorStats",
    "RriOrdinalBinner",
    "SelectedPathCostMetrics",
    "SelectedRolloutMetrics",
    "TargetRolloutMetricSummary",
    "TorchRolloutMetrics",
    "VinMetrics",
    "VinMetricsConfig",
    "loss_key",
    "metric_key",
    "topk_accuracy_from_probs",
    "chamfer_point_mesh",
    "chamfer_point_mesh_batched",
    "DistanceAggregation",
    "DistanceBreakdown",
    "RootEvalPointCloud",
    "RriResult",
    "RriEvaluationPointCloudSource",
    "RriRewardMode",
    "build_root_eval_pointcloud",
    "candidate_best_value",
    "candidate_masked_mean",
    "candidate_order_consistency",
    "candidate_policy_entropy",
    "candidate_topk_oracle_hit",
    "coral_expected_from_logits",
    "coral_logits_to_prob",
    "coral_loss",
    "coral_random_loss",
    "canonical_fuse_points",
    "discounted_selected_return",
    "endpoint_log_gain",
    "endpoint_log_gain_tensor",
    "endpoint_target_gain",
    "endpoint_target_gain_tensor",
    "finite_horizon_target_return",
    "ordinal_labels_to_levels",
    "observed_prefix_frame_indices",
    "selected_target_reward",
    "selected_path_length_tensor",
    "selected_target_rri",
    "summarize_selected_rollout_tensors",
    "summarize_target_rollout_metrics",
    "target_point_mesh_error_after",
    "target_point_mesh_error_before",
]
