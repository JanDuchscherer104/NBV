# Oracle

`aria_nbv.oracle` owns privileged target-task preparation, evidence resolution,
scene/target RRI scoring, and label-generation pipelines. It may consume GT
geometry and raw/offline data, but final scorer modules must not import rollout
replay or persistence contracts.

## Current Layout

```text
oracle/
  __init__.py
  _scoring.py
  evidence.py
  scene_rri.py
  target_rri.py
  target_selection.py
  pipelines/
```

WP07 established target-task ownership. WP08-WP09 established scene/target
scoring, typed evidence invalidity, and the shared private scoring engine.
Pipeline relocation remains WP12.

Baseline: `4daf9d4`

Graphify refresh: `2026-07-11T18:23:00+02:00`

## Symbol Ownership Matrix

### `__init__.py`

No top-level AST definitions. The package exports only the scene/target scorer
classes and configs; imported names and `__all__` are excluded from the matrix.

### `_scoring.py`

| Symbol | Kind | Visibility | Before module | Current module | Final owner | Status |
|---|---|---|---|---|---|---|
| `PreparedRriScorerConfig` | config | private | `rri_metrics.oracle_rri` | `oracle._scoring` | `oracle._scoring` | moved |
| `PreparedRriScorer` | class | private | `rri_metrics.oracle_rri` | `oracle._scoring` | `oracle._scoring` | moved |
| `_CandidateRriScoringEngine` | class | private | duplicated scene/target scorer paths | `oracle._scoring` | `oracle._scoring` | moved |
| `_root_error_tensor` | function | private | duplicated scorer helpers | `oracle._scoring` | `oracle._scoring` | moved |
| `_crop_mesh_to_aabb` | function | private | `rri_metrics.oracle_rri` | `oracle._scoring` | `oracle._scoring` | moved |
| `_canonical_fused_unions` | function | private | `rri_metrics.oracle_rri` | `oracle._scoring` | `oracle._scoring` | moved |
| `_source_balanced_capped_union` | function | private | `rri_metrics.oracle_rri` | `oracle._scoring` | `oracle._scoring` | moved |

### `evidence.py`

| Symbol | Kind | Visibility | Before module | Current module | Final owner | Status |
|---|---|---|---|---|---|---|
| `Tensor` | alias | public | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `oracle.evidence` | moved |
| `CameraLabel` | alias | public | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `oracle.evidence` | moved |
| `OracleEvidenceInvalidReason` | enum | public | string-only target failures | `oracle.evidence` | `oracle.evidence` | moved |
| `_OracleEvidenceError` | class | private | string-only target failures | `oracle.evidence` | `oracle.evidence` | moved |
| `OracleRriState` | protocol | public | rollout trajectory coupling | `oracle.evidence` | `oracle.evidence` | moved |
| `RriEvaluationPointCloudSource` | enum | public | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `oracle.evidence` | moved |
| `RriRewardMode` | enum | public | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `oracle.evidence` | moved |
| `RootEvalPointCloud` | DTO | public | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `oracle.evidence` | moved |
| `canonical_fuse_points` | function | public | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `oracle.evidence` | moved |
| `_root_evidence_token` | function | private | duplicated scorer helpers | `oracle.evidence` | `oracle.evidence` | moved |
| `_eval_depth_far_m` | function | private | duplicated scorer helpers | `oracle.evidence` | `oracle.evidence` | moved |
| `target_gt_obb_world` | function | public | `data_handling._target_selection` | `oracle.evidence` | `oracle.evidence` | moved |
| `crop_points_to_obb` | function | public | `rollouts.target_counterfactuals` | `oracle.evidence` | `oracle.evidence` | moved |
| `crop_padded_pointclouds_to_obb` | function | public | `rollouts.target_counterfactuals` | `oracle.evidence` | `oracle.evidence` | moved |
| `crop_mesh_to_obb` | function | public | `rollouts.target_counterfactuals` | `oracle.evidence` | `oracle.evidence` | moved |
| `target_aabb_from_points` | function | public | `rollouts.target_counterfactuals` | `oracle.evidence` | `oracle.evidence` | moved |
| `_points_inside_obb_mask` | function | private | `rollouts.target_counterfactuals` | `oracle.evidence` | `oracle.evidence` | moved |
| `build_root_eval_pointcloud` | function | public | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `oracle.evidence` | moved |
| `observed_prefix_frame_indices` | function | public | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `oracle.evidence` | moved |
| `_root_time_ns` | function | private | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `oracle.evidence` | moved |
| `_root_trajectory_index` | function | private | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `oracle.evidence` | moved |
| `_exact_trajectory_index` | function | private | `rri_metrics.eval_pointclouds` | `oracle.evidence` | `oracle.evidence` | moved |

### `scene_rri.py`

