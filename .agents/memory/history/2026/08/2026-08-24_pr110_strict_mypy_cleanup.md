---
id: 2026-08-24_pr110_strict_mypy_cleanup
date: 2026-08-24
title: "PR 110 Strict Mypy Cleanup"
status: done
topics: [python, mypy, streamlit, q-h, rollout-inspection]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/AGENTS.md
  - aria_nbv/pyproject.toml
  - aria_nbv/aria_nbv
  - aria_nbv/tests
  - scripts/__init__.py
codex_thread: codex://threads/01a02e4d-39ed-7e43-99e0-6790460a36ff
repo_object_format: sha1
repo_head: 945954d6d3d5d7bb56f4d233a00aacd927ef0f07
repo_branch: codex/pr110-strict-mypy
worktree_kind: linked
---

## Task

Resolve strict mypy failures in every Python file changed by merged PR #110,
without using `object` as an annotation, and publish the cleanup separately
from the already-merged feature PR.

## Method

The cleanup was rebased onto the merge commit on `origin/main` and isolated in
its own worktree. Dynamic boundaries were narrowed with unions, protocols,
`TypedDict` records, generics, or verified third-party `Any`; local repository
scripts received a package marker so mypy follows their implementation instead
of suppressing an untyped import. Behavior regressions exposed by focused tests
were repaired without changing persisted schemas or scientific contracts.

## Verification

- Strict mypy succeeded for all 74 Python files changed by merged PR #110.
- An AST census found zero `object` annotations.
- Ruff format and lint succeeded for all affected Python files.
- The 26 affected package test files passed: 627 tests.
- The affected Quartodoc script test passed: 2 tests.
- Changed modules compiled and both staged and unstaged diffs passed
  `git diff --check`.
- The hosted-CI-equivalent `PYTEST_WORKERS=0 make ruff-full package-smoke`
  passed after refreshing the replay/oracle golden's source-identity seal: 469
  Q_H contract tests and 125 package-smoke tests passed.

## Canonical-state impact

The changes strengthen typing and repository guidance only. Runtime behavior,
persistence formats, scientific projections, and the merged PR #110 feature
surface remain unchanged. The replay/oracle fixture changed only its persisted
SHA-256 for the byte-modified `rollouts/zarr_store.py` source owner.
