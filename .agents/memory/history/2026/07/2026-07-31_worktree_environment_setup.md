---
id: 2026-07-31_worktree_environment_setup
date: 2026-07-31
title: "Worktree Environment Setup"
status: done
topics: [worktrees, developer-environment, shell, testing]
confidence: high
canonical_updates_needed: []
files_touched:
  - scripts/setup_worktree_env.sh
  - scripts/tests/test_setup_worktree_env.sh
---

## Task

Add a portable, fail-closed setup seam for linked ARIA-NBV worktrees without
copying the primary checkout's Python runtime or generated data cache.

## Method

The setup script links the shared virtual environment and available cache
directories, initializes the worktree's recorded submodules, and creates the
local `.env` activation link. Portable path comparison uses the shared Python
runtime instead of platform-specific `readlink` flags. Check mode validates the
same runtime, cache, activation, and submodule contracts without mutating the
worktree.

## Findings

The data-directory parent must exist before cache links are created. Readiness
also depends on `.env`: accepting a missing activation file would report a
worktree ready even though the printed next step could not succeed. The sandbox
regression covers a fresh worktree, normal setup, portable path resolution, and
the missing-`.env` failure.

## Verification

Shell syntax validation and `scripts/tests/test_setup_worktree_env.sh` exercise
the setup and check paths in an isolated temporary Git repository. Repository
agent-memory validation checks this debrief's schema and links.

## Canonical state impact

No canonical scientific or implementation state changes are needed. The script
and its regression test own this developer-workflow contract.
