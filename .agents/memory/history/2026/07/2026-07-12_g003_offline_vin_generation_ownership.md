---
id: 2026-07-12_g003_offline_vin_generation_ownership
date: 2026-07-12
title: "G003 Offline VIN Generation Ownership"
status: done
topics: [oracle, pipelines, data-handling, offline-store, ultragoal]
confidence: high
canonical_updates_needed: []
---

# G003 Offline VIN Generation Ownership

## Scope

Moved immutable VIN generation composition from `data_handling.offline` to
`oracle.pipelines` without changing CLI names, TOML fields, store schemas,
manifest semantics, or failure/interrupt behavior.

## Changes

- Added `oracle.pipelines.offline_vin` as owner of raw iteration, Oracle
  labeling, optional backbone inference, generation config, and orchestration.
- Reduced `data_handling.offline.writer` to prepared-row, split, and immutable
  shard codecs.
- Moved `nbv-build-offline` dispatch into `oracle.pipelines.cli` and deleted the
  old data-handling CLI module without a compatibility facade.
- Removed `VinOfflineWriter` and `VinOfflineWriterConfig` from the broad
  `data_handling` root surface; both remain available from their owning leaf.
- Updated API navigation and package ownership READMEs.

Production Python LOC decreased from 68,011 to 67,976 (-35).

## Verification

- Ruff format/check, compileall, and the data-handling public typing contract
  passed.
- 154 data-handling, Oracle, rollout-writer/CLI, and config tests passed; six
  data-dependent tests skipped.
- The canonical `build_vin_offline_81286.toml` parsed through the relocated CLI
  in a real `--dry-run` after temporarily mounting the repository's shared
  local ASE assets into the isolated execution worktree.
- `nbv-build-offline --help`, Quartodoc generation, Graphify refresh, stale-path
  scans, and `git diff --check` passed.
- Repository-wide `make check-agent-memory` remains blocked by pre-existing
  tracked `.omx` runtime artifacts unrelated to this package.

## Canonical Updates Needed

- None. The package READMEs and API navigation now describe the new owner.
