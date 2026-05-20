# Rollout Zarr, Q_H, And Invalidity Contract

This is the internal implementation contract for future ARIA-NBV rollout and
Q_H dataset writers. It is a draft schema only. Do not treat it as evidence
that writers, migrations, stochastic rollout generation, Q_H training, LRZ
templates, or CI exist.

Public-facing implementation context lives in generated API docs under
`docs/reference/` and the rollout modules themselves. This reference is allowed
to be more mechanical because it is an internal developer contract.

## Scope

The store must support:

- replayable bounded rollout chains from ASE mesh/oracle counterfactuals;
- target-conditioned scene and target RRI labels;
- full-shell candidate ordering with stable row ids;
- hard validity masks and explicit reason codes;
- optional selected-action or retained-chain diagnostics;
- external full-mesh references and embedded target crops;
- padded finite-candidate Q_H tensor views for training/evaluation.

The store must not:

- duplicate full ASE meshes;
- encode invalid candidates as low RRI;
- expose GT mesh, GT OBB crops, or oracle labels as actor-visible V1 inputs;
- require heavy diagnostics for training;
- hide mixed lineage behind a single manifest.

## Root Metadata

Root attributes:

| Field | Required | Notes |
|---|---:|---|
| `schema_id` | yes | Suggested value: `aria_nbv.rollout_zarr_q_invalidity`. |
| `schema_version` | yes | Start as `0.1-draft`; bump for incompatible changes. |
| `zarr_format` | yes | Intended Zarr major format. |
| `zarr_core_spec` | yes | Zarr core spec URI or version label used by the writer. |
| `created_at_utc` | yes | ISO timestamp. |
| `aria_nbv_git_revision` | yes | Commit or source-tree digest. |
| `source_offline_store_version` | yes | VIN/offline-store version used as input. |
| `split_manifest_hash` | yes | Scene-level split contract. |
| `reason_code_version` | yes | Invalidity dictionary version. |
| `target_protocol_version` | yes | V0/V1 target contract version. |
| `return_semantics` | yes | Default: `cumulative_target_root_gain`. |
| `field_retention_policy` | yes | Example: `compact`, `selected_heavy`, or `audit`. |
| `selected_depth_enabled` | yes | True when one selected-action depth row is required for every step. |
| `selected_depth_width_px`, `selected_depth_height_px` | when enabled | Persisted selected-action raster size; default `240 x 240`. |
| `selected_depth_dtype`, `selected_depth_valid_mask_dtype` | when enabled | Default `float16` depth and `bool` mask. |
| `selected_depth_units` | when enabled | Metric metres. |
| `selected_depth_invalid_fill_value` | when enabled | Default `0.0`; valid pixels are defined by the separate mask. |
| `selected_depth_codec` | when enabled | Default `blosc:zstd:clevel=5:bitshuffle`. |
| `selected_depth_chunk_steps` | when enabled | Default first chunk dimension, currently `16`. |
| `selected_depth_role` | when enabled | Default `selected_successor_state_history`; not an oracle-label semantic. |
| `selected_depth_renderer`, `selected_depth_znear_m`, `selected_depth_zfar_m` | when enabled | Renderer identity and depth clip planes. |
| `selected_depth_source_resolution` | when enabled | Default `exact_output_size`; selected-depth output is rendered directly at persisted size. |

Variable-length strings can be dictionary encoded. A future writer may use
Zarr string dtypes where appropriate, but row linkage should not depend on
string array behavior.

## Group Layout

