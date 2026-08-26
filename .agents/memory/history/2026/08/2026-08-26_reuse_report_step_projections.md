---
id: 2026-08-26_reuse_report_step_projections
date: 2026-08-26
title: "Reuse report step projections"
status: done
topics: [rollouts, reporting, performance]
confidence: high
canonical_updates_needed:
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/aria_nbv/rollouts/reporting.py
touched_owner_paths:
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/aria_nbv/rollouts/reporting.py
  - aria_nbv/tests/rollouts/test_reporting.py
codex_thread: codex://threads/01a03eda-0ffb-78a3-b1f7-4a6549bbd0bd
repo_object_format: sha1
repo_head: 082a523e4696d5f52bdb8d92875ec505764caf7a
repo_branch: "codex/rollout-report-reuse"
worktree_kind: linked
---

## Task
Reuse the report-owned per-step projection when aggregating rollout-tree rows.

## Method
Added an optional supplied-row path to the existing rollout-tree reducer and
passed the report builder's already materialized step rows through that path.

## Findings
`rollout_tree_summary_rows` previously rebuilt `rollout_step_objective_rows`
while report construction had already obtained the same data. The existing
public reader path remains available for independent callers.

## Commits
- [082a523e4696d5f52bdb8d92875ec505764caf7a](https://github.com/JanDuchscherer104/ARIA-NBV/commit/082a523e4696d5f52bdb8d92875ec505764caf7a)

## Verification
`ruff format --check` and `ruff check` passed for the three touched files.
The targeted report tests passed and include a guard that fails if the tree
reducer performs a second per-step store traversal.

## Canonical Owner Impact
The Python rollout-inspection and reporting owners now share one factual step
projection within report construction; no thesis claim changed.
