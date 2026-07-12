---
id: 2026-07-12_rwp01_evaluated_rollout_ownership
date: 2026-07-12
title: "RWP01 Evaluated Rollout Ownership"
status: done
topics: [oracle, rollouts, persistence, architecture]
confidence: high
canonical_updates_needed: []
---

# RWP01 Evaluated Rollout Ownership

## Scope

Removed the forwarding facade introduced with the pipeline-local evaluated
rollout aggregate while preserving replay, Oracle, panel, and Zarr behavior.

## Changes

- Reduced `EvaluatedRolloutStep` to `transition` plus `evaluation`.
- Removed all forwarding properties from `EvaluatedRolloutStep` and all writer
  convenience methods from `EvaluatedRolloutRecord`.
- Made the Zarr writer input protocol private and kept lineage composition at
  the writer boundary.
- Migrated Streamlit, rollout generation, persistence, tests, and fixtures to
  the explicit nested owners.

## Verification

- Ruff format/check and Python compilation passed for touched files.
- `171` Oracle, rollout, Streamlit, Rerun, and dispatcher tests passed.
- `EvaluatedRolloutStep` has exactly two dataclass fields and no properties.
- Production Python LOC decreased from `68,600` to `68,440`.
- Graphify refreshed; `git diff --check` passed.

## Canonical Updates Needed

- None. This is the corrective RWP01 package already specified by the
  replacement module-pruning plan.
