---
id: 2026-08-25_ci_pinned_uv_bootstrap_contract
date: 2026-08-25
title: "CI pinned uv bootstrap contract"
status: done
topics: [ci, scaffold, verification]
confidence: high
canonical_updates_needed:
  - .github/workflows/ci.yml
  - scripts/tests/test_ci_impact.py
touched_owner_paths:
  - .github/workflows/ci.yml
  - scripts/tests/test_ci_impact.py
repo_object_format: sha1
repo_head: 40e9c39734139b2d04378999886f7c408ae7d34e
repo_branch: "codex/pr109-academic-scaffold-salvage"
worktree_kind: linked
codex_thread: codex://threads/01a02ab6-c75e-7313-be12-e5f90ae0cde3
---

## Task

Repair the Root Verification failure introduced when CI replaced the stalled
`setup-uv` action with an exact pip-installed `uv` bootstrap.

## Findings

The first failure was in the CI topology regression, not the bootstrap command:
it still required the removed `astral-sh/setup-uv` action and its cache
settings. The next hosted run installed `uv==0.12.5` correctly, but invoked a
preinstalled older `uv` found earlier on `PATH`. The active workflow now calls
the exact pip-installed module through `python -m uv` for both version proof
and environment synchronization.

## Verification

- `make ci-impact-self-test PYTHON_INTERPRETER=python3` — 14 tests passed.
- Parsed `.github/workflows/ci.yml` and asserted the package-only bootstrap,
  interpreter-bound exact pinned version, module-based sync, and absence of a
  `uses` action.
- `git diff --check` — passed.

## Canonical Owner Impact

The CI workflow remains the executable owner; its topology regression now
locks the intentional pinned-pip bootstrap rather than the retired action.

## Commits

- [6621b463ba55a905c91d61a432eb85a72bca8834](https://github.com/JanDuchscherer104/ARIA-NBV/commit/6621b463ba55a905c91d61a432eb85a72bca8834) — test: lock pinned uv bootstrap
- [40e9c39734139b2d04378999886f7c408ae7d34e](https://github.com/JanDuchscherer104/ARIA-NBV/commit/40e9c39734139b2d04378999886f7c408ae7d34e) — implementation: bind uv commands to pinned module
