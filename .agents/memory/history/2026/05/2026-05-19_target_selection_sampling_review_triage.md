---
id: 2026-05-19_target_selection_sampling_review_triage
date: 2026-05-19
title: "Target Selection Sampling Review Triage"
status: done
topics: [target-selection, candidate-generation, rollouts, docs, agents-db]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/issues.toml
  - .agents/todos.toml
  - docs/contents/theory/candidate_sampling_target_selection.qmd
---

## Task

Triaged `.agents/work/target-selection-sampling/02-review-gpt55pro.md` against
the current `aria_nbv` implementation and public theory page, without runtime
code changes.

## Method

Read the review, source-order guidance, docs guidance, agents-db schema, the
current theory page, target selector implementation, candidate mixture and
position sampling code, rollout branch selection, and rollouts.zarr persistence.
The review's `position_id` persistence finding was stale for the current
checkout because `candidate_diagnostics/position_id` is written, but the
join/validation concern remains valid for training and inspection profiles.

## Outputs

Amended `issue-020` and existing todos instead of creating duplicate backlog
items:

- `todo-029`: target selector threshold/profile calibration, raw-vs-clipped
  projected area, score-factor decoupling, GT-match audit separation, and robust
  target softmax or stratified sampling.
- `todo-028`: realistic candidate profile matrix, angular-cap caveat,
  horizontal target-bearing displacement option, and three-family production
  profile before using the current five-family sampler as the main evidence.
- `todo-030`: per-component valid-count, invalid-reason, selected-frequency,
  final-motion, and oracle-gain diagnostics so valid-budget collapse is not
  mistaken for no planning headroom.
- `todo-027`: diversity guard activation/fallback reporting and stochastic
  rollout provenance diagnostics.
- `todo-058`: retention-profile handling for target eval crops and joinable
  candidate provenance including `position_id`.

Updated `docs/contents/theory/candidate_sampling_target_selection.qmd` to mark
the current formulas as implementation utilities, explain scale-readiness
caveats, state that projected visibility should be clipped for production,
clarify that angular caps constrain raw draws rather than final target-aware
movement, and add the recommended profile matrix.

## Verification

- `make agents-db AGENTS_ARGS='validate'`
- `make agents-db`
- `make qmd-frontmatter-check`
- `cd docs && quarto render contents/theory/candidate_sampling_target_selection.qmd`
- `rg -n "TODO|alreadyvsaturated" docs/contents/theory/candidate_sampling_target_selection.qmd`

## Canonical State Impact

No canonical memory update needed. The durable outcome is active backlog scope
and public theory clarification, not a new project-wide decision.
