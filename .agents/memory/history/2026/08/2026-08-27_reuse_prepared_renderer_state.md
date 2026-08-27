---
id: 2026-08-27_reuse_prepared_renderer_state
date: 2026-08-27
title: "Reuse Prepared Renderer State"
status: done
topics: [performance, rendering, geometry]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/rendering
  - aria_nbv/tests/rendering
codex_thread: codex://threads/01a043b5-883e-7100-bbc4-06f4f2db8870
repo_object_format: sha1
repo_head: 6b932d7f8869d41eae9e7e8aa25c522e1e129020
repo_branch: "codex/perf-rendering-context"
worktree_kind: linked
---

## Task
Remove repeated renderer, ray-grid, and unprojection setup from candidate rendering hot paths.

## Method
Added mutation-aware renderer preparation, cached camera ray and pixel grids, reused Trimesh ray engines, and filtered candidate rows before transfer.

## Findings
The rendering owners now reuse static mesh and camera state while preserving candidate-specific poses, rasterization, and visibility results.

## Commits
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/6b932d7f8869d41eae9e7e8aa25c522e1e129020

## Verification
- Ruff over the touched renderer owners: passed.
- Focused rendering tests: 14 passed, 1 skipped.

## Canonical Owner Impact
The rendering package and focused tests now own static renderer-state reuse and invalidation.
