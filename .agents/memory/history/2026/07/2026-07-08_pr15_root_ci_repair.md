---
id: 2026-07-08_pr15_root_ci_repair
date: 2026-07-08
title: "PR15 Root CI Repair"
status: done
topics: [pr15, ci, dependencies, rollouts, vin]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/pyproject.toml
  - aria_nbv/uv.lock
  - Makefile
  - aria_nbv/aria_nbv/vin/scorer_context.py
---

## Task

Repaired the failing Root Verification workflow for PR15 on the
`codex/rollout-diverse-metrics-models` branch while preserving unrelated dirty
worktree edits.

## Changes

- Moved `openpoints-shim` out of the default Linux dependency set and into the
  optional `pointnext` extra so package-smoke CI no longer builds the inactive
  PointNeXt integration by default.
- Updated package-smoke rollout paths from the stale
  `tests/pose_generation/test_counterfactuals.py` location to
  `tests/rollouts/test_counterfactuals.py`.
- Removed the runtime `vin/scorer_context.py` dependency on private
  `data_handling._raw` imports. Trajectory extraction now uses structural
  access to direct `t_world_rig` or nested `trajectory.t_world_rig`.

## Verification

- Local static checks passed for the final VIN patch:
  `uvx ruff format --check aria_nbv/aria_nbv/vin/scorer_context.py`,
  `uvx ruff check aria_nbv/aria_nbv/vin/scorer_context.py`, `git diff --check`,
  AST parsing, and a local reproduction of the public API import-contract scan.
- GitHub Root Verification workflow run `28942491174` passed on head
  `f803eefc84602eeb9417c104b9b477ca83df4bae`: agents DB validation passed,
  agent memory validation passed, ruff passed, and package-smoke pytest reported
  81 passed tests.

## Notes

The local `uv run --extra dev` validation path remained impractical in this
worktree because it repeatedly entered the slow local `pytorch3d` build. The
clean GitHub runner completed that package build and the root CI contract.
