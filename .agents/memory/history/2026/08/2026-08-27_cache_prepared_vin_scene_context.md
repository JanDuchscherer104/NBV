---
id: 2026-08-27_cache_prepared_vin_scene_context
date: 2026-08-27
title: "Cache Prepared VIN Scene Context"
status: done
topics: [performance, vin, inference]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/vin/models/scene_myopic.py
  - aria_nbv/tests/vin/test_vin_model_v3_core.py
codex_thread: codex://threads/01a043b5-883e-7100-bbc4-06f4f2db8870
repo_object_format: sha1
repo_head: aa63c28c943efc0db77b8a977476126aa47537fc
repo_branch: "codex/perf-vin-scene-context"
worktree_kind: linked
---

## Task
Reuse invariant VIN scene inference state across repeated candidate scoring calls.

## Method
Added an evaluation-only, no-grad prepared scene context keyed by input tensor identity/version and model parameter versions.

## Findings
VIN conversion, scene fields, pooled voxels, and static semidense tensors are reused; candidate-dependent computation remains per call and caches clear on mode transition.

## Commits
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/aa63c28c943efc0db77b8a977476126aa47537fc

## Verification
- Ruff over the touched VIN owner and tests: passed.
- Focused VIN core and method tests: 36 passed.

## Canonical Owner Impact
The scene-myopic model now owns the prepared inference-context lifecycle and invalidation rules.
