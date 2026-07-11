# Oracle

`aria_nbv.oracle` owns privileged target-task preparation, evidence resolution,
scene/target RRI scoring, and label-generation pipelines. It may consume GT
geometry and raw/offline data, but final scorer modules must not import rollout
replay or persistence contracts.

## Current Layout

```text
oracle/
  __init__.py
  evidence.py
  target_selection.py
  pipelines/
```

WP07 establishes target-task ownership. WP08-WP09 add scene and target scorer
facades plus their shared private scoring engine. Pipeline relocation remains
WP12.

Baseline: `4daf9d4`

Graphify refresh: `2026-07-11`

## Symbol Ownership Matrix

### `__init__.py`

No top-level AST definitions; imported names and `__all__` are excluded.

### `evidence.py`

| Symbol | Kind | Visibility | Before module | Current module | Final owner | Status |
|---|---|---|---|---|---|---|
| `target_gt_obb_world` | function | public | `data_handling._target_selection` | `oracle.evidence` | `oracle.evidence` | moved |

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
