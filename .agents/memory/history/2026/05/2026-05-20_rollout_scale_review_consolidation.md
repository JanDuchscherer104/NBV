---
id: 2026-05-20_rollout_scale_review_consolidation
date: 2026-05-20
title: "Rollout Scale Review Consolidation"
status: done
topics: [rollouts, agents-db, plan-grill, review]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/issues.toml
  - .agents/todos.toml
  - .agents/refactors.toml
  - .agents/work/rollout-scale-readiness/README.md
  - .agents/work/rollout-scale-readiness/01-path-collision-invalidity-plan.md
  - .agents/work/rollout-scale-readiness/02-three-family-sampler-preflight-plan.md
  - .agents/work/rollout-scale-readiness/03-rollout-generation-preflight-plan.md
  - .agents/work/rollout-scale-readiness/04-zarr-chunking-manifest-plan.md
  - .agents/work/rollout-scale-readiness/05-review-questions.md
---

## Task

Consolidated the latest GPT-5.5 Pro scale-readiness review with the current
local agents DB and rollout readiness plan pack.

## Findings

The review's no-go verdict remains valid for broad rollout generation. The
branch mismatch is now explicit: the accessible remote review ref did not
contain the local readiness plan pack or linked DB records. The current checkout
already fixes or supersedes several visible-branch findings, including schema
`1.0-target-rollout-core`, hot `position_id` provenance, pruned candidate-major
q_h bootstrap/scene-RRI arrays, clipped projected-area visibility, geometry-only
GT match after eligibility, and seed-once lineage. Remaining blockers were
captured as concrete plan/DB work.

## Outputs

Refined the rollout readiness plans with fixed-priority invalidity semantics,
production low-valid-root thresholds, flat-reward thresholds, preflight JSON
sections, scene split and stochastic replay requirements, byte-budget chunking,
and scope-control decisions.

Updated agents DB records and added two first-class todos:

- `todo-090`: expose the readiness plan pack on the reviewed branch/ref.
- `todo-091`: add an explicit H=1 target-label rollout profile.

## Verification

Ran:

- `python3 scripts/agents_db.py validate`
- `make agents-db AGENTS_ARGS='validate'`
- `make agents-db`

All passed.
