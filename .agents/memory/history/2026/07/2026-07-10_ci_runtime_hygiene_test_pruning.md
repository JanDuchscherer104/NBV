---
id: 2026-07-10_ci_runtime_hygiene_test_pruning
date: 2026-07-10
title: "Inert test pruning"
status: done
topics: [test-hygiene]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/tests/data_handling
  - aria_nbv/tests/rendering/test_pytorch3d_renderer.py
  - aria_nbv/tests/test_pose_generation.py
---

## Task

Remove tests that executed no assertions because their subject had been
removed.

## Findings

Two entire test modules and three individual tests unconditionally skipped
because their subject had been removed.

## Outcome

The inert test suites and bodies were deleted; active downloader CLI coverage
remains. Focused pytest and changed-file Ruff checks pass. No canonical state
update is needed.
