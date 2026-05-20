---
id: 2026-05-20_rollout_probe_agents_db
date: 2026-05-20
title: "Rollout Probe Findings Added To Agents DB"
status: done
topics: [rollouts, agents-db, simplification, target-rri]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/issues.toml
  - .agents/todos.toml
  - .agents/refactors.toml
  - .agents/memory/history/2026/05/2026-05-20_rollout_probe_agents_db.md
artifacts:
  - .artifacts/rollout_probe/rollouts_target_first_3family_probe.zarr
  - .artifacts/rollout_probe/rollouts_target_first_3family_lean_probe.zarr
  - .artifacts/rollout_probe/rollouts_target_first_3family_no_path_collision_probe.zarr
---

## Task

Patch the agents DB with findings from fresh target-first rollout probe generation and inspection, focusing on blockers before broader offline rollout generation.

## Method

Generated and inspected small schema-1.0 rollout probes, compared validated and non-validated stores, checked stale local default stores, and reviewed the Zarr payload footprint. Patched the existing target-first rollout alignment issue and added high-priority TODO/refactor records for concrete blockers.

## Findings Captured

- Path-collision diagnostics and invalidity bitsets are inconsistent: probes with path collision enabled fail validation because `path_collision_mask` rows can lack the `PATH_SEGMENT_COLLISION` invalidity bit.
- The realistic three-family sampler collapses in the current probe: only `forward_local` produced valid and selected candidates, with approximately 5 percent valid candidates overall.
- Target root gains in the structural probe are near numerical noise, so the current sampler/root pairs do not yet demonstrate meaningful target-RRI signal.
- Local default rollout stores are stale relative to schema `1.0-target-rollout-core`, while configs and Makefile defaults still point at older generation surfaces.
- Zarr pose arrays currently create many small chunks/files; chunking and manifest payloads need simplification before scale generation.

## DB Updates

- Amended `issue-032` with the rollout probe evidence and additional references.
- Added `todo-087` for path-collision invalidity consistency.
- Added `todo-088` for three-family sampler validity preflight.
- Added `todo-089` for a hard rollout-generation preflight gate.
- Added `refactor-021` for Zarr chunking and manifest payload streamlining.

## Verification

Ran `make agents-db AGENTS_ARGS='validate'` successfully after the edits, then regenerated the active DB summary with `make agents-db`.

## Canonical State Impact

No canonical state files require updates from this patch. The findings are actionable backlog and refactor records under the agents DB, with this debrief as history evidence.
