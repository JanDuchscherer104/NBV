---
id: 2026-05-20_candidate_view_dependence_theory
date: 2026-05-20
title: "Candidate View Dependence Theory Extraction"
status: done
topics: [architecture, docs, typst, qh, candidate-sets]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/contents/theory/candidate_view_dependence.qmd
  - docs/_quarto.yml
  - docs/references.bib
  - docs/typst/thesis/advisor_distillation.typ
---

## Task

Extracted the key ideas and suggestions from `.agents/work/architecture-considerations/candidate-view-dependence-gpt55pro.md` into public theory documentation and a focused advisor-distillation patch.

## Method

Converted the scratch note into a Quarto theory page that frames candidate views as a permutation-equivariant finite set sampled from a target-specific RRI utility field over SE(3). Patched the advisor handout at the finite-candidate value-model section rather than rewriting unrelated sections. Added bibliography entries for Conditional Neural Processes and multipoint expected improvement so the new theory page can point to the external literature directly.

## Findings

The extraction preserved the main architecture guidance: independent absolute RRI scoring should remain the calibrated base for one-step labels, while set/context interaction is safer as a zero-mean residual or in a residual dueling `Q_H` head. The page also records SE(3) relative pose features, Fisher/SCONE support-overlap attention biases, directional novelty features, permutation-equivariance requirements, local smoothness limits, loss design, ablation ladders, robustness tests, and failure modes such as absolute-label contamination, generator overfitting, duplicate instability, mask leakage, and shortcut strategy priors.

## Verification

- `make qmd-frontmatter-check` passed.
- `cd docs && quarto render contents/theory/candidate_view_dependence.qmd` passed.
- `cd docs && typst compile typst/thesis/advisor_distillation.typ /tmp/advisor_distillation.pdf --root .` passed.
- Visual PDF QA inspected rendered pages 9, 10, 12, 13, and 14 around the new advisor content.
- `make kg-claim-check KG_CLAIM="ARIA-NBV should treat candidate views as a permutation-equivariant finite set sampled from a locally structured, piecewise-smooth target-RRI utility field over SE(3), using an independent calibrated scorer plus zero-mean candidate-set residual or residual dueling Q_H to avoid corrupting absolute RRI labels."` returned `unverifiable` because literature `paper:*` nodes lack source paths today.
- `make kg-search KG_QUERY="candidate views permutation equivariant Deep Sets Set Transformer FisherRF RRI Q_H"` found the current thesis spine, candidate-shuffling contract, FisherRF bibliography entry, and roadmap context; semantic search was unavailable because Ollama was unreachable.

## Canonical State Impact

No separate canonical state update is needed. The new Quarto theory page owns the distilled architecture guidance, and the advisor handout carries the short thesis-facing version.
