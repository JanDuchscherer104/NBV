---
id: 2026-06-22_efm3d_representation_backbone_literature
date: 2026-06-22
title: "EFM3D Representation Backbone Literature Patch"
status: done
topics: [efm3d, representation, backbone, cubercnn, docs]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/contents/literature/efm3d.qmd
---

## Task

Synthesize the requested transcript, prior representation distillation, current thesis direction, local EFM3D sources, and Cube R-CNN/ATEK evidence into the EFM3D literature page.

## Method

Used the active `autoresearch-goal` mission for `efm3d-representation-backbone`, the requested transcript `019eea90-7925-7b62-88f3-46be5740c081`, the prior EFM3D scene-representation report under `.omx/goals/autoresearch/aria-nbv-efm3d-scene-representations-beyond-limi/`, current thesis/source-order docs, local EFM3D TeX sources, and local ATEK/Cube R-CNN docs.

## Findings

`docs/contents/literature/efm3d.qmd` now ranks the backbone requirements for ARIA-NBV, names the actor-visible and candidate-mask invariants, separates local EVL evidence from broader semidense/fused scene memory, specifies target/candidate/intersection pooling, lists salvageable EFM3D internals for limited voxel extent handling, and frames Cube R-CNN as a single-frame 3D OBB detector and ROI-feature baseline rather than a scene-memory replacement.

## Verification

- `git diff --check -- docs/contents/literature/efm3d.qmd`
- `make qmd-frontmatter-check`
- `cd docs && quarto render contents/literature/efm3d.qmd`
- `make kg-claim-check KG_FORMAT=json KG_CLAIM="For ARIA-NBV, EFM3D/EVL should be treated as an actor-visible OBB and local support anchor, while broader target-conditioned Q_H scene state should use semidense or fused point evidence with optional logged DINO descriptors rather than treating the fixed local EVL voxel extent as complete scene memory."`

The EFM3D/semidense split claim was supported by litkg. The Cube R-CNN claim was `unverifiable` in litkg, so it was checked by direct local source reads: `external/ATEK/docs/example_cubercnn_customization.md`, `external/ATEK/docs/example_training.md`, `external/ATEK/atek/data_loaders/cubercnn_model_adaptor.py`, `docs/literature/tex-src/arXiv-EFM3D/persistence.tex`, and `docs/literature/tex-src/arXiv-scene-script/sections/suppmat.tex`.

## Canonical state impact

No canonical state update is needed. The public literature page now carries the current synthesis; future implementation should prove the DINO-on-point and EVL-internal feature-bank ablations with stored artifacts before treating them as implemented.
