# Rollouts

`aria_nbv.rollouts` owns replay transitions, persisted traces/stores, manifests,
audits, and read-side inspection. Rollout dataset/shard generation lives in
`aria_nbv.oracle.pipelines`; the top-level scene labeler moves there in WP12.

## Layout

```text
rollouts/
  audits.py               # operational validity/provenance/path checks
  counterfactuals.py      # future replay split
  target_counterfactuals.py  # future oracle extraction
  inspection.py
  manifest.py
  shard_manifest.py
  trace.py
  zarr_store.py
  info_cli.py
```

Baseline: `6b72b62639e24fc13bba845ec63bc8fc72c77aae`

Inventory generated: `2026-07-10T16:10:28.231382+00:00`

Graphify refresh: `2026-07-10T18:34:29+02:00`

## Symbol Ownership Matrix

### `__init__.py`

No top-level AST definitions; imported names and `__all__` are excluded.

### `audits.py`

Operational audit reducers and TorchMetrics moved out of the former mixed
metrics modules. These symbols are evaluation-only.

| Symbol | Kind | Visibility | Final owner | Status |
|---|---|---|---|---|
| `CandidateOrderConsistency` | `DTO` | `public` | `rollouts.audits` | `moved` |
| `CandidatePathIncrementStats` | `DTO` | `public` | `rollouts.audits` | `moved` |
| `CandidatePrimaryInvalidReasonStats` | `DTO` | `public` | `rollouts.audits` | `moved` |
| `selected_path_length_tensor` | `function` | `public` | `rollouts.audits` | `moved` |
| `candidate_order_consistency` | `function` | `public` | `rollouts.audits` | `moved` |
| `candidate_policy_entropy` | `function` | `public` | `rollouts.audits` | `moved` |
| `candidate_provenance_share` | `function` | `public` | `rollouts.audits` | `moved` |
| `candidate_path_increment_stats` | `function` | `public` | `rollouts.audits` | `moved` |
| `candidate_primary_invalid_reason_share` | `function` | `public` | `rollouts.audits` | `moved` |
| `candidate_masked_mean` | `function` | `public` | `rollouts.audits` | `moved` |
| `candidate_best_value` | `function` | `public` | `rollouts.audits` | `moved` |
| `_as_path_matrix` | `function` | `private` | `rollouts.audits` | `moved` |
| `_as_candidate_matrix` | `function` | `private` | `rollouts.audits` | `moved` |
| `_candidate_valid_matrix` | `function` | `private` | `rollouts.audits` | `moved` |
| `_masked_argmax` | `function` | `private` | `rollouts.audits` | `moved` |
| `_finite_mask` | `function` | `private` | `rollouts.audits` | `moved` |
| `_id_membership` | `function` | `private` | `rollouts.audits` | `moved` |
| `CandidateTableMetrics` | `class` | `public` | `rollouts.audits` | `moved` |
| `CandidatePathIncrementMetric` | `class` | `public` | `rollouts.audits` | `moved` |
| `CandidatePrimaryInvalidReasonMetric` | `class` | `public` | `rollouts.audits` | `moved` |
| `SelectedPathCostMetrics` | `class` | `public` | `rollouts.audits` | `moved` |
| `CandidateOrderConsistencyMetric` | `class` | `public` | `rollouts.audits` | `moved` |
| `CandidatePolicyEntropyMetric` | `class` | `public` | `rollouts.audits` | `moved` |
| `CandidateProvenanceShareMetric` | `class` | `public` | `rollouts.audits` | `moved` |
| `_safe_mean` | `function` | `private` | `rollouts.audits` | `moved` |

### `counterfactuals.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `_pose_row` | `function` | `private` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `_pose_batch_len` | `function` | `private` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `_pose_at` | `function` | `private` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `_pose_token` | `function` | `private` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `_root_token` | `function` | `private` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `_exact_pose_index` | `function` | `private` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `_time_value` | `function` | `private` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `_root_error_for_metric` | `function` | `private` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `_root_error_tensor` | `function` | `private` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `_eval_depth_far_m` | `function` | `private` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `_robust_temperature_logits` | `function` | `private` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `_valid_diversity_metadata` | `function` | `private` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `_pose_yaw_rad` | `function` | `private` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `_angular_separation` | `function` | `private` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `_circular_min_delta` | `function` | `private` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `_append_diversity_selection` | `function` | `private` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `CounterfactualSelectionPolicy` | `enum` | `public` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `CounterfactualSelectionRecord` | `DTO` | `public` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `_CandidateDiversityMetadata` | `DTO` | `private` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `CounterfactualMetricBundle` | `DTO` | `public` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `CounterfactualCandidateEvaluation` | `DTO` | `public` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `CounterfactualStepResult` | `DTO` | `public` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `CounterfactualTrajectory` | `DTO` | `public` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `CounterfactualRolloutResult` | `DTO` | `public` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `CounterfactualEvaluatorFn` | `constant` | `public` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `CounterfactualPoseGeneratorConfig` | `config` | `public` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `CounterfactualOracleRriScorerConfig` | `config` | `public` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `CounterfactualOracleRriScorer` | `class` | `public` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |
| `CounterfactualPoseGenerator` | `class` | `public` | `rollouts.counterfactuals` | `rollouts.counterfactuals` | `rollouts.replay` | `blocked: symbol split` |

