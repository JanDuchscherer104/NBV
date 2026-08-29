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
repo_head: 909e980c9b355ae4c3a4bb35c0f66eb8e1c945a0
repo_branch: "codex/issue-186-thesis-evidence-gates"
worktree_kind: linked
---

## Task
Implement every scientifically and editorially valid suggestion from GitHub issue 186 as an orthogonal four-branch thesis stack based on `origin/main`.

## Method
Audited the issue against the live base, separated edits by canonical narrative owner, and implemented four cumulative lanes: thesis spine and Foundations; experimental world and measurement validity; selected finite-horizon Method; and evidence gates with result-owned interpretation. Moved implementation registries and unselected hypotheses to explicit development-only owners, regenerated notation and PDF artifacts, and reviewed rendered pages after each lane.

## Findings
- `docs/typst/thesis/sections/01-introduction.typ`, `01-research-questions.typ`, and `02-foundations/` now establish a conditional core evaluation, its validity conditions, and a relational account of view value.
- `docs/typst/thesis/sections/03-oracle-and-data-generation/` now defines the experimental world through actor/oracle information roles, finite task and action construction, measurement, and evidence lineage; exact storage vocabulary moved to `appendix/index.typ` and the S2 pilot moved to `development/s2-rollout-pilot.typ`.
- `docs/typst/thesis/sections/04-method/` now presents one selected A1--H0--S0 direct-regression method and the epistemic role of exact Q2; unselected carriers, architectures, and objectives moved to `development/method-alternatives.typ`.
- `docs/typst/thesis/sections/05-experimental-design/` through `08-conclusion.typ` now use six ordered gates, gate-owned result fields, and first-failure attribution without fabricating empirical outcomes. `figures/qh_learning_evidence_loop.typ` owns the consolidated visual claim path.
- Canonical unit-vector notation was added through `docs/typst/shared/equations/action.typ` and `docs/notation.yml`; generated projections and the tracked thesis PDF were regenerated.

## Commits
- [15e2b2c5b18cb632613d4d333a8df0d42f921777](https://github.com/JanDuchscherer104/ARIA-NBV/commit/15e2b2c5b18cb632613d4d333a8df0d42f921777) — narrative spine and Foundations
- [14fbbd812f1bc8bfc573b57f83b774739b50e821](https://github.com/JanDuchscherer104/ARIA-NBV/commit/14fbbd812f1bc8bfc573b57f83b774739b50e821) — representation trade-offs and review refinements
- [7acb753409681feb1002de71b24f1a10698bfc50](https://github.com/JanDuchscherer104/ARIA-NBV/commit/7acb753409681feb1002de71b24f1a10698bfc50) — direct core-evaluation framing
- [49800c64dca7de9e5647e118dbccb8eea16ee101](https://github.com/JanDuchscherer104/ARIA-NBV/commit/49800c64dca7de9e5647e118dbccb8eea16ee101) — experimental world and measurement contract
- [52c04dcdf55dbb04b8783e271c579118c6b5b9fd](https://github.com/JanDuchscherer104/ARIA-NBV/commit/52c04dcdf55dbb04b8783e271c579118c6b5b9fd) — measurement-owner wording and live Graphify projection compatibility
- [917a9841b30ab195f7d8299beed6565eeab6f970](https://github.com/JanDuchscherer104/ARIA-NBV/commit/917a9841b30ab195f7d8299beed6565eeab6f970) — selected finite-horizon method
- [909e980c9b355ae4c3a4bb35c0f66eb8e1c945a0](https://github.com/JanDuchscherer104/ARIA-NBV/commit/909e980c9b355ae4c3a4bb35c0f66eb8e1c945a0) — evidence gates, results, discussion, conclusion, and regenerated PDF

## Verification
- `make glossary`: passed with 57 terms, 110 symbols, and 113 equations.
- `make thesis-literature-provenance`: 31 tests passed.
- `make typst-authoring-contract`: 21 tests passed after updating the intentional publication-table inventory from 29 to 25 across the stack.
- `make thesis-marker-contract`, `make thesis-pdf-ci`, `make thesis-pdf`, and `git diff --check`: passed.
- Rendered-page review covered the changed Chapter 1--8 ranges and the standalone evidence-gate figure; no clipping or orphaned chapter page remained.
- Submission-mode compilation remained correctly blocked because no explicit confirmatory thesis-data artifact was supplied. The work promotes no empirical-result claim.

## Canonical Owner Impact
All accepted decisions were applied to the exact active Typst, notation, figure, appendix, development-only, and authoring-contract owners listed in `touched_owner_paths`. No further canonical update is required for this workpackage; unresolved empirical gates remain explicit in the active thesis.
