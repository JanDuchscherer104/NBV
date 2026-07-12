# Offline Data

`aria_nbv.data_handling.offline` owns immutable VIN offline formats, stores, datasets, writers, diagnostics, CLIs, batches, and view adapters. Package-root convenience exports remain minimal; stable compatibility is provided only by `aria_nbv.data_handling`.

## Layout

```text
data_handling/offline/
  format.py
  store.py
  dataset.py
  writer.py
  batch.py
  adapter.py
  diagnostics.py
  inventory.py
  cli.py
  info_cli.py
```

Baseline: `6b72b62639e24fc13bba845ec63bc8fc72c77aae`

Inventory generated: `2026-07-10T16:19:49.706440+00:00`

Graphify refresh: `2026-07-10T18:34:29+02:00`

## Symbol Ownership Matrix

### `__init__.py`

No top-level AST definitions; imported names and `__all__` are excluded.

### `format.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `VinOfflineBlockSpec` | `DTO` | `public` | `data_handling._offline_format` | `data_handling.offline.format` | `data_handling.offline.format` | `moved` |
| `VinOfflineShardSpec` | `DTO` | `public` | `data_handling._offline_format` | `data_handling.offline.format` | `data_handling.offline.format` | `moved` |
| `VinOfflineMaterializedBlocks` | `DTO` | `public` | `data_handling._offline_format` | `data_handling.offline.format` | `data_handling.offline.format` | `moved` |
| `VinOfflineManifest` | `DTO` | `public` | `data_handling._offline_format` | `data_handling.offline.format` | `data_handling.offline.format` | `moved` |
| `VinOfflineIndexRecord` | `DTO` | `public` | `data_handling._offline_format` | `data_handling.offline.format` | `data_handling.offline.format` | `moved` |

### `store.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `OFFLINE_DATASET_VERSION` | `constant` | `public` | `data_handling._offline_store` | `data_handling.offline.store` | `data_handling.offline.store` | `moved` |
| `VinOfflineStoreConfig` | `config` | `public` | `data_handling._offline_store` | `data_handling.offline.store` | `data_handling.offline.store` | `moved` |
| `VinOfflineShardWriter` | `DTO` | `public` | `data_handling._offline_store` | `data_handling.offline.store` | `data_handling.offline.store` | `moved` |
| `IndexedMsgpackRecordBlock` | `DTO` | `public` | `data_handling._offline_store` | `data_handling.offline.store` | `data_handling.offline.store` | `moved` |
| `OpenedShard` | `DTO` | `public` | `data_handling._offline_store` | `data_handling.offline.store` | `data_handling.offline.store` | `moved` |
| `VinOfflineStoreReader` | `class` | `public` | `data_handling._offline_store` | `data_handling.offline.store` | `data_handling.offline.store` | `moved` |

### `dataset.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `VinOfflineOracleBlock` | `DTO` | `public` | `data_handling._offline_dataset` | `data_handling.offline.dataset` | `data_handling.offline.dataset` | `moved` |
| `VinOfflineSample` | `DTO` | `public` | `data_handling._offline_dataset` | `data_handling.offline.dataset` | `data_handling.offline.dataset` | `moved` |
| `VinOfflineDatasetItem` | `constant` | `public` | `data_handling._offline_dataset` | `data_handling.offline.dataset` | `data_handling.offline.dataset` | `moved` |
| `VinOfflineDatasetConfig` | `config` | `public` | `data_handling._offline_dataset` | `data_handling.offline.dataset` | `data_handling.offline.dataset` | `moved` |
| `VinOfflineDataset` | `class` | `public` | `data_handling._offline_dataset` | `data_handling.offline.dataset` | `data_handling.offline.dataset` | `moved` |

### `writer.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `DEFAULT_BACKBONE_NUMERIC_KEEP_FIELDS` | `constant` | `public` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `DEFAULT_BACKBONE_PAYLOAD_KEEP_FIELDS` | `constant` | `public` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `_utc_now_iso` | `function` | `private` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `_json_signature` | `function` | `private` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `_split_membership_rank` | `function` | `private` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `_default_sample_key` | `function` | `private` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `_to_numpy` | `function` | `private` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `_pose_to_numpy` | `function` | `private` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `_pad_first_axis` | `function` | `private` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `_stack_numeric_rows` | `function` | `private` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `_camera_param_to_numpy` | `function` | `private` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `_wrapper_to_numpy` | `function` | `private` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `_probabilities_to_numpy` | `function` | `private` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `_validate_candidate_vector` | `function` | `private` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `_validate_candidate_first_axis` | `function` | `private` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `_validate_candidate_label_alignment` | `function` | `private` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `_semantic_names_payload` | `function` | `private` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `_keep_field` | `function` | `private` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `PreparedVinOfflineSample` | `DTO` | `public` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `prepare_vin_offline_sample` | `function` | `public` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `flush_prepared_samples_to_shard` | `function` | `public` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `_assign_splits` | `function` | `private` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `VinOfflineWriterConfig` | `config` | `public` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |
| `VinOfflineWriter` | `class` | `public` | `data_handling._offline_writer` | `data_handling.offline.writer` | `data_handling.offline.writer` | `moved` |

