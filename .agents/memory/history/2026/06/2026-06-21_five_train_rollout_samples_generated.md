---
id: 2026-06-21_five_train_rollout_samples_generated
date: 2026-06-21
title: "Five Train Rollout Samples Generated"
status: done
topics: [rollouts, zarr, generation, validation]
confidence: high
canonical_updates_needed: []
artifacts:
  - .tmp/build_rollouts_5_samples_20260621.toml
  - .data/offline_cache/rollouts_v1_five_samples_train_20260621.zarr
  - .data/offline_cache/rollouts_v1_five_samples_20260621.zarr
---

## Task

Generate five new ARIA-NBV rollout source samples through the canonical rollout writer path.

## Method

Created a temporary rollout-writer config from the CPU microset recipe with `max_samples = 5`, `source.split = "train"`, candidate budget 32, `target_source = "oracle_target_task_sampler"`, `horizon = 2`, `branch_factor = 2`, and `beam_width = 2`.

An initial `source.split = "all"` attempt wrote `.data/offline_cache/rollouts_v1_five_samples_20260621.zarr` but failed post-write validation because the shard mixed train and val splits. The final generated store is train-only:

`.data/offline_cache/rollouts_v1_five_samples_train_20260621.zarr`

## Outputs

- Source rows: 5
- Rollout rows: 10
- Steps: 20
- Candidates: 640
- Targets: 5
- Selected depths: 20
- Schema: `1.0-target-rollout-core`
- Source split: `train`

## Verification

- `cd aria_nbv && uv run nbv-build-rollouts --config-path ../.tmp/build_rollouts_5_samples_20260621.toml --dry-run`
- `cd aria_nbv && uv run nbv-build-rollouts --config-path ../.tmp/build_rollouts_5_samples_20260621.toml`
- `cd aria_nbv && uv run nbv-rollouts-info --store /home/jd/repos/ARIA-NBV/.data/offline_cache/rollouts_v1_five_samples_train_20260621.zarr --json`
- Python inspection with `RolloutZarrStoreReader.validate()` returned `ok=True`, `num_rollouts=10`, `num_steps=20`, `num_candidates=640`, and no errors.

## Notes

The failed mixed-split artifact was left in place for traceability. It is current-schema but invalid because a rollout shard must contain exactly one split.
