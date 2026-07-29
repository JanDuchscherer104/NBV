---
id: 2026-07-28_local_100scene_resumable_rollout_plan
date: 2026-07-28
title: "Local 100-Scene Resumable Rollout Plan"
status: done
topics: [rollouts, ase, target-matching, zarr, planning]
confidence: high
canonical_updates_needed: []
artifacts:
  - .omx/plans/local-100scene-resumable-realistic-rollouts-20260728.md
---

# Local 100-Scene Resumable Rollout Plan

## Task

Plan a local-only rollout campaign that covers one eligible snippet from every
ASE scene with a GT mesh, accepts every actor-visible target whose
class-compatible one-to-one 3D OBB match clears the centralized IoU threshold,
and supports safe stop, resume, and additive growth.

## Method and output

Inspected the live dataset inventory, GPU and disk headroom, existing pilot
stores and benchmark evidence, current rollout writer and shard lifecycle,
candidate-family and replay-policy implementations, ATEK matching semantics,
and the thesis V1 target-input contract. Produced the implementation-ready plan
at `.omx/plans/local-100scene-resumable-realistic-rollouts-20260728.md`.

The plan selects one deterministic root per scene without gain-based cherry
picking, starts V1 target matching at `min_iou = 0.20`, removes target caps,
uses immutable validated shards behind an additive collection index, and stages
candidate/policy/horizon breadth behind bandwidth gates. No rollout data or
source-code changes were produced in this planning pass.

## Verification

The plan is grounded in current repository paths and local runtime evidence.
Final validation covered required OMX plan metadata, native debrief metadata,
and whitespace integrity.

## Canonical state impact

None. These are execution-plan decisions pending implementation and empirical
validation; they do not yet change canonical project truth.
