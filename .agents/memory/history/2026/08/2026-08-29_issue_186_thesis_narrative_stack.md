---
id: 2026-08-29_issue_186_thesis_narrative_stack
date: 2026-08-29
title: "Issue 186 Thesis Narrative Stack"
status: done
topics: [thesis, typst, narrative, evidence-gates, issue-186]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - docs/typst/thesis/sections/
  - docs/typst/thesis/development/
  - docs/typst/thesis/appendix/index.typ
  - docs/typst/thesis/figures/qh_learning_evidence_loop.typ
  - docs/typst/thesis/main.typ
  - docs/typst/shared/equations.typ
  - docs/typst/shared/equations/action.typ
  - docs/notation.yml
  - scripts/tests/test_typst_authoring_hygiene.py
codex_thread: codex://threads/01a04e7a-ee77-7950-909c-61d1e1cb45b4
repo_object_format: sha1
repo_head: ded1dd2ab542114cc3b98e4615259dca9f2f79e5
repo_branch: "codex/issue-186-thesis-evidence-gates"
worktree_kind: linked
---

## Task
Implement every scientifically and editorially valid suggestion from GitHub issue 186 as an orthogonal four-branch thesis stack based on `origin/main`.

## Method
Audited the issue against the live base, separated edits by canonical narrative owner, and implemented four cumulative lanes: thesis spine and Foundations; experimental world and measurement validity; selected finite-horizon Method; and evidence stages with result-owned interpretation. Moved implementation registries and unselected hypotheses to explicit development-only owners, regenerated notation and PDF artifacts, and reviewed rendered pages after each lane. A subsequent whole-stack regression audit compared every changed submission-facing source with the merge-base, repaired nine accepted narrative or executable-template regressions at their owning layers, and restacked all descendants.

## Findings
- `docs/typst/thesis/sections/01-introduction.typ`, `01-research-questions.typ`, and `02-foundations/` now state RQ2 directly, name the measurement, information, and support conditions without a principal/enabling hierarchy, and develop a relational account of view value.
- `docs/typst/thesis/sections/03-oracle-and-data-generation/` now defines the experimental world through actor/oracle information roles, finite task and action construction, measurement, and evidence lineage; exact storage vocabulary moved to `appendix/index.typ` and the S2 pilot moved to `development/s2-rollout-pilot.typ`.
- `docs/typst/thesis/sections/04-method/` now presents one selected A1--H0--S0 direct-regression method and the epistemic role of exact Q2; unselected carriers, architectures, and objectives moved to `development/method-alternatives.typ`.
- `docs/typst/thesis/sections/05-experimental-design/` through `08-conclusion.typ` now use six ordered inferential stages and first-failure attribution without fabricating empirical outcomes. The Results availability predicates keep measurement independent of population support, and `figures/qh_learning_evidence_loop.typ` owns the consolidated visual claim path.
- Rendered review removed a duplicate RQ2 heading and replaced manuscript bookkeeping such as "methodological spine", "executable contracts", and "principal research question" with the scientific distinction each passage needed to carry.
- Canonical unit-vector notation was added through `docs/typst/shared/equations/action.typ` and `docs/notation.yml`; generated projections and the tracked thesis PDF were regenerated.

## Commits
- [c783ae4700031e972e2947c254131c805013f5ec](https://github.com/JanDuchscherer104/ARIA-NBV/commit/c783ae4700031e972e2947c254131c805013f5ec) — final narrative-spine and Foundations layer
- [28f09958df9f1443ba091ee5712436234f01bb5d](https://github.com/JanDuchscherer104/ARIA-NBV/commit/28f09958df9f1443ba091ee5712436234f01bb5d) — final experimental-world and measurement layer
- [a2dec57ab4ec022050c58c0feb562570eb08c2b5](https://github.com/JanDuchscherer104/ARIA-NBV/commit/a2dec57ab4ec022050c58c0feb562570eb08c2b5) — final selected finite-horizon Method layer
- [ded1dd2ab542114cc3b98e4615259dca9f2f79e5](https://github.com/JanDuchscherer104/ARIA-NBV/commit/ded1dd2ab542114cc3b98e4615259dca9f2f79e5) — final evidence-stage, Conclusion, and rendered-PDF layer

## Verification
- `make glossary`: passed with 57 terms, 110 symbols, and 113 equations.
- `make thesis-literature-provenance`: 31 tests passed.
- `make typst-authoring-contract`: 21 tests passed after updating the intentional publication-table inventory from 29 to 25 across the stack.
- `make thesis-marker-contract`, `make thesis-pdf-ci`, `make thesis-pdf`, and `git diff --check`: passed.
- The regression audit reviewed every changed submission-facing Typst source against merge-base `fae1b1b08e31978fd16234d1f32f090738ad0403`; nine accepted findings were patched and rechecked.
- Rendered-page review covered the changed Chapter 1--8 ranges and the standalone evidence-gate figure. It found and repaired one duplicate RQ2 heading; the final 114-page PDF has no clipping, overlap, broken table, unreadable figure, or orphaned chapter page in the affected ranges.
- Submission-mode compilation remained correctly blocked because no explicit confirmatory thesis-data artifact was supplied. The work promotes no empirical-result claim.

## Canonical Owner Impact
All accepted decisions were applied to the exact active Typst, notation, figure, appendix, development-only, and authoring-contract owners listed in `touched_owner_paths`. No further canonical update is required for this workpackage; unresolved empirical gates remain explicit in the active thesis.
