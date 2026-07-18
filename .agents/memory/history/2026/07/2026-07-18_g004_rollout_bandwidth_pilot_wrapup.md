---
id: 2026-07-18_g004_rollout_bandwidth_pilot_wrapup
date: 2026-07-18
title: "G004 Rollout Bandwidth Pilot Wrap-Up"
status: done
topics: [rollouts, data-generation, bandwidth, pytorch3d, cuda]
confidence: high
canonical_updates_needed: []
artifacts:
  - .configs/build_vin_offline_rollout_pilot50_v7.toml
  - .configs/rollout_pilot50_source_manifest.json
  - .configs/rollout_pilot50_target_audit.json
  - .omx/artifacts/rollout-pilot-g004-20260717T185232Z
---

## Task and stop decision

Build a paired 50-root pilot, measure local generation bandwidth, compare the
realistic and diverse candidate profiles, and collapse them only if matched
evidence justified promotion. On 2026-07-18 the user declared the generated
candidate evidence sufficient and stopped further generation. No realistic or
diverse generation was restarted during wrap-up.

## Durable source evidence

- G002 built a strict-v7 VIN source with 50 ordered roots: ten snippets from
  each of ASE GT-mesh scenes `81283`, `81286`, `82004`, `83515`, and `83550`.
  The build completed in 3 minutes 9 seconds with 9.32 GiB peak RSS.
- The profile-independent source manifest freezes source-manifest hash
  `0cfa7252e18c1565`, split-manifest hash `0c746d304c1feac2`, and one audited
  oracle target for every row. The source is all-train for this paired pilot;
  it is not a production scene-split result.
- Both rollout profiles parse against those exact 50 rows, one target per root,
  60 candidates per state, and the same four policy recipes. Only their
  candidate-family mixture and output destination differ.

## Generation attempts

| Attempt | Configuration and outcome | Runtime / progress | Resource evidence |
|---|---|---|---|
| 01 | Unbounded PyTorch3D view batch; failed on the first 51-view render while extending the 5,512,522-vertex / 4,599,814-face mesh. The failing allocation was 106 MiB. | 8.30 s; no usable rollout store. | 2,229,920 KiB max RSS; sampled GPU memory reached 11,883 MiB. |
| 02 | Renderer cap 4; processed 39 roots and reached scene `83550`, then failed while rasterizing its 6,110,247-vertex / 7,800,254-face mesh. The failing allocation was 994 MiB, with 2.41 GiB reserved but unallocated. | 1:23:30; 157 rollout summaries and 281 target-scorer calls. | 6,292,372 KiB max RSS; sampled GPU peak 11,611 MiB, median 9,947 MiB, mean utilization 91.96%. |
| Scene-5 smoke | Renderer cap 2 with `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`; source row 40 (`ASE_83550_Atek_000000`) completed and its Zarr store validated. | 1:01.22; 6 rollouts, 10 steps, 600 candidates. | 2,876,584 KiB max RSS; sampled GPU peak 4,665 MiB. |
| 03 | Renderer cap 2 with expandable segments; no CUDA OOM was observed. The process was externally terminated by the workstation shutdown before store commit. | GPU/progress sampling spans `2026-07-17T22:40:01+02:00` to `2026-07-18T00:54:00+02:00`; 39 roots, 156 rollout summaries, and 280 target-scorer calls. | Sampled GPU peak 5,797 MiB, median 4,121 MiB, mean utilization 94.76%. RSS is unavailable because `/usr/bin/time -v` did not flush before shutdown. System journal proves `jd` invoked `/usr/sbin/shutdown -h now` at exactly `2026-07-18 00:54:00+02:00`. |

Attempt 03 preserved only console, progress, and GPU telemetry because the
writer commits the standalone rollout store after the generation loop. There
is therefore no promoted 50-root rollout store from either realistic attempt.

## Valid throughput and storage evidence

- Candidate-shell generation was stable across the two long attempts. Attempt
  02 expanded 307 nodes in 175.802 seconds and attempt 03 expanded 306 nodes in
  174.439 seconds: approximately 104.8 and 105.3 generated candidates per
  second, respectively, for 60-candidate shells.
- Renderer cap 4 scored 11,418 valid candidate views in 3,203.641 render
  seconds, or 3.564 valid views/s, but exhausted the 11.63 GiB GPU. Cap 2
  scored 11,415 valid views in 6,039.996 render seconds, or 1.890 valid views/s,
  while reducing sampled peak GPU memory from 11,611 MiB to 5,797 MiB. The cap
  therefore bounded memory as intended, with an observed throughput cost.
