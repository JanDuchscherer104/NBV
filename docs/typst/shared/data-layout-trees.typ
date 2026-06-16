// Reusable tdtr tree figures for ARIA-NBV data-store layouts.
//
// These helpers render stable schema-level trees for Markdown and Typst
// inclusion. They intentionally do not inspect local Zarr payloads.

#import "@preview/tdtr:0.5.5": *
#import "symbols.typ": symb

#let data_color = rgb("F5F5F5")
#let group_color = rgb("E8F3FF")
#let leaf_color = rgb("F4F6FB")
#let array_color = rgb("EAF7EA")
#let derived_color = rgb("FCE8E8")
#let text_muted = rgb("64748B")

#let group = metadata("group")
#let leaf = metadata("leaf")
#let array_node = metadata("array")
#let derived = metadata("derived")

#let code(name) = raw(name, lang: none)
#let code-strong(name) = text(weight: "bold")[#code(name)]
#let dim(body) = text(fill: text_muted, size: 0.92em)[#body]

#let _left-right-draw-edge = (from-node, to-node, edge-label) => {
  let from-anchor = (name: from-node.name, anchor: "east")
  let to-anchor = (name: to-node.name, anchor: "west")
  let middle-anchor = (from-anchor, 50%, to-anchor)
  if from-node.pos.x == to-node.pos.x {
    (
      vertices: (from-anchor, to-anchor),
      marks: "-|>",
      label: edge-label,
    )
  } else {
    (
      vertices: (
        from-anchor,
        ((), "-|", middle-anchor),
        ((), "|-", to-anchor),
        to-anchor,
      ),
      marks: "-|>",
      label: edge-label,
    )
  }
}

#let _style(
  compact: true,
  text-size: 8pt,
  node-width: 19em,
  spacing: (8pt, 13pt),
  orientation: "tb",
) = tidy-tree-graph.with(
  compact: compact,
  text-size: text-size,
  node-width: node-width,
  node-inset: 3pt,
  spacing: spacing,
  draw-edge: if orientation == "lr" {
    _left-right-draw-edge
  } else {
    tidy-tree-draws.horizontal-vertical-draw-edge
  },
  draw-node: (
    tidy-tree-draws.metadata-match-draw-node.with(
      matches: (
        group: (fill: group_color, stroke: 0.65pt + group_color.darken(28%)),
        leaf: (fill: leaf_color, stroke: 0.5pt + leaf_color.darken(18%)),
        array: (fill: array_color, stroke: 0.55pt + array_color.darken(24%)),
        derived: (fill: derived_color, stroke: 0.65pt + derived_color.darken(28%)),
      ),
      default: (fill: data_color, stroke: 0.5pt + data_color.darken(18%)),
    ),
    if orientation == "lr" { tidy-tree-draws.horizontal-draw-node } else { (..) => (:) },
  ),
)

/// Immutable VIN offline-store physical tree.
#let vin-offline-tree(
  compact: true,
  text-size: 8pt,
  node-width: 18em,
  spacing: (8pt, 13pt),
) = {
  let tree = _style(compact: compact, text-size: text-size, node-width: node-width, spacing: spacing)
  tree[
    - #code-strong("vin_offline/") #group
      - #code("manifest.json") -- version, source config, blocks, shards #leaf
      - #code("sample_index.jsonl") -- global row to split, scene, snippet, shard row #leaf
      - #code-strong("splits/") #group
        - #code("all.npy") -- global sample indices #array_node
        - #code("train.npy") -- train source rows #array_node
        - #code("val.npy") -- validation source rows #array_node
      - #code-strong("shards/") #group
        - #code-strong("shard-000000/") #group
          - #code-strong("numeric_blocks.zarr/") -- fixed numeric blocks by row #group
            - #code("backbone.*") -- cached EFM/VIN tensors #array_node
            - #code("candidates.*") -- one-step candidate substrate #array_node
            - #code("depths.*") -- optional cached depth blocks #array_node
          - #code("records.msgpack") -- optional variable diagnostics #leaf
          - #code("records_offsets.npy") -- offsets into diagnostics #array_node
        - #code-strong("shard-000001/") -- same contract #group
  ]
}

