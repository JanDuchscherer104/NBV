# Oracle Pipelines

`aria_nbv.oracle.pipelines` owns operational Oracle-label generation and the
composition of immutable VIN and rollout datasets. The package marker provides
no convenience exports.

## Layout

```text
oracle/pipelines/
  evaluated_rollout.py
  offline_vin.py
  online_vin.py
  rollout_dataset.py
  scene_labels.py
  shards.py
  cli.py
```

Baseline: `6b72b62639e24fc13bba845ec63bc8fc72c77aae`

Inventory generated: `2026-07-10T16:10:28.231382+00:00`

Graphify refresh: `2026-07-11T20:46:10+02:00`

## Symbol Ownership Matrix

### `__init__.py`

No top-level AST definitions; imported names and `__all__` are excluded.

### `evaluated_rollout.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `OracleInvalidity` | protocol | public | implicit exception contract | `oracle.pipelines.evaluated_rollout` | `oracle.pipelines.evaluated_rollout` | moved |
| `OracleCandidateScorer` | protocol | public | replay evaluator callable | `oracle.pipelines.evaluated_rollout` | `oracle.pipelines.evaluated_rollout` | moved |
| `EvaluatedRolloutStep` | DTO | public | wide replay step | `oracle.pipelines.evaluated_rollout` | `oracle.pipelines.evaluated_rollout` | moved |
| `EvaluatedRollout` | DTO | public | wide replay result | `oracle.pipelines.evaluated_rollout` | `oracle.pipelines.evaluated_rollout` | moved |
| `EvaluatedRolloutRecord` | DTO | public | `rollouts.trace.RolloutZarrRecord` | `oracle.pipelines.evaluated_rollout` | `oracle.pipelines.evaluated_rollout` | moved |
| `OracleReplayAdapter` | class | public | writer-local target adapter | `oracle.pipelines.evaluated_rollout` | `oracle.pipelines.evaluated_rollout` | moved |
| `OracleReplayInvalidityError` | exception | public | writer-local exception | `oracle.pipelines.evaluated_rollout` | `oracle.pipelines.evaluated_rollout` | moved |
| `_PipelineOracleState` | DTO | private | replay trajectory Oracle state | `oracle.pipelines.evaluated_rollout` | `oracle.pipelines.evaluated_rollout` | moved |

### `rollout_dataset.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `RolloutDatasetWriterStats` | `DTO` | `public` | `rollouts.dataset_writer` | `oracle.pipelines.rollout_dataset` | `oracle.pipelines.rollout_dataset` | `moved` |
| `RolloutRecipeConfig` | `config` | `public` | `rollouts.dataset_writer` | `oracle.pipelines.rollout_dataset` | `oracle.pipelines.rollout_dataset` | `moved` |
| `SelectedDepthRetentionConfig` | `config` | `public` | `rollouts.dataset_writer` | `oracle.pipelines.rollout_dataset` | `oracle.pipelines.rollout_dataset` | `moved` |
| `RolloutDatasetWriterConfig` | `config` | `public` | `rollouts.dataset_writer` | `oracle.pipelines.rollout_dataset` | `oracle.pipelines.rollout_dataset` | `moved` |
| `_RolloutSourceLineageBuilder` | `DTO` | `private` | `rollouts.dataset_writer` | `oracle.pipelines.rollout_dataset` | `oracle.pipelines.rollout_dataset` | `moved` |
| `_RolloutTargetSelectionResult` | `DTO` | `private` | `rollouts.dataset_writer` | `oracle.pipelines.rollout_dataset` | `oracle.pipelines.rollout_dataset` | `moved` |
| `_SplitRecord` | `protocol` | `private` | untyped lineage helper input | `oracle.pipelines.rollout_dataset` | `oracle.pipelines.rollout_dataset` | `moved` |
| `RolloutDatasetWriter` | `class` | `public` | `rollouts.dataset_writer` | `oracle.pipelines.rollout_dataset` | `oracle.pipelines.rollout_dataset` | `moved` |
| `_lineage_split` | `function` | `private` | `rollouts.dataset_writer` | `oracle.pipelines.rollout_dataset` | `oracle.pipelines.rollout_dataset` | `moved` |

### `offline_vin.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `VinOfflineWriterConfig` | `config` | `public leaf` | `data_handling.offline.writer` | `oracle.pipelines.offline_vin` | `oracle.pipelines.offline_vin` | `moved` |
| `VinOfflineWriter` | `class` | `public leaf` | `data_handling.offline.writer` | `oracle.pipelines.offline_vin` | `oracle.pipelines.offline_vin` | `moved` |

