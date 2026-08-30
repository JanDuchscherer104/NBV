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
repo_head: 943c991ab73f480f7a77abecb722976f42325903
repo_branch: "codex/issue-186-thesis-evidence-gates"
worktree_kind: linked
---

## Task
Implement every scientifically and editorially valid suggestion from GitHub issue 186 as an orthogonal four-branch thesis stack based on current `origin/main`.

## Method
Audited the issue against the live base, separated edits by canonical narrative owner, and implemented four cumulative lanes: thesis spine and Foundations; experimental world and measurement validity; selected finite-horizon Method; and evidence stages with result-owned interpretation. Moved implementation registries and unselected hypotheses to explicit development-only owners, regenerated notation and PDF artifacts, and reviewed rendered pages after each lane. A subsequent whole-stack regression audit and same-context scientific-review passes compared every changed submission-facing source with the merge-base. The stack was then rebased onto `origin/main` at `8f35426cabf4b88425f05ed4701ea49ad69f3c9d`, preserving PR #181's candidate-orbit evidence while repairing fifteen accepted narrative, mathematical-notation, executable-template, or integration regressions at their owning layers.

## Findings
- `docs/typst/thesis/sections/01-introduction.typ`, `01-research-questions.typ`, and `02-foundations/` now state RQ2 directly, name the measurement, information, and support conditions without a principal/enabling hierarchy, and develop a relational account of view value.
- `docs/typst/thesis/sections/03-oracle-and-data-generation/` now defines the experimental world through actor/oracle information roles, finite task and action construction, measurement, and evidence lineage; exact storage vocabulary moved to `appendix/index.typ` and the S2 pilot moved to `development/s2-rollout-pilot.typ`.
- `docs/typst/thesis/sections/04-method/` now presents one selected A1--H0--S0 direct-regression method and the epistemic role of exact Q2; unselected carriers, architectures, and objectives moved to `development/method-alternatives.typ`.
- `docs/typst/thesis/sections/05-experimental-design/` through `08-conclusion.typ` now use a seven-stage prerequisite graph without fabricating empirical outcomes. Actor-protocol validity is reportable independently of oracle headroom; explicit false gate decisions retain their own estimates but fail closed for dependent claims. `figures/qh_learning_evidence_loop.typ` owns the consolidated visual claim graph.
- Rendered and scientific review removed a duplicate RQ2 heading and replaced manuscript bookkeeping such as "methodological spine", "executable contracts", "principal research question", "thesis-core configuration", and "artifact-driven report seam" with the scientific distinction each passage needed to carry.
- Current-main integration retained the candidate-orbit pilot as development evidence and its candidate-support estimands in the active analysis, corrected the publication-table inventory to 26, and replaced two newly visible process labels with the actual aggregation populations and estimands.
- The open #189 notation review was resolved scientifically: `norm(v)` remains the scalar norm, while every vector-normalization construction now uses the explicitly defined `normalize(v) = v / ||v||_2` operator already used by the target-frame equations.
- Exact-head CI exposed a layer-specific table-inventory regression hidden by the cumulative final check: PR #190 contains 27 publication tables, while PR #191 intentionally reduces the active inventory to 26. Both stacked layers now assert their own derived count and pass independently.
- Canonical unit-vector notation was added through `docs/typst/shared/equations/action.typ` and `docs/notation.yml`; generated projections and the tracked thesis PDF were regenerated.
- The accepted scientific-review repairs distinguish oracle headroom from learned-control endpoint-gap closure, fail explicitly instead of silently changing the PowerSpherical sampling intervention, align the selected Method with the implemented scorer inputs and joint budget--query support, and require target matching, actor-input identity, leakage, aggregation, uncertainty, and explicit Boolean decisions before RQ3 claims are admitted.
- Final exact-layer review conditioned the `realistic_core_60` radius law on candidate family, replaced a desired pair-gated runtime contract with the literal dense-Q1, diagonal-recursion, horizon-gated implementation boundary, and bound actor matching, Q1 calibration, exact Q2, and endpoint recovery to positive denominators and declared aggregation contracts. Receipt and analysis identities must additionally be canonical SHA-256 digests that resolve to the referenced report sidecars.

## Commits
- [c4f88bacbf70db489309b4b36480e6124dbde8a9](https://github.com/JanDuchscherer104/ARIA-NBV/commit/c4f88bacbf70db489309b4b36480e6124dbde8a9) — final narrative-spine and Foundations layer with the observed-target core gate, exact contribution locators, gap-closure admissibility, and synchronized PDF
- [66d1d5687c25b797f0e839fa21efde73639e456d](https://github.com/JanDuchscherer104/ARIA-NBV/commit/66d1d5687c25b797f0e839fa21efde73639e456d) — final experimental-world layer with explicit sampling-intervention failure semantics, family-conditioned candidate radii, and synchronized PDF
- [bfc8dabcf47e073959d3bf96bb62475e9b64e19c](https://github.com/JanDuchscherer104/ARIA-NBV/commit/bfc8dabcf47e073959d3bf96bb62475e9b64e19c) — final selected finite-horizon Method layer with implementation-faithful inputs, literal deployed horizon support, its 27-table guard, and synchronized PDF
- [943c991ab73f480f7a77abecb722976f42325903](https://github.com/JanDuchscherer104/ARIA-NBV/commit/943c991ab73f480f7a77abecb722976f42325903) — final evidence-stage repair before this debrief, with fail-closed decisions, population-bound actor-protocol evidence, uncertainty-bearing calibration, sidecar-resolved exact Q2 and recovery contracts, and an explicit learned gap-closure estimability rule

## Verification
- `make glossary`: passed with 57 terms, 110 symbols, and 122 equations.
- `make thesis-literature-provenance`: 31 tests passed.
- `make typst-authoring-contract`: 21 tests passed with the current-main publication-table inventory of 26.
- `make thesis-marker-contract`, `make thesis-pdf-ci`, `make thesis-pdf`, and `git diff --check`: passed.
- `make thesis-report-data-contract`: passed, including explicit false-versus-true gate-decision fixtures; focused pose-generation tests passed with the silent sampler fallback removed.
- The regression and scientific-review passes covered every changed submission-facing Typst source against merge-base `fae1b1b08e31978fd16234d1f32f090738ad0403` and current main `8f35426cabf4b88425f05ed4701ea49ad69f3c9d`; fifteen accepted findings were patched and rechecked.
- Rendered-page review covered the changed Chapter 1--8 ranges, the standalone evidence-gate figure, and the preserved candidate-orbit development pages. It found and repaired one duplicate RQ2 heading and two current-main process labels; the repaired 126-page evidence-stage PDF has no clipping, overlap, broken table, unreadable figure, or orphaned chapter page in the affected ranges.
- Submission-mode compilation remained correctly blocked because no explicit confirmatory thesis-data artifact was supplied. The work promotes no empirical-result claim.

## Canonical Owner Impact
All accepted decisions were applied to the exact active Typst, notation, figure, appendix, development-only, and authoring-contract owners listed in `touched_owner_paths`. No further canonical update is required for this workpackage; unresolved empirical gates remain explicit in the active thesis.
