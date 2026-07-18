---
id: 2026-07-17_g002_paired_rollout_source
date: 2026-07-17
title: "G002 Paired Rollout Pilot Source"
status: done
topics: [vin-offline, rollouts, dataset-cache, target-selection]
confidence: high
canonical_updates_needed: []
artifacts:
  - .configs/build_vin_offline_rollout_pilot50_v7.toml
  - .configs/rollout_pilot50_source_manifest.json
  - .configs/rollout_pilot50_target_audit.json
---

## Task

Build a strict-v7, deterministic 50-row VIN source spanning at least five ASE
GT-mesh scenes, freeze one ordered source manifest for paired rollout profiles,
and audit one authoritative oracle target per row before pilot generation.

## Method and findings

- Selected samples `000000` through `000009` from each of scenes `81283`,
  `81286`, `82004`, `83515`, and `83550`.
- A combined 50-key `snippet_ids` configuration was rejected because config
  construction repeatedly scans tar headers for every sample key. The durable
  writer config instead names ten ordered shard paths and applies the same 50
  keys through `snippet_key_filter`; parsing took 0.352 seconds locally.
- The source build is all-train (`train_val_split = 0.0`) because the current
  VIN writer assigns nonzero validation splits by sample-key hash, not scene.
  This avoids sample-key leakage inside the paired pilot but does not close the
  production scene-split blocker.
- The strict-v7 build completed 50/50 rows in 3 minutes 9 seconds with five
  ten-row shards, 9.32 GiB peak RSS, and no tolerated failures. The resulting
  source occupies 34.5 MiB allocated / 23.2 MiB logical across 1,170 files.
- The store preserves full 50,000-point VIN roots, full-resolution GT meshes
  for live reattachment, GT OBBs, and trajectory metadata. EVL backbone,
  candidate depths, point clouds, and diagnostics are omitted because the
  paired pilot regenerates its scientific candidate families and does not read
  cached one-step backbone blocks.
- A profile-independent source-manifest contract now owns the ordered VIN rows,
  strict cache version, source manifest hash, and split manifest hash without a
  rollout writer-config hash.

## Target audit

- Source manifest hash: `0cfa7252e18c1565`; ordered train-split manifest
  hash: `0c746d304c1feac2`; sampler hash: `b925c06071d96e20`.
- The authoritative `OracleTargetTaskSampler` with cap 1, seed 0, and uniform
  sampling selected one unique matched target for all 50 rows. All 931 oracle
  pool rows were identity-valid; valid pool size per snippet was 3 minimum,
  20 median, 34 maximum, and 18.62 mean. The audit freezes each selected target
  ID, source index, instance/semantic identity, eligibility count, selection
  probability, extents, and reference distance in source-row order.
- The selected 50 targets span 13 classes: chair 11, picture frame 7, lamp 5,
  sofa 5, container 4, window 4, dresser 3, mirror 3, bed 2, floor mat 2, table
  2, cabinet 1, and ladder 1.
- Selected target distance was 0.460 m minimum, 2.412 m median, 6.733 m p95,
  and 9.292 m maximum. Selected OBB diagonal was 0.401 m minimum, 1.352 m
  median, 3.274 m p95, and 5.393 m maximum; selected volume was 0.00354 m3
  minimum, 0.310 m3 median, 4.595 m3 p95, and 8.844 m3 maximum.
- Support, projected area, GT IoU, and ambiguity distributions are not exposed
  by the authoritative oracle sampler. This first-pass contract admits finite
  positive GT geometry only; it does not match actor detections or apply
  projected-visibility/support gates. The audit artifact records these as
  explicit unsupported fields instead of zero-valued measurements.

## Verification

- `aria_nbv/.venv/bin/nbv-build-offline --config-path .configs/build_vin_offline_rollout_pilot50_v7.toml --dry-run`
- Full `nbv-build-offline` run: version 7, 50 samples, 5 scenes, 5 shards,
  train 50 / validation 0, candidate count exactly 1.
- `aria_nbv/.venv/bin/nbv-offline-info summary --store vin_offline_rollout_pilot50_v7 --max-samples 50 --json`
- Live source reattachment reopened `ASE_81283_Atek_000000` and attached its
  full `(5512522, 3)` vertices / `(4599814, 3)` faces GT mesh.
- `cd aria_nbv && uv run pytest tests/rollouts/test_dataset_writer.py -q`
- Focused Ruff checks over the source-manifest implementation and tests.
- `git diff --check`

## Canonical state impact

No canonical state file changed. The source config and frozen manifest are the
durable G002 owners; production scene-level splitting remains an existing
rollout-readiness gate.