| Symbol | Kind | Visibility | Before module | Current module | Final owner | Status |
|---|---|---|---|---|---|---|
| `SceneRriEvaluation` | DTO | public | rollout evaluation coupling | `oracle.scene_rri` | `oracle.scene_rri` | moved |
| `SceneRriScorerConfig` | config | public | `rollouts.counterfactuals` | `oracle.scene_rri` | `oracle.scene_rri` | moved |
| `SceneRriScorer` | class | public | `rollouts.counterfactuals` | `oracle.scene_rri` | `oracle.scene_rri` | moved |

### `target_rri.py`

| Symbol | Kind | Visibility | Before module | Current module | Final owner | Status |
|---|---|---|---|---|---|---|
| `TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1` | constant | public | `rollouts.target_counterfactuals` | `oracle.target_rri` | `oracle.target_rri` | moved |
| `SCENE_CROP_POLICY_SNIPPET_EXTENT_V1` | constant | public | `rollouts.target_counterfactuals` | `oracle.target_rri` | `oracle.target_rri` | moved |
| `TargetRriInvalidity` | DTO | public | exception-only invalidity | `oracle.target_rri` | `oracle.target_rri` | moved |
| `TargetRriEvaluation` | DTO | public | rollout evaluation coupling | `oracle.target_rri` | `oracle.target_rri` | moved |
| `TargetRriScorerConfig` | config | public | `rollouts.target_counterfactuals` | `oracle.target_rri` | `oracle.target_rri` | moved |
| `TargetRriScorer` | class | public | `rollouts.target_counterfactuals` | `oracle.target_rri` | `oracle.target_rri` | moved |

### `target_selection.py`

| Symbol | Kind | Visibility | Before module | Current module | Final owner | Status |
|---|---|---|---|---|---|---|
| `TARGET_INVALID_REASON_CODES` | constant | public | `data_handling._target_selection` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `TARGET_INVALID_REASON_VERSION` | constant | public | `data_handling._target_selection` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `ORACLE_TARGET_TASK_SOURCE` | constant | public | `data_handling._target_selection` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `TargetCandidateRow` | DTO | public | `data_handling._target_selection` | `oracle.target_selection` | pipeline label compatibility | deferred: semantic WP |
| `TargetTaskIdentityStatus` | enum | public | `data_handling._target_selection` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `OracleTargetTaskSelectionPolicy` | enum | public | `data_handling._target_selection` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `OracleTargetTaskRow` | DTO | public | `data_handling._target_selection` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `OracleTargetTaskSamplingResult` | DTO | public | `data_handling._target_selection` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `_TargetSource` | DTO | private | `data_handling._target_selection` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `OracleTargetTaskSamplerConfig` | config | public | `data_handling._target_selection` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `OracleTargetTaskSampler` | class | public | `data_handling._target_selection` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `target_candidate_row_from_task` | function | public | `oracle.pipelines.rollout_dataset` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `target_descriptor_from_candidate_row` | function | public | `oracle.pipelines.rollout_dataset` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `_oracle_target_invalidity` | function | private | `oracle.pipelines.rollout_dataset` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `_compact_obb_block` | function | private | `data_handling._target_selection` | `oracle.target_selection` | `oracle.evidence` | deferred: semantic WP |
| `_world_obbs_for_sample` | function | private | `data_handling._target_selection` | `oracle.target_selection` | `oracle.evidence` | deferred: semantic WP |
| `_latest_valid_obb_slice` | function | private | `data_handling._target_selection` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `_valid_obb_data_with_source_indices` | function | private | `data_handling._target_selection` | `oracle.target_selection` | `oracle.evidence` | deferred: semantic WP |
| `_sample_snippet_view` | function | private | `data_handling._target_selection` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `_snippet_t_world_snippet` | function | private | `data_handling._target_selection` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `_reference_pose_world_rig` | function | private | `data_handling._target_selection` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `_pose_on_device` | function | private | `data_handling._target_selection` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `_obb_geometry_valid` | function | private | `data_handling._target_selection` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `_class_name` | function | private | `data_handling._target_selection` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `_target_id` | function | private | `data_handling._target_selection` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `_first_scalar_string` | function | private | `data_handling._target_selection` | `oracle.target_selection` | `oracle.target_selection` | moved |
| `_float_tuple` | function | private | `data_handling._target_selection` | `oracle.target_selection` | `oracle.target_selection` | moved |

## Target State

```text
oracle/
  evidence.py
  target_selection.py
  scene_rri.py
  target_rri.py
  _scoring.py
  pipelines/
```

`scene_rri.py` and `target_rri.py` are public facades over `_scoring.py`.
`evidence.py` prepares privileged scorer inputs. Replay consumes scorer outputs
through later pipeline-owned contracts; Oracle never imports replay internals.