```text
rollouts.zarr/
  metadata/
    generation_manifest
    reason_codes
    field_retention_policy
  dictionaries/
    scene
    snippet
    rollout
    target
    policy
    config
    class_name
  splits/
    scene_split
    rollout_split
  lineage/
    rollout_index
    config_hashes
  mesh_refs/
    scene_mesh_index
  targets/
    target_index
    crop_vertices
    crop_vertex_offsets
    crop_faces
    crop_face_offsets
  rollouts/
    rollout_index
  steps/
    step_index
    reason_histogram
  candidates/
    candidate_index
    candidate_pose_world_cam
    candidate_pose_relative
    metric_vectors
    position_id
  candidate_diagnostics/
    candidate_row_id
    position_id
    mesh_distance_m
    path_min_clearance_m
    path_collision_mask
    free_space_margin_m
    motion_step_length_m
    motion_height_delta_m
    motion_backward_step_m
    motion_yaw_delta_deg
    target_distance_m
    target_bearing_yaw_deg
  selected_depth/
    step_row_id
    candidate_row_id
    depth_m
    valid_mask
    focal_px
    principal_point_px
    image_size_hw
  target_eval_crops/        # optional sampled/audit payload; empty in lean stores
    crop_row_id
    step_row_id
    candidate_row_id
    source_role_id
    points_world
    lengths
    mask
  q_h/
    state_step_row_id
    source_row_id
    candidate_row_id
    valid_action_mask
    q_train_mask
    target_row_id
    invalid_reason_bitset
    one_step_target_rri
    one_step_target_root_gain
    selected_candidate_index
    td_selected_candidate_row_id
    td_reward
    td_reward_target_rri
    td_next_step_row_id
    td_terminal_mask
    td_discount
  diagnostics/
    depth
    depth_valid_mask
    face_index
    point_cloud
    point_cloud_offsets
    collision_segments
    rerun_artifact_index
```

`diagnostics/` groups are optional. Required table groups should exist even if
some optional columns are all unavailable.

## Row Identity

Use signed 64-bit row ids unless a future implementation proves a smaller type
is sufficient:

- `target_row_id`: one target record for one scene/snippet target protocol.
- `rollout_row_id`: one rollout chain for one root state and target.
- `step_row_id`: one horizon step within a rollout chain.
- `candidate_row_id`: one candidate from the full sampled shell at one step.

Rows should be append-only within a shard. Joins must use row ids, not implicit
array order alone. Candidate full-shell order is represented by
`shell_index` within each `step_row_id`.

## Target Records

`targets/target_index` columns:

| Column | Shape or type | Notes |
|---|---|---|
| `target_row_id` | `[T] int64` | Primary key. |
| `scene_id`, `snippet_id` | `[T] dict/int` | Source identity. |
| `target_id` | `[T] dict/int` | Stable within snippet where available. |
| `target_protocol_version` | `[T] dict/int` | Separates V0 and V1. |
| `actor_visible_source` | `[T] enum/int` | `gt_obb`, `pred_obb`, `tracked_obb`, etc. |
| `class_id`, `class_name` | `[T] int/dict` | Actor-visible class prediction or GT for V0 only. |
| `confidence` | `[T] float32` | Actor-visible confidence. |
| `observed_obb_world` | `[T, O] float32` | OBB fields with frame/parameterization attrs. |
| `observed_support` | `[T, K] float32` | Semidense/EVL/projected-area support summary. |
| `matched_gt_target_id` | `[T] dict/int` | GT target id for evaluation. |
| `gt_obb_world` | `[T, O] float32` | Oracle/evaluation only. |
| `match_iou`, `match_score` | `[T] float32` | Matching diagnostics. |
| `target_valid_mask` | `[T] bool` | True if target can be used for the protocol. |
| `target_invalid_reason_bitset` | `[T] uint32` | Reason bitset. |
| `primary_invalid_reason` | `[T] uint16` | Dominant reason for reporting. |
| `target_crop_row_id` | `[T] int64` | Links to ragged crop arrays. |

Target crop ragged arrays:

- `crop_vertices`: `[sum_vertices, 3] float32`, world frame;
- `crop_vertex_offsets`: `[num_crops + 1] int64`;
- `crop_faces`: `[sum_faces, 3] int32`, local to the crop vertex span;
- `crop_face_offsets`: `[num_crops + 1] int64`.

Crop attributes must record source mesh hash, crop bounds, margin, face
retention rule, unit convention, and coordinate frame.

## Mesh References

`mesh_refs/scene_mesh_index` columns:

