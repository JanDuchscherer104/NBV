---
id: 2026-08-27_admit_repeated_qh_actor_state
date: 2026-08-27
title: "Admit Repeated QH Actor State"
status: done
topics: [performance, qh, vin]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/vin/models/target_finite_horizon.py
  - aria_nbv/tests/vin/test_target_finite_horizon.py
codex_thread: codex://threads/01a043b5-883e-7100-bbc4-06f4f2db8870
repo_object_format: sha1
repo_head: c0d3c9cabbd9bc233b1aac9106f3c95fc7cc144d
repo_branch: "codex/perf-qh-admitted-forward"
worktree_kind: linked
---

## Task
Avoid rebuilding invariant Q_H actor state across repeated candidate-horizon scoring calls.

## Method
Added a typed admitted-actor seam with mutation-aware invalidation and a forward path that accepts already-admitted state.

## Findings
Requested horizons and output finiteness remain call-specific; only actor-visible invariant tensors and transforms are reused.

## Commits
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/c0d3c9cabbd9bc233b1aac9106f3c95fc7cc144d

## Verification
- Ruff over the touched Q_H owner and tests: passed.
- Focused target finite-horizon tests: 60 passed.

## Canonical Owner Impact
The target finite-horizon model now owns the admitted actor-state lifecycle and exact invalidation contract.
