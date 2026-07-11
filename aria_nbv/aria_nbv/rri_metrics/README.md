# RRI Metrics

`aria_nbv.rri_metrics` owns reconstruction formulas and reusable evaluation
adapters. Oracle evidence and scorers live in `aria_nbv.oracle`; rollout
operational checks live in `aria_nbv.rollouts.audits`.

## Current Layout

```text
rri_metrics/
  point_mesh.py
  rri.py
  returns.py
  ranking.py
  ordinal.py
  torchmetrics_single.py
  torchmetrics_multi.py
  logging.py
  plotting.py
```

The package root exports only `compute_rri`, `RriConfig`, `RriResult`, and
`RriOrdinalBinner`. Specialized functions and adapters use leaf imports.

## Differentiability

| Module | Differentiable | Contract |
|---|---:|---|
| `point_mesh.py` | yes where PyTorch3D permits | point-mesh primitives |
| `rri.py` | yes | prepared RRI formula |
| `returns.py` | yes for tensor kernels | gains and finite-horizon returns |
| `ranking.py` | no | rank, top-k, percentile, regret |
| `ordinal.py` | no | ordinal label construction |
| `torchmetrics_*.py` | no | stateful evaluation only |
| `rollouts.audits` | no | operational diagnostics only |

Tensor kernels in `returns.py` are authoritative. Mapping/scalar adapters
delegate to them.

## Symbol Ownership Matrix

Exact top-level AST inventory generated on 2026-07-10 after a Graphify owner
query. Imported names, methods, fields, and `__all__` are excluded.

### `__init__.py`

Owner role: four-symbol stable root.

No top-level definitions.

### `logging.py`

Owner role: log names and key policy.

| Symbol | Kind | Visibility | Current module | Status |
|---|---|---|---|---|
| `LogSpec` | `DTO` | `public` | `rri_metrics.logging` | `landed` |
| `Logable` | `class` | `public` | `rri_metrics.logging` | `landed` |
| `Metric` | `class` | `public` | `rri_metrics.logging` | `landed` |
| `Loss` | `class` | `public` | `rri_metrics.logging` | `landed` |
| `_namespace_prefix` | `function` | `private` | `rri_metrics.logging` | `landed` |
| `metric_key` | `function` | `public` | `rri_metrics.logging` | `landed` |
| `loss_key` | `function` | `public` | `rri_metrics.logging` | `landed` |

### `ordinal.py`

Owner role: non-differentiable RRI label binning.

| Symbol | Kind | Visibility | Current module | Status |
|---|---|---|---|---|
| `_unique_path` | `function` | `private` | `rri_metrics.ordinal` | `landed` |
| `_atomic_write_text` | `function` | `private` | `rri_metrics.ordinal` | `landed` |
| `_atomic_torch_save` | `function` | `private` | `rri_metrics.ordinal` | `landed` |
| `ordinal_labels_to_levels` | `function` | `public` | `rri_metrics.ordinal` | `landed` |
| `RriOrdinalBinner` | `DTO` | `public` | `rri_metrics.ordinal` | `landed` |

### `plotting.py`

Owner role: lightweight RRI result plots.

| Symbol | Kind | Visibility | Current module | Status |
|---|---|---|---|---|
| `rri_color_map` | `function` | `public` | `rri_metrics.plotting` | `landed` |
| `plot_rri_scores` | `function` | `public` | `rri_metrics.plotting` | `landed` |
| `plot_pm_distances` | `function` | `public` | `rri_metrics.plotting` | `landed` |
| `plot_pm_accuracy` | `function` | `public` | `rri_metrics.plotting` | `landed` |
| `plot_pm_completeness` | `function` | `public` | `rri_metrics.plotting` | `landed` |
| `_as_list` | `function` | `private` | `rri_metrics.plotting` | `landed` |

### `point_mesh.py`

Owner role: differentiable point-mesh primitives.

| Symbol | Kind | Visibility | Current module | Status |
|---|---|---|---|---|
| `DistanceBreakdown` | `DTO` | `public` | `rri_metrics.point_mesh` | `landed` |
| `chamfer_point_mesh` | `function` | `public` | `rri_metrics.point_mesh` | `landed` |
| `chamfer_point_mesh_batched` | `function` | `public` | `rri_metrics.point_mesh` | `landed` |

### `ranking.py`

Owner role: non-differentiable ranking evaluation.

| Symbol | Kind | Visibility | Current module | Status |
|---|---|---|---|---|
| `SelectedActionOracleComparison` | `DTO` | `public` | `rri_metrics.ranking` | `landed` |
| `candidate_topk_oracle_hit` | `function` | `public` | `rri_metrics.ranking` | `landed` |
| `selected_action_oracle_comparison` | `function` | `public` | `rri_metrics.ranking` | `landed` |

### `returns.py`

Owner role: differentiable gain and return kernels plus mapping adapters.

