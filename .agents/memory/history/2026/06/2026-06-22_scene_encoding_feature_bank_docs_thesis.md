---
id: 2026-06-22_scene_encoding_feature_bank_docs_thesis
date: 2026-06-22
title: "Scene Encoding Feature Bank Docs And Prototype"
status: done
topics: [vin, efm3d, thesis, feature-bank, actor-visible]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/contents/literature/efm3d.qmd
  - docs/contents/theory/efm3d_scene_embeddings.qmd
  - docs/contents/thesis/roadmap.qmd
  - docs/contents/thesis/questions.qmd
  - docs/typst/shared/equations/features.typ
  - docs/typst/thesis/sections/03-method.typ
  - aria_nbv/aria_nbv/vin/scene_feature_bank.py
  - aria_nbv/aria_nbv/vin/__init__.py
  - aria_nbv/tests/vin/test_scene_feature_bank.py
---

## Task

Implemented `.omx/plans/scene-encoding-docs-thesis-feature-bank-20260622T152059Z.md`.
The main decision encoded in docs and code is that EFM3D/EVL remains the
actor-visible local target/support substrate, semidense/fused points plus logged
DINO-on-point descriptors are the planned broad scene-memory upgrade, and Cube
R-CNN remains an auxiliary detector/ROI baseline.

## Method

Added shared Quarto and Typst equations for logged-frame world-point projection,
`rgb/feat2d_upsampled`-style feature sampling, projection-valid weighted pooling,
and compressed point descriptors. Updated roadmap/RQ/method prose to distinguish
root EVL evidence, broad semidense/fused point memory, optional logged DINO-on-
point features, and actor-visible target hypotheses.

Added `aria_nbv.vin.scene_feature_bank` as a read-only prototype. It samples
logged EFM3D image features at semidense/fused world points using `PoseTW`,
`CameraTW`, and EFM3D `sample_images`, then returns pooled descriptors, masks,
valid-frame counts, source frames, and provenance metadata. It does not change
rollout or offline-store schema.

## Verification

- `aria_nbv/.venv/bin/ruff check aria_nbv/aria_nbv/vin/scene_feature_bank.py aria_nbv/aria_nbv/vin/__init__.py aria_nbv/tests/vin/test_scene_feature_bank.py`
- `cd aria_nbv && uv run pytest tests/vin/test_scene_feature_bank.py`
- `git diff --check`
- `make qmd-frontmatter-check`
- `cd docs && quarto render contents/literature/efm3d.qmd`
- `cd docs && quarto render contents/theory/efm3d_scene_embeddings.qmd`
- `cd docs && quarto render contents/thesis/roadmap.qmd`
- `cd docs && quarto render contents/thesis/questions.qmd`
- `typst compile docs/typst/thesis/main.typ /tmp/aria-nbv-thesis-check.pdf --root docs`
- `make kg-claim-check KG_CLAIM="EFM3D/EVL is the primary actor-visible local target-support substrate for ARIA-NBV, while semidense/fused points with logged DINO descriptors are a planned broad scene-memory ablation and Cube R-CNN is an auxiliary detector/ROI baseline."`

The KG claim check returned supported with confidence 1.0 from canonical
`docs/contents/literature/efm3d.qmd` evidence.

## Notes

Ralph architect verification first returned `WATCH` for exact-string provenance
guarding and identity-only projection coverage. The follow-up patch added an
approved actor-visible feature-source allow-list, forbidden-family markers,
constructor-time provenance validation, alias-drift leakage tests, and a
translated-camera `PoseTW` projection regression.
