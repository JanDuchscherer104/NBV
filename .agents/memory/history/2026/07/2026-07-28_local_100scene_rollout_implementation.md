---
id: 2026-07-28_local_100scene_rollout_implementation
date: 2026-07-28
title: "Local 100-Scene Resumable Rollout Implementation"
status: done
topics: [rollouts, ase, target-matching, zarr, generation]
confidence: high
canonical_updates_needed: []
artifacts:
  - .configs/generation/rollouts/campaigns/build_rollouts_v1_local_100scene.toml
  - .configs/evidence/rollouts/local_100scene/plan.json
  - .configs/evidence/rollouts/local_100scene/root_inventory.json
  - .configs/evidence/rollouts/local_100scene/progress.jsonl
  - .configs/evidence/rollouts/local_100scene/status.json
---

# Local 100-Scene Resumable Rollout Implementation

## Task

Implement and start a local-only V1 rollout campaign across the 100 ASE scenes
with GT meshes. Admit every actor-visible detected target whose
class-compatible one-to-one oriented OBB match has strict 3D IoU greater than
0.20, cover multiple candidate and selection families, and support safe stop,
resume, and append-only collection growth.

## Method and output

Added the V1 observed-target matcher and privileged GT-match lineage, a
deterministic one-root-per-scene inventory with shard-level reserves, immutable
source/profile shards, a hash-chained collection ledger, centralized campaign
configuration, and plan/run/status CLIs. Operational failures propagate;
scientific no-target ineligibility alone advances reserves. Exhausted scenes
are incomplete, and rollout failure attempts are bounded.

The live plan contains 100 selected roots, 576 reserve candidates, four
60-candidate profiles, five rollout recipes per profile, and 240 planned
scene/profile shards. The bounded invocation uses eight new shards, a 120-minute
limit, a 75 GiB free-disk floor, and a three-failure ceiling.

Generation was launched in tmux session `aria-nbv-rollout-v1-local100`. The
initial source `AriaSyntheticEnvironment_889_AtekDataSample_000008` completed
with three IoU-admitted observed targets, and rollout rendering began from its
realistic candidate family.

## Verification

Ruff passed on all touched Python files. Targeted mypy passed for the campaign
and campaign CLI. The focused integration suite passed 136 tests, and the full
rollout suite passed 222 tests. An independent final code review returned
`APPROVE` after the operational/scientific failure boundary was hardened.

## Canonical state impact

No canonical update is needed while the bounded empirical generation run is in
progress. Promote measured coverage, bandwidth, and quality results only after
the produced collection has been audited.
