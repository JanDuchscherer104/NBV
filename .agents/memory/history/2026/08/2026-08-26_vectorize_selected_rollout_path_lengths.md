---
id: 2026-08-26_vectorize_selected_rollout_path_lengths
date: 2026-08-26
title: "Vectorize selected rollout path lengths"
status: done
topics: [rollouts, inspection, performance]
confidence: high
canonical_updates_needed:
  - aria_nbv/aria_nbv/rollouts/inspection.py
touched_owner_paths:
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/tests/rollouts/test_inspection.py
codex_thread: codex://threads/01a03eda-0ffb-78a3-b1f7-4a6549bbd0bd
repo_object_format: sha1
repo_head: c6fcb1704016f96456a5186cf76833c7adbd58f5
repo_branch: "codex/rollout-selected-path-vectorization"
worktree_kind: linked
---

## Task
Vectorize selected rollout path-length reduction without changing factual path order.

## Method
Filtered selected candidate rows once, mapped them to rollout rows, applied a
stable `(rollout, step, physical-row)` ordering, and reduced root-to-first plus
successive path segments with NumPy arrays.

## Findings
The former reducer scanned every candidate row once per rollout and invoked a
scalar norm for every segment. The new reducer leaves absent selected chains at
zero, ignores orphaned selected rows as before, and retains stable ties.

## Commits
- [c6fcb1704016f96456a5186cf76833c7adbd58f5](https://github.com/JanDuchscherer104/ARIA-NBV/commit/c6fcb1704016f96456a5186cf76833c7adbd58f5)

## Verification
Ruff format and lint passed. Targeted tests passed for the new scalar-equivalence
and empty-table cases and for the report/CLI statistic consumer.

## Canonical Owner Impact
`aria_nbv.rollouts.inspection` retains its existing selected-path statistic
meaning while avoiding repeated whole-table scans; no thesis claim changed.