| Column | Notes |
|---|---|
| `scene_id` | Scene dictionary id. |
| `mesh_role` | `ase_gt_full`, `scene_crop`, `diagnostic_decimated`, etc. |
| `mesh_uri` | External path or URI under configured data roots. |
| `mesh_sha256` | Content digest. |
| `mesh_version` | Source or preprocessing version. |
| `coordinate_frame` | Frame name, usually world. |
| `unit_m` | Unit scale in meters. |
| `bounds_world` | Optional AABB. |
| `vertex_count`, `face_count` | Counts for sanity and budget reports. |
| `preprocess_hash` | Hash of crop/simplification config, if derived. |

Full scene meshes remain external. Only target crops may be embedded once per
target.

## Rollout And Step Tables

`rollouts/rollout_index` columns:

- `rollout_row_id`, `rollout_id`, `chain_id`;
- `scene_id`, `snippet_id`, `target_row_id`, `split`;
- `root_pose_world_rig`, `root_pose_world_cam` when defined;
- `horizon`, `branch_factor`, `beam_width`, `candidate_count_budget`;
- `policy_id`, `branch_schedule_id`, `temperature`, `random_seed`;
- `candidate_config_hash`, `oracle_config_hash`, `rollout_config_hash`;
- `model_checkpoint_hash` when learned scores are used;
- `termination_reason`;
- `final_cumulative_target_root_gain`, `final_cumulative_scene_root_gain`;
- `final_cumulative_target_rri`, `final_cumulative_scene_rri` diagnostics;
- `path_length_m`, `view_count`, `invalid_action_rate`, `runtime_ms`.

`steps/step_index` columns:

- `step_row_id`, `rollout_row_id`, `step_index`;
- `current_pose_world_rig`, `current_pose_world_cam` where defined;
- `selected_candidate_row_id`, `selected_shell_index`,
  `selected_compact_valid_index`;
- `num_candidates`, `num_valid_candidates`;
- `cumulative_target_root_gain`, `cumulative_scene_root_gain`;
- `cumulative_target_rri`, `cumulative_scene_rri`, `path_length_m` diagnostics;
- `step_runtime_ms`;
- `reason_histogram_offset` for compact per-step invalidity summaries.

## Selected-Action Depth

`selected_depth/` is the durable selected-view observation table for the first
`Q_H`/history-encoder path. It is separate from oracle transition labels:
all-candidate RRI scoring continues to use the low-resolution render path
configured under `target_scorer.depth`, while only materialized selected
actions are re-rendered at the selected-depth resolution.

Required arrays when `selected_depth_enabled=true`:

| Array | Shape | Dtype | Notes |
|---|---|---|---|
| `step_row_id` | `[D]` | `int64` | Must equal `steps/step_row_id`; one row per step. |
| `candidate_row_id` | `[D]` | `int64` | Must align with `steps/selected_candidate_row_id`. |
| `depth_m` | `[D, H, W]` | `float16` | Metric metres; invalid pixels filled with `0.0`. |
| `valid_mask` | `[D, H, W]` | `bool` | True exactly where `depth_m` is valid. |
| `focal_px` | `[D, 2]` | `float32` | Selected-depth camera focal lengths in pixels. |
| `principal_point_px` | `[D, 2]` | `float32` | Selected-depth principal point in pixels. |
| `image_size_hw` | `[D, 2]` | `int32` | Persisted height and width. |

Default retention is `240 x 240`, `float16` depth, `bool` mask, metric metres,
Zarr v3 Blosc/Zstd level 5 with bitshuffle, and chunks
`(16, 240, 240)`. `224 x 224` is a training-reader resize option, not the
persisted artifact. Store/group metadata records the renderer, clip planes,
source-resolution policy, units, invalid-fill value, and codec; row metadata
records selected camera intrinsics. Selected-depth metadata must not be folded
into target-RRI labels or invalidity reasons.

## Candidate Table

`candidates/candidate_index` columns:

