---
id: 2026-07-10_module_pruning_plan_revision_autoresearch
date: 2026-07-10
title: "ARIA-NBV Module Pruning Plan Revision Autoresearch"
status: done
topics: [aria-nbv, architecture, oracle, rollouts, rri-metrics, data-handling]
confidence: high
canonical_updates_needed: []
artifacts:
  - .omx/specs/autoresearch-aria-nbv-module-pruning-revision-20260710/report.md
---

# ARIA-NBV Module-Pruning Plan Revision

## Outcome

Re-audited the 2026-07-09 module-pruning report and latest draft execution plan
against current `rri_metrics`, `rollouts`, `pipelines`, and `data_handling`
source. The draft remains blocked before RALPLAN because file moves do not
resolve formula duplication, scorer/replay DTO coupling, or the concrete
data-handling/oracle composition cycle.

## Durable Artifact

- `.omx/specs/autoresearch-aria-nbv-module-pruning-revision-20260710/report.md`

## Key New Evidence

- `data_handling` constructs concrete oracle labelers while the labeler imports
  data-handling views; the root currently relies on import order.
- `rri_metrics/metrics/torchmetrics_multi.py` is 692 LOC with test/barrel
  consumers only.
- Lightning logging policy and rendering-heavy plotting remain misplaced under
  `rri_metrics`.
- current public-contract tests encode old ownership and cannot by themselves
  justify compatibility shells.

## Validation

- Graphify relationship and path queries
- deterministic source/import/LOC scans
- independent Explore and code-review lanes
- independent architect verdict: APPROVED, no material findings
- make check-agent-memory
- git diff --check over the durable artifacts
- reconciled both session-local autoresearch state files after a Codex App
  session rotation; both record inactive, complete, and approved

## canonical_updates_needed

- Update package `AGENTS.md` files only when the implementation lands.
- Update the current `.omx` execution plan status after architect validation.
- Derive a new RALPLAN only after the report's decision gates are closed.
