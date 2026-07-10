# RRI Metrics

`aria_nbv.rri_metrics` owns reconstruction metric computation and reusable evaluation adapters. This move-only pass changes paths, not formulas.

## Layout

```text
rri_metrics/
  point_mesh.py        # moved from metrics.py
  ordinal.py           # moved from rri_binning.py
  ...                   # mixed modules remain until symbol-level WPs
```

Baseline: `6b72b62639e24fc13bba845ec63bc8fc72c77aae`

Inventory generated: `2026-07-10T15:58:15.078783+00:00`

Graphify refresh: `2026-07-10T18:34:29+02:00`

## Symbol Ownership Matrix

### `__init__.py`

No top-level AST definitions; imported names and `__all__` are excluded.

### `eval_pointclouds.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `Tensor` | `constant` | `public` | `rri_metrics.eval_pointclouds` | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `deferred: semantic WP` |
| `CameraLabel` | `constant` | `public` | `rri_metrics.eval_pointclouds` | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `deferred: semantic WP` |
| `RriEvaluationPointCloudSource` | `class` | `public` | `rri_metrics.eval_pointclouds` | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `deferred: semantic WP` |
| `RriRewardMode` | `class` | `public` | `rri_metrics.eval_pointclouds` | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `deferred: semantic WP` |
| `RootEvalPointCloud` | `DTO` | `public` | `rri_metrics.eval_pointclouds` | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `deferred: semantic WP` |
| `canonical_fuse_points` | `function` | `public` | `rri_metrics.eval_pointclouds` | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `deferred: semantic WP` |
| `build_root_eval_pointcloud` | `function` | `public` | `rri_metrics.eval_pointclouds` | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `deferred: semantic WP` |
| `observed_prefix_frame_indices` | `function` | `public` | `rri_metrics.eval_pointclouds` | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `deferred: semantic WP` |
| `_root_time_ns` | `function` | `private` | `rri_metrics.eval_pointclouds` | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `deferred: semantic WP` |
| `_root_trajectory_index` | `function` | `private` | `rri_metrics.eval_pointclouds` | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `deferred: semantic WP` |
| `_exact_trajectory_index` | `function` | `private` | `rri_metrics.eval_pointclouds` | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `deferred: semantic WP` |

### `logging.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `LogSpec` | `DTO` | `public` | `rri_metrics.logging` | `rri_metrics.logging` | `rri_metrics.logging` | `blocked: symbol split` |
| `Logable` | `class` | `public` | `rri_metrics.logging` | `rri_metrics.logging` | `rri_metrics.logging` | `blocked: symbol split` |
| `Metric` | `class` | `public` | `rri_metrics.logging` | `rri_metrics.logging` | `rri_metrics.logging` | `blocked: symbol split` |
| `Loss` | `class` | `public` | `rri_metrics.logging` | `rri_metrics.logging` | `rri_metrics.logging` | `blocked: symbol split` |
| `LabelHistogram` | `class` | `public` | `rri_metrics.logging` | `rri_metrics.logging` | `rri_metrics.torchmetrics_single` | `blocked: symbol split` |
| `RriErrorStats` | `class` | `public` | `rri_metrics.logging` | `rri_metrics.logging` | `rri_metrics.torchmetrics_single` | `blocked: symbol split` |
| `VinMetrics` | `class` | `public` | `rri_metrics.logging` | `rri_metrics.logging` | `rri_metrics.torchmetrics_single` | `blocked: symbol split` |
| `VinMetricsConfig` | `config` | `public` | `rri_metrics.logging` | `rri_metrics.logging` | `rri_metrics.torchmetrics_single` | `blocked: symbol split` |
| `_namespace_prefix` | `function` | `private` | `rri_metrics.logging` | `rri_metrics.logging` | `rri_metrics.logging` | `blocked: symbol split` |
| `metric_key` | `function` | `public` | `rri_metrics.logging` | `rri_metrics.logging` | `rri_metrics.logging` | `blocked: symbol split` |
| `loss_key` | `function` | `public` | `rri_metrics.logging` | `rri_metrics.logging` | `rri_metrics.logging` | `blocked: symbol split` |
| `topk_accuracy_from_probs` | `function` | `public` | `rri_metrics.logging` | `rri_metrics.logging` | `rri_metrics.torchmetrics_single` | `blocked: symbol split` |

