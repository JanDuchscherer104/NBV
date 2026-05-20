---
id: 2026-05-20_efm3d_scene_embedding_docs
date: 2026-05-20
title: "EFM3D Scene Embedding Docs"
status: done
topics: [docs, efm3d, scene-representation, thesis]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/contents/theory/efm3d_scene_embeddings.qmd
  - docs/_quarto.yml
  - docs/contents/literature/efm3d.qmd
  - docs/contents/literature/index.qmd
  - docs/contents/thesis/roadmap.qmd
  - docs/typst/thesis/advisor_distillation.typ
  - docs/typst/shared/equations/features.typ
  - docs/typst/shared/glossary.typ
  - docs/contents/glossary.qmd
  - docs/typst/shared/glossary.generated.typ
  - docs/_generated/context/glossary.jsonl
  - docs/glossary/terms.yml
---

## Task

Implemented the documentation-only EFM3D scene embedding plan on 2026-05-20. The public thesis narrative now treats EVL as actor-visible target support and local evidence, while documenting semidense/fused points with optional compressed DINO features as the recommended broader scene representation hypothesis for target-conditioned RRI and finite-candidate Q_H.

## Method

Created a new theory page for EFM3D scene embeddings, added it to Quarto navigation, patched the EFM3D literature ledger and thesis roadmap wording, updated the advisor Typst handout, and refreshed shared feature equations. Glossary source terms for EVL and CF0 state were revised and generated glossary artifacts were rebuilt with `make glossary`.

## Findings

Local EFM3D exposes DINO maps/tokens, lifted voxel features, neck features, voxel/head outputs, voxel poses/extents, and predicted OBB records. ATEK/ASE exposes semidense world points, uncertainty, observation/support metadata, and scene-scale point evidence. The new docs classify compressed DINO-on-semidense-point tokens as a hypothesis and planned ablation, not a current cache implementation.

## Verification

Ran `make qmd-frontmatter-check`, `cd docs && quarto render contents/theory/efm3d_scene_embeddings.qmd`, `cd docs && quarto render contents/literature/efm3d.qmd`, `cd docs && quarto render contents/literature/index.qmd`, `cd docs && quarto render contents/thesis/roadmap.qmd`, `cd docs && typst compile typst/thesis/advisor_distillation.typ /tmp/advisor_distillation.pdf --root .`, and the requested KG claim check. The claim check returned `supported (confidence=1.0)` with supporting canonical evidence in `docs/contents/thesis/questions.qmd:584` and `docs/contents/thesis/roadmap.qmd:114`.

## Canonical State Impact

No canonical memory update is required beyond the public docs and this debrief. The change is documentation-only and does not add Python APIs, cache writers, model code, or dataset schema changes.
