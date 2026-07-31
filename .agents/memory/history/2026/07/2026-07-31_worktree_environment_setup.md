---
id: 2026-07-31_worktree_environment_setup
date: 2026-07-31
title: "Worktree Environment Setup"
status: done
topics: [worktrees, developer-environment, shell, testing]
confidence: high
canonical_updates_needed: []
files_touched:
  - .codex/environments/aria-nbv.toml
  - .gitignore
  - scripts/setup_worktree_env.sh
  - scripts/tests/test_setup_worktree_env.sh
---

## Task

Add a selectable Codex Desktop environment and a portable, fail-closed setup
seam for linked ARIA-NBV worktrees without copying the source checkout's
Python runtime or ignored artifacts.

## Method

The tracked `.codex/environments/aria-nbv.toml` passes Codex's source and new
worktree paths to the setup script. The script links the shared virtual
environment, every ignored top-level data cache, and downloaded literature
PDFs; it initializes the worktree's recorded submodules and creates the local
`.env` activation link. Tracked TeX/Bib sources stay Git-owned. The linked
virtual environment is the sole command-runtime owner. Portable path comparison
uses its Python interpreter instead of platform-specific `readlink` flags.
Check mode validates the same runtime, cache, activation, PDF, and submodule
contracts without mutating the worktree.

## Findings

The data and literature parent directories must exist before links are created.
Downloaded PDFs need a non-directory ignore rule so their symlink does not
appear as untracked state. Readiness also depends on `.env`: accepting a missing
activation file would report a worktree ready even though the printed next step
could not succeed. The sandbox regression covers the TOML contract, a fresh
worktree, normal setup, portable path resolution, PDF-link failure, and the
missing-`.env` failure. It also proves that activated commands use the linked
virtual environment without a second mamba environment and that readiness
rejects a missing shared Python interpreter.

## Verification

Shell syntax validation and `scripts/tests/test_setup_worktree_env.sh` exercise
the setup and check paths in an isolated temporary Git repository. Repository
agent-memory validation checks this debrief's schema and links.

## Canonical state impact

No canonical scientific or implementation state changes are needed. The script
and its regression test own this developer-workflow contract.