### `scene_labels.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `OracleRriSample` | `DTO` | `public leaf` | `pipelines.oracle_rri_labeler` | `oracle.pipelines.scene_labels` | `oracle.pipelines.scene_labels` | `moved` |
| `_target_cls` | `function` | `private` | `pipelines.oracle_rri_labeler` | `oracle.pipelines.scene_labels` | `oracle.pipelines.scene_labels` | `moved` |
| `OracleRriLabelerConfig` | `config` | `public leaf` | `pipelines.oracle_rri_labeler` | `oracle.pipelines.scene_labels` | `oracle.pipelines.scene_labels` | `moved` |
| `OracleRriLabeler` | `class` | `public leaf` | `pipelines.oracle_rri_labeler` | `oracle.pipelines.scene_labels` | `oracle.pipelines.scene_labels` | `moved` |

### `shards.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `RolloutShardRunResult` | `DTO` | `public` | `rollouts.shards` | `oracle.pipelines.shards` | `oracle.pipelines.shards` | `moved` |
| `RolloutShardStatus` | `DTO` | `public` | `rollouts.shards` | `oracle.pipelines.shards` | `oracle.pipelines.shards` | `moved` |
| `RolloutShardCampaignStatus` | `DTO` | `public` | `rollouts.shards` | `oracle.pipelines.shards` | `oracle.pipelines.shards` | `moved` |
| `plan_rollout_shards` | `function` | `public` | `rollouts.shards` | `oracle.pipelines.shards` | `oracle.pipelines.shards` | `moved` |
| `write_rollout_shard_manifest_from_config` | `function` | `public` | `rollouts.shards` | `oracle.pipelines.shards` | `oracle.pipelines.shards` | `moved` |
| `summarize_rollout_shard_campaign` | `function` | `public` | `rollouts.shards` | `oracle.pipelines.shards` | `oracle.pipelines.shards` | `moved` |
| `run_rollout_shard` | `function` | `public` | `rollouts.shards` | `oracle.pipelines.shards` | `oracle.pipelines.shards` | `moved` |
| `_summarize_rollout_shard_entry` | `function` | `private` | `rollouts.shards` | `oracle.pipelines.shards` | `oracle.pipelines.shards` | `moved` |
| `_records_by_split` | `function` | `private` | `rollouts.shards` | `oracle.pipelines.shards` | `oracle.pipelines.shards` | `moved` |
| `_chunks` | `function` | `private` | `rollouts.shards` | `oracle.pipelines.shards` | `oracle.pipelines.shards` | `moved` |
| `_completed_shard_is_current` | `function` | `private` | `rollouts.shards` | `oracle.pipelines.shards` | `oracle.pipelines.shards` | `moved` |
| `_owner_payload` | `function` | `private` | `rollouts.shards` | `oracle.pipelines.shards` | `oracle.pipelines.shards` | `moved` |
| `_success_payload` | `function` | `private` | `rollouts.shards` | `oracle.pipelines.shards` | `oracle.pipelines.shards` | `moved` |
| `_write_failed_marker` | `function` | `private` | `rollouts.shards` | `oracle.pipelines.shards` | `oracle.pipelines.shards` | `moved` |
| `_write_json_atomic` | `function` | `private` | `rollouts.shards` | `oracle.pipelines.shards` | `oracle.pipelines.shards` | `moved` |

### `cli.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `_HELP_SETTINGS` | `constant` | `private` | `rollouts.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `build_app` | `constant` | `public` | `rollouts.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `offline_app` | `constant` | `public leaf` | `data_handling.offline.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `plan_app` | `constant` | `public` | `rollouts.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `status_app` | `constant` | `public` | `rollouts.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `main` | `function` | `public` | `rollouts.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `offline_main` | `function` | `public leaf` | `data_handling.offline.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `plan_main` | `function` | `public` | `rollouts.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `status_main` | `function` | `public` | `rollouts.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `build_rollouts_command` | `function` | `public` | `rollouts.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `build_offline_command` | `function` | `public leaf` | `data_handling.offline.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `plan_rollout_shards_command` | `function` | `public` | `rollouts.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `status_rollout_shards_command` | `function` | `public` | `rollouts.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `_raw_argv` | `function` | `private` | `rollouts.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
