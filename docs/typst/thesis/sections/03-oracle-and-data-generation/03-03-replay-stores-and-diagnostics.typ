#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../../shared/data-layout-trees.typ": *
#import "../../../shared/style.typ": gh-wip
#import "../../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

== Replay Stores and Diagnostic Evidence

// source: aria_nbv/aria_nbv/data_handling/_offline_store.py:1-9 owns the immutable VIN offline layout.
// source: aria_nbv/aria_nbv/rollouts/dataset_writer.py:1-14 defines rollout stores as standalone target-conditioned replay artifacts.
// source: aria_nbv/aria_nbv/rollouts/zarr_store.py:1-18 defines row tables, masks, derived q_h arrays, and invalidity semantics.
The data-generation pipeline deliberately materializes two different stores. The immutable `vin_offline/` store is a source substrate: it caches expensive logged-state evidence and one-step oracle products for ASE snippets so that scorer training and audits do not repeatedly run EFM3D/VIN extraction, mesh rendering, backprojection, and point-mesh scoring. The standalone `rollouts.zarr/` store is a target-conditioned replay sidecar: it references VIN source rows, creates target-task rows, regenerates finite candidate tables for each rollout state, records masks and invalidity reasons, persists selected-action successor evidence, and exposes a derived #symb.rl.qh training view. This separation is scientific, not only operational. It prevents selected-transition experiments from mutating the immutable one-step substrate, and it prevents the thesis from treating all-candidate oracle labels as if they were already multi-step replay.

The implementation anchors for this contract are the #gh-wip("aria_nbv/aria_nbv/data_handling/_offline_store.py", body: [VIN offline-store owner], line: 1), #gh-wip("aria_nbv/aria_nbv/rollouts/dataset_writer.py", body: [rollout writer], line: 1), and #gh-wip("aria_nbv/aria_nbv/rollouts/zarr_store.py", body: [rollout schema owner], line: 1). These anchors support reproducibility of the data contract; manifest-backed store audits remain the source for reported counts.

#prune_todo(
  [The live v7 and dated audit-store snapshots below are development evidence. Remove them from the final Method chapter or replace and relocate them with manifest-backed final split statistics in Results or a reproducibility appendix.],
  source: [thesis peer review; final manifest requirement],
  gate: [final dataset and rollout manifests],
)

The source store is immutable because it defines the logged actor substrate. In the current local v7 store, `vin_offline/` contains 48 samples, split into 38 train and 10 validation rows, and materializes backbone fields, candidate point clouds, and candidate depth blocks. A row contains frozen local EVL/VIN fields, one-step candidate poses and labels, rendered depth/camera payloads, and semi-dense VIN geometry/history. These are valid source evidence for myopic scorer training and rollout construction, but they do not themselves define a target-conditioned finite-horizon dataset.

#figure(
  vin-offline-tree(
    compact: true,
    text-size: 6.9pt,
    node-width: 15.5em,
    spacing: (6pt, 8pt),
    orientation: "lr",
  ),
  caption: [Immutable VIN offline-store schema. The live v7 store writes row-aligned Zarr arrays directly inside each shard group and uses indexed MessagePack record blocks for variable diagnostics. The thesis needs the row-level roles and actor/oracle boundary; chunking and byte-level layout belong in reproducibility notes.],
) <fig:vin-offline-store-layout>

The rollout store is normalized around replay identity rather than tensor convenience. One source row can produce multiple target rows; one target row can produce multiple policy/branch rollout rows; each rollout row expands into step rows; each step row owns a full finite candidate shell; and the padded `q_h/` arrays are a derived, validated view over those factual tables. Invalid candidates remain in the full shell with reason codes, but their action, training, and bootstrap masks are false. Thus invalidity is stored as a hard constraint and diagnostic, not as a low target-specific @relative-reconstruction-improvement:short label.

#figure(
  offline-rollout-relation-tree(
    compact: true,
    text-size: 6.9pt,
    node-width: 16.5em,
    spacing: (6pt, 9pt),
    orientation: "lr",
  ),
  caption: [Persistent relation between immutable VIN offline rows and target-conditioned rollout rows. `rollouts.zarr/` stores joins, target tasks, selected branches, candidate masks, selected-depth successor history, and a derived #symb.rl.qh training view; it does not copy or rewrite the heavy source substrate.],
) <fig:offline-rollout-store-relation>

#figure(
  rollout-zarr-tree(
    compact: true,
    text-size: 6.3pt,
    node-width: 16.7em,
    spacing: (6pt, 8pt),
    orientation: "lr",
  ),
  caption: [Implemented standalone rollout replay schema. The row tables are the canonical facts; `q_h/` is a persisted cache for high-throughput finite-candidate training and is validated against `steps/`, `candidates/`, `rollouts/`, and `targets/`.],
) <fig:rollout-replay-store-layout>