### `info_cli.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `_HELP_SETTINGS` | `constant` | `private` | `rollouts.info_cli` | `rollouts.info_cli` | `rollouts.info_cli` | `already aligned` |
| `_STRATEGY_NAMES` | `constant` | `private` | `rollouts.info_cli` | `rollouts.info_cli` | `rollouts.info_cli` | `already aligned` |
| `app` | `constant` | `public` | `rollouts.info_cli` | `rollouts.info_cli` | `rollouts.info_cli` | `already aligned` |
| `main` | `function` | `public` | `rollouts.info_cli` | `rollouts.info_cli` | `rollouts.info_cli` | `already aligned` |
| `info_command` | `function` | `public` | `rollouts.info_cli` | `rollouts.info_cli` | `rollouts.info_cli` | `already aligned` |
| `_random_index_payload` | `function` | `private` | `rollouts.info_cli` | `rollouts.info_cli` | `rollouts.info_cli` | `already aligned` |
| `_stats_payload` | `function` | `private` | `rollouts.info_cli` | `rollouts.info_cli` | `rollouts.info_cli` | `already aligned` |
| `_preflight_payload` | `function` | `private` | `rollouts.info_cli` | `rollouts.info_cli` | `rollouts.info_cli` | `already aligned` |
| `_target_component_count` | `function` | `private` | `rollouts.info_cli` | `rollouts.info_cli` | `rollouts.info_cli` | `already aligned` |
| `_reward_signal_payload` | `function` | `private` | `rollouts.info_cli` | `rollouts.info_cli` | `rollouts.info_cli` | `already aligned` |
| `_storage_payload` | `function` | `private` | `rollouts.info_cli` | `rollouts.info_cli` | `rollouts.info_cli` | `already aligned` |
| `_selected_path_lengths` | `function` | `private` | `rollouts.info_cli` | `rollouts.info_cli` | `rollouts.info_cli` | `already aligned` |
| `_reason_counts` | `function` | `private` | `rollouts.info_cli` | `rollouts.info_cli` | `rollouts.info_cli` | `already aligned` |
| `_id_counts` | `function` | `private` | `rollouts.info_cli` | `rollouts.info_cli` | `rollouts.info_cli` | `already aligned` |
| `_component_names` | `function` | `private` | `rollouts.info_cli` | `rollouts.info_cli` | `rollouts.info_cli` | `already aligned` |
| `_read_string_array` | `function` | `private` | `rollouts.info_cli` | `rollouts.info_cli` | `rollouts.info_cli` | `already aligned` |
| `_distribution` | `function` | `private` | `rollouts.info_cli` | `rollouts.info_cli` | `rollouts.info_cli` | `already aligned` |
| `_safe_fraction` | `function` | `private` | `rollouts.info_cli` | `rollouts.info_cli` | `rollouts.info_cli` | `already aligned` |
| `_print_text_summary` | `function` | `private` | `rollouts.info_cli` | `rollouts.info_cli` | `rollouts.info_cli` | `already aligned` |
| `_print_stats` | `function` | `private` | `rollouts.info_cli` | `rollouts.info_cli` | `rollouts.info_cli` | `already aligned` |