### `batch.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `CompactObbBlock` | `DTO` | `public` | `data_handling.vin_oracle_types` | `data_handling.offline.batch` | `data_handling.offline.batch` | `moved` |
| `CompactTrajectoryBlock` | `DTO` | `public` | `data_handling.vin_oracle_types` | `data_handling.offline.batch` | `data_handling.offline.batch` | `moved` |
| `VinOracleBatch` | `DTO` | `public` | `data_handling.vin_oracle_types` | `data_handling.offline.batch` | `data_handling.offline.batch` | `moved` |
| `VinOracleDatasetBase` | `protocol` | `public` | `data_handling.vin_oracle_types` | `data_handling.offline.batch` | `data_handling.offline.batch` | `moved` |

### `adapter.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `DEFAULT_VIN_SNIPPET_PAD_POINTS` | `constant` | `public` | `data_handling.vin_adapter` | `data_handling.offline.adapter` | `data_handling.offline.adapter` | `moved` |
| `vin_snippet_cache_config_hash` | `function` | `public` | `data_handling.vin_adapter` | `data_handling.offline.adapter` | `data_handling.offline.adapter` | `moved` |
| `collapse_vin_points` | `function` | `public` | `data_handling.vin_adapter` | `data_handling.offline.adapter` | `data_handling.offline.adapter` | `moved` |
| `pad_vin_points` | `function` | `public` | `data_handling.vin_adapter` | `data_handling.offline.adapter` | `data_handling.offline.adapter` | `moved` |
| `build_vin_snippet_view` | `function` | `public` | `data_handling.vin_adapter` | `data_handling.offline.adapter` | `data_handling.offline.adapter` | `moved` |
| `empty_vin_snippet` | `function` | `public` | `data_handling.vin_adapter` | `data_handling.offline.adapter` | `data_handling.offline.adapter` | `moved` |

### `diagnostics.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `RRI_COMPONENT_BLOCKS` | `constant` | `public` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `POSE_CAMERA_BLOCKS` | `constant` | `public` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `NumericSummary` | `DTO` | `public` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `VinOfflineMemoryDiagnostic` | `DTO` | `public` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `VinOfflineBackboneDiagnostic` | `DTO` | `public` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `VinOfflineBlockDiagnostic` | `DTO` | `public` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `VinOfflineSampleDiagnostic` | `DTO` | `public` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `VinOfflineCoverageSceneDiagnostic` | `DTO` | `public` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `VinOfflineCoverageStats` | `DTO` | `public` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `VinOfflineDatasetStats` | `DTO` | `public` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_finite_values` | `function` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_summary` | `function` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_component_key` | `function` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_collect_block_diagnostics` | `function` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_shards_by_id` | `function` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_has_record_block` | `function` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_read_valid_vector` | `function` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_normalise` | `function` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_broadcast_ref_pose` | `function` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_roll_about_forward` | `function` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_candidate_pose_values` | `function` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_component_for_memory_block` | `function` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_row_block_nbytes` | `function` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_memory_diagnostics` | `function` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_BackboneAccumulator` | `DTO` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_collect_backbone_diagnostics` | `function` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_batch_shape_preview` | `function` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `collect_vin_offline_dataset_stats` | `function` | `public` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_ARIA_SAMPLE_RE` | `constant` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_pair_from_tar_member` | `function` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_resolve_coverage_tar_paths` | `function` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_resolve_manifest_path` | `function` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `_scan_tar_pairs` | `function` | `private` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |
| `collect_vin_offline_dataset_coverage` | `function` | `public` | `data_handling._offline_diagnostics` | `data_handling.offline.diagnostics` | `data_handling.offline.diagnostics` | `moved` |

