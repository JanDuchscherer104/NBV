---
id: 2026-07-12_g002_target_dto_pruning
date: 2026-07-12
title: "G002 Residual Oracle Target DTO Pruning"
status: done
topics: [oracle, targets, dto, rollouts, ultragoal]
confidence: high
canonical_updates_needed: []
---

## Task

Apply the deletion test to residual `OracleTargetTask` and sampling-result
fields without changing target semantics or persisted rollout schemas.

## Result

- Removed construction-only `scene_id` and `snippet_id` from
  `OracleTargetTask`.
- Removed constant `source`; pipeline/app callers use
  `ORACLE_TARGET_TASK_SOURCE` directly.
- Removed stored `identity_valid_rows`; diagnostics derive the count from
  `rows`.
- Retained `target_row_id` after the app contract proved it can differ from
  `source_index`.
- Left `TargetLineage`, Zarr arrays, reason codes, and global target-row
  normalization unchanged.

Production Python LOC decreased from 68,024 to 68,011 (-13).

## Verification

- Ruff format/check and compileall passed for all touched Python files.
- 126 targeted Oracle, rollout writer/Zarr, and Streamlit tests passed.
- `git diff --check` passed.
- Independent code review returned `APPROVE` with no findings.