/// Top-level relation between immutable VIN offline rows and rollout rows.
#let offline-rollout-relation-tree(
  compact: true,
  text-size: 7.6pt,
  node-width: 17em,
  spacing: (9pt, 12pt),
  orientation: "lr",
) = {
  let tree = _style(
    compact: compact,
    text-size: text-size,
    node-width: node-width,
    spacing: spacing,
    orientation: orientation,
  )
  tree[
    - #text(weight: "bold")[offline to rollout persisted relation] #group
      - #code-strong("vin_offline/") -- immutable cached source substrate #group
        - #code("sample_index.jsonl") -- sample_index to scene, snippet, split #leaf
        - #code("numeric_blocks.zarr/") -- cached VIN/EFM substrate by source row #group
        - #code("VinOfflineSample") -- runtime root row; not copied #leaf
      - #code-strong("rollouts.zarr/") -- target-conditioned replay sidecar #group
        - #code("manifest.json") -- generation config and source coverage #leaf
        - #code-strong("sources/") -- references VIN rows #group
          - #code("source_row_id") -- rollout-local source key #array_node
          - #code("sample_index") -- joins back to #code("vin_offline/sample_index.jsonl") #array_node
        - #code-strong("targets/") -- top-K target rows per source #group
          - #code("source_row_id -> target_row_id") -- one source branches to targets #array_node
        - #code-strong("rollouts/") -- retained policy chains per target #group
          - #code("target_row_id -> rollout_row_id") -- branch by policy and chain_id #array_node
        - #code-strong("steps/") -- rollout time rows #group
          - #code("rollout_row_id + step_index") -- time index $t$ #array_node
        - #code-strong("candidates/") -- finite candidate shell per step #group
          - #code("step_row_id + shell_index") -- candidate row $q_(t,i)$ #array_node
        - #code-strong("candidate_diagnostics/") -- candidate-generation audit metrics #group
        - #code-strong("selected_depth/") -- selected-action history depth #group
        - #code("target_eval_crops/") -- optional sampled/audit target crops #group
        - #code-strong("q_h/") -- persisted derived training view #derived
  ]
}

