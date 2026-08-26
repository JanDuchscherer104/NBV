---
id: 2026-08-26_cache_rollout_candidate_shell_index
date: 2026-08-26
title: "Cache rollout candidate shell index"
status: done
topics: [rollouts, zarr, performance]
confidence: high
canonical_updates_needed:
  - aria_nbv/aria_nbv/rollouts/zarr_store.py
  - aria_nbv/aria_nbv/rollouts/read_model.py
touched_owner_paths:
  - aria_nbv/aria_nbv/rollouts/zarr_store.py
  - aria_nbv/aria_nbv/rollouts/read_model.py
  - aria_nbv/tests/rollouts/test_read_model.py
codex_thread: codex://threads/01a03eda-0ffb-78a3-b1f7-4a6549bbd0bd
repo_object_format: sha1
repo_head: a56db795875e92c3bf16ff3d3f674a876928dcb2
repo_branch: "codex/rollout-shell-index-cache"
worktree_kind: linked
---

## Task
Cache immutable candidate-shell lookup metadata within one rollout-store reader.

## Method
Built a reader-local shell-ordered index keyed by persisted step row id and
routed repeated `rollout_steps` projections through it.

## Findings
The cache preserves candidate ids and shell order while removing repeated
whole-table candidate metadata reads for the same reader instance.

## Commits
- [a56db79587431170ca3295d4ea30e0f652d5a2df](https://github.com/JanDuchscherer104/ARIA-NBV/commit/a56db79587431170ca3295d4ea30e0f652d5a2df)

## Verification
Ruff format and lint passed. The full read-model suite passed (12 tests),
including a regression proving repeated projections read each indexed array once.

## Canonical Owner Impact
The read-only Zarr and read-model owners now share an in-memory index only; no
persisted schema or thesis claim changed.
