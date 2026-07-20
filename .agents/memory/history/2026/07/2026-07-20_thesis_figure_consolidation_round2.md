---
id: 2026-07-20_thesis_figure_consolidation_round2
date: 2026-07-20
title: "Thesis Figure Consolidation Round 2"
status: done
topics: [thesis, typst, figures, replay, lookahead, q-h]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/typst/thesis/figures/oracle_lookahead_tree.typ
  - docs/typst/thesis/figures/replay_lineage_relations.typ
  - docs/typst/thesis/figures/qh_learning_evidence_loop.typ
  - docs/typst/thesis/sections/03-oracle-and-data-generation
  - docs/typst/thesis/sections/05-experimental-design
---

## Task

Rebase the geometric-figure overhaul onto the current `docs-update-latest`
branch and continue the autoresearch critic loop over the complete rendered
thesis figure inventory.

## Decisions and outputs

- Rebased the first figure pass onto `origin/docs-update-latest` at `d923d5b`.
  Git skipped three already-applied commits and replayed only the scoped figure
  overhaul.
- Replaced three consecutive physical storage-layout trees with one normalized
  replay-lineage diagram. It distinguishes immutable source rows, target tasks,
  retained chains, ordered steps, full candidate shells, selected transitions,
  and the derived `q_h/` cache. Exact directories and array groups remain
  reproducibility metadata rather than main-text figures.
- Rebuilt the lookahead figure as a symbolic state-node/action-edge tree. Invalid
  rows have no child, non-retained legal branches are distinct from invalidity,
  and greedy-versus-lookahead behavior is expressed by inequalities rather than
  fabricated decimal rewards.
- Removed the standalone teacher/student render-path figure because it duplicated
  the actor/oracle boundary and promoted unimplemented belief-render,
  distillation, and teacher-value paths. The prose now routes render-derived
  evidence through the existing privileged-supervision boundary.
- Reduced the `Q_H` process wall to two explicit surfaces: implemented factual
  selected-transition lineage and a separately labelled planned masked Double-Q
  computation. Residual heads, held-out policy claims, and evaluation stages no
  longer appear as if implemented.
- Corrected the replay relation after critic review: selection is the
  `steps/selected_candidate_row_id` link into the factual candidate shell;
  successor and TD fields are derived in `q_h/`, not persisted as a separate
  transition entity. The learning panel now indexes the row-wise training mask
  as $m^{train}_{t,i}$ and the selected entry as $m^{train}_{t,a_t}$. TD
  admission accepts either a valid successor link or a factual terminal
  transition with zero bootstrap discount.
- Added the candidate-scene view contract to generated JSON and the manuscript:
  Panel A is a 35-degree vertical-FOV perspective view and Panel B is a
  7.8-metre-wide orthographic bird's-eye view; eye, look-at, up, clipping, and
  resolution values are machine-readable provenance.
- The development manuscript now contains eight figures rather than eleven.

## Verification

- Replayed the candidate-scene, point-mesh, and directional-memory exporters
  against the pinned local stores and mesh after the rebase.
- Ruff checks passed for all exporter scripts.
- All eight included standalone Typst figures compiled independently.
- `make thesis-pdf` passed; the modified lookahead, replay-lineage, and learning
  pages were inspected at final A4 layout.
- Submission mode still fails closed on the explicit evidence-bundle gate, and
  the diary section independently fails on the first unresolved marker.
- The Typst-authoring skill validator and `git diff --check` passed.
- `make check-agent-memory` reaches an inherited `docs-update-latest` failure:
  `.omx/plans/measured-autoresearch-sidecar.md` lacks required YAML frontmatter.
  The same base-branch gate fails in the primary checkout and is outside this
  figure-only patch.

## Canonical state impact

No implementation or research-direction contract changed. The revision removes
redundant implementation inventories and makes the manuscript's evidence versus
hypothesis boundary more explicit.
