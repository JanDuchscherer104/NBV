---
id: 2026-08-14_cuda_rollout_rebased_verification
date: 2026-08-14
title: "CUDA rollout rebased verification"
status: done
topics: [rollouts, cuda, campaign, rebase, verification]
confidence: high
canonical_updates_needed: []
files_touched:
  - .configs/build_rollouts_v1_cuda_campaign.toml
  - .configs/build_rollouts_v1_cuda_campaign_writer.toml
  - .configs/rollout_campaign100_source_manifest.json
  - aria_nbv/aria_nbv/oracle/pipelines/campaign.py
  - aria_nbv/aria_nbv/oracle/target_selection.py
  - aria_nbv/tests/oracle/test_campaign.py
  - aria_nbv/tests/oracle/test_target_selection.py
---

## Task

Finish rebased verification of the CUDA rollout campaign without launching the
broad campaign, and tune the canonical local generation settings for an NVIDIA
GeForce RTX 3080 Ti, 32 GB RAM, and an 8-core/16-thread Ryzen 7 5800X while
keeping the implementation and operational model simple.

## Method

The implementation branch was previously rebased from pre-rebase commit
`756e1030db00f9543fbfdd1c10c659704bcac0c0` onto exact `origin/main`
`8323b8ed83867e1a2f0c754c7cf3025153b21c41`; the initial rebased head was
`731b3c5b3642c9c4bb8ef3f4b95011e07adb2477`. All earlier green evidence was
treated as stale.

The missing canonical source prerequisite was closed without relaxing the
100-scene contract: a reviewed immutable V7 source store was completed with one
row per scene, the generated source manifest contains 100 rows across 100
scenes, and strict actor-visible admission produced 434 audit rows, 362
admitted targets, 72 explicitly rejected targets, and 870 deterministic
target/profile work units. Campaign admission audit reads were narrowed to the
persisted geometry/trajectory fields they consume, and CPU/CUDA OBB transform
alignment was repaired at the target-selection boundary.

The real smoke path then exposed and drove root-cause repairs for admission-row
hash normalization and the distinction between the reviewed campaign manifest
file digest and the VIN source-manifest identity. One-row shard lineage is now
bound before writer validation and uses the existing canonical split-hash
function. Failed pre-repair runtime artifacts were preserved under
`.campaign-quarantine-pre-source-lineage-fix-20260814/` rather than deleted.

## Findings

The canonical one-target smoke succeeded with plan hash
`95118ab2f3853bf5`. It wrote and validated one promoted V1 Zarr shard containing
12 rollouts, 78 retained trajectory steps, and 4,680 candidate rows. During the
long compute phase, `nvidia-smi dmon` showed sustained 97--100% SM utilization,
about 4.99 GiB peak framebuffer use, and roughly 180--258 W draw. Worker RSS was
about 2.4 GiB.

The hardware evidence does not justify concurrent work units, a larger
candidate population, or another scheduling layer. The accepted simple local
settings remain one serial worker, exactly 60 candidates, renderer
`max_views_per_batch = 2`, selected-depth `chunk_steps = 16`, branch factor 2,
and beam width 2. Free VRAM is not treated as evidence of idle compute; the GPU
was already saturated. The changed-files AI-slop pass removed the remaining
fallback from VIN source lineage to the unrelated campaign file digest and
replaced it with explicit fail-closed validation. Narrow legacy in-memory
fixture compatibility remains tested and does not weaken the canonical path.

## Verification

- Ruff format/check and explicit-worktree `git diff --check` passed.
- The post-cleaner campaign/target/CLI behavior lock passed: 118 tests.
- The existing focused campaign, writer, CLI, Streamlit, and router gate passed:
  195 tests.
- Geometry, Zarr schema, public API, and legacy TOML invariant tests passed: 48
  tests.
- The canonical 100-scene plan and real one-target CUDA smoke passed without a
  broad campaign launch.
- Exact final commit, config digests, final post-commit smoke evidence, final
  independent reviews, and the architecture audit are recorded in the durable
  Ultragoal ledger rather than duplicated here.
- No push, pull request, issue, or other external GitHub write was performed.

## Canonical State Impact

None. The package code, tests, canonical TOML/source manifest, and durable
Ultragoal ledger own current behavior and terminal evidence. No
`.agents/memory/state/*.md` update is needed; this file is episodic debrief only.