### `oracle_rri.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `OracleRRIConfig` | `config` | `public` | `rri_metrics.oracle_rri` | `rri_metrics.oracle_rri` | `rri_metrics.rri` | `blocked: symbol split` |
| `OracleRRI` | `class` | `public` | `rri_metrics.oracle_rri` | `rri_metrics.oracle_rri` | `rri_metrics.rri` | `blocked: symbol split` |
| `_crop_mesh_to_aabb` | `function` | `private` | `rri_metrics.oracle_rri` | `rri_metrics.oracle_rri` | `rri_metrics.rri` | `blocked: symbol split` |
| `_canonical_fused_unions` | `function` | `private` | `rri_metrics.oracle_rri` | `rri_metrics.oracle_rri` | `rri_metrics.rri` | `blocked: symbol split` |
| `_source_balanced_capped_union` | `function` | `private` | `rri_metrics.oracle_rri` | `rri_metrics.oracle_rri` | `rri_metrics.rri` | `blocked: symbol split` |

### `ordinal.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `_unique_path` | `function` | `private` | `rri_metrics.rri_binning` | `rri_metrics.ordinal` | `rri_metrics.ordinal` | `moved` |
| `_atomic_write_text` | `function` | `private` | `rri_metrics.rri_binning` | `rri_metrics.ordinal` | `rri_metrics.ordinal` | `moved` |
| `_atomic_torch_save` | `function` | `private` | `rri_metrics.rri_binning` | `rri_metrics.ordinal` | `rri_metrics.ordinal` | `moved` |
| `ordinal_labels_to_levels` | `function` | `public` | `rri_metrics.rri_binning` | `rri_metrics.ordinal` | `rri_metrics.ordinal` | `moved` |
| `RriOrdinalBinner` | `DTO` | `public` | `rri_metrics.rri_binning` | `rri_metrics.ordinal` | `rri_metrics.ordinal` | `moved` |

### `plotting.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `rri_color_map` | `function` | `public` | `rri_metrics.plotting` | `rri_metrics.plotting` | `rri_metrics.plotting` | `already aligned` |
| `plot_rri_scores` | `function` | `public` | `rri_metrics.plotting` | `rri_metrics.plotting` | `rri_metrics.plotting` | `already aligned` |
| `plot_pm_distances` | `function` | `public` | `rri_metrics.plotting` | `rri_metrics.plotting` | `rri_metrics.plotting` | `already aligned` |
| `plot_pm_accuracy` | `function` | `public` | `rri_metrics.plotting` | `rri_metrics.plotting` | `rri_metrics.plotting` | `already aligned` |
| `plot_pm_completeness` | `function` | `public` | `rri_metrics.plotting` | `rri_metrics.plotting` | `rri_metrics.plotting` | `already aligned` |
| `plot_rri_scene` | `function` | `public` | `rri_metrics.plotting` | `rri_metrics.plotting` | `rri_metrics.plotting` | `already aligned` |
| `_as_list` | `function` | `private` | `rri_metrics.plotting` | `rri_metrics.plotting` | `rri_metrics.plotting` | `already aligned` |

### `point_mesh.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `chamfer_point_mesh` | `function` | `public` | `rri_metrics.metrics` | `rri_metrics.point_mesh` | `rri_metrics.point_mesh` | `moved` |
| `chamfer_point_mesh_batched` | `function` | `public` | `rri_metrics.metrics` | `rri_metrics.point_mesh` | `rri_metrics.point_mesh` | `moved` |

