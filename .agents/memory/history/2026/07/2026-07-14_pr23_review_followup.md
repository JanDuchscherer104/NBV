---
id: 2026-07-14_pr23_review_followup
date: 2026-07-14
title: "PR 23 Review Follow-up"
status: done
topics: [pr-23, review, simplification, vin-diagnostics]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/data_handling/offline/batch.py
  - aria_nbv/aria_nbv/data_handling/offline/diagnostics.py
  - aria_nbv/aria_nbv/data_handling/raw/views.py
  - aria_nbv/aria_nbv/rendering/candidate_depth_renderer.py
  - aria_nbv/aria_nbv/vin/models/scene_myopic.py
  - aria_nbv/aria_nbv/app/config.py
---

## Task

Verify the PR 23 GitHub and local review findings, implement only the accepted
merge-readiness and diagnostics-ownership cleanup, and record durable no-action
decisions for broader scientific or versioned-contract proposals.

## Method and output

The bounded implementation moved `VinOracleBatch.shape_summary()` to
`offline.diagnostics.summarize_vin_batch_shapes()`, preserved exact unbatched
and batched mappings, made the store preview delegate to the diagnostics owner,
removed confirmed stale comments, preserved the configured first-K renderer
prefix with full-shell indices, and inlined the one-use Streamlit app target
forwarder. The diagnostics runtime migration and smoke coverage were repaired
separately in the same follow-up.

## Accepted and no-action mapping

- Accepted: GitHub mode-restoration/runtime-ownership verification, focused
  diagnostics tests and smoke coverage, batch shape-summary ownership, stale
  diagnostics/raw-view/renderer/scene comments, precise renderer log wording,
  and the app-local `_target_cls` forwarder.
- Already addressed and verified: exact prior train/eval restoration and typed
  VIN diagnostics runtime ownership.
- No code action: stale PR body bookkeeping; GitHub mutation was not requested.
- `issue-010`: renderer config truthfulness and redundant device ownership;
  versioned config cleanup (`use_voxel_valid_frac_gate`, backbone ownership,
  cached statistics, `semidense_valid_frac` aliases); diagnostics forwarders;
  residual `RriResult.fscore_tau`; target/scene policy, timing, aliases, and
  possible redundant crop; orientation-config redesign; unused labeler config
  fields.
- `issue-007` / `todo-007`: deterministic semidense inference sampling, CW90
  parity, and the live `apply_cw90_correction` contract.
- `issue-031`: homogeneous Oracle root/label-family evidence and candidate
  point-cloud root ownership.
- `issue-021` / `todo-031`: the cross-surface `candidate_valid` semantic rename.
- Terminal no-action for this PR: raw-view repr redesign; broad Lightning and
  scorer/Zarr decomposition; active v3/legacy plot API and callbacks; typed
  projection records; trajectory pruning; removal of the shared-protocol
  `runtime_context` argument. These lack a reproduced defect, proven net
  deletion, or safe caller migration.
- Verified intentional: `max_candidates_final` selects the configured compact
  first-K prefix while returned indices remain in the full candidate shell.
- Rejected move: DTO codecs remain reader-owned because offline dataset readers
  actively call `from_serializable`.

## Verification

Focused exact-dictionary, delegation, candidate-prefix, app-target, Ruff,
repository-memory, and agents-DB checks were run as part of the Ultragoal
quality gate. Scientific/config/persistence/frame/scoring surfaces remained
outside the implementation scope.

## Canonical state impact

No canonical current-truth update is needed. Existing issue and todo owners
already cover every accepted deferred finding; this dated record preserves the
PR-specific evidence and terminal no-action decisions.
