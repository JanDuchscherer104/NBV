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
  orientation: "tb",
) = {
  let tree = _style(
    compact: compact,
    text-size: text-size,
    node-width: node-width,
    spacing: spacing,
    orientation: orientation,
  )
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
          - #code("zarr.json") -- shard root Zarr v3 metadata #leaf
          - #code("backbone/*") -- local EVL/VIN fields and voxel support #array_node
          - #code("oracle/*") -- one-step candidates, depth, cameras, RRI #array_node
          - #code("vin/*") -- semi-dense points and trajectory history #array_node
          - #code("*__*.msgpack + *.offsets.npy") -- indexed diagnostics #leaf
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
        - #code("shards/shard-*/") -- cached VIN/EFM substrate by source row #group
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
    - #code-strong("rollouts.zarr/") -- schema 1.0 target-rollout-core shard #group
      - #code("zarr.json + manifest.json") -- schema, counts, provenance, config hashes #leaf
      - #code("metadata/ + dictionaries/") -- reason bits and compact ids #group
      - #code("sources/") -- VIN source-row references and split coverage #array_node
      - #code("targets/") -- target geometry, validity, GT-EVAL audit #array_node
      - #code("rollouts/ + lineage/") -- policy branches, root pose, config ids #array_node
      - #code("steps/") -- time rows and selected action links #array_node
      - #code("candidates/") -- finite shells, poses, masks, rewards, provenance #array_node
      - #code("candidate_diagnostics/") -- clearance, motion, target-distance audits #array_node
      - #code("selected_depth/") -- selected successor depth + valid mask #array_node
      - #code("target_eval_crops/") -- optional oracle/eval target crops #array_node
      - #code("q_h/") -- derived [T,N_q] training view #derived
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
            - #code-strong("candidate_shell/") -- $#symb.rl.candidate_table$ #group
              - #code("pose_world_cam") -- $#symb.rl.candidate_qti$; float32[N_q,12] #array_node
              - #code("actor_action_mask") -- $#symb.rl.action_mask$; bool[N_q] #array_node
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