### `rollout.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `TargetRolloutMetricSummary` | `DTO` | `public` | `rri_metrics.rollout` | `rri_metrics.rollout` | `rri_metrics.returns` | `blocked: symbol split` |
| `selected_target_rri` | `function` | `public` | `rri_metrics.rollout` | `rri_metrics.rollout` | `rri_metrics.returns` | `blocked: symbol split` |
| `selected_target_reward` | `function` | `public` | `rri_metrics.rollout` | `rri_metrics.rollout` | `rri_metrics.returns` | `blocked: symbol split` |
| `target_point_mesh_error_before` | `function` | `public` | `rri_metrics.rollout` | `rri_metrics.rollout` | `rri_metrics.returns` | `blocked: symbol split` |
| `target_point_mesh_error_after` | `function` | `public` | `rri_metrics.rollout` | `rri_metrics.rollout` | `rri_metrics.returns` | `blocked: symbol split` |
| `finite_horizon_target_return` | `function` | `public` | `rri_metrics.rollout` | `rri_metrics.rollout` | `rri_metrics.returns` | `blocked: symbol split` |
| `endpoint_target_gain` | `function` | `public` | `rri_metrics.rollout` | `rri_metrics.rollout` | `rri_metrics.returns` | `blocked: symbol split` |
| `endpoint_log_gain` | `function` | `public` | `rri_metrics.rollout` | `rri_metrics.rollout` | `rri_metrics.returns` | `blocked: symbol split` |
| `summarize_target_rollout_metrics` | `function` | `public` | `rri_metrics.rollout` | `rri_metrics.rollout` | `rri_metrics.returns` | `blocked: symbol split` |
| `_point_mesh_error` | `function` | `private` | `rri_metrics.rollout` | `rri_metrics.rollout` | `rri_metrics.returns` | `blocked: symbol split` |
| `_endpoint_errors` | `function` | `private` | `rri_metrics.rollout` | `rri_metrics.rollout` | `rri_metrics.returns` | `blocked: symbol split` |
| `_finite_metric` | `function` | `private` | `rri_metrics.rollout` | `rri_metrics.rollout` | `rri_metrics.returns` | `blocked: symbol split` |

### `torch_rollout.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `TorchRolloutMetrics` | `DTO` | `public` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rri_metrics.returns` | `blocked: symbol split` |
| `CandidateOrderConsistency` | `DTO` | `public` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rollouts.audits` | `blocked: symbol split` |
| `SelectedActionOracleComparison` | `DTO` | `public` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rri_metrics.ranking` | `blocked: symbol split` |
| `CandidatePathIncrementStats` | `DTO` | `public` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rollouts.audits` | `blocked: symbol split` |
| `CandidatePrimaryInvalidReasonStats` | `DTO` | `public` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rollouts.audits` | `blocked: symbol split` |
| `discounted_selected_return` | `function` | `public` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rri_metrics.returns` | `blocked: symbol split` |
| `endpoint_target_gain_tensor` | `function` | `public` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rri_metrics.returns` | `blocked: symbol split` |
| `endpoint_log_gain_tensor` | `function` | `public` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rri_metrics.returns` | `blocked: symbol split` |
| `summarize_selected_rollout_tensors` | `function` | `public` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rri_metrics.returns` | `blocked: symbol split` |
| `selected_path_length_tensor` | `function` | `public` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rollouts.audits` | `blocked: symbol split` |
| `candidate_order_consistency` | `function` | `public` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rollouts.audits` | `blocked: symbol split` |
| `candidate_policy_entropy` | `function` | `public` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rollouts.audits` | `blocked: symbol split` |
| `candidate_topk_oracle_hit` | `function` | `public` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rri_metrics.ranking` | `blocked: symbol split` |
| `selected_action_oracle_comparison` | `function` | `public` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rri_metrics.ranking` | `blocked: symbol split` |
| `candidate_provenance_share` | `function` | `public` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rollouts.audits` | `blocked: symbol split` |
| `candidate_path_increment_stats` | `function` | `public` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rollouts.audits` | `blocked: symbol split` |
| `candidate_primary_invalid_reason_share` | `function` | `public` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rollouts.audits` | `blocked: symbol split` |
| `candidate_masked_mean` | `function` | `public` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rollouts.audits` | `blocked: symbol split` |
| `candidate_best_value` | `function` | `public` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rollouts.audits` | `blocked: symbol split` |
| `_as_step_matrix` | `function` | `private` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rollouts.audits` | `blocked: symbol split` |
| `_as_path_matrix` | `function` | `private` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rollouts.audits` | `blocked: symbol split` |
| `_as_candidate_matrix` | `function` | `private` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rollouts.audits` | `blocked: symbol split` |
| `_candidate_valid_matrix` | `function` | `private` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rollouts.audits` | `blocked: symbol split` |
| `_masked_argmax` | `function` | `private` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rollouts.audits` | `blocked: symbol split` |
| `_discount_weights` | `function` | `private` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rri_metrics.returns` | `blocked: symbol split` |
| `_finite_mask` | `function` | `private` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rri_metrics.returns` | `blocked: symbol split` |
| `_valid_endpoint_errors` | `function` | `private` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rri_metrics.returns` | `blocked: symbol split` |
| `_id_membership` | `function` | `private` | `rri_metrics.torch_rollout` | `rri_metrics.torch_rollout` | `rollouts.audits` | `blocked: symbol split` |

