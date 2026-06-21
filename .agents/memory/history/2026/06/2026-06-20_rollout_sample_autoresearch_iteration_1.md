---
id: 2026-06-20_rollout_sample_autoresearch_iteration_1
date: 2026-06-20
title: "Rollout Sample Autoresearch Iteration 1"
status: done
topics: [rollouts, target-rri, rerun, autoresearch]
confidence: high
canonical_updates_needed: []
artifacts:
  - /home/jd/repos/ARIA-NBV/.artifacts/rollout_research/iter01/shard-000000
  - /home/jd/repos/ARIA-NBV/.artifacts/rollout_research/iter01/preflight_smoke.json
  - /home/jd/repos/ARIA-NBV/.artifacts/rollout_research/iter01/iter01_row04.rerun.rrd
  - /home/jd/repos/ARIA-NBV/.artifacts/rollout_research/iter01/iter01_row04_topdown.png
  - /home/jd/repos/ARIA-NBV/.artifacts/rollout_research/iter01/iter01_row04_selected_depth_fixedmask.png
---

## Task
Run the first autoresearch-goal iteration for rollout sample validity by generating one fresh rollout store, inspecting schema/metadata/geometry/depth artifacts, and leaving a Rerun command for human visual confirmation.

## Method
- Created OMX autoresearch-goal slug `aria-nbv-rollout-sample-validity-and-geometric-c`.
- Planned and built one rollout shard from `.configs/build_rollouts_v1_smoke.toml` into `/home/jd/repos/ARIA-NBV/.artifacts/rollout_research/iter01/shard-000000`.
- Ran `nbv-rollouts-info --preflight --profile smoke --json`, row-level Zarr tensor inspection, quick Matplotlib top-down/depth plots, and `nbv-rerun-inspect --save`.
- Recorded one fail verdict for the initial build blockers and one pass verdict after fixes and artifact validation.

## Findings
- Fixed `RolloutDatasetWriterConfig.max_targets_per_sample` propagation in `aria_nbv/aria_nbv/rollouts/dataset_writer.py`: the writer-level `None` means no rollout cap and must not overwrite the nested oracle target-task sampler's positive sample cap.
- Added `test_rollout_writer_config_allows_unbounded_targets_per_sample` in `aria_nbv/tests/rollouts/test_dataset_writer.py`.
- Set smoke-only `min_valid_root_candidates = 1` in `.configs/build_rollouts_v1_smoke.toml`; the first one-row sample otherwise produced no records because each target/recipe had only one valid root candidate and the writer default required three.
- Generated store counts: 18 rollouts, 30 steps, 150 candidates, 3 targets, 30 selected-depth frames.
- Smoke preflight passed with schema `1.0-target-rollout-core`, no blockers, no warnings, 62/150 valid candidates, invalid reasons dominated by `CLEARANCE_TOO_SMALL` and `PATH_SEGMENT_COLLISION`, and non-flat `target_root_gain`.
- Primary Rerun row is rollout index 4: `temperature_softmax`, horizon 2, target row 0, final target-root gain about 0.2434. Quick plots show a local selected path and fully valid selected-depth masks.
- Contrast row 10 is valid but low-gain and target-distant; useful for later sampler/target-distance QA, not a schema blocker.

## Verification
- `cd aria_nbv && uv run pytest tests/rollouts/test_dataset_writer.py -q` passed: 13 tests.
- `cd aria_nbv && uv run ruff check aria_nbv/rollouts/dataset_writer.py tests/rollouts/test_dataset_writer.py` passed.
- `git diff --check` passed.
- `cd aria_nbv && uv run nbv-rollouts-info --store /home/jd/repos/ARIA-NBV/.artifacts/rollout_research/iter01/shard-000000 --preflight --profile smoke --json` passed with `go=true`.
- `cd aria_nbv && uv run nbv-rerun-inspect --config-path /home/jd/repos/ARIA-NBV/.configs/rerun_offline.toml --rollout-store /home/jd/repos/ARIA-NBV/.artifacts/rollout_research/iter01/shard-000000 --rollout-index 4 --save /home/jd/repos/ARIA-NBV/.artifacts/rollout_research/iter01/iter01_row04.rerun.rrd` passed.

## Canonical State Impact
None. This iteration changed implementation/config/test surfaces and left evidence artifacts; no durable project decision beyond those files needs promotion to `.agents/memory/state/`.
