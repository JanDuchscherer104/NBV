---
id: 2026-07-12_rwp03a_online_vin_ownership
date: 2026-07-12
title: "RWP03A Online VIN Ownership"
status: done
topics: [oracle, data-handling, lightning, pipelines, architecture]
confidence: high
canonical_updates_needed: []
---

# RWP03A Online VIN Ownership

## Scope

Moved online Oracle-labelled VIN generation out of `data_handling`, separated
the immutable offline source config, and made Lightning the owner of source
composition without changing source discriminators or fields.

## Changes

- Moved `VinOracleOnlineDataset` and its config to
  `oracle.pipelines.online_vin`.
- Moved `VinOfflineSourceConfig` to `data_handling.offline.source`.
- Moved `VinDatasetSourceConfig` to `lightning.lit_datamodule`.
- Moved online label-to-batch adaptation out of `VinOracleBatch` and deleted
  `VinOfflineSample.to_vin_oracle_batch()`; the offline dataset's private
  `_build_vin_batch` remains the sole offline training conversion.
- Migrated app, Lightning, tests, generated API navigation, and ownership
  matrices to leaf owners; removed four `data_handling` root exports.

## Verification

- The online and offline config class ASTs are identical to their pre-move
  definitions, preserving all Pydantic fields and discriminators.
- Ruff format/check, Python compilation, and the static public typing contract
  passed.
- `78` Lightning, online Oracle, app-config, offline-store, target-selection,
  and public-contract tests passed.
- Focused tests lock online retry exhaustion, non-finite label skipping,
  label-to-batch adaptation, worker constraints, and both source
  discriminators.
- `data_handling.__all__` decreased from `51` to `47` names.
- Production Python LOC decreased from `68,030` to `67,920`, excluding the
  unrelated user-owned `rollouts/inspection.py` drift.
- Graphify and Quartodoc were refreshed; `git diff --check` passed.
- Independent reviewer agents were started but exhausted their account quota
  before returning a verdict. No review finding was produced; the commit relies
  on the local contract, test, typing, AST-parity, and LOC evidence above.

## Deferred Boundary

- `data_handling.offline.writer` still imports the scene-label pipeline. RWP03B
  owns removal of that final lower-owner generation dependency together with
  offline generation composition.

## Canonical Updates Needed

- None. This is RWP03A from the replacement module-pruning plan.
