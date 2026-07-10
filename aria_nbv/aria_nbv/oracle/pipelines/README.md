# Oracle Pipelines

`aria_nbv.oracle.pipelines` owns operational label and rollout-dataset generation. The public package markers intentionally provide no convenience exports.

## Layout

```text
oracle/pipelines/
  rollout_dataset.py
  shards.py
  cli.py
```

Baseline: `6b72b62639e24fc13bba845ec63bc8fc72c77aae`

Inventory generated: `2026-07-10T16:10:28.231382+00:00`

Graphify refresh: `2026-07-10T16:10:28.231382+00:00`

## Symbol Ownership Matrix

### `__init__.py`

No top-level AST definitions; imported names and `__all__` are excluded.

### `rollout_dataset.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `RolloutDatasetWriterStats` | `DTO` | `public` | `rollouts.dataset_writer` | `oracle.pipelines.rollout_dataset` | `oracle.pipelines.rollout_dataset` | `moved` |
| `RolloutRecipeConfig` | `config` | `public` | `rollouts.dataset_writer` | `oracle.pipelines.rollout_dataset` | `oracle.pipelines.rollout_dataset` | `moved` |
| `SelectedDepthRetentionConfig` | `config` | `public` | `rollouts.dataset_writer` | `oracle.pipelines.rollout_dataset` | `oracle.pipelines.rollout_dataset` | `moved` |
| `RolloutTargetSource` | `enum` | `public` | `rollouts.dataset_writer` | `oracle.pipelines.rollout_dataset` | `oracle.pipelines.rollout_dataset` | `moved` |
| `RolloutDatasetWriterConfig` | `config` | `public` | `rollouts.dataset_writer` | `oracle.pipelines.rollout_dataset` | `oracle.pipelines.rollout_dataset` | `moved` |
| `_RolloutSourceLineageBuilder` | `DTO` | `private` | `rollouts.dataset_writer` | `oracle.pipelines.rollout_dataset` | `oracle.pipelines.rollout_dataset` | `moved` |
| `_RolloutTargetSelectionResult` | `DTO` | `private` | `rollouts.dataset_writer` | `oracle.pipelines.rollout_dataset` | `oracle.pipelines.rollout_dataset` | `moved` |
| `RolloutDatasetWriter` | `class` | `public` | `rollouts.dataset_writer` | `oracle.pipelines.rollout_dataset` | `oracle.pipelines.rollout_dataset` | `moved` |
| `_lineage_split` | `function` | `private` | `rollouts.dataset_writer` | `oracle.pipelines.rollout_dataset` | `oracle.pipelines.rollout_dataset` | `moved` |
| `_oracle_target_task_to_candidate_row` | `function` | `private` | `rollouts.dataset_writer` | `oracle.pipelines.rollout_dataset` | `oracle.pipelines.rollout_dataset` | `moved` |
| `_oracle_target_invalidity` | `function` | `private` | `rollouts.dataset_writer` | `oracle.pipelines.rollout_dataset` | `oracle.pipelines.rollout_dataset` | `moved` |

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
| `load_rollout_shard_entry_for_cli` | `function` | `public` | `rollouts.shards` | `oracle.pipelines.shards` | `oracle.pipelines.shards` | `moved` |
| `load_rollout_shard_manifest_for_status` | `function` | `public` | `rollouts.shards` | `oracle.pipelines.shards` | `oracle.pipelines.shards` | `moved` |
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
| `plan_app` | `constant` | `public` | `rollouts.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `status_app` | `constant` | `public` | `rollouts.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `main` | `function` | `public` | `rollouts.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `plan_main` | `function` | `public` | `rollouts.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `status_main` | `function` | `public` | `rollouts.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `build_rollouts_command` | `function` | `public` | `rollouts.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `plan_rollout_shards_command` | `function` | `public` | `rollouts.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `status_rollout_shards_command` | `function` | `public` | `rollouts.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
| `_raw_argv` | `function` | `private` | `rollouts.cli` | `oracle.pipelines.cli` | `oracle.pipelines.cli` | `moved` |
