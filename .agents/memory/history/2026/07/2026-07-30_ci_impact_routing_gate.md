---
id: 2026-07-30_ci_impact_routing_gate
date: 2026-07-30
title: "CI impact routing gate"
status: done
topics: [ci, github-actions, validation]
confidence: high
canonical_updates_needed: []
---

## Task

Reduce unrelated pull-request CI work without weakening validation or changing
the existing required-check identity.

## Method

Replaced the workflow-level PR path filter with a tested, fail-closed impact
selector and conditional steps inside the existing `Root Verification / ci`
job. Reused the existing Make targets and added no dependency or build system.

## Findings

- `scripts/ci_impact.py` owns four validation families and selects all of them
  for shared, unknown, or mixed known/unknown diffs.
- `scripts/tests/test_ci_impact.py` locks the selection matrix and required-check
  identity.
- `.github/workflows/ci.yml` now always reports the PR check while conditionally
  installing and running only affected validation families.
- `Makefile` exposes the selector regression suite as `ci-impact-self-test`.

## Verification

- `make ci-impact-self-test PYTHON_INTERPRETER=python3`: passed (9 tests),
  including a cross-family rename producer regression.
- Ruff format/check for both Python files: passed.
- Parsed `.github/workflows/ci.yml` with PyYAML and asserted the workflow name,
  unfiltered PR trigger, permissions, and sole `ci` job: passed.
- `make agents-db-validate check-agent-memory PYTHON_INTERPRETER=python3`:
  passed.
- Hosted GitHub Actions: pending publication at debrief creation time.

## Canonical State Impact

None. This changes CI routing, not scientific or repository-domain truth.
