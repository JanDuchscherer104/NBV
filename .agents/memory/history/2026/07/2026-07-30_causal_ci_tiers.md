---
id: 2026-07-30_causal_ci_tiers
date: 2026-07-30
title: "Causal CI tiers"
status: done
topics: [ci, github-actions, validation]
confidence: high
canonical_updates_needed: []
---

## Task

Replace the first path-routed CI gate with independently observable causal
validation tiers while preserving the required `Root Verification / ci` check.

## Result

- `.github/ci-impact.toml` is the sole path and additive-label policy owner for
  governance, scientific, package, documentation, and Graphify validation.
- Pull requests validate GitHub's synthetic merge ref while impact selection
  uses a three-dot base/head diff and JSON-encoded labels. Pushes, merge-queue
  checks, and manual runs select every tier.
- Five conditional jobs feed one `if: always()` aggregate. The aggregate rejects
  selected skips and every failure, cancellation, or missing result.
- Shared policy checks have one owner: the impact job runs the Python
  documentation ratchet once per pull request. The scientific tier owns
  `qh-ci`; the package tier owns package smoke plus the lightweight API-doc
  generation contract. Full and overlapping selections therefore compose
  distinct evidence instead of repeating the expensive scientific matrix.

## Verification

- CI selector suite: 23 tests passed.
- Ruff and strict mypy: passed for the selector and tests.
- Governance, scientific, package, documentation, and Graphify tier targets:
  passed. Package validation includes the API-doc generation self-test and
  worktree-local Quartodoc configuration regression.
- Full `make ci`: passed with the pinned Graphify executable and GPU visibility
  disabled to reproduce the CPU-only hosted runner.
- Memory validation, workflow parsing/static contracts, and diff checks: passed.

## Canonical State Impact

None. The change routes verification and does not redefine scientific or
package behavior.