### `inspection.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `_INVALID_REASON_NAMES` | `constant` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_TARGET_INVALID_REASON_NAMES` | `constant` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_POSITION_NAMES` | `constant` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_STRATEGY_NAMES` | `constant` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `RolloutSuspiciousQueryConfig` | `config` | `public` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `decode_invalid_reason` | `function` | `public` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `decode_target_invalid_reason` | `function` | `public` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `decode_position_id` | `function` | `public` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `decode_strategy_id` | `function` | `public` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `discover_rollout_store_paths` | `function` | `public` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `rollout_store_inventory_rows` | `function` | `public` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `candidate_audit_rows` | `function` | `public` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `target_audit_rows` | `function` | `public` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `validity_waterfall_rows` | `function` | `public` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `candidate_group_summary_rows` | `function` | `public` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `rollout_step_objective_rows` | `function` | `public` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `rollout_tree_summary_rows` | `function` | `public` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `selected_depth_summary_rows` | `function` | `public` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `selected_depth_preview` | `function` | `public` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_selected_depth_base_row` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_selected_depth_unavailable_row` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_selected_depth_dense_summary` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_accumulate_optional` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_mean_accumulator` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `candidate_result_diagnostic_counts` | `function` | `public` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `suspicious_rollout_rows` | `function` | `public` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_low_fanout_rows` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_dominant_invalid_reason_rows` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_missing_label_rows` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_high_score_invalid_target_rows` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_selected_motion_outlier_rows` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_rollout_store_inventory_row` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_schema_sort_rank` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_validation_status` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_safe_manifest` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_manifest_profile` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_manifest_config_stem` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_manifest_coverage_count` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_store_stats` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_path_mtime` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_array_size` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_mask_count` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_mask_fraction` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_rollout_dictionary_summary` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_numeric_summary` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_candidate_diagnostics` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_rollout_context_by_id` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_rollout_rows_by_id` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_selected_candidate_context_by_id` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_step_selection_entropy` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_component_names` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_reader_dictionaries` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_dict_value` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_optional_array` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_finite_or_none` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |
| `_safe_fraction` | `function` | `private` | `rollouts.inspection` | `rollouts.inspection` | `rollouts.inspection` | `deferred: semantic WP` |

### `manifest.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `ROLLOUT_MANIFEST_FILENAME` | `constant` | `public` | `rollouts.manifest` | `rollouts.manifest` | `rollouts.manifest` | `already aligned` |
| `ROLLOUT_MANIFEST_VERSION` | `constant` | `public` | `rollouts.manifest` | `rollouts.manifest` | `rollouts.manifest` | `already aligned` |
| `RolloutStoreInvocation` | `DTO` | `public` | `rollouts.manifest` | `rollouts.manifest` | `rollouts.manifest` | `already aligned` |
| `RolloutStoreManifestContext` | `DTO` | `public` | `rollouts.manifest` | `rollouts.manifest` | `rollouts.manifest` | `already aligned` |
| `utc_timestamp` | `function` | `public` | `rollouts.manifest` | `rollouts.manifest` | `rollouts.manifest` | `already aligned` |
| `manifest_json_bytes` | `function` | `public` | `rollouts.manifest` | `rollouts.manifest` | `rollouts.manifest` | `already aligned` |
| `manifest_sha256` | `function` | `public` | `rollouts.manifest` | `rollouts.manifest` | `rollouts.manifest` | `already aligned` |
| `write_rollout_store_manifest` | `function` | `public` | `rollouts.manifest` | `rollouts.manifest` | `rollouts.manifest` | `already aligned` |
| `read_rollout_store_manifest` | `function` | `public` | `rollouts.manifest` | `rollouts.manifest` | `rollouts.manifest` | `already aligned` |
| `collect_runtime_provenance` | `function` | `public` | `rollouts.manifest` | `rollouts.manifest` | `rollouts.manifest` | `already aligned` |
| `_git_root` | `function` | `private` | `rollouts.manifest` | `rollouts.manifest` | `rollouts.manifest` | `already aligned` |
| `_git_summary` | `function` | `private` | `rollouts.manifest` | `rollouts.manifest` | `rollouts.manifest` | `already aligned` |
| `_run_git` | `function` | `private` | `rollouts.manifest` | `rollouts.manifest` | `rollouts.manifest` | `already aligned` |
| `_package_versions` | `function` | `private` | `rollouts.manifest` | `rollouts.manifest` | `rollouts.manifest` | `already aligned` |

