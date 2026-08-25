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
repo_head: 4c43acd32e9738cf9198afe5a48e86add3c2b19d
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
and environment synchronization. The version proof accepts uv's documented
platform suffix while rejecting any other semantic version.

## Verification

- `make ci-impact-self-test PYTHON_INTERPRETER=python3` — 14 tests passed.
- Parsed `.github/workflows/ci.yml` and asserted the package-only bootstrap,
  interpreter-bound exact pinned version, module-based sync, and absence of a
  `uses` action.
- Checked the shell predicate against both supported `uv 0.12.5` forms and a
  mismatched `uv 0.12.6` version.
- `git diff --check` — passed.

## Canonical Owner Impact

The CI workflow remains the executable owner; its topology regression now
locks the intentional pinned-pip bootstrap rather than the retired action.
The root Makefile exposes the same interpreter-bound command through `UV`, so
the package-validation gate cannot silently fall back to an older runner `uv`.

## Commits

- [6621b463ba55a905c91d61a432eb85a72bca8834](https://github.com/JanDuchscherer104/ARIA-NBV/commit/6621b463ba55a905c91d61a432eb85a72bca8834) — test: lock pinned uv bootstrap
- [40e9c39734139b2d04378999886f7c408ae7d34e](https://github.com/JanDuchscherer104/ARIA-NBV/commit/40e9c39734139b2d04378999886f7c408ae7d34e) — implementation: bind uv commands to pinned module
- [47e67f352834c634ab45759edc5e54e4d5198f65](https://github.com/JanDuchscherer104/ARIA-NBV/commit/47e67f352834c634ab45759edc5e54e4d5198f65) — implementation: accept uv platform version suffix
- [4c43acd32e9738cf9198afe5a48e86add3c2b19d](https://github.com/JanDuchscherer104/ARIA-NBV/commit/4c43acd32e9738cf9198afe5a48e86add3c2b19d) — implementation: propagate the pinned module through package validation
