---
id: 2026-06-20_rollout_sample_autoresearch_iteration_3
date: 2026-06-20
title: "Rollout Sample Autoresearch Iteration 3"
status: done
topics: []
confidence: high
canonical_updates_needed: []
---

## Task
Generate the next distinct rollout sample, inspect schema/tensor/geometry
coherence, and produce a Rerun artifact for manual review.

## Method
Attempted an Iteration 3 build by widening
`.configs/build_rollouts_v1_smoke.toml` in memory to `max_samples=3` and
`source.limit=3`, then planning one-row rollout shards. The first attempt chose
`shard-000002` by ordinal and was recorded as a failed autoresearch attempt
because split-grouped shard ordering mapped it back to `sample_index=1`, already
inspected in Iteration 2.

Corrected the loop by selecting the unseen source identity directly:
`sample_index=2`, which planned as `shard-000001` under the widened in-memory
config. Built only that one source-row shard at
`.artifacts/rollout_research/iter03/shard-000001`.

Then ran:

- `cd aria_nbv && uv run nbv-rollouts-info --store /home/jd/repos/ARIA-NBV/.artifacts/rollout_research/iter03/shard-000001 --preflight --profile smoke --json`
- `cd aria_nbv && uv run nbv-rollouts-info --store /home/jd/repos/ARIA-NBV/.artifacts/rollout_research/iter03/shard-000001 --stats --json`
- `cd aria_nbv && uv run nbv-rollouts-info --store /home/jd/repos/ARIA-NBV/.artifacts/rollout_research/iter03/shard-000001 --random-index --min-horizon 2 --seed 1 --json`
- `cd aria_nbv && uv run nbv-rerun-inspect --config-path /home/jd/repos/ARIA-NBV/.configs/rerun_offline.toml --rollout-store /home/jd/repos/ARIA-NBV/.artifacts/rollout_research/iter03/shard-000001 --rollout-index 4 --save /home/jd/repos/ARIA-NBV/.artifacts/rollout_research/iter03/iter03_row04.rerun.rrd`

## Findings
Corrected Iteration 3 produced a valid one-source training shard:

- Store: `.artifacts/rollout_research/iter03/shard-000001`
- Source row: `sample_index=2`, `scene=81286`,
  `snippet=ASE_81286_Atek_000002`, split `train`
- Counts: `18` rollouts, `30` steps, `150` candidates, `30` selected depths,
  `3` targets
- Smoke preflight: `go=true`, `validation.ok=true`, no blockers or warnings
- Candidate validity: `100/150` valid, invalid reasons
  `CLEARANCE_TOO_SMALL=26` and `PATH_SEGMENT_COLLISION=24`
- Reward signal: finite count `100`, mean `0.0264416`, std `0.0699606`,
  max `0.360276`
- Deterministic random H=2 row: rollout `4`
- Best inspection row: rollout `4`, `temperature_softmax`, H=2, final
  target-root gain `0.360795`

Generated artifacts:

- `.artifacts/rollout_research/iter03/preflight_smoke.json`
- `.artifacts/rollout_research/iter03/stats.json`
- `.artifacts/rollout_research/iter03/random_h2_row.json`
- `.artifacts/rollout_research/iter03/iter03_geometry_summary.json`
- `.artifacts/rollout_research/iter03/iter03_row04_topdown.png`
- `.artifacts/rollout_research/iter03/iter03_row04_selected_depth_fixedmask.png`
- `.artifacts/rollout_research/iter03/iter03_row04.rerun.rrd`

Sample-level interpretation: this is a stronger rollout sample than Iteration 2.
The target is valid (`gt_match_iou=1.0`) and closer to the root (`6.45 m`) but
still not near-field. The selected H=2 path remains local around the root while
the second selected view produces a large target-root gain. Selected depths are
fully valid (`57600/57600` pixels at both selected steps).

Issue surfaced: iterative sample selection must use source identity
(`sample_index`, `scene_id`, `snippet_id`) rather than shard ordinal. The shard
planner groups by split, so widening `source.limit` changes shard IDs. The
duplicate failed attempt remains under `.artifacts/rollout_research/iter03/shard-000002`
and maps to Iteration 2's `sample_index=1`.

Follow-up nuance: target descriptor audit fields in `targets/` can be zero when
the root view has no descriptor support, while candidate-level
`target_current_support` and `target_candidate_support` become nonzero after
selected views. That appears coherent for this far/local acquisition sample but
should remain visible in future sample checks.

## Verification
Passed for corrected Iteration 3:

- Shard generation: wrote `18` rollouts, `30` steps, `150` candidates
- Smoke preflight: `go=true`, no blockers, no warnings
- Validation: `ok=true`
- Visual QA: inspected top-down and selected-depth panels for rollout `4`
- Rerun export: `.artifacts/rollout_research/iter03/iter03_row04.rerun.rrd`,
  size about `5.1M`
- OMX verdicts:
  - fail for duplicate source-row attempt caused by selecting shard ordinal
  - pass for corrected `sample_index=2` artifact

## Canonical State Impact
None. This is sample-level rollout-loop evidence and an operator lesson for the
next iteration, not a settled project-state change.
