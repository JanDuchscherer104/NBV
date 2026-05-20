---
id: 2026-05-20_rollout_scale_readiness_plans
date: 2026-05-20
title: "Rollout Scale Readiness Plans Persisted"
status: done
topics: [rollouts, agents-db, plan-grill, scale-readiness]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/work/rollout-scale-readiness/README.md
  - .agents/work/rollout-scale-readiness/01-path-collision-invalidity-plan.md
  - .agents/work/rollout-scale-readiness/02-three-family-sampler-preflight-plan.md
  - .agents/work/rollout-scale-readiness/03-rollout-generation-preflight-plan.md
  - .agents/work/rollout-scale-readiness/04-zarr-chunking-manifest-plan.md
  - .agents/work/rollout-scale-readiness/05-review-questions.md
  - .agents/issues.toml
  - .agents/todos.toml
  - .agents/refactors.toml
---

## Task

Persist concrete resolution plans for the rollout probe findings and link the
agents DB records to those plans before the next review and plan-grill round.

## Method

Created an internal plan pack under `.agents/work/rollout-scale-readiness/`
covering path-collision invalidity consistency, three-family sampler preflight,
rollout generation preflight, and Zarr chunking/manifest streamlining. Added a
review-question checklist for the next plan-grill round and linked the relevant
issue, TODO, and refactor records to the plan files.

## Verification

Ran `make agents-db AGENTS_ARGS='validate'` and `make agents-db` after linking
the records. A follow-up `make check-agent-memory` remains part of the final
commit verification for the combined memory edits.

## Canonical State Impact

No canonical state file update is required. The plans are active-work evidence
for `issue-032`, `todo-087`, `todo-088`, `todo-089`, and `refactor-021`.