### `shard_manifest.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `ROLLOUT_SHARD_MANIFEST_VERSION` | `constant` | `public` | `rollouts.shard_manifest` | `rollouts.shard_manifest` | `rollouts.shard_manifest` | `already aligned` |
| `ROLLOUT_SHARD_SUCCESS_FILENAME` | `constant` | `public` | `rollouts.shard_manifest` | `rollouts.shard_manifest` | `rollouts.shard_manifest` | `already aligned` |
| `ROLLOUT_SHARD_OWNER_FILENAME` | `constant` | `public` | `rollouts.shard_manifest` | `rollouts.shard_manifest` | `rollouts.shard_manifest` | `already aligned` |
| `RolloutShardRow` | `DTO` | `public` | `rollouts.shard_manifest` | `rollouts.shard_manifest` | `rollouts.shard_manifest` | `already aligned` |
| `RolloutShardEntry` | `DTO` | `public` | `rollouts.shard_manifest` | `rollouts.shard_manifest` | `rollouts.shard_manifest` | `already aligned` |
| `canonical_rollout_shard_id` | `function` | `public` | `rollouts.shard_manifest` | `rollouts.shard_manifest` | `rollouts.shard_manifest` | `already aligned` |
| `write_rollout_shard_manifest` | `function` | `public` | `rollouts.shard_manifest` | `rollouts.shard_manifest` | `rollouts.shard_manifest` | `already aligned` |
| `read_rollout_shard_manifest` | `function` | `public` | `rollouts.shard_manifest` | `rollouts.shard_manifest` | `rollouts.shard_manifest` | `already aligned` |
| `load_rollout_shard_entry` | `function` | `public` | `rollouts.shard_manifest` | `rollouts.shard_manifest` | `rollouts.shard_manifest` | `already aligned` |

### `target_counterfactuals.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1` | `constant` | `public` | `rollouts.target_counterfactuals` | `rollouts.target_counterfactuals` | `oracle.target_rri` | `blocked: dependency direction` |
| `SCENE_CROP_POLICY_SNIPPET_EXTENT_V1` | `constant` | `public` | `rollouts.target_counterfactuals` | `rollouts.target_counterfactuals` | `oracle.target_rri` | `blocked: dependency direction` |
| `TargetRriInvalidError` | `class` | `public` | `rollouts.target_counterfactuals` | `rollouts.target_counterfactuals` | `oracle.target_rri` | `blocked: dependency direction` |
| `CounterfactualTargetOracleRriScorerConfig` | `config` | `public` | `rollouts.target_counterfactuals` | `rollouts.target_counterfactuals` | `oracle.target_rri` | `blocked: dependency direction` |
| `CounterfactualTargetOracleRriScorer` | `class` | `public` | `rollouts.target_counterfactuals` | `rollouts.target_counterfactuals` | `oracle.target_rri` | `blocked: dependency direction` |
| `_crop_points_to_obb` | `function` | `private` | `rollouts.target_counterfactuals` | `rollouts.target_counterfactuals` | `oracle.target_rri` | `blocked: dependency direction` |
| `_crop_padded_pointclouds_to_obb` | `function` | `private` | `rollouts.target_counterfactuals` | `rollouts.target_counterfactuals` | `oracle.target_rri` | `blocked: dependency direction` |
| `_crop_mesh_to_obb` | `function` | `private` | `rollouts.target_counterfactuals` | `rollouts.target_counterfactuals` | `oracle.target_rri` | `blocked: dependency direction` |
| `_points_inside_obb_mask` | `function` | `private` | `rollouts.target_counterfactuals` | `rollouts.target_counterfactuals` | `oracle.target_rri` | `blocked: dependency direction` |
| `_aabb_from_points` | `function` | `private` | `rollouts.target_counterfactuals` | `rollouts.target_counterfactuals` | `oracle.target_rri` | `blocked: dependency direction` |

### `trace.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `INVALID_REASON_CODES` | `constant` | `public` | `rollouts.trace` | `rollouts.trace` | `rollouts.trace` | `already aligned` |
| `INVALID_REASON_VERSION` | `constant` | `public` | `rollouts.trace` | `rollouts.trace` | `rollouts.trace` | `already aligned` |
| `_RULE_REASON_BITS` | `constant` | `private` | `rollouts.trace` | `rollouts.trace` | `rollouts.trace` | `already aligned` |
| `_HARD_DIAGNOSTIC_REASON_BITS` | `constant` | `private` | `rollouts.trace` | `rollouts.trace` | `rollouts.trace` | `already aligned` |
| `_PRIMARY_INVALID_REASON_PRIORITY` | `constant` | `private` | `rollouts.trace` | `rollouts.trace` | `rollouts.trace` | `already aligned` |
| `RolloutLineage` | `DTO` | `public` | `rollouts.trace` | `rollouts.trace` | `rollouts.trace` | `already aligned` |
| `RolloutZarrRecord` | `DTO` | `public` | `rollouts.trace` | `rollouts.trace` | `rollouts.trace` | `already aligned` |
| `_full_candidate_vector` | `function` | `private` | `rollouts.trace` | `rollouts.trace` | `rollouts.trace` | `already aligned` |
| `_full_shell_or_default` | `function` | `private` | `rollouts.trace` | `rollouts.trace` | `rollouts.trace` | `already aligned` |
| `_candidate_invalid_reasons` | `function` | `private` | `rollouts.trace` | `rollouts.trace` | `rollouts.trace` | `already aligned` |
| `_full_shell_bool_extra` | `function` | `private` | `rollouts.trace` | `rollouts.trace` | `rollouts.trace` | `already aligned` |
| `_primary_candidate_invalid_reason` | `function` | `private` | `rollouts.trace` | `rollouts.trace` | `rollouts.trace` | `already aligned` |
| `_termination_reason` | `function` | `private` | `rollouts.trace` | `rollouts.trace` | `rollouts.trace` | `already aligned` |
| `_policy_name` | `function` | `private` | `rollouts.trace` | `rollouts.trace` | `rollouts.trace` | `already aligned` |

