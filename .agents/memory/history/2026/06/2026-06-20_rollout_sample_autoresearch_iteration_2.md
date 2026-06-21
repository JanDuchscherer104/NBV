---
id: 2026-06-20_rollout_sample_autoresearch_iteration_2
date: 2026-06-20
title: "Rollout Sample Autoresearch Iteration 2"
status: done
topics: []
confidence: high
canonical_updates_needed: []
---

## Task
Generate one additional rollout sample shard, inspect validity and geometry, and
record whether the artifact is usable for Rerun/manual review.

## Method
Built only the second VIN source row as
`.artifacts/rollout_research/iter02/shard-000001` by loading
`.configs/build_rollouts_v1_smoke.toml` programmatically, widening
`max_samples` and `source.limit` to `2` in memory, planning one-row shards, and
executing `shard-000001`.

Then ran:

- `cd aria_nbv && uv run nbv-rollouts-info --store /home/jd/repos/ARIA-NBV/.artifacts/rollout_research/iter02/shard-000001 --preflight --profile smoke --json`
- `cd aria_nbv && uv run nbv-rollouts-info --store /home/jd/repos/ARIA-NBV/.artifacts/rollout_research/iter02/shard-000001 --stats --json`
- `cd aria_nbv && uv run nbv-rollouts-info --store /home/jd/repos/ARIA-NBV/.artifacts/rollout_research/iter02/shard-000001 --random-index --min-horizon 2 --seed 1 --json`
- `cd aria_nbv && uv run nbv-rerun-inspect --config-path /home/jd/repos/ARIA-NBV/.configs/rerun_offline.toml --rollout-store /home/jd/repos/ARIA-NBV/.artifacts/rollout_research/iter02/shard-000001 --rollout-index 4 --save /home/jd/repos/ARIA-NBV/.artifacts/rollout_research/iter02/iter02_row04.rerun.rrd`

## Findings
Iteration 2 produced a valid one-source validation shard:

- Store: `.artifacts/rollout_research/iter02/shard-000001`
- Shard row: `sample_index=1`, `scene=81286`, `snippet=ASE_81286_Atek_000001`, split `val`
- Counts: `6` rollouts, `10` steps, `50` candidates, `10` selected depths, `1` target
- Smoke preflight: `go=true`, `validation.ok=true`, no blockers or warnings
- Candidate validity: `16/50` valid, invalid reasons `CLEARANCE_TOO_SMALL=20` and `PATH_SEGMENT_COLLISION=14`
- Reward signal: finite count `16`, mean `0.0289766`, std `0.0326887`, max `0.070307`
- Deterministic random H=2 row: rollout `3`
- Best inspection row: rollout `4`, `temperature_softmax`, H=2, final target-root gain `0.0703067`

Generated inspection artifacts:

- `.artifacts/rollout_research/iter02/preflight_smoke.json`
- `.artifacts/rollout_research/iter02/stats.json`
- `.artifacts/rollout_research/iter02/random_h2_row.json`
- `.artifacts/rollout_research/iter02/iter02_geometry_summary.json`
- `.artifacts/rollout_research/iter02/iter02_row04_topdown.png`
- `.artifacts/rollout_research/iter02/iter02_row04_selected_depth_fixedmask.png`
- `.artifacts/rollout_research/iter02/iter02_row04.rerun.rrd`

Sample-level interpretation: the target is label-valid (`gt_match_iou=1.0`) but
far from the root (`10.46 m`). The H=2 local candidates therefore remain near
the root; the sample is useful for validating lineage, invalidity masks,
selected-depth persistence, and Rerun inspectability, but it is not a
near-target acquisition example. Several oracle target/recipe attempts were
skipped because the current target crop contained too few points, which should
be tracked as target-pool quality evidence rather than treated as low-RRI
labels.

## Verification
Passed:

- Iteration 2 shard generation: wrote `6` rollouts, `10` steps, `50` candidates
- Smoke preflight: `go=true`, no blockers, no warnings
- Validation: `ok=true`
- Rerun export: `.artifacts/rollout_research/iter02/iter02_row04.rerun.rrd`, size about `5.0M`
- Visual QA: inspected top-down and selected-depth panels for rollout `4` and
  deterministic H=2 rollout `3`
- OMX verdict: `omx autoresearch-goal verdict --slug aria-nbv-rollout-sample-validity-and-geometric-c --verdict pass ...`

## Canonical State Impact
None. This is sample-level evidence for the current rollout loop, not a settled
canonical state change.
