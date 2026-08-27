---
id: 2026-08-27_reuse_prepared_pose_geometry
date: 2026-08-27
title: "Reuse Prepared Pose Geometry"
status: done
topics: [performance, pose-generation, geometry]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/pose_generation
  - aria_nbv/tests/pose_generation
codex_thread: codex://threads/01a043b5-883e-7100-bbc4-06f4f2db8870
repo_object_format: sha1
repo_head: 6d1300e824c06b3eb95ce18f12453093d47cafe2
repo_branch: "codex/perf-prepared-geometry"
worktree_kind: linked
---

## Task
Eliminate repeated mesh conversion and query-engine construction during candidate pose generation.

## Method
Prepared immutable mesh-query state once per generation request and threaded it through samplers, builders, rules, and mixture components.

## Findings
`aria_nbv/aria_nbv/pose_generation/geometry.py` now owns reusable PyTorch3D triangles plus Trimesh proximity and ray adapters. Empty eligible candidate sets return before downstream geometry work.

## Commits
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/6d1300e824c06b3eb95ce18f12453093d47cafe2

## Verification
- Ruff over the touched pose-generation owners: passed.
- Focused pose-generation tests: 26 passed, 1 skipped.

## Canonical Owner Impact
The pose-generation geometry owners and their focused tests now define request-scoped mesh preparation and reuse.
