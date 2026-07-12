---
id: 2026-07-12_rwp02_target_dto_collapse
date: 2026-07-12
title: "RWP02 Target DTO Collapse"
status: done
topics: [oracle, targets, rollouts, persistence, architecture]
confidence: high
canonical_updates_needed: []
---

# RWP02 Target DTO Collapse

## Scope

Collapsed the Oracle target-task handoff to `TargetDescriptor` plus one
producer-owned `OracleTargetTask`. Persistence-only compatibility fields remain
writer-owned and the rollout Zarr schema is unchanged.

## Changes

- Renamed and pruned `OracleTargetTaskRow` to `OracleTargetTask`.
- Deleted `TargetCandidateRow` and the task-to-candidate-to-descriptor adapter
  round trip.
- Kept semantic and geometric actor inputs in `TargetDescriptor` while Oracle
  identity, source, confidence, and sampling fields remain on the task.
- Moved frozen target-column sentinel and reason-code encoding to the rollout
  dataset writer boundary.
- Simplified the Streamlit target audit to fields that the domain task actually
  owns.

## Verification

- Ruff format/check and Python compilation passed for touched files.
- `169` target, Oracle, rollout, Zarr, Streamlit, config, and public-contract
  tests passed in one focused run.
- A deterministic before/after rollout fixture matched exactly across all
  `193` arrays, including shape, dtype, values, and NaN placement. The fresh
  store passed public validation; only generation timestamp and derived
  manifest hash differed.
- Production Python LOC decreased from `68,440` to `68,030`, excluding the
  unrelated user-owned `rollouts/inspection.py` drift.
- Graphify refreshed; stale Python symbol scans and `git diff --check` passed.

## Canonical Updates Needed

- None. This is RWP02 from the replacement module-pruning plan.
