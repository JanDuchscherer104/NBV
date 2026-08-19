---
id: 2026-08-19_g001_d1_v1_admission_contract_docs
date: 2026-08-19
title: "G001 D1 V1 admission contract documentation"
status: done
topics: [target-matching, thesis, typst, memory]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/memory/state/DECISIONS.md
  - .agents/memory/state/OPEN_QUESTIONS.md
  - docs/contents/thesis/questions.qmd
  - docs/typst/shared/equations/entity.typ
  - docs/notation.yml
  - docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ
  - .agents/memory/history/2026/08/2026-08-19_g001_d1_v1_admission_contract_docs.md
---

## Task

Replace the unresolved D1 matching decision and stale composite-match equation
with the signed implemented V1 admission contract, while preserving D2 and the
historical V0 oracle-task description.

## Method And Findings

Inspected the target matcher and campaign audit path. The implementation filters
GT rows by compatible class, computes oriented 3D IoU, qualifies only rows with
IoU strictly greater than `0.20`, and admits exactly one qualified row. Equality
is rejected and multiple qualifying rows are explicitly ambiguous/rejected; no
runner-up score, gap, or composite `mu` is part of the contract.

Updated the canonical decision and open-question owners, replaced the shared
entity equations and notation entries, and documented the V1 contract in the
active target-task thesis section and Quarto research-question page. The
existing V0 geometry-valid GT-row sampler remains explicitly identified as V0
evidence rather than being relabeled as actor-visible matching. D2 remains
`max(12, ceil(0.25 * N_q)) = 15`.

## Verification

- `aria_nbv/.venv/bin/python scripts/glossary_build.py validate` passed: 77
  symbols and 83 equations validated.
- Focused thesis compile passed:
  `typst compile --root docs --input
  aria-thesis-data=/typst/thesis/data/report-bundle-fixture.json
  docs/typst/thesis/main.typ /tmp/aria-g001-d1-typst/thesis.pdf`.
- Rendered pages 44-45 of the compiled thesis and visually inspected the new
  V1 section and equations.
- `git diff --check` passed.
- `make check-agent-memory` passed after this debrief was added.
- Focused matcher/campaign tests passed: 13 selected, 182 deselected.

## Canonical-State Impact

D1 is now current truth in `DECISIONS.md`; its matching and ambiguity questions
are resolved in `OPEN_QUESTIONS.md`. The active thesis and shared notation now
describe V1 strict unique same-class IoU admission without a runner-up-gap or
composite score. No implementation, configuration, GitHub, or OMX state was
changed.
