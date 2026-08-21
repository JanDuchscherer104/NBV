---
id: 2026-08-21_qh_camera_depth_contract_repair
date: 2026-08-21
title: "Q_H Camera And Depth Contract Repair"
status: done
topics: [qh, rollout, camera, depth, evl]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/data_handling/qh_data
  - aria_nbv/aria_nbv/data_handling/vin_store/writer.py
  - aria_nbv/aria_nbv/rendering
  - aria_nbv/aria_nbv/rollouts
  - aria_nbv/aria_nbv/lightning/qh_module.py
---

## Task

Repair the confirmed Q_H candidate-axis, EVL-presence, actor-profile,
selected-camera/depth, target-RRI, and audit-retention contracts without a
rollout Zarr layout change.

## Method And Findings

- Candidate selection now gathers vector rows on the candidate axis rather
  than the pose-feature axis.
- VIN shard writing rejects mixed per-row `backbone.*` presence before writes;
  Q_H EVL preflight requires all eight implemented fields in every shard.
- Root EVL and selected CF-GT observations are independent closed profiles,
  compared across stages and declared by the scorer configuration.
- Existing focal, principal-point, and raster rows reconstruct a linear
  `CameraTW`; `PerspectiveCameras` remains derived at one renderer-owned
  adapter. Camera-z, clip, fill, raster, and calibration semantics are
  documented and validated without adding arrays or changing the schema
  version.
- `one_step_target_rri` remains supervision-only, and optional chain audits
  remain CPU-only and batch aligned through transfer.

The available corrected-v2 pilot shard is historical schema
`1.0-target-rollout-core`; current code already requires
`2.0-target-rollout-provenance`, so that artifact cannot provide a current
compatibility proof. Current-schema write, validation, reader, materialization,
collation, and camera-backprojection paths are covered by fresh focused tests.

## Verification

- Combined focused suite: 202 passed.
- Ruff format check and lint passed for all changed Python files.
- Package compileall and `git diff --check` passed.
- Targeted mypy remains non-clean in pre-existing Zarr typing and Lightning
  override sites; no package-wide type-clean claim is made.

## Commits

- `810d742f28` — candidate-axis gathering.
- `56484c4925` — partial EVL rejection.
- `394680b22f` — independent actor evidence profiles.
- `6b28451fac` — typed selected camera/depth geometry.
- `77e3be6d3e` — target-RRI and audit retention.
