---
id: 2026-07-19_thesis_invalid_row_supervision
date: 2026-07-19
title: "Thesis invalid-row supervision contract"
status: done
topics: [thesis, validity-mask, selective-prediction, curriculum]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/typst/thesis/sections/02-foundations/02-02-geometric-learning.typ
  - docs/references.bib
---

## Task

Replace the geometric-learning TODO on invalid candidate rows with a sourced,
testable training contract.

## Outcome

Invalid rows receive feasibility/reject supervision but no RRI regression
target: their RRI is undefined rather than zero or a synthetic negative value.
Hard masking remains the deployment constraint; a calibrated soft feasibility
gate is an ablation only. The thesis now cites SelectiveNet, Deep Gamblers, and
the existing curriculum-learning reference.

## Verification

`cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-masking.pdf --root .`
completed successfully. The staged commit scope excludes unrelated dirty files.

## Canonical State Impact

None; this records a thesis-method hypothesis, not implemented behavior.
