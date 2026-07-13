---
id: 2026-07-13_g001_rerun_rollout_read_model
date: 2026-07-13
title: "G001 Rerun Rollout Read-Model Migration"
status: done
topics: [rollouts, rerun, read-model, simplification]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/rollouts/read_model.py
  - aria_nbv/aria_nbv/rerun_inspector/_rollout_zarr.py
  - aria_nbv/tests/rollouts/test_read_model.py
  - aria_nbv/tests/rerun_inspector/test_rollout_zarr_logger.py
artifacts:
  - .omx/plans/ralplan-aria-nbv-module-pruning-resume-20260713.md
---

## Task

Migrate the Rerun rollout-store adapter to the shared store-semantic read model,
delete duplicate Zarr interpretation, and retain all entities, transforms,
colors, plots, and display payloads in the Rerun owner.

## Outcome

- Replaced the Rerun-local selected-rollout wrapper with `StoredRollout` and
  consumed shared rollout, step, target, and selected-depth projections.
- Added persisted `target_center_world` to `StoredTarget`; the Rerun target
  overlay no longer infers that field from object-pose translation.
- Reused `candidate_policy_entropy` from rollout audits.
- Deleted 17 top-level Rerun symbols covering duplicate row resolution,
  dictionaries, candidate-step joins, target lookup, optional scalars, selected
  depth, entropy, and reason/component decoding.
- Preserved the exact eight-symbol rollout root, all schemas/configs, and all
  Rerun presentation owners.
- Production Python LOC changed from 67,729 at `15a0811` to 67,350 (`-379`).

## Verification

- Ruff format/check, compileall, and `git diff --check` passed.
- The two touched test modules passed: 22 tests.
- Complete rollout and Rerun suites passed: 175 tests.
- A real `nbv-rerun-inspect` save-mode smoke produced a 322,879-byte `.rrd`
  from a two-step fixture rollout store.
- Graphify refreshed to 5,486 nodes and 12,552 edges; the read model and Rerun
  logger resolve as adjacent owners without presentation leakage.
- Repository-wide stale-symbol scans passed.
- Independent code review and architecture review both approved with no
  findings.

## Canonical State Impact

No scientific, persisted, configuration, or public-root contract changed. The
read-model seam now has two real adapters, Streamlit and Rerun, and therefore
passes the planned deletion test.