### `zarr_store.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `ROLLOUT_ZARR_SCHEMA_ID` | `constant` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `ROLLOUT_ZARR_SCHEMA_VERSION` | `constant` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `DEFAULT_RETURN_SEMANTICS` | `constant` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `Q_H_REWARD_METRIC` | `constant` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `DEFAULT_TARGET_EVAL_CROP_MAX_POINTS` | `constant` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `SELECTED_DEPTH_INVALID_FILL_VALUE` | `constant` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `SELECTED_DEPTH_CODEC` | `constant` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `Q_H_TD_SEMANTICS` | `constant` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `Q_H_ARRAY_NAMES` | `constant` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_TableField` | `DTO` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_TableSchema` | `DTO` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `SOURCE_TABLE` | `constant` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `ROLLOUT_TABLE` | `constant` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `LINEAGE_TABLE` | `constant` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `STEP_TABLE` | `constant` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `CANDIDATE_TABLE` | `constant` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `CANDIDATE_DIAGNOSTIC_TABLE` | `constant` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `SELECTED_DEPTH_TABLE` | `constant` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `TARGET_EVAL_CROP_TABLE` | `constant` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `RolloutZarrWriteResult` | `DTO` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `RolloutZarrValidationResult` | `DTO` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_RolloutTables` | `DTO` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `RolloutZarrStoreConfig` | `config` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `RolloutZarrStoreReader` | `class` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `write_rollout_zarr_store` | `function` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_RolloutZarrWriteSession` | `class` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `validate_rollout_zarr_store` | `function` | `public` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_RolloutZarrValidator` | `class` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_required_groups` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_root_metadata_payload` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_build_manifest_payload` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_source_coverage` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_manifest_config_hashes` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_add_manifest_hash` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_records_with_global_target_row_ids` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_global_target_key` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_unique_targets` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_write_metadata_group` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_build_dictionaries` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_write_dictionaries` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_write_targets` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_target_rows_from_records` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_flatten_records` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_append_source_row` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_source_identity` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_lineage_source_row_id` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_empty_rows` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_empty_candidate_rows` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_empty_candidate_diagnostic_rows` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_empty_selected_depth_rows` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_empty_target_eval_crop_rows` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_append_target_eval_crop_rows` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_append_target_eval_crop_row` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_fixed_crop_payload` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_append_candidate_row` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_append_candidate_diagnostic_row` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_append_selected_depth_row` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_write_rollout_tables` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_write_selected_depth_group` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_write_target_eval_crops_group` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_write_q_h_group` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_build_q_h_arrays` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_table_horizon` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_rows_to_numpy_table` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_rows_to_numpy_selected_depth_table` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_rows_to_numpy_target_eval_crop_table` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_read_tables_from_root` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_read_group_table` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_read_selected_depth_table` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_read_target_eval_crop_table` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_read_q_h_arrays` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_read_q_h_arrays_if_present` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_q_h_arrays_for_validation` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_stored_horizon` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_max_candidates_per_step` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_write_array` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_write_selected_depth_array` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_write_q_h_array` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_write_string_array` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_read_string_array` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_default_chunks` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_selected_depth_chunks` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_q_h_chunks` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_q_h_arrays_differ` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_selected_depth_compressors` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_dict_id` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_record_items` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_first_temperature` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_nan_if_none` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_trajectory_cumulative_metric` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_accumulate_selected_metric` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_float_or_nan` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_fixed_float_vector` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_selected_depth_image_size` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_int_or_default` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_candidate_valid` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_compact_valid_index` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_metric_value` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_full_shell_value` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_candidate_extra_value` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_candidate_extra_bool` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_valid_vector_value` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_lineage_target_label_valid` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_relative_pose_to_root` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_missing_lineage_token` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_target_identifier_mentions_other_snippet` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_encoded_values` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
| `_read_string_array` | `function` | `private` | `rollouts.zarr_store` | `rollouts.zarr_store` | `rollouts.zarr_store` | `already aligned` |
