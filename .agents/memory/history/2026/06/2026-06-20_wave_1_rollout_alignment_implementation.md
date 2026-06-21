---
id: 2026-06-20_wave_1_rollout_alignment_implementation
date: 2026-06-20
title: "Wave 1 Rollout Alignment Implementation"
status: done
topics: [rollouts, target-rri, preflight, invalidity]
confidence: high
canonical_updates_needed: []
---

## Task
Implemented the Wave 1 rollout-alignment slice for invalidity consistency, oracle target-task rollout wiring, and rollout-store preflight gating.

## Method
Worked directly in the rollout/data-handling surfaces after reading the root and nested AGENTS contracts. Kept changes scoped to rollout invalidity derivation, rollout target-source configuration, preflight inspection, rollout configs, and focused tests.

## Findings
- `aria_nbv/aria_nbv/rollouts/trace.py` now ORs hard diagnostic invalidity bits, including `path_collision_mask`, independently of cumulative sampler-rule order and derives deterministic primary invalid reasons by priority.
- `aria_nbv/aria_nbv/rollouts/dataset_writer.py` now exposes `RolloutTargetSource`, defaults rollout data generation to `oracle_target_task_sampler`, adapts identity-valid oracle target-task rows into the existing target lineage DTO, and preserves actor-visible selection for explicit V1 diagnostic/deployable-input profiles.
- `.configs/build_rollouts_v1_*.toml` now set `target_source = "oracle_target_task_sampler"` for rollout generation profiles.
- `aria_nbv/aria_nbv/rollouts/info_cli.py` now supports `nbv-rollouts-info --preflight --profile smoke|production --json` with schema, validation, lineage, coverage, validity, reward, retention, storage, and go/no-go reporting.
- Existing `.data/offline_cache/rollouts_v1_smoke.zarr` is correctly blocked by production preflight: stale schema `0.6-rollout-core`, invalid store, and flat/missing target-root-gain reward signal.

## Verification
- `cd aria_nbv && uv run ruff check aria_nbv/rollouts/trace.py aria_nbv/rollouts/dataset_writer.py aria_nbv/rollouts/info_cli.py tests/rollouts/test_zarr_store.py tests/rollouts/test_dataset_writer.py tests/rollouts/test_info_cli.py` passed.
- `cd aria_nbv && uv run pytest tests/rollouts/test_zarr_store.py tests/rollouts/test_dataset_writer.py tests/pose_generation/test_pose_generation.py -q` passed: 47 passed.
- `cd aria_nbv && uv run pytest tests/data_handling/test_target_selection.py tests/rollouts/test_dataset_writer.py -q` passed: 36 passed.
- `cd aria_nbv && uv run pytest tests/rollouts/test_inspection.py tests/rollouts/test_zarr_store.py tests/rollouts/test_info_cli.py -q` passed: 35 passed.
- `cd aria_nbv && uv run nbv-rollouts-info --store rollouts_v1_smoke.zarr --preflight --profile production --json` exited 1 with `go=false`, as expected for the stale existing cache artifact.
- `make agents-db AGENTS_ARGS='validate'`, `make check-agent-memory`, `make scaffold-audit`, and `git diff --check` passed; scaffold audit reported warnings only.

## Canonical State Impact
None. This debrief records implementation evidence; no `.agents/memory/state/*.md` update was needed.
