# Replay

`aria_nbv.rollouts.replay` owns finite-candidate policy, hard-masked score
inputs, in-memory transitions, and tree expansion. It does not import Oracle
scorers or persisted Zarr rows. Pipelines adapt Oracle outputs before replay;
writers flatten replay and label/evidence aggregates afterward.

## Layout

```text
replay/
  policy.py   # immutable RolloutPolicySpec and selection names
  types.py    # minimal CandidateScores policy input
  state.py    # selected transitions, trajectories, and rollout result
  engine.py   # candidate expansion and selection implementation
```

Baseline: `d6b809a`

Graphify refresh: `2026-07-11T19:40:59+02:00`

## Symbol Ownership Matrix

### `__init__.py`

No top-level AST definitions; imported names and `__all__` are excluded.

### `policy.py`

| Symbol | Kind | Visibility | Before module | Current module | Final owner | Status |
|---|---|---|---|---|---|---|
| `CounterfactualSelectionPolicy` | enum | public | `rollouts.counterfactuals` | `rollouts.replay.policy` | `rollouts.replay.policy` | moved |
| `RolloutPolicySpec` | config | public | duplicated engine/recipe fields | `rollouts.replay.policy` | `rollouts.replay.policy` | moved |

### `types.py`

| Symbol | Kind | Visibility | Before module | Current module | Final owner | Status |
|---|---|---|---|---|---|---|
| `CandidateScores` | DTO | public | wide evaluator score fields | `rollouts.replay.types` | `rollouts.replay.types` | moved |

### `state.py`

| Symbol | Kind | Visibility | Before module | Current module | Final owner | Status |
|---|---|---|---|---|---|---|
| `_pose_row` | function | private | `rollouts.counterfactuals` | `rollouts.replay.state` | `rollouts.replay.state` | moved |
| `_pose_at` | function | private | `rollouts.counterfactuals` | `rollouts.replay.state` | `rollouts.replay.state` | moved |
| `_root_error_for_metric` | function | private | `rollouts.counterfactuals` | `rollouts.replay.state` | removed with legacy metric fields in WP11 | deferred: semantic WP |
| `CounterfactualSelectionRecord` | DTO | public | `rollouts.counterfactuals` | `rollouts.replay.state` | `rollouts.replay.state` | moved |
| `CounterfactualStepResult` | DTO | public | `rollouts.counterfactuals` | `rollouts.replay.state` | narrowed transition in WP11 | deferred: semantic WP |
| `CounterfactualTrajectory` | DTO | public | `rollouts.counterfactuals` | `rollouts.replay.state` | `rollouts.replay.state` | moved |
| `CounterfactualRolloutResult` | DTO | public | `rollouts.counterfactuals` | `rollouts.replay.state` | `rollouts.replay.state` | moved |

### `engine.py`

| Symbol | Kind | Visibility | Before module | Current module | Final owner | Status |
|---|---|---|---|---|---|---|
| `_pose_batch_len` | function | private | `rollouts.counterfactuals` | `rollouts.replay.engine` | `rollouts.replay.engine` | moved |
| `_exact_pose_index` | function | private | `rollouts.counterfactuals` | `rollouts.replay.engine` | `rollouts.replay.engine` | moved |
| `_time_value` | function | private | `rollouts.counterfactuals` | `rollouts.replay.engine` | `rollouts.replay.engine` | moved |
| `_robust_temperature_logits` | function | private | `rollouts.counterfactuals` | `rollouts.replay.engine` | `rollouts.replay.engine` | moved |
| `_valid_diversity_metadata` | function | private | `rollouts.counterfactuals` | `rollouts.replay.engine` | `rollouts.replay.engine` | moved |
| `_pose_yaw_rad` | function | private | `rollouts.counterfactuals` | `rollouts.replay.engine` | `rollouts.replay.engine` | moved |
| `_angular_separation` | function | private | `rollouts.counterfactuals` | `rollouts.replay.engine` | `rollouts.replay.engine` | moved |
| `_circular_min_delta` | function | private | `rollouts.counterfactuals` | `rollouts.replay.engine` | `rollouts.replay.engine` | moved |
| `_append_diversity_selection` | function | private | `rollouts.counterfactuals` | `rollouts.replay.engine` | `rollouts.replay.engine` | moved |
| `_CandidateDiversityMetadata` | DTO | private | `rollouts.counterfactuals` | `rollouts.replay.engine` | `rollouts.replay.engine` | moved |
| `CounterfactualMetricBundle` | DTO | public | `rollouts.counterfactuals` | `rollouts.replay.engine` | split labels/evidence in WP11 | deferred: semantic WP |
| `CounterfactualCandidateEvaluation` | DTO | public | `rollouts.counterfactuals` | `rollouts.replay.engine` | split labels/evidence in WP11 | deferred: semantic WP |
| `CounterfactualEvaluatorFn` | alias | public | `rollouts.counterfactuals` | `rollouts.replay.engine` | score-provider protocol after WP11 | deferred: semantic WP |
| `CounterfactualPoseGeneratorConfig` | config | public | `rollouts.counterfactuals` | `rollouts.replay.engine` | `rollouts.replay.engine` | moved |
| `CounterfactualPoseGenerator` | class | public | `rollouts.counterfactuals` | `rollouts.replay.engine` | `rollouts.replay.engine` | moved |

## Current Contract

- Selection consumes `CandidateScores`, whose compact values are bound to the
  full-shell hard mask and stable shell-row order.
- `RolloutPolicySpec` is the sole owner of horizon, branch, beam, stochastic,
  temperature, diversity, and seed controls. Engine and pipeline configs
  compose it.
- Wide metric/evidence fields remain transitional until WP11 splits
  `OracleCandidateLabels` and `RetainedOracleEvidence`; they are not part of
  `CandidateScores`.

## Migration

This is a clean internal API transition. Import replay symbols from their leaf
modules or the stable `aria_nbv.rollouts` root; the removed
`aria_nbv.rollouts.counterfactuals` module has no compatibility facade.
`CounterfactualPoseGeneratorConfig` and `RolloutRecipeConfig` now compose one
`RolloutPolicySpec`; canonical repository TOMLs were migrated atomically, and
legacy flat policy fields are intentionally rejected.
