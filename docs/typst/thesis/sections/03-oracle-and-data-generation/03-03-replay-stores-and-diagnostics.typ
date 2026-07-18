#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/data-layout-trees.typ": *
#import "@preview/booktabs:0.0.4": *

== Replay Stores and Diagnostic Evidence

The pipeline materializes two stores with different ownership. Immutable `vin_offline/` caches logged snippet evidence and expensive one-step oracle products. Standalone `rollouts.zarr/` references those source rows and stores target tasks, retained rollout chains, per-step finite candidate shells, masks, reason codes, selected-action successor evidence, and a derived #symb.rl.qh view. This separation prevents counterfactual experiments from mutating the source substrate and prevents one-step candidate labels from being mistaken for multi-step replay.

The source store is immutable because it defines the logged actor substrate. Its manifest records source identity, split, schema, materialized blocks, and provenance. A source row may contain frozen EVL/VIN fields, one-step candidate poses and labels, compact rendering payloads, and semidense geometry/history. These fields support scorer training and rollout construction, but they do not themselves define target-conditioned finite-horizon data.

#figure(
  vin-offline-tree(
    compact: true,
    text-size: 6.9pt,
    node-width: 15.5em,
    spacing: (6pt, 8pt),
    orientation: "lr",
  ),
  caption: [Immutable VIN offline-store schema. Row-aligned Zarr arrays store tensor fields, while indexed MessagePack blocks retain variable diagnostics. The main text needs the row roles and actor/oracle boundary; version-specific layout belongs in the resolved reproducibility record.],
) <fig:vin-offline-store-layout>

The rollout store is normalized around replay identity. One source can produce multiple target rows, each target can produce multiple recipe and retained-chain rows, each chain expands into selected steps, and each step owns a full candidate shell. The store therefore captures selected or beam-retained chain evidence, not the complete counterfactual search tree. Padded `q_h/` arrays are a validated cache over the factual row tables. Invalid candidate rows remain inspectable, but action, training, and bootstrap masks exclude them.

#figure(
  offline-rollout-relation-tree(
    compact: true,
    text-size: 6.9pt,
    node-width: 16.5em,
    spacing: (6pt, 9pt),
    orientation: "lr",
  ),
  caption: [Relation between immutable VIN rows and target-conditioned replay. `rollouts.zarr/` stores joins, target tasks, retained chains, full per-step candidate shells, selected-depth successor history, and a derived #symb.rl.qh view without rewriting the source store.],
) <fig:offline-rollout-store-relation>

#figure(
  rollout-zarr-tree(
    compact: true,
    text-size: 6.3pt,
    node-width: 16.7em,
    spacing: (6pt, 8pt),
    orientation: "lr",
  ),
  caption: [Implemented rollout replay schema. Row tables are the facts; `q_h/` is a dense training cache validated against steps, candidates, retained chains, and targets.],
) <fig:rollout-replay-store-layout>

#figure(
  table(
    columns: (0.8fr, 1.35fr),
    toprule(),
    table.header([*Evidence family*], [*Interpretation contract*]),
    midrule(),
    [Sources and targets],
    [Manifest-backed task coverage; not proof of actor-visible target discovery.],
    [Candidates and invalidity],
    [Full-shell support with hard action, training, and bootstrap masks.],
    [Retained chains and steps],
    [Recipe-selected evidence; not a persisted exhaustive search tree.],
    [Selected depth],
    [Chosen-action successor history; not all-candidate or endpoint evidence.],
    [#symb.rl.qh view],
    [Derived training cache whose rewards and masks must agree with factual rows.],
    bottomrule(),
  ),
  caption: [Interpretation contract for rollout-store audits. Numeric values are rendered from the resolved report bundle in the experiment and reproducibility sections.],
) <tab:current-rollout-store-audit>

Selected-depth persistence stores only the depth raster and calibration for the chosen action at each retained step. It is sufficient to reconstruct selected history without duplicating dense all-candidate renders, but it is not an independently scored endpoint artifact. Likewise, rollout rows summarize final cumulative selected-chain metrics; they do not preserve every rejected branch or a policy-neutral endpoint reconstruction. These limitations must be resolved by matched endpoint re-evaluation before confirmatory policy comparison.

Scientific reporting is generated from the same inspection frames used by the diagnostic application. The main text needs target-task coverage, candidate validity and invalid reasons, family survival and selection, selected-history sanity, gain distributions, and runtime/storage summaries. Exact schema columns, compression, chunking, hashes, and cluster invocation belong in the reproducibility appendix and must be read from the resolved manifest and report bundle. Development bandwidth pilots are train-only feasibility checks; their counts and throughput may size later jobs but cannot support held-out reconstruction or policy claims.
