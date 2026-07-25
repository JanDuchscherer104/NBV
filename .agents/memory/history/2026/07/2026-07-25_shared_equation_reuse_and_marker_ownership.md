---
id: 2026-07-25_shared_equation_reuse_and_marker_ownership
date: 2026-07-25
title: "Shared Equation Reuse And Marker Ownership"
status: done
topics: [thesis, typst, notation, draft-markers, measured-autoresearch]
confidence: high
canonical_updates_needed:
  - docs/typst/shared/equations
  - docs/notation.yml
  - aria_nbv/aria_nbv/data_handling/offline/inventory.py
---

# Shared Equation Reuse And Marker Ownership

## Outcome

Active thesis sections now render existing `eqs.*` definitions directly rather
than wrapping those definitions in new section-local math blocks. The remaining
seven research, validation, and decision markers link to exact agents-DB owners:
`todo-018`, `todo-037`, `todo-038`, `todo-048`, and `todo-052`. Scientific prose,
equation bodies, action gates, and task status did not change.

## Measurement

Iteration 2 of
`.omx/goals/autoresearch/scaffold-notation-ownership-v2-20260725/` was retained.
Against retained iteration 1, ownership violations decreased from 431 to 376,
section-local symbolic math fragments from 229 to 181, and unowned action
markers from 7 to 0. Unregistered shared references remained 195. Measured
non-test LOC decreased from 14461 to 14365. Every frozen hard gate passed.

Iteration 3 centralized seven finite-horizon queries and learning targets used
by the Method and Experimental Design chapters. Ownership violations decreased
again from 376 to 364 and section-local symbolic math fragments from 181 to
169. Unregistered references and unowned markers remained unchanged. Measured
non-test LOC increased by 7 lines because the named equations and generated
cross-modal lookup projections replace two independent formula copies. Every
hard gate passed. Review then rejected an eighth proposed name because its body
duplicated `rl.target_rri_reward`; the final source reuses that existing owner.
The post-review evaluator rerun preserved all iteration-3 metrics and reduced
measured non-test LOC by a further 10 lines.

## TODO Disposition

| Surface | Disposition |
| --- | --- |
| Active thesis plain `TODO`/`FIXME`/`HACK` comments | Zero; typed draft markers remain the only thesis action mechanism. |
| Active typed action markers | All have exact agents-DB locators; they remain unresolved until their recorded gates pass. |
| Active Python inline TODOs | Deferred to the owner of `data_handling/offline/inventory.py`; no package behavior changed in this thesis commit. |
| Data-handling README TODO | Deferred with the same package owner. |
| Historical seminar and archive TODOs | Retained as historical evidence, not active thesis work. |
| Prompt and transcript TODO ideas | Evidence only until temporal discount, deduplication, and an explicit agents-DB owner are established. The current transcript exports remain quarantined and untracked. |
| Shared-reference registry gaps | The 195 occurrences require bounded registration or removal in later G008 iterations; no duplicate equation owner was introduced here. |

## Verification

- frozen successor evaluator, append, validate, and report
- generated Typst and Quarto notation lookup projections
- development Typst compile and PDF text inspection
- submission status-marker success and actionable-marker expected failure
- exact agents-DB locator existence checks
- `git diff --check`
