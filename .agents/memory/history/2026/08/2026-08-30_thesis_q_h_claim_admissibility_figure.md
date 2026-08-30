---
id: 2026-08-30_thesis_q_h_claim_admissibility_figure
date: 2026-08-30
title: "Thesis Q_H claim-admissibility figure"
status: done
topics: [thesis, typst, figures, q-h, scientific-review]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - docs/typst/thesis/experiment_data.typ
  - docs/typst/thesis/figures/qh_learning_evidence_loop.typ
  - docs/typst/thesis/sections/05-experimental-design/index.typ
  - docs/typst/thesis/sections/06-results.typ
  - docs/typst/thesis/sections/07-discussion.typ
  - docs/typst/thesis/sections/08-conclusion.typ
  - docs/typst/thesis/tests/evidence_gate_state.typ
  - scripts/tests/test_typst_report_data_contract.py
codex_thread: codex://threads/01a04fd9-0c7c-7813-a9c5-dc49f2f867a6
repo_object_format: sha1
repo_head: 9897e0f4709ca9ca3ec9c5933fd0e2de2ba1dccf
repo_branch: "codex/thesis-figure-qh-evidence-gates"
worktree_kind: linked
---

## Task

Replace the serial Q_H evidence-gate diagram and matching thesis interpretation
with a scientifically correct claim-dependency graph that keeps evidence,
decision, and claim admissibility distinct.

## Method

Located the exact Experimental Design and Results owners, froze standalone and
page-size baselines, applied Fletcher and Typst guidance to a bounded DAG,
synchronized the report-data state helpers, rendered color and grayscale
evidence, and iterated independent professor/scientific and student/visual
reviews until zero P0--P2 findings remained.

## Findings

- Measurement and population/action support are shared foundations; oracle
  headroom and actor-visible learned-value evidence are parallel claim paths.
- Endpoint recovery requires admissible headroom and learned-versus-exact
  `Q_2` agreement. A measured non-pass remains reportable and does not suppress
  evidence from the other lane.
- `docs/typst/thesis/experiment_data.typ` now requires exact boolean decision
  passage and derives claim admissibility separately from evidence presence.
- `docs/typst/thesis/figures/qh_learning_evidence_loop.typ` and the Experimental
  Design, Results, Discussion, and Conclusion prose now share this dependency
  model and reader-facing terminology.
- Exact-head Codex review found one valid residual P2: the failure-attribution
  matrix still conflated unavailable headroom evidence with an observed
  negative result. Its six prerequisite rows now distinguish unresolved
  evidence from a measured decision non-pass explicitly.

## Commits

- https://github.com/JanDuchscherer104/ARIA-NBV/commit/9897e0f4709ca9ca3ec9c5933fd0e2de2ba1dccf
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/f1ddfdef8f37c287158fdfa8501a729c2e1089fc

## Verification

Passed `make thesis-pdf`, `make thesis-pdf-ci`,
`make thesis-report-data-contract`, `make typst-authoring-contract` (22 tests),
`make thesis-marker-contract`, Ruff check/format, Python byte compilation, PDF
page-size checks, and `git diff --check`. Exact standalone and embedded renders
were inspected in color and grayscale. Independent exact-candidate scientific
and visual reviews each approved with zero P0--P2 findings.

## Canonical Owner Impact

Current thesis truth now lives in the touched Typst figure, report-data,
Experimental Design, Results, Discussion, and Conclusion owners. The new Typst
fixture and report-data contract test preserve false-decision versus missing-
evidence behavior. No package runtime or experiment artifact was changed.
