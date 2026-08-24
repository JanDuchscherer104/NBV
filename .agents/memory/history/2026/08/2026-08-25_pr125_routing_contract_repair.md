---
id: 2026-08-25_pr125_routing_contract_repair
date: 2026-08-25
title: "PR 125 workspace-write routing contract repair"
status: done
topics: [scaffold, routing, verification]
confidence: high
canonical_updates_needed:
  - scripts/scaffold/run_routing_trials.py
  - scripts/tests/test_routing_trials.py
touched_owner_paths:
  - scripts/scaffold/run_routing_trials.py
  - scripts/tests/test_routing_trials.py
repo_object_format: sha1
repo_head: b0fc077ef841d5e2effa2c54948d02cfef39517a
repo_branch: "codex/pr109-academic-scaffold-salvage"
worktree_kind: linked
codex_thread: codex://threads/01a02ab6-c75e-7313-be12-e5f90ae0cde3
---

## Task

Repair PR #125's workspace-write routing completion predicate after review
found that prefix-only fixture contracts could not pass despite satisfying their
declared containment contract.

## Findings

Workspace-write trials require every changed path to remain inside a declared
prefix and require evidence of the required proof. Exact changed paths are an
optional additional constraint, not a universal prerequisite. The previous
predicate incorrectly required a non-empty exact-path list, making valid
prefix-only fixtures impossible to pass. It also did not check declared exact
paths when they were present.

## Verification

- `uv run --no-project --with pytest --with ruff pytest -q scripts/tests/test_routing_trials.py scripts/tests/test_ci_impact.py` — 95 tests and 57 subtests passed.
- `uv run --no-project --with ruff ruff check scripts/scaffold/run_routing_trials.py scripts/tests/test_routing_trials.py` — passed.
- `make scaffold-audit scaffold-audit-self-test ci-impact-self-test PYTHON_INTERPRETER=python3` — passed.
- `git diff --check` — passed.
- Added fixture-wide coverage proving each workspace-write fixture has an attainable terminal contract, plus a negative exact-path regression.

## Canonical Owner Impact

The routing runner remains the single executable owner of workspace-write
completion. Fixture declarations can now use prefixes alone, while declarations
that include exact paths are enforced as a strict subset of the observed diff.

## Commits

- [b0fc077ef841d5e2effa2c54948d02cfef39517a](https://github.com/JanDuchscherer104/ARIA-NBV/commit/b0fc077ef841d5e2effa2c54948d02cfef39517a) — implementation: satisfy prefix-only routing contracts