| Symbol | Kind | Visibility | Current module | Status |
|---|---|---|---|---|
| `TargetRolloutMetricSummary` | `DTO` | `public` | `rri_metrics.returns` | `landed` |
| `TorchRolloutMetrics` | `DTO` | `public` | `rri_metrics.returns` | `landed` |
| `selected_target_rri` | `function` | `public` | `rri_metrics.returns` | `landed` |
| `selected_target_reward` | `function` | `public` | `rri_metrics.returns` | `landed` |
| `target_point_mesh_error_before` | `function` | `public` | `rri_metrics.returns` | `landed` |
| `target_point_mesh_error_after` | `function` | `public` | `rri_metrics.returns` | `landed` |
| `root_normalized_gain` | `function` | `public` | `rri_metrics.returns` | `landed` |
| `log_error_gain` | `function` | `public` | `rri_metrics.returns` | `landed` |
| `discounted_selected_return` | `function` | `public` | `rri_metrics.returns` | `landed` |
| `endpoint_target_gain_tensor` | `function` | `public` | `rri_metrics.returns` | `landed` |
| `endpoint_log_gain_tensor` | `function` | `public` | `rri_metrics.returns` | `landed` |
| `summarize_selected_rollout_tensors` | `function` | `public` | `rri_metrics.returns` | `landed` |
| `finite_horizon_target_return` | `function` | `public` | `rri_metrics.returns` | `landed` |
| `endpoint_target_gain` | `function` | `public` | `rri_metrics.returns` | `landed` |
| `endpoint_log_gain` | `function` | `public` | `rri_metrics.returns` | `landed` |
| `summarize_target_rollout_metrics` | `function` | `public` | `rri_metrics.returns` | `landed` |
| `_point_mesh_error` | `function` | `private` | `rri_metrics.returns` | `landed` |
| `_endpoint_errors` | `function` | `private` | `rri_metrics.returns` | `landed` |
| `_finite_metric` | `function` | `private` | `rri_metrics.returns` | `landed` |
| `_as_step_matrix` | `function` | `private` | `rri_metrics.returns` | `landed` |
| `_discount_weights` | `function` | `private` | `rri_metrics.returns` | `landed` |
| `_finite_mask` | `function` | `private` | `rri_metrics.returns` | `landed` |
| `_valid_endpoint_errors` | `function` | `private` | `rri_metrics.returns` | `landed` |
| `_optional_scalar` | `function` | `private` | `rri_metrics.returns` | `landed` |

### `rri.py`

Owner role: prepared differentiable RRI.

| Symbol | Kind | Visibility | Current module | Status |
|---|---|---|---|---|
| `RriConfig` | `config` | `public` | `rri_metrics.rri` | `landed` |
| `_DEFAULT_RRI_CONFIG` | `constant` | `private` | `rri_metrics.rri` | `landed` |
| `RriResult` | `DTO` | `public` | `rri_metrics.rri` | `landed` |
| `compute_rri` | `function` | `public` | `rri_metrics.rri` | `landed` |

### `torchmetrics_multi.py`

Owner role: stateful multi-step evaluation.

| Symbol | Kind | Visibility | Current module | Status |
|---|---|---|---|---|
| `SelectedRolloutMetrics` | `class` | `public` | `rri_metrics.torchmetrics_multi` | `landed` |
| `_safe_mean` | `function` | `private` | `rri_metrics.torchmetrics_multi` | `landed` |

### `torchmetrics_single.py`

Owner role: stateful one-step evaluation.

| Symbol | Kind | Visibility | Current module | Status |
|---|---|---|---|---|
| `LabelHistogram` | `class` | `public` | `rri_metrics.torchmetrics_single` | `landed` |
| `RriErrorStats` | `class` | `public` | `rri_metrics.torchmetrics_single` | `landed` |
| `VinMetrics` | `class` | `public` | `rri_metrics.torchmetrics_single` | `landed` |
| `VinMetricsConfig` | `config` | `public` | `rri_metrics.torchmetrics_single` | `landed` |
| `topk_accuracy_from_probs` | `function` | `public` | `rri_metrics.torchmetrics_single` | `landed` |
| `CandidateTopKOracleHitMetric` | `class` | `public` | `rri_metrics.torchmetrics_single` | `landed` |
| `SelectedActionOracleComparisonMetric` | `class` | `public` | `rri_metrics.torchmetrics_single` | `landed` |
| `_safe_mean` | `function` | `private` | `rri_metrics.torchmetrics_single` | `landed` |


## Dependency Rules

- Final metric modules do not import `oracle`, `rollouts`, VIN, Lightning,
  app, or rendering.
- Oracle facades call `compute_rri`; they do not own its formula.
- Lightning owns metric lifecycle, not reducer implementations.
- Rollout provenance, invalidity, path, entropy, and order checks stay in
  `rollouts.audits`.

## Lightning Lifecycle

WP06 types and documents every TorchMetric state. Lightning owns separate
candidate-ranking accumulators for train, validation, and test stages, logs
table-weighted epoch results, and resets each stage explicitly. The existing
training-step ranking keys remain available without driving epoch reduction.

`SelectedRolloutMetrics` remains the reusable multi-step adapter. It is not
updated from `VinOracleBatch`: that one-step contract has neither trajectory
rewards nor endpoint errors. The future finite-horizon Lightning path must
connect it only when those tensors are real batch fields.

WP08 moved privileged evidence and scene scoring into `aria_nbv.oracle`.
