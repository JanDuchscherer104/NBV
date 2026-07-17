---
id: 2026-07-17_ase_100_rollout_readiness
date: 2026-07-17
title: "ASE-100 Multi-Step Rollout Readiness"
status: done
topics: [pose-generation, rollouts, data-generation, slurm, target-rri]
confidence: high
canonical_updates_needed: []
artifacts:
  - .omx/goals/autoresearch/ase-100-multistep-rollout-readiness/research-report.md
  - .omx/goals/autoresearch/ase-100-multistep-rollout-readiness/experiment-ledger.jsonl
---

## Task

Review and experimentally improve pose generation, rollout generation, dataset handling, thesis alignment, and LRZ readiness before 100-scene multi-step rollout generation.

## Findings and changes

- A real ASE probe found that motion realism compared VIO +Z-up candidates using world-Y height/yaw logic. The focused fix raised realistic support from 3/60 to 35/60 on scene 81283.
- Final generation remains blocked by target-RRI tessellation/density validation, full VIN source-store and scene-split construction, derived seed schedules, hard-invalidity consistency, family-aware preflight, one real LRZ shard, and Zarr file-count scaling.
- Oracle target-sampler and renderer settings are explicit in TOML; inactive target-selector blocks were removed.
- The real Slurm launcher now requires a manifest-sized array and a prebuilt frozen environment.

## Verification

- `cd aria_nbv && uv run pytest tests/pose_generation tests/rollouts tests/data_handling -q`
- `cd aria_nbv && uv run python -u ../.omx/goals/autoresearch/ase-100-multistep-rollout-readiness/real_ase_candidate_probe.py`
- `bash -n scripts/templates/lrz/rollout_generation.sbatch scripts/templates/lrz/rollout_generation_dry_run.sbatch`
- Config-only dry-runs for realistic, diverse, and LRZ rollout profiles.

## Canonical state impact

No canonical state files were changed. Existing backlog entries `todo-084`, `todo-085`, `todo-087`, `todo-088`, `todo-089`, `issue-022`, and `refactor-021` already own the unresolved gates.