/// Implemented manifest-backed rollout sidecar tree.
#let rollout-zarr-tree(
  compact: true,
  text-size: 7.2pt,
  node-width: 18em,
  spacing: (9pt, 12pt),
  orientation: "lr",
) = {
  let tree = _style(
    compact: compact,
    text-size: text-size,
    node-width: node-width,
    spacing: spacing,
    orientation: orientation,
  )
  tree[
    - #code-strong("rollouts.zarr/") -- schema 0.9 candidate-diagnostics shard #group
      - #code("zarr.json") -- compact attrs, counts, manifest hash #leaf
      - #code("manifest.json") -- resolved config, TOML, provenance, coverage #leaf
      - #code-strong("metadata/") #group
        - #code("reason_code_bits") -- uint16[K_reason] #array_node
        - #code("reason_code_names") -- JSON string-list bytes #leaf
        - #code("field_retention_policy") -- JSON bytes #leaf
      - #code-strong("dictionaries/") -- compact string dictionaries #group
        - #code("scene, snippet, split") -- ids for source coverage #leaf
        - #code("policy, rollout") -- ids for branch semantics #leaf
        - #code("target, class_name, target_source") -- ids for target rows #leaf
        - #code("config, score_source, reason") -- ids for lineage #leaf
      - #code-strong("sources/") -- one row per VIN source root #group
        - #code("source_row_id") -- int64[S], source primary key #array_node
        - #code("sample_index") -- int64[S], VIN offline row #array_node
        - #code("scene_id, snippet_id, split_id") -- int32[S] dictionary ids #array_node
        - #code("source_*_hash_id") -- int32[S] config/manifest hashes #array_node
      - #code-strong("targets/") -- actor-visible target + GT-EVAL fields #group
        - #code("target_row_id") -- int64[E], target primary key #array_node
        - actor-visible geometry #group
          - #code("target_center_world") -- $#symb.oracle.center _e in RR^3$; float32[E,3] #array_node
          - #code("target_extents") -- float32[E,3] #array_node
          - #code("target_pose_world_object") -- PoseTW float32[E,12] #array_node
        - validity and GT-EVAL #group
          - #code("target_valid_mask, gt_label_valid_mask") -- bool[E] #array_node
          - #code("gt_match_iou, gt_match_score") -- float32[E] #array_node
          - #code("target_invalid_reason_bitset") -- uint32[E] #array_node
      - #code-strong("rollouts/") -- one row per retained branch #group
        - #code("rollout_row_id") -- int64[R], rollout primary key #array_node
        - #code("source_row_id, target_row_id") -- int64[R] foreign keys #array_node
        - #code("policy_id, chain_id") -- policy and branch ids #array_node
        - #code("horizon, branch_factor, beam_width") -- int16[R] #array_node
        - #code("root_pose_world") -- PoseTW float32[R,12] #array_node
        - #code("root_time_ns, root_frame_index") -- rollout root lineage #array_node
        - #code("final_cumulative_target_root_gain") -- $G_0^((H))$; float32[R] #array_node
        - #code("final_cumulative_target_rri") -- diagnostic float32[R] #array_node
      - #code-strong("lineage/") -- rollout config/protocol ids #group
        - #code("rollout_row_id") -- int64[R] #array_node
        - #code("candidate_config_id, oracle_config_id") -- int32[R] #array_node
        - #code("rollout_config_id, target_crop_policy_id") -- int32[R] #array_node
      - #code-strong("steps/") -- one row per rollout time step #group
        - #code("step_row_id") -- int64[T], step primary key #array_node
        - #code("rollout_row_id") -- int64[T] foreign key #array_node
        - #code("step_index") -- $t$; int16[T] #array_node
        - #code("selected_candidate_row_id") -- int64[T] foreign key #array_node
        - #code("num_candidates, num_valid_candidates") -- int32[T] #array_node
        - #code("cumulative_target_root_gain") -- float32[T] #array_node
        - #code("cumulative_target_rri") -- diagnostic float32[T] #array_node
      - #code-strong("candidates/") -- finite candidate shells #group
        - row identity #group
          - #code("candidate_row_id") -- int64[C], candidate primary key #array_node
          - #code("step_row_id, rollout_row_id") -- int64[C] foreign keys #array_node
          - #code("shell_index") -- candidate index $i$; int32[C] #array_node
        - pose payload #group
          - #code("pose_world_cam") -- $#symb.oracle.candidate_qti$; PoseTW float32[C,12] #array_node
          - #code("pose_relative_root") -- PoseTW float32[C,12] #array_node
        - masks and labels #group
          - #code("actor_action_mask") -- $#symb.rl.validity_mask$; bool[C] #array_node
          - #code("oracle_label_mask, q_train_mask, selected_mask") -- bool[C] #array_node
          - #code("target_root_gain") -- default reward float32[C] #array_node
          - #code("target_rri") -- diagnostic $r_t^e(q_(t,i))$; float32[C] #array_node
          - #code("scene_rri") -- diagnostic float32[C] #array_node
        - provenance and invalidity #group
          - #code("strategy_id, position_id, mixture_id") -- int32[C] provenance #array_node
          - #code("invalid_reason_bitset") -- uint32[C] #array_node
      - #code-strong("candidate_diagnostics/") -- typed generator audit metrics #group
        - #code("candidate_row_id, position_id") -- candidate links and position family #array_node
        - #code("mesh_distance_m, path_min_clearance_m") -- clearance diagnostics #array_node
        - #code("motion_step_length_m, target_distance_m") -- motion/target diagnostics #array_node
      - #code-strong("selected_depth/") -- selected-action history rasters #group
        - #code("step_row_id, candidate_row_id") -- int64[T] links #array_node
        - #code("depth_m") -- float16[T,240,240], metres #array_node
        - #code("valid_mask") -- bool[T,240,240] #array_node
      - #code-strong("target_eval_crops/") -- optional sampled/audit target crops #group
        - #code("crop_row_id, step_row_id, candidate_row_id") -- row links #array_node
        - #code("points_world") -- float32[K,50000,3] #array_node
        - #code("lengths, mask") -- int32[K], bool[K,50000] #array_node
      - #code-strong("q_h/") -- derived hot training view, validated from row tables #derived
        - #code("source_row_id, target_row_id") -- state joins #array_node
        - #code("candidate_row_id, valid_action_mask") -- [T,N_q] #array_node
        - #code("q_train_mask") -- training mask #array_node
        - #code("one_step_target_root_gain") -- reward float32[T,N_q] #array_node
        - #code("one_step_target_rri") -- diagnostic float32[T,N_q] #array_node
        - #code("td_reward, td_*") -- selected transition reward and links #array_node
  ]
}

