---
id: 2026-08-27_cache_prepared_rri_geometry
date: 2026-08-27
title: "Cache Prepared RRI Geometry"
status: done
topics: [performance, rri, geometry]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/geometry
  - aria_nbv/aria_nbv/rri_metrics
  - aria_nbv/tests/rri_metrics
codex_thread: codex://threads/01a043b5-883e-7100-bbc4-06f4f2db8870
repo_object_format: sha1
repo_head: 7c40885a176e4f71af41afe5b3ecf1675c73ba51
repo_branch: "codex/perf-prepared-rri"
worktree_kind: linked
---

## Task
Reuse target geometry, crop state, and reference distances across repeated RRI candidate scoring.

## Method
Moved the shared point-to-mesh query into the geometry owner, added mutation-aware request reuse, and bounded candidate mesh evaluation in explicit chunks.

## Findings
`aria_nbv/aria_nbv/rri_metrics/prepared.py` now owns device- and dtype-aware prepared target state while candidate-dependent geometry remains evaluated on each call.

## Commits
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/7c40885a176e4f71af41afe5b3ecf1675c73ba51

## Verification
- Ruff over pose-generation, geometry, RRI, oracle, and rollout owners: passed.
- Focused pose/RRI/oracle/rollout tests: 73 passed, 1 skipped.

## Canonical Owner Impact
The shared geometry query and RRI prepared-state owners now define cache invalidation, batching, and reuse contracts.
