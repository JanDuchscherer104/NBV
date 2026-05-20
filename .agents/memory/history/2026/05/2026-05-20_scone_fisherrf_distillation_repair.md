---
id: 2026-05-20_scone_fisherrf_distillation_repair
date: 2026-05-20
title: "SCONE FisherRF Distillation Repair"
status: done
topics: [literature, docs, scone, fisherrf, qh]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/contents/literature/scone_fisherrf.qmd
---

## Task

Reviewed `docs/contents/literature/scone_fisherrf.qmd` against `.agents/work/scone-fisherrf-literature-review/literature-distillation-gpt55pro.md` after the initial public page dropped many details from the scratch distillation.

## Method

Compared the public page with the original GPT-5.5 Pro distillation and the local SCONE/FisherRF TeX mirrors. Rewrote the page as a fuller curated literature note, preserving the thesis boundary while restoring the important equations, implementation pointers, diagnostics, and external-source links.

## Findings

The previous page kept the high-level target-RRI boundary but omitted the surface-coverage integral, SCONE volumetric approximation, SCONE module details, factual support integral, target-support probability construction, Fisher information/EIG/log-det/diagonal approximations, target-local uncertainty variables, marginal branch-diversity rule, candidate-token hierarchy, and concrete `target_support_features` proposal. The revised page restores those elements and keeps SCONE/FisherRF as auxiliary actor-visible support/information channels rather than replacement objectives.

## Verification

- `make qmd-frontmatter-check` passed.
- `cd docs && quarto render contents/literature/scone_fisherrf.qmd` passed.
- `make kg-claim-check KG_CLAIM="SCONE and FisherRF should be represented in ARIA-NBV as auxiliary actor-visible support, visibility, directional novelty, target-local information, and branch-diversity channels, while target-specific RRI remains the thesis utility and oracle evaluation target."` returned `supported` with confidence `1.0`.

## Canonical State Impact

No separate canonical state update is needed. The public literature page owns this curated distillation.
