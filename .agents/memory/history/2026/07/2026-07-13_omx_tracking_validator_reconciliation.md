---
id: 2026-07-13_omx_tracking_validator_reconciliation
date: 2026-07-13
title: "OMX Tracking Validator Reconciliation"
status: done
topics: [omx, agent-memory, ci, package-smoke]
confidence: high
canonical_updates_needed: []
---

## Scope

Reconciled root CI with the repository's existing distinction between durable
OMX planning artifacts and operator-local runtime state. Also corrected the
package-smoke path left stale by the offline data hierarchy move.

## Changes

- Updated `validate_agent_memory.py` to accept only the durable OMX prefixes
  already allowed by `.gitignore`: `context`, `plans`, `specs`, and
  `goals/autoresearch`.
- Kept caches, logs, state, temporary files, generated goal artifacts, and
  `.omx/ultragoal` forbidden, with focused path-classification tests.
- Removed a tracked session guidance snapshot and an unrelated stale
  Ultragoal brief from ignored runtime locations.
- Updated `PACKAGE_SMOKE_RUFF_PATHS` from the removed `_offline_writer.py`
  path to `data_handling/offline/writer.py`.

No production package, public API, configuration, checkpoint, persisted schema,
or scientific behavior changed.

## Verification

- 14 validator regression cases passed.
- `make check-agent-memory` passed against the staged real branch index.
- `make package-smoke` passed with 89 tests.
- Ruff and `git diff --check` passed for the corrective scope.

## Canonical State Impact

None. The change enforces the durable/runtime boundary already declared by the
tracked `.gitignore` policy.
