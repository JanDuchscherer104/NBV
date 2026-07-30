---
id: 2026-07-29_modular_stored_rollout_supervision_redesign
date: 2026-07-29
title: "Modular Stored-Rollout Supervision Redesign"
status: done
topics: [streamlit, stored-rollouts, qh, topology, scientific-audit, rerun]
confidence: high
canonical_updates_needed: []
---

## Task

Redesign stored-rollout supervision as a modular, science-first inspection
surface without absorbing unrelated changes from the dirty worktree.

## Outcome

- Kept the page coordinator and session layer thin across seven sections, with
  shared topology and QH-admission ownership instead of page-local duplicates.
- Added an independent scientific audit, exact matched-cohort oracle headroom,
  validity masks with explicit reasons, and candidate geometry and distribution
  evidence.
- Separated pilot from confirmatory reporting and added rich theory popovers so
  claims, denominators, assumptions, and failure conditions remain visible.
- Retained direct inspection and Rerun launch paths while removing the query and
  promotion workbench.
- Preserved all unrelated dirty-worktree edits.

## Verification

- Scoped Ruff passed; scoped mypy passed for all five checked files.
- Broad pytest passed with `396 passed, 1 skipped`.
- Quartodoc API self-test passed.
- Headless Streamlit started cleanly and was stopped by the bounded timeout.
- `make check-agent-memory` passed.
- Graphify code refresh succeeded; freshness correctly remains nonzero for dirty
  source files and pre-existing pending semantic extraction.
- The anti-slop gate held at 110 tests before and after cleanup. The only
  behavior-preserving follow-up was one clarity-only session control-flow
  change.
- Two independent review cycles found and repaired treatment-hash,
  seed/RNG/checkpoint, candidate-denominator, and default audit-bridge checkpoint
  binding issues.
- Final independent code review returned `APPROVE`; independent architect review
  returned `CLEAR`.

## Canonical state impact

None. The redesign changes read-only inspection and reporting ownership, not
persisted rollout schemas or training semantics.