- The completed scene-5 smoke store contains 600 candidate rows, of which 207
  were valid. Valid candidates per state were 18 minimum, 20.7 mean, and 21
  median; its hard invalid reasons were 375 `CLEARANCE_TOO_SMALL` and 18
  `PATH_SEGMENT_COLLISION` rows.
- The smoke store used 280,901 logical bytes, 6,574,080 allocated bytes, and
  1,589 files. This is 468 logical bytes, 10,957 allocated bytes, and 2.65
  files per candidate. A naive 50-root linear projection is about 14.0 MB
  logical, 329 MB allocated, and 79,450 files; it is bandwidth guidance, not a
  substitute for a completed multi-scene store.
- Store schema validation passed for the smoke, but production preflight did
  not: all ten selected actions came from `forward_local`, producing the
  `degenerate_target_aware_family_contribution` blocker. The smoke proves the
  large scene, batching, selected-depth, Q_H-view, and write/read paths; it
  does not prove scientific candidate-family support.

## Implementation evidence

- `Pytorch3DDepthRendererConfig.max_views_per_batch` bounds mesh replication;
  the renderer chunks camera batches and restores global face indices after
  concatenation.
- The regression test compares cap-2 output against an unchunked reference and
  proves mesh extension sizes `[2, 2, 1]` for five views while preserving
  depth, `pix_to_face`, and camera transforms.
- The realistic, diverse, and LRZ profiles currently select a two-view
  renderer cap. The long-run telemetry above is real-data confirmation that
  cap 2 avoids the cap-4 memory envelope on this workstation.
- The reviewed source-manifest contract and tests bind direct rollout builds
  to ordered source rows, source-store identity, split hash, and exact row
  count before generation.

## Explicit no-actions

- No diverse rollout generation was run.
- No paired scientific comparison or candidate-family promotion was claimed.
- No `build_rollouts_v1.toml` single-profile collapse was made; the realistic
  and diverse pilot TOMLs remain separate evidence configurations.
- No partial or smoke store was promoted as training data.
- No larger local, LRZ, Slurm, or 100-scene campaign was launched.
- The source store and raw telemetry logs were retained. The disposable
  scene-5 smoke store was removed, and evidence-only helper scripts plus their
  bytecode cache were removed after this debrief captured their results.

## Verification

- `uv run ruff check` passed for the renderer, rollout writer/shard/source
  manifest implementation, and focused tests.
- `uv run ruff format --check` passed for the same seven Python files after a
  mechanical format pass on the renderer.
- `uv run pytest tests/rendering/test_pytorch3d_depth_renderer.py tests/rollouts/test_dataset_writer.py tests/rollouts/test_diverse_rollout_profile.py -q`
  passed: 29 tests.
- Dry-runs passed for `.configs/build_rollouts_v1_realistic.toml`,
  `.configs/build_rollouts_v1_diverse.toml`, and
  `.configs/build_vin_offline_rollout_pilot50_v7.toml`; no generation objects
  were instantiated.
- `make check-agent-memory` is the final debrief/scaffold gate.

## Commit scope and remaining risks

Suggested reviewable commit split:

1. Source-population contract: the VIN pilot config, source manifest, target
   audit, source-manifest writer/reader changes, focused rollout writer/profile
   tests, and the G002 debrief.
2. Renderer memory bound: `pytorch3d_depth_renderer.py`, its regression test,
   and the renderer-cap changes in realistic/diverse/LRZ TOMLs.
3. This G004 debrief. Keep concurrent rollout-reporting and Typst thesis work
   in their own commit; it was not modified during this wrap-up.

The main remaining operational risk is monolithic end-of-run persistence: a
late shutdown loses all completed roots. A larger campaign still requires
small deterministic shards with per-shard success artifacts and consolidation.
Scientifically, the incomplete realistic run and absent diverse run cannot
answer family utility, matched headroom, or promotion questions. Production
scene-level splits, family-support gates, and real LRZ shard evidence also
remain outside this stopped pilot.

## Canonical state impact

No canonical state file changed. This debrief records the bounded G004 outcome
and explicit stop/no-action decisions without promoting incomplete pilot data
to project truth.
