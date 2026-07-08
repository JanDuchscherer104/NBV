---
id: 2026-06-23_thesis_scene_encoding_migration
date: 2026-06-23
title: "Thesis Scene-Encoding Migration"
status: done
topics: [thesis, typst, efm3d, scene-encoding, docs]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/typst/thesis/main.typ
  - docs/typst/thesis/sections/
  - docs/typst/shared/equations/
  - docs/typst/shared/symbols/
  - docs/notation.yml
  - docs/contents/literature/efm3d.qmd
  - docs/contents/theory/efm3d_scene_embeddings.qmd
assumptions:
  - The final active layout uses Chapter 03 for oracle/data generation and Chapter 04 for the learned method.
  - Shadow copy artifacts were temporary and removed after active compilation and PDF text audit.
---

## Task

Implement the 2026-06-23 thesis scene-encoding migration plan without losing content. The active thesis now separates foundations, oracle/data generation, method, experimental design, results, discussion, and conclusion. Appendix ownership is explicit from `main.typ` rather than hidden in the thesis template.

## Method

Built and compiled a shadow `sections_new`/`main_new.typ` layout first, then copied the compiled structure into the active `sections/` tree. Pruned inactive flat section files only after the active tree compiled and the old/new PDF text audit showed the intended chapter migration. Moved reusable scene-encoding, candidate-generation, state-process, row-equivariance, and ray-memory equations into shared Typst equation modules and regenerated notation artifacts from `docs/notation.yml`.

## Outputs

Chapter 03 now owns actor/oracle state boundaries, target selection, candidate generation, validity, target-RRI labels, and replay/data-generation evidence. Chapter 04 starts with scene-representation requirements and then describes EFM3D/EVL local evidence, sparse ray-aware memory, DINO-on-point projection, descriptor/query pools, replay contracts, geometry acceptance tests, and finite-candidate `Q_H`. The EFM3D Quarto notes now hold implementation-level policies for `EvlBackboneOutput`, EVL feature modes, optional `free_input`, `pts_world`, `clas_pr`, `sample_images`, `scene_feature_bank`, and storage/compression.

## Verification

`typst compile` passed for the shadow layout and the active final layout, including `--input aria-wip-links=false`. `make glossary`, `git diff --check`, `make qmd-frontmatter-check`, focused `quarto render` for the two changed EFM3D pages, `make check-agent-memory`, and the required KG claim check passed. The KG check reported the scene-encoding claim as supported with confidence 1.0 and no contradictions. Historical debrief path strings were mechanically migrated from the deleted flat thesis files to the new chapter files so memory validation continues to resolve canonical-update paths. The final cleanup/review gate removed stale structure notes, deleted-file pointers, local config/store names in thesis prose, section-level implementation identifiers, and raw repeated `obs` notation grouping.

## Canonical State Impact

No canonical state file update is needed. The migration updates public thesis/docs surfaces directly and keeps future implementation details in Quarto pages rather than the thesis body.
