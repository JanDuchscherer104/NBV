---
id: 2026-08-27_reuse_static_sample_geometry
date: 2026-08-27
title: "Reuse Static Sample Geometry"
status: done
topics: [performance, rendering, oracle]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/rendering
  - aria_nbv/aria_nbv/oracle
  - aria_nbv/tests/rendering
codex_thread: codex://threads/01a043b5-883e-7100-bbc4-06f4f2db8870
repo_object_format: sha1
repo_head: 185e6fe58a7803278860a83d43d4b058c6107d73
repo_branch: "codex/perf-static-sample-geometry"
worktree_kind: linked
---

## Task
Prepare static semidense sample geometry once for repeated candidate point-cloud construction and scoring.

## Method
Introduced a typed prepared sample geometry object and cached it per device and dtype in the candidate RRI scoring engine.

## Findings
Static semidense collapse, lengths, and bounds are reused, while candidate-dependent camera bounds and transformed observations remain on the hot path.

## Commits
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/6170bf4b9f9df41462618d5d23f0506c9c52d5dc
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/37f7b93b39920432a1d9a7ed44b63845313d75bd

## Verification
- Ruff over rendering and oracle owners: passed.
- Focused rendering/oracle tests: 60 passed, 1 skipped.

## Canonical Owner Impact
Rendering and candidate-scoring owners now define prepared static sample geometry and its reuse boundary.
