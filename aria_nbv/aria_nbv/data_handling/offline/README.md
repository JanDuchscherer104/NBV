# Offline Data

`aria_nbv.data_handling.offline` owns immutable VIN offline formats, stores, datasets, writers, batches, and view adapters. Package-root convenience exports remain minimal; stable compatibility is provided only by `aria_nbv.data_handling`.

## Layout

```text
data_handling/offline/
  format.py
  store.py
  dataset.py
  writer.py
  batch.py
  adapter.py
```

Baseline: `6b72b62639e24fc13bba845ec63bc8fc72c77aae`

Inventory generated: `2026-07-10T16:16:03.131034+00:00`

Graphify refresh: `2026-07-10T16:16:03.131034+00:00`

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