/// Joined trainable multi-step sample view.
#let rollout-sample-tree(
  compact: true,
  text-size: 7.5pt,
  node-width: 18em,
  spacing: (7pt, 11pt),
  orientation: "lr",
) = {
  let tree = _style(
    compact: compact,
    text-size: text-size,
    node-width: node-width,
    spacing: spacing,
    orientation: orientation,
  )
  tree[
    - #text(weight: "bold")[joined sample root] #group
      - #code-strong("source/") -- $s_0^"cf0"$ source refs #group
        - #code("source_row_id") -- int64[1] #array_node
        - #code("sample_key, scene_id, snippet_id, split") -- scalar dictionary ids #leaf
        - #code("cached_backbone_ref") -- external VIN block reference #leaf
        - #code("raw_snippet_ref") -- external EfmSnippetView reference #leaf
        - #code("mesh_ref") -- external $#symb.ase.mesh$ path/hash/version #leaf
      - #code-strong("target/") -- $e, #symb.entity.target_desc$ #group
        - #code("target_row_id") -- int64[1] #array_node
        - #code("target_center_world") -- $#symb.oracle.center _e in RR^3$; float32[3] #array_node
        - #code("observed_obb_world") -- actor-visible OBB payload #array_node
        - #code("support_summary") -- float32[F_aux] #array_node
        - #code("gt_match_score") -- $mu(hat(e), e)$; GT-EVAL only #array_node
        - #code("target_valid_mask, gt_label_valid_mask") -- bool[1] #array_node
      - #code-strong("rollout/") -- policy $pi$, horizon $H$ #group
        - #code("rollout_row_id") -- int64[1] #array_node
        - #code("chain_id") -- retained branch index #leaf
        - #code("policy_id") -- random, greedy, lookahead, softmax #leaf
        - #code("final_cumulative_target_root_gain") -- $G_0^((H))$; float32[1] #array_node
        - #code-strong("steps/") -- $t=0, ..., H-1$ #group
          - #code-strong("step_t/") #group
            - #code("step_index") -- $t$; int16[1] #array_node
            - #code("selected_candidate_row_id") -- action chosen at step $t$ #array_node
            - #code("cumulative_target_root_gain") -- float32[1] #array_node
            - #code-strong("candidate_shell/") -- $#symb.oracle.candidates_t$ #group
              - #code("pose_world_cam") -- $#symb.oracle.candidate_qti$; float32[N_q,12] #array_node
              - #code("actor_action_mask") -- $#symb.rl.validity_mask$; bool[N_q] #array_node
              - #code("invalid_reason_bitset") -- uint32[N_q] #array_node
              - #code("target_root_gain") -- default reward float32[N_q] #array_node
              - #code("target_rri") -- diagnostic float32[N_q] #array_node
              - #code("selected_mask") -- one true row when action exists #array_node
            - #code-strong("retained_depth/") -- optional selected-heavy payload #group
              - #code("depth") -- $#symb.oracle.depth_q$; float16[H_img,W_img] #array_node
              - #code("valid_mask") -- $#symb.oracle.mask_q$; bool[H_img,W_img] #array_node
        - #code-strong("q_h/") -- persisted derived tensors, shape [H,N_q] #derived
          - #code("candidate ids, masks, rewards") -- selected-transition view #array_node
          - #code("terminal/bootstrap fields") -- validated from row tables #array_node
  ]
}

/// Target architecture for a sharded rollout collection.
#let rollout-sharded-target-tree(
  compact: true,
  text-size: 7.8pt,
  node-width: 20em,
  spacing: (7pt, 12pt),
) = {
  let tree = _style(compact: compact, text-size: text-size, node-width: node-width, spacing: spacing)
  tree[
    - #code-strong("rollouts_v1/") -- target collection architecture #group
      - #code("manifest.json") -- collection schema, coverage, shard index #leaf
      - #code("dictionaries.json") -- optional shared dictionaries #leaf
      - #code-strong("splits/") #group
        - #code("train.json") #leaf
        - #code("val.json") #leaf
        - #code("test.json") #leaf
      - #code-strong("audit/") #group
        - #code("source_rows.jsonl") -- source attempts and skips #leaf
        - #code("targets.jsonl") -- target attempts and skips #leaf
        - #code("build_summary.json") -- shard/job summary #leaf
      - #code-strong("shards/") #group
        - #code-strong("split=train/") #group
          - #code-strong("shard=000000.zarr/") -- one validated rollout shard #group
            - #code("zarr.json") #leaf
            - #code("manifest.json") #leaf
            - #code("metadata/, dictionaries/") #group
            - #code("sources/, targets/, rollouts/") #group
            - #code("lineage/, steps/, candidates/") #group
            - #code("selected_depth/") -- selected-action depth profile #group
            - #code("target_eval_crops/") -- optional sampled/audit target crops #group
            - #code("q_h/") -- persisted derived training view #group
            - #code("diagnostics/") -- optional inspection payloads #group
          - #code-strong("shard=000001.zarr/") -- same contract #group
        - #code-strong("split=val/") -- independent validation shards #group
  ]
}