| Column | Shape or type | Notes |
|---|---|---|
| `candidate_row_id` | `[N] int64` | Primary key. |
| `step_row_id` | `[N] int64` | Parent state. |
| `rollout_row_id` | `[N] int64` | Redundant join accelerator. |
| `step_index` | `[N] int16` | Horizon index. |
| `shell_index` | `[N] int16/int32` | Full sampled shell order. |
| `compact_valid_index` | `[N] int16/int32` | `-1` for invalid candidates. |
| `pose_world_cam` | `[N, 12] float32` | Match `PoseTW.tensor()` convention if used. |
| `pose_relative_root` | `[N, R] float32` | Candidate-relative encoding attrs required. |
| `strategy_id` | `[N] enum/int` | Candidate source strategy. |
| `mixture_id` | `[N] enum/int` | Sampler mixture component. |
| `sampler_probability` | `[N] float32` | Optional proposal probability. |
| `actor_action_mask` | `[N] bool` | Canonical persisted action-feasibility mask; actor-selectable. |
| `oracle_label_mask` | `[N] bool` | Oracle label exists and is valid. |
| `q_train_mask` | `[N] bool` | Usable for configured Q_H target. |
| `selected_mask` | `[N] bool` | Selected at this step. |
| `invalid_reason_bitset` | `[N] uint32` | Versioned reason bitset. |
| `primary_invalid_reason` | `[N] uint16` | Reporting reason. |
| `target_root_gain`, `scene_root_gain` | `[N] float32` | Root-normalized reward fields; NaN when masked. |
| `scene_rri`, `target_rri` | `[N] float32` | State-relative diagnostics; NaN when masked. |
| `target_log_error_gain`, `scene_log_error_gain` | `[N] float32` | Optional diagnostics. |
| `target_pm_dist_before`, `target_pm_dist_after` | `[N] float32` | Point-mesh audit fields. |
| `accuracy_delta`, `completeness_delta` | `[N] float32` | Optional oracle components. |
| `target_visible_fraction` | `[N] float32` | Protocol-defined visibility. |
| `oracle_rank`, `model_rank` | `[N] int16/int32` | `-1` when unavailable. |
| `one_step_model_score` | `[N] float32` | Optional learned score. |
| `model_uncertainty` | `[N] float32` | Optional calibration field. |

Full-shell candidate rows remain present for invalid candidates. The masks
define action/training eligibility.

## Invalidity Reason Codes

Reason codes are bit positions stored as `uint32` bitsets. Bit 0 is reserved
for the all-clear value and is not combined with failures.

| Bit | Code |
|---:|---|
| 0 | `VALID` |
| 1 | `POSE_NONFINITE` |
| 2 | `POSE_OUT_OF_EXTENT` |
| 3 | `CAMERA_OUT_OF_EXTENT` |
| 4 | `COLLISION_MESH` |
| 5 | `CLEARANCE_TOO_SMALL` |
| 6 | `PATH_SEGMENT_COLLISION` |
| 7 | `FRUSTUM_OUT_OF_BOUNDS` |
| 8 | `DEPTH_NO_HIT` |
| 9 | `DEPTH_TOO_SPARSE` |
| 10 | `BACKPROJECT_EMPTY` |
| 11 | `CANDIDATE_DUPLICATE` |
| 12 | `SAMPLER_RULE_REJECTED` |
| 13 | `TARGET_NOT_ACTOR_VISIBLE` |
| 14 | `TARGET_GT_UNMATCHED` |
| 15 | `TARGET_CROP_EMPTY` |
| 16 | `TARGET_SUPPORT_TOO_LOW` |
| 17 | `TARGET_VISIBILITY_TOO_LOW` |
| 18 | `SEMIDENSE_SUPPORT_TOO_LOW` |
| 19 | `EVL_EVIDENCE_MISSING` |
| 20 | `MESH_REFERENCE_MISSING` |
| 21 | `ORACLE_DISTANCE_FAILED` |
| 22 | `CANDIDATE_ORDER_GUARD_FAILED` |
| 23 | `RUNTIME_ERROR` |

Append new codes only at the end. Never reuse a meaning within a schema
version family.

## Mask Semantics

Use these masks consistently:

- `actor_action_mask`: the canonical persisted action-feasibility mask. The
  actor or one-step scorer may select the action using actor-visible state
  only when this mask is true.
