---
id: 2026-07-10_package_layout_moves
date: 2026-07-10
title: "Mechanical Package Layout Moves"
status: done
topics: [architecture, data-handling, oracle, rollouts, rri-metrics]
confidence: high
canonical_updates_needed: []
artifacts:
  - .omx/specs/autoresearch-aria-nbv-module-pruning-20260709/report.md
  - .omx/ultragoal/goals.json
  - .omx/ultragoal/ledger.jsonl
---

## Task

Applied the approved move-only package transition in the isolated
`codex/package-layout-moves` worktree. The implementation changed module paths,
imports, CLI targets, generated API references, and package README inventories;
it did not change executable bodies, signatures, persisted schemas, config
fields, or command names.

## Result

- Renamed RRI point-mesh and ordinal leaves and moved CORAL ownership to VIN.
- Moved rollout generation and shard operations to `oracle.pipelines`.
- Grouped immutable offline contracts and operations under
  `data_handling.offline`.
- Grouped raw ASE/EFM dataset access under `data_handling.raw` while retaining
  mixed view and identifier helpers at the parent.
- Preserved all 67 ordered `data_handling` root exports and all 15 CLI names.

## Verification

All 19 moved implementations matched their baseline executable AST after
stripping imports and module docstrings. The affected final suite passed with
566 tests and 5 environment-dependent skips; Ruff, compileall, Quartodoc,
Graphify, glossary validation, CLI help, stale-path scans, dependency-direction
checks, and nine README-to-AST reconciliations also passed. Production Python
LOC changed from 68,699 to 68,659.

## Canonical State Impact

The canonical architecture report already owns the target boundaries. No
additional canonical state update is required; later semantic pruning and
symbol-splitting workpackages remain deferred.
