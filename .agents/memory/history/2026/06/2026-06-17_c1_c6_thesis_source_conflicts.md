---
id: 2026-06-17_c1_c6_thesis_source_conflicts
date: 2026-06-17
title: "C1-C6 Thesis Source Conflict Repair"
status: done
topics: [thesis, source-order, roadmap, questions, rri, rollouts]
confidence: high
canonical_updates_needed:
  - .agents/memory/state/PROJECT_STATE.md
  - .agents/memory/state/DECISIONS.md
  - .agents/memory/state/OPEN_QUESTIONS.md
files_touched:
  - AGENTS.md
  - docs/index.qmd
  - docs/contents/thesis/questions.qmd
  - docs/contents/thesis/roadmap.qmd
  - docs/contents/thesis/advisor_meeting_2026_05_22_questions.md
  - docs/typst/shared/equations/entity.typ
  - docs/typst/thesis/advisor_distillation.typ
  - docs/typst/thesis/sections/proposal/02-problem.typ
  - docs/typst/thesis/sections/proposal/04-method.typ
  - docs/typst/thesis_slides/slides_thesis_outlook.typ
  - .agents/skills/counterfactual-rollout-planner/SKILL.md
  - .agents/todos.toml
---

## Task

Resolve the first six thesis source-of-truth conflicts: demote the seminar
paper from current thesis truth, adopt the 2026-05-22 advisor RQ order, separate
root-normalized rollout training return from state-relative diagnostic RRI,
leave gamma open, clarify that counterfactual rollout traces belong in
standalone `rollouts.zarr`, and make online discrete `Q_H` the RQ5 bridge after
offline `Q_H`.

## Method

The public thesis docs were updated first, then canonical memory and active
agent guidance were aligned to the same owner split. Historical transcript and
old debrief records were left untouched as archive evidence.

## Outputs

- `docs/contents/thesis/questions.qmd` now uses the May 22 order: RQ1 method,
  RQ2 offline finite-candidate `Q_H`, RQ3 actor-visible representations, RQ4
  candidate/rollout/scale support, RQ5 online discrete `Q_H`, and RQ6
  continuous or simulator escalation.
- Public reward prose now uses root-normalized target gain as the default
  rollout and `Q_H` reward; state-relative RRI is diagnostic/VIN-compatible.
- The historical outlook slide deck is marked low-trust and uses
  `rollouts.zarr` for rollout traces while leaving gamma open.
- Canonical state records now distinguish the RQ5 online-discrete bridge from
  generic Gymnasium/SB3/external simulator online RL.

## Verification

Run `git diff --check`, `make check-agent-memory`,
`make qmd-frontmatter-check`, render the touched Quarto thesis pages, and render
the touched Typst slide deck when local assets and tools permit.
