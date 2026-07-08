---
id: 2026-06-23_efm3d_evl_scene_encoding_consolidation
date: 2026-06-23
title: "EFM3D EVL Scene Encoding Consolidation"
status: done
topics: [vin, efm3d, evl, thesis, scene-encoding, actor-visible]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/work/scene-encoding-efm-backbone/06-tractable-efm3d-evl-scene-encodings.md
  - docs/contents/literature/efm3d.qmd
  - docs/contents/theory/efm3d_scene_embeddings.qmd
  - docs/typst/shared/equations/features.typ
  - docs/typst/thesis/sections/04-method/04-01-scene-representation-requirements.typ
  - docs/typst/thesis/sections/04-method/04-02-descriptor-and-encoding-plan.typ
  - docs/typst/thesis/sections/04-method/04-05-finite-candidate-value-model.typ
---

## Task

Consolidated the EFM3D/EVL scene-encoding reports, current thesis/docs, VIN EVL
types/adapter, and `external/efm3d` implementation into a tractable
scene-representation policy for ARIA-NBV.

## Findings

The durable decision is that EFM3D/EVL remains the Aria-native local evidence
and target-proposal substrate, but not the complete persistent scene memory.
Naive head voxel fields such as `occ_pr`, `cent_pr`, `bbox_pr`, and `clas_pr`
are useful baseline evidence, but they are local, task-collapsed, and do not
preserve broad free/unknown state, candidate visibility, directional history, or
counterfactual modality boundaries.

The recommended first serious state is sparse and actor-visible: semidense or
fused occupied/free/unknown memory with support, uncertainty, and directional
history, queried by target and candidate, with local EVL reads as coverage-aware
evidence and compressed logged DINO-on-point/cell descriptors as a later
visibility-gated ablation. Extending the EVL voxel area is documented as a
diagnostic ablation, not the default memory solution.

## Outputs

Added a dedicated synthesis note under `.agents/work/scene-encoding-efm-backbone/`
and threaded the stable claims into the EFM3D literature page, scene-embedding
theory page, thesis method section, and shared Typst feature equations.

## Verification

- `git diff --check -- .agents/work/scene-encoding-efm-backbone/06-tractable-efm3d-evl-scene-encodings.md docs/contents/literature/efm3d.qmd docs/contents/theory/efm3d_scene_embeddings.qmd docs/typst/shared/equations/features.typ docs/typst/thesis/sections/04-method/04-01-scene-representation-requirements.typ docs/typst/thesis/sections/04-method/04-02-descriptor-and-encoding-plan.typ docs/typst/thesis/sections/04-method/04-05-finite-candidate-value-model.typ .agents/memory/history/2026/06/2026-06-23_efm3d_evl_scene_encoding_consolidation.md`
- `make qmd-frontmatter-check`
- `typst compile typst/thesis/main.typ /tmp/aria-nbv-thesis-efm3d-scene-encodings.pdf --root .`
- `quarto render contents/literature/efm3d.qmd`
- `quarto render contents/theory/efm3d_scene_embeddings.qmd`
- autoresearch critic command covering synthesis-file existence, required claim strings, targeted `git diff --check`, and thesis Typst compile
- `make kg-claim-check KG_CLAIM="ARIA-NBV should use EFM3D/EVL as local actor-visible evidence and target support while broad scene memory is a sparse ray-aware occupied/free/unknown map with visibility-gated logged appearance descriptors as an ablation."`

The KG claim check returned supported with confidence 1.0 and no contradictions.
`make check-agent-memory` still fails on pre-existing tracked `.omx/**` runtime
state, not on this debrief.
