---
id: 2026-05-19_scone_fisherrf_literature_init
date: 2026-05-19
title: "SCONE And FisherRF Literature Initialization"
status: done
topics: [literature, docs, nbv, scone, fisherrf]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/contents/literature/scone_fisherrf.qmd
  - docs/contents/literature/index.qmd
  - docs/contents/literature/active_3dgs_nbv.qmd
  - docs/literature/sources.jsonl
  - docs/literature/README.md
  - docs/literature/tex-src/arXiv-FisherRF/
  - docs/literature/pdf/FisherRF.pdf
  - docs/_quarto.yml
---

## Task

Initialized the SCONE/FisherRF literature surface from `.agents/work/scone-fisherrf-literature-review/literature-distillation-gpt55pro.md` and the local paper TeX sources. FisherRF was missing from `docs/literature/sources.jsonl`, so it was added and materialized from arXiv `2311.17874`.

## Method

- Read root/docs guidance and the distillation note.
- Verified SCONE was already present in the literature manifest and local TeX tree.
- Added FisherRF to `docs/literature/sources.jsonl` and `docs/literature/README.md`.
- Ran `uv run python scripts/download_arxiv_tex_src.py docs/literature/sources.jsonl --download-pdfs`, which fetched `docs/literature/tex-src/arXiv-FisherRF/` and `docs/literature/pdf/FisherRF.pdf`.
- Added `docs/contents/literature/scone_fisherrf.qmd` as a focused public literature page and linked it from the literature overview and Quarto sidebar.

## Findings

The durable thesis framing is that SCONE and FisherRF motivate actor-visible candidate support, visibility, directional novelty, and diminishing-returns information channels. They do not replace target-specific RRI, oracle target-quality evaluation, or the finite-candidate Q_H thesis path.

## Verification

- JSONL parse check passed for `docs/literature/sources.jsonl`.
- FisherRF TeX tree has no empty `.tex` files and no Git LFS pointer `.tex` files.
- `make context-literature-index` completed.
- `cd docs && quarto render contents/literature/index.qmd` passed.
- `cd docs && quarto render contents/literature/active_3dgs_nbv.qmd` passed.
- `cd docs && quarto render contents/literature/scone_fisherrf.qmd` passed after rerunning alone; the first parallel attempt hit a transient Quarto `site_libs/quarto-diagram/mermaid.css` race.
- `make kg-claim-check KG_CLAIM="SCONE and FisherRF should be used in ARIA-NBV as auxiliary actor-visible support, visibility, directional novelty, and information-gain channels rather than replacing target-specific RRI as the thesis utility."` returned `supported` with confidence `1.0`.

## Canonical State Impact

No separate canonical state update is needed. The new public literature page and source manifest entry are the owning surfaces for this initialization.