### `torch_rollout_metrics.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `FiniteMeanMetric` | `class` | `public` | `rri_metrics.torch_rollout_metrics` | `rri_metrics.torch_rollout_metrics` | `rri_metrics.torchmetrics_multi` | `blocked: symbol split` |
| `SelectedRolloutMetrics` | `class` | `public` | `rri_metrics.torch_rollout_metrics` | `rri_metrics.torch_rollout_metrics` | `rri_metrics.torchmetrics_multi` | `blocked: symbol split` |
| `CandidateTableMetrics` | `class` | `public` | `rri_metrics.torch_rollout_metrics` | `rri_metrics.torch_rollout_metrics` | `rollouts.audits` | `blocked: symbol split` |
| `CandidatePathIncrementMetric` | `class` | `public` | `rri_metrics.torch_rollout_metrics` | `rri_metrics.torch_rollout_metrics` | `rollouts.audits` | `blocked: symbol split` |
| `CandidatePrimaryInvalidReasonMetric` | `class` | `public` | `rri_metrics.torch_rollout_metrics` | `rri_metrics.torch_rollout_metrics` | `rollouts.audits` | `blocked: symbol split` |
| `SelectedPathCostMetrics` | `class` | `public` | `rri_metrics.torch_rollout_metrics` | `rri_metrics.torch_rollout_metrics` | `rollouts.audits` | `blocked: symbol split` |
| `CandidateOrderConsistencyMetric` | `class` | `public` | `rri_metrics.torch_rollout_metrics` | `rri_metrics.torch_rollout_metrics` | `rollouts.audits` | `blocked: symbol split` |
| `CandidatePolicyEntropyMetric` | `class` | `public` | `rri_metrics.torch_rollout_metrics` | `rri_metrics.torch_rollout_metrics` | `rollouts.audits` | `blocked: symbol split` |
| `CandidateTopKOracleHitMetric` | `class` | `public` | `rri_metrics.torch_rollout_metrics` | `rri_metrics.torch_rollout_metrics` | `rri_metrics.torchmetrics_multi` | `blocked: symbol split` |
| `CandidateProvenanceShareMetric` | `class` | `public` | `rri_metrics.torch_rollout_metrics` | `rri_metrics.torch_rollout_metrics` | `rollouts.audits` | `blocked: symbol split` |
| `SelectedActionOracleComparisonMetric` | `class` | `public` | `rri_metrics.torch_rollout_metrics` | `rri_metrics.torch_rollout_metrics` | `rri_metrics.torchmetrics_multi` | `blocked: symbol split` |
| `_safe_mean` | `function` | `private` | `rri_metrics.torch_rollout_metrics` | `rri_metrics.torch_rollout_metrics` | `rri_metrics.torchmetrics_multi` | `blocked: symbol split` |

### `types.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `Tensor` | `constant` | `public` | `rri_metrics.types` | `rri_metrics.types` | `rri_metrics.point_mesh` | `blocked: symbol split` |
| `DistanceAggregation` | `class` | `public` | `rri_metrics.types` | `rri_metrics.types` | `rri_metrics.point_mesh` | `blocked: symbol split` |
| `DistanceBreakdown` | `DTO` | `public` | `rri_metrics.types` | `rri_metrics.types` | `rri_metrics.point_mesh` | `blocked: symbol split` |
| `RriResult` | `DTO` | `public` | `rri_metrics.types` | `rri_metrics.types` | `rri_metrics.rri` | `blocked: symbol split` |

## Deferred Whole-File Moves

`oracle_rri.py`, `logging.py`, `rollout.py`, `torch_rollout.py`, `torch_rollout_metrics.py`, and `types.py` mix symbols with different final owners. They remain in place until their semantic workpackages can split them without compatibility modules.
