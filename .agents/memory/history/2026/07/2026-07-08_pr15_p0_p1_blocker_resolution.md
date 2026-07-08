---
id: 2026-07-08_pr15_p0_p1_blocker_resolution
date: 2026-07-08
title: "PR15 P0/P1 Blocker Resolution"
status: done
topics: [pr15, vin, lightning, diagnostics, agent-memory]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/memory/history/2026/06/2026-06-17_thesis_architecture_iteration22_data_product_contract.md
  - .agents/memory/history/2026/06/2026-06-17_thesis_architecture_iteration24_query_descriptor.md
  - aria_nbv/aria_nbv/app/panels/vin_diagnostics.py
  - aria_nbv/aria_nbv/app/panels/vin_utils.py
  - aria_nbv/aria_nbv/lightning/lit_module.py
  - aria_nbv/aria_nbv/vin/models/scene_myopic.py
  - aria_nbv/tests/app/panels/test_vin_diagnostics_runtime.py
  - aria_nbv/tests/lightning/test_vin_batch_collate.py
  - aria_nbv/tests/vin/test_vin_model_v3_core.py
---

## Task

Resolved the accepted PR15 blockers P0-1, P0-2, P1-1, and P1-2 in the
`pre-pr15-rollout-boundary` worktree without broad VIN, `rri_metrics`, or
Lightning restructuring.

## Changes

- Fixed the root agent-memory gate by replacing the stale VIN pose encoder path
  with `aria_nbv/aria_nbv/vin/encoders/pose.py` and removing a missing transient
  `.agents/work` artifact from canonical-update requirements.
- Added a private VIN diagnostics runtime setup helper so checkpoint-backed
  experiment configs load through `VinLightningModule.load_for_inference`, while
  config-built diagnostics still prepare the module and fail closed on
  preparation errors.
- Split Lightning candidate-table metric logging so each scalar uses the finite
  sample count appropriate to that metric, and the selected valid-table rate is
  weighted by total table rows.
- Made `VinModelV3.forward` require cached `EvlBackboneOutput`, removing lazy
  backbone construction and module movement from the scorer forward path.

## Verification

- `make check-agent-memory` passed.
- Touched Python files passed `ruff format --check` and `ruff check` using the
  main ARIA-NBV virtualenv because `uv run` in this worktree is blocked by the
  broken editable `external/efm3d` checkout.
- Focused blocker tests passed: diagnostics runtime tests, candidate-table metric
  denominator test, cached-backbone VIN forward tests, and
  `tests/rri_metrics/test_torch_rollout_metrics.py`.

## Remaining Risk

The broad requested test subset still depends on local data/vendor fixtures
outside this blocker diff: ASE shard discovery under `.data/ase_efm` and
`external/PointNeXt/cfgs/s3dis/pointnext-s.yaml`.