- `oracle_label_mask`: oracle target-root-gain reward exists and is valid.
- `q_train_mask`: the row is usable for the configured Q_H target tensor.
- `target_valid_mask`: target record is usable under the protocol.

For the first Q_H dataset, `q_train_mask` should require actor-selectability,
valid oracle target-root gain, finite diagnostic target RRI, and valid target
record. Dense `q_h/` padding is derived from `candidate_row_id == -1` plus
false masks, not persisted in the candidate table.

## Q_H Tensor View

`q_h/` is a dense padded tensor view persisted as a derived training-hot cache.
The columnar candidate/step/rollout tables are still the source of truth, and
validation must reject a store when persisted `q_h/` arrays diverge from those
factual tables.

Recommended tensor shapes:

| Array | Shape | Dtype | Fill |
|---|---|---|---|
| `state_step_row_id` | `[S]` | `int64` | none |
| `source_row_id` | `[S]` | `int64` | none |
| `candidate_row_id` | `[S, C_max]` | `int64` | `-1` |
| `valid_action_mask` | `[S, C_max]` | `bool` | `false` |
| `q_train_mask` | `[S, C_max]` | `bool` | `false` |
| `invalid_reason_bitset` | `[S, C_max]` | `uint32` | `0` for padded plus `valid_action_mask=false` |
| `target_row_id` | `[S]` | `int64` | none |
| `selected_candidate_index` | `[S]` | `int16/int32` | `-1` |
| `one_step_target_rri` | `[S, C_max]` | `float32` | `NaN` |
| `one_step_target_root_gain` | `[S, C_max]` | `float32` | `NaN` |
| `td_selected_candidate_row_id` | `[S]` | `int64` | `-1` |
| `td_reward` | `[S]` | `float32` | `NaN` |
| `td_reward_target_rri` | `[S]` | `float32` | `NaN` |
| `td_next_step_row_id` | `[S]` | `int64` | `-1` |
| `td_terminal_mask` | `[S]` | `bool` | `true` |
| `td_discount` | `[S]` | `float32` | configured gamma |

Multi-step target tensors such as `q_target_target_rri[S,H,C]` are future
derived views, not part of the current schema
`1.0-target-rollout-core` writer.

Array attributes must record:

- `td_semantics="selected_transition_only"`;
- `reward_metric="target_root_gain"`;
- `return_semantics="cumulative_target_root_gain"`;
- `discount_gamma`;
- target RRI semantics as state-relative diagnostics;
- target protocol version;
- split protocol and scene-level split hash;
- whether scalar motion/rule penalties are absent or included.

Initial Q_H targets should be pure bounded cumulative target-root gain. Scalar
motion, rule, and invalidity penalties are separate ablations and require a
different `return_semantics` attribute.

## Optional Heavy Diagnostics

Heavy diagnostics may be materialized for selected actions, retained chains, or
audit samples:

- high-resolution selected-action depth is canonical under `selected_depth/`;
- `diagnostics/depth`: rendered depth, ragged or padded by image shape;
- `diagnostics/depth_valid_mask`;
- `diagnostics/face_index`;
- `diagnostics/point_cloud` plus offsets;
- target-cropped current/candidate point clouds;
- collision segments and clearance samples;
- Rerun artifact URI/index rows.

Heavy diagnostics must have availability masks and row backlinks. Missing
optional diagnostics must not change training masks unless the protocol
declares them required.

## Rejection Rules

Reject a store or shard for Q_H training when:

- schema id/version is unknown;
- reason-code version is unknown;
- split manifest hash is missing or incompatible;
- candidate row ids do not align with Q_H `candidate_row_id` backlinks;
- any selected action has `actor_action_mask=false`;
- invalid candidates have finite Q targets without an explicit ablation
  return-semantic;
- target records lack valid matched GT evaluation where the protocol requires
  target RRI;
- full meshes are embedded instead of externally referenced;
- target crops are duplicated per candidate instead of once per target;
- mixed code/config/checkpoint hashes are not separated by lineage.
