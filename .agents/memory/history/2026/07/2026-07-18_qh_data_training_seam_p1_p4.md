---
id: 2026-07-18_qh_data_training_seam_p1_p4
date: 2026-07-18
title: "Q_H Data and Training Seam P1-P4"
status: done
topics: [qh, rollouts, vin, lightning, zarr]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/targets/protocol.py
  - aria_nbv/aria_nbv/rollouts/qh_reader.py
  - aria_nbv/aria_nbv/data_handling/offline/actor.py
  - aria_nbv/aria_nbv/lightning/qh_data.py
---

## Task

Implement the approved P1-P4 `Q_H` data/training seam in an isolated
`codex/qh-data-training-seam` worktree based on commit `d94ed2d`, while
preserving strict actor/oracle separation and leaving P5 model training and P6
scientific evaluation deferred.

## Method and output

P0 closed with the realistic rollout pilot in a terminal state and no partial,
smoke, or interrupted output promoted as a training store. P1 introduced
canonical `v0_gt_input` and `v1_observed` target-protocol admission, including
fail-closed provenance checks that prevent legacy or oracle-derived metadata
from being presented as observed actor input.

P2 added the storage-only `QhRolloutReader`, whose small interface hides schema,
lineage, target-protocol, and transition interpretation. Preflight reads are
bounded to metadata and shape checks, while item access reads only the requested
state and selected transition slices; it does not route training through eager
whole-store `q_h_view()` or `array()` materialization. P3 added
`VinActorSource`, which projects only actor-visible VIN evidence and enforces an
explicit denylist against oracle labels, raw GT geometry, and selected-depth
audit rasters.

P4 added `QhDataModule`, transition-complete collation, and explicit samplers.
The batch contract carries current actor input, optional next actor input,
transition facts, lineage, and the exact `row_train_mask` and
`bootstrap_mask`. Training uses an accounted padded distributed sampler;
validation and test use deterministic non-padding rank partitioning. Trainer
construction disables Lightning's automatic sampler replacement so those
semantics remain owned by the data module.

The initial architect and code reviews blocked completion because preflight
eagerly materialized all `scene_ids` and mixed or invalid lineage could survive
until item access. The repair stores compact scene/source metadata during
preflight and rejects split, target-protocol, invalid-reason, and configuration
lineage mismatches before the first batch. Final independent code review
returned `APPROVE` and the architect returned `CLEAR`.

## Verification

After the cleaner pass, the focused protocol, reader, actor-source, data-module,
trainer-policy, rollout-store, writer, fixture, and configuration regressions
passed: 178 tests. Ruff format and lint checks passed for the touched Python
surface. Verification reused the repository's shared virtual environment;
broad environment checks that require `external/efm3d` were unavailable in the
isolated worktree because that external checkout was not hydrated, rather than
because of a failure in this implementation.

## Canonical state impact

No canonical current-truth update is required. The implementation and focused
regressions own the P1-P4 contracts. P5 finite-horizon scoring/Double-Q training
and P6 held-out scientific evaluation remain deferred, and no completed pilot
store or performance claim was promoted. P4 still lacks non-blocking throughput
observability; add it before P6-scale data loading rather than widening this
seam implementation.
