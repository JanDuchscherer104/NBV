---
id: 2026-06-17_thesis_architecture_iteration25_recurrence_budget
date: 2026-06-17
title: "Thesis Architecture Iteration 25 Recurrence Budget"
status: done
topics: [thesis, architecture, deja-view, recurrence, q-h, selected-history]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/03-method.typ
  - docs/typst/thesis/sections/04-evaluation.typ
  - docs/typst/thesis/sections/05-conclusion.typ
  - docs/contents/theory/rl_planning.qmd
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Summary

Iteration 25 refines the Deja View transfer into a bounded recurrence budget
contract. Recurrence step count `K` is a neural compute/refinement budget for a
fixed decision state, not an acquisition horizon `H`, candidate width `N_q`, or
rollout branch width `B`. Deja View-style recurrence stays a later ablation over
selected-history or candidate-context tokens after fixed-depth `Q_H`, masks,
target support, rollout lineage, and selected-history provenance are stable.

## Evidence

- `docs/literature/tex-src/arXiv-Deja-View/sections/00_abstract.tex` and
  `01_introduction.tex` frame Deja View as a looped transformer block applied
  recurrently for `K` refinement steps, exposing `K` as an inference-time
  compute knob.
- `docs/literature/tex-src/arXiv-Deja-View/sections/03_method.tex` distinguishes
  its directional refinement from fixed-point convergence and from RAFT-style
  task-space output refinement.
- `docs/literature/tex-src/arXiv-Deja-View/sections/04_experiments.tex` trains
  variable `K` in a bounded range and compares fixed and variable step counts.
- `docs/literature/tex-src/arXiv-Deja-View/sections/06_supplemental.tex` and
  `05_conclusion.tex` state that pushing inference beyond the trained range
  eventually degrades or collapses because feature channels drift.
- `docs/contents/theory/rl_planning.qmd` and
  `docs/typst/thesis/sections/03-method.typ` define selected-view history,
  candidate tables, masks, and the finite-candidate `Q_H` state contract.
- Iteration 14 already established that recurrence may only consume
  selected-history evidence and must not see unselected candidate renderings or
  oracle labels.

## Canonical Updates Needed

- Add wording in the thesis method/discussion that distinguishes `K`, `H`,
  `N_q`, and rollout branch width `B`.
- Gate recurrence behind positive evidence from calibrated one-step scoring,
  fixed-depth candidate-set models, selected-history features, and oracle
  lookahead headroom.
- If recurrence is implemented, report state norm, relative update norm,
  cosine-to-final-state, logit/value deltas, rank stability, calibration,
  oracle-rescored endpoint gain, and runtime/memory by `K`.
- Treat beyond-trained-range `K` only as a failure/generalization diagnostic,
  not as thesis evidence for unbounded planning or convergence.