### `inventory.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `OfflineVisualInventoryError` | `class` | `public` | `data_handling._offline_visual_inventory` | `data_handling.offline.inventory` | `data_handling.offline.inventory` | `moved` |
| `OfflineVisualInventory` | `DTO` | `public` | `data_handling._offline_visual_inventory` | `data_handling.offline.inventory` | `data_handling.offline.inventory` | `moved` |
| `_missing` | `function` | `private` | `data_handling._offline_visual_inventory` | `data_handling.offline.inventory` | `data_handling.offline.inventory` | `moved` |
| `_invalid` | `function` | `private` | `data_handling._offline_visual_inventory` | `data_handling.offline.inventory` | `data_handling.offline.inventory` | `moved` |
| `_get_required` | `function` | `private` | `data_handling._offline_visual_inventory` | `data_handling.offline.inventory` | `data_handling.offline.inventory` | `moved` |
| `_as_tensor` | `function` | `private` | `data_handling._offline_visual_inventory` | `data_handling.offline.inventory` | `data_handling.offline.inventory` | `moved` |
| `_finite_prefix` | `function` | `private` | `data_handling._offline_visual_inventory` | `data_handling.offline.inventory` | `data_handling.offline.inventory` | `moved` |
| `_shape_metadata` | `function` | `private` | `data_handling._offline_visual_inventory` | `data_handling.offline.inventory` | `data_handling.offline.inventory` | `moved` |
| `_first_length` | `function` | `private` | `data_handling._offline_visual_inventory` | `data_handling.offline.inventory` | `data_handling.offline.inventory` | `moved` |
| `_validate_vin_snippet` | `function` | `private` | `data_handling._offline_visual_inventory` | `data_handling.offline.inventory` | `data_handling.offline.inventory` | `moved` |
| `_validate_pose` | `function` | `private` | `data_handling._offline_visual_inventory` | `data_handling.offline.inventory` | `data_handling.offline.inventory` | `moved` |
| `_validate_p3d_cameras` | `function` | `private` | `data_handling._offline_visual_inventory` | `data_handling.offline.inventory` | `data_handling.offline.inventory` | `moved` |
| `_candidate_count` | `function` | `private` | `data_handling._offline_visual_inventory` | `data_handling.offline.inventory` | `data_handling.offline.inventory` | `moved` |
| `_validate_oracle` | `function` | `private` | `data_handling._offline_visual_inventory` | `data_handling.offline.inventory` | `data_handling.offline.inventory` | `moved` |
| `_optional_inventory` | `function` | `private` | `data_handling._offline_visual_inventory` | `data_handling.offline.inventory` | `data_handling.offline.inventory` | `moved` |
| `_sample_metadata` | `function` | `private` | `data_handling._offline_visual_inventory` | `data_handling.offline.inventory` | `data_handling.offline.inventory` | `moved` |
| `collect_offline_visual_inventory` | `function` | `public` | `data_handling._offline_visual_inventory` | `data_handling.offline.inventory` | `data_handling.offline.inventory` | `moved` |

### `cli.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `_HELP_SETTINGS` | `constant` | `private` | `data_handling.offline_cli` | `data_handling.offline.cli` | `data_handling.offline.cli` | `moved` |
| `app` | `constant` | `public` | `data_handling.offline_cli` | `data_handling.offline.cli` | `data_handling.offline.cli` | `moved` |
| `main` | `function` | `public` | `data_handling.offline_cli` | `data_handling.offline.cli` | `data_handling.offline.cli` | `moved` |
| `build_offline_command` | `function` | `public` | `data_handling.offline_cli` | `data_handling.offline.cli` | `data_handling.offline.cli` | `moved` |

### `info_cli.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `Split` | `enum` | `public` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `_SPLITS` | `constant` | `private` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `_HELP_SETTINGS` | `constant` | `private` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `StoreOption` | `constant` | `public` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `JsonOption` | `constant` | `public` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `app` | `constant` | `public` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `main` | `function` | `public` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `_normalize_default_summary` | `function` | `private` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `summary_command` | `function` | `public` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `tree_command` | `function` | `public` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `samples_command` | `function` | `public` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `random_index_command` | `function` | `public` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `_print_or_json` | `function` | `private` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `_summary_payload` | `function` | `private` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `_tree_payload` | `function` | `private` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `_samples_payload` | `function` | `private` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `_random_index_payload` | `function` | `private` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `_sample_row` | `function` | `private` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `_path_entry` | `function` | `private` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `_shard_payload` | `function` | `private` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `_block_payload` | `function` | `private` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `_numeric_summary` | `function` | `private` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `_bytes_to_mib` | `function` | `private` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `_print_summary` | `function` | `private` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `_print_tree` | `function` | `private` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `_print_samples` | `function` | `private` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |
| `_dict_rows` | `function` | `private` | `data_handling.offline_info_cli` | `data_handling.offline.info_cli` | `data_handling.offline.info_cli` | `moved` |

### `source.py`

| Symbol | Kind | Visibility | Before module | Current module | Final owner | Status |
|---|---|---|---|---|---|---|
| `VinOfflineSourceConfig` | config | public | `data_handling._vin_sources` | `data_handling.offline.source` | `data_handling.offline.source` | moved: RWP03A |
