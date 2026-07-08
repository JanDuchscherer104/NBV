---
id: 2026-07-08_pr15_simplification_todos_2_5
date: 2026-07-08
title: "PR15 Simplification TODOs 2-5"
status: done
topics: [aria-nbv, pr15, simplification, vin, rri-metrics, lightning]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/vin/__init__.py
  - aria_nbv/aria_nbv/vin/models/__init__.py
  - aria_nbv/aria_nbv/vin/models/_context_mixin.py
  - aria_nbv/aria_nbv/vin/models/scene_myopic.py
  - aria_nbv/aria_nbv/vin/geometry/semidense_schema.py
  - aria_nbv/aria_nbv/vin/types/prediction.py
  - aria_nbv/aria_nbv/vin/types/diagnostics.py
  - aria_nbv/aria_nbv/rri_metrics/torch_rollout_metrics.py
  - aria_nbv/aria_nbv/rri_metrics/logging.py
  - aria_nbv/aria_nbv/lightning/lit_module.py
---

## Task

Resolve PR15 cleanup TODOs 2, 3, 4, and 5 in the
`/home/jd/repos/ARIA-NBV-packages/pre-pr15-rollout-boundary` worktree.

## Output

- Demoted non-runnable target-myopic and finite-horizon VIN scaffolds from the
  broad `aria_nbv.vin` and `aria_nbv.vin.models` public namespaces while keeping
  leaf-module imports and candidate-scorer config parsing.
- Deleted the unused `PolicyTableMetrics` composite wrapper and its wrapper-only
  tests; retained the smaller metric owners used by Lightning and proposal
  diagnostics.
- Removed `vin.models._context_mixin` and routed `VinModelV3` directly through
  stateless `vin.scorer_context` helpers.
- Canonicalized semidense visibility metric naming around
  `semidense_candidate_vis_frac`; preserved read-only compatibility properties
  on prediction/diagnostic DTOs, but removed projection-schema aliases and
  duplicate Lightning metric enum/log entries.

## Verification

- `ruff check` over touched Python files passed using the repo venv.
- Focused pytest suite passed: `114 passed` for VIN namespace/context,
  RRI torch rollout metrics, candidate scorer contract, and VIN batch collate.
- App diagnostics smoke passed: `5 passed` for VIN diagnostics runtime and bin
  values tab tests.
- `git diff --check` passed.
- `graphify-out/graph.json` was absent in this worktree, so no graph update was
  available.

## Canonical State Impact

No canonical memory/state updates needed. This was a scoped pre-PR15 cleanup
against already accepted TODOs, not a thesis-direction or public-contract change.