The current audit-scale store `rollouts_v1_realistic_35_train_20260621.zarr` validates under schema `1.0-target-rollout-core`. It was generated from the train split with a 35-source cap, but after target and rollout gates it contains 16 source roots from one ASE scene, 16 target tasks, 96 retained rollout branches, 160 step states, and 9600 full-shell candidate rows. It persists 160 selected-depth successor rasters at 240 x 240 and a 160-state #symb.rl.qh view with at most 60 candidate rows per state. Target-eval crop payloads are disabled in this audit store, so target crops remain oracle/evaluation logic rather than a stored actor input.

#figure(
  table(
    columns: (0.72fr, 0.78fr, 1.2fr),
    toprule(),
    table.header([*Field family*], [*Current audit value*], [*Scientific interpretation*]),
    midrule(),
    [Sources / targets],
    [16 / 16],
    [Audit-scale coverage only; final claims require scene-level scale and held-out splits.],
    [Rollouts / steps],
    [96 / 160],
    [Selected-transition evidence exists, but the branch mix remains a generated replay profile, not a deployment policy.],
    [Candidates],
    [9600 full-shell rows, 3757 valid],
    [The valid-action support is non-degenerate but strongly pruned; invalid rows must be reported, masked, and stratified.],
    [Invalid reasons],
    [`CLEARANCE_TOO_SMALL`: 5174; `PATH_SEGMENT_COLLISION`: 669],
    [Most pruning is geometry/support related, so policy failures must be interpreted with validity diagnostics.],
    [Selected-depth retention],
    [160 rows, 240 x 240, float16 depth + bool mask],
    [Enough to represent selected successor geometry/history without storing all-candidate dense render payloads.],
    [#symb.rl.qh view],
    [160 states, $N_q <= 60$, reward `target_root_gain`],
    [Training-hot cache derived from factual tables; row tables remain the schema authority.],
    bottomrule(),
  ),
  caption: [Current validated rollout-store audit facts. These numbers document a real generated store, not final experiment scale.],
) <tab:current-rollout-store-audit>

The thesis should show this layout because the representation and learning claims depend on it: the actor state, candidate mask, selected-depth history, target reward, and successor candidate table must all be reproducible for a #symb.rl.qh row. It should not, however, spend main-text space on every chunk shape, byte count, local absolute path, or cluster job flag. A master's thesis needs enough layout detail to prove leakage safety, replay reproducibility, and scalability of the proposed experiment. Exact shard sizing, compression, cache paths, and Slurm-array mechanics belong in a reproducibility appendix once the final build manifests exist. Until then, local audit stores should be labeled as audit-scale evidence.

The Streamlit app already covers the diagnostic figures needed before interpreting value-model results. The thesis result chapter should not jump directly from a trained policy to endpoint gain; it should first show target validity, candidate support, selected-action diversity, invalidity, and selected-depth sanity checks.

#prune_todo(
  [Replace the following Streamlit/Python-file inventory with the scientific diagnostics actually reported in figures and tables. UI tabs and implementation routing belong in developer documentation or a reproducibility appendix, not the final main narrative.],
  source: [thesis peer review],
  gate: [final diagnostic figures],
)

#figure(
  table(
    columns: (0.78fr, 0.92fr, 1.18fr),
    toprule(),
    table.header([*Diagnostic slot*], [*Current source*], [*Thesis use*]),
    midrule(),
    [Target-task audit],
    [`target_audit.py`; `stored_rollouts.py` target audit tab],
    [Report identity-match status, projected area/support, class/source distribution, and invalid target reasons before target-specific @relative-reconstruction-improvement:short claims.],
    [Candidate geometry and pruning],
    [`candidates.py`; stored rollout candidate audit],
    [Show candidate centers/frusta, position-family counts, rule masks, clearance/path rejections, and valid fanout by family.],
    [Rollout objective traces],
    [`stored_rollouts.py` metrics and branch tabs],
    [Plot cumulative target-root gain, policy/branch coverage, selected family, fanout, entropy, and invalid fraction.],
    [Selected-depth successor state],
    [`stored_rollouts.py` selected-depth tab; `depth.py`],
    [Inspect persisted selected-depth rasters and validity masks so counterfactual geometry updates are visually plausible.],
    [All-candidate oracle renders],
    [`depth.py`; live counterfactual panel],
    [Use as oracle-label diagnostics or appendix material; do not treat all-candidate dense renders as actor-visible inputs.],
    bottomrule(),
  ),
  caption: [Required diagnostic figure slots supported by the current Streamlit panels. These plots are evidence gates before final policy comparisons, not optional UI screenshots.],
) <tab:streamlit-diagnostic-slots>

#validation_todo(
  [Export or regenerate the target audit, candidate validity, rollout objective, selected-depth, and candidate-geometry plots from the final manifest-backed rollout stores before presenting final results. Current 35-source-cap numbers are audit-scale evidence only.],
  source: [Streamlit panels listed in @tab:streamlit-diagnostic-slots],
  gate: [final result chapter and reproducibility appendix],
)
