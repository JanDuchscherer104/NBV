---
id: 2026-06-18_target_task_sampler_method_split
date: 2026-06-18
title: "Target Task Sampler Method Split"
status: done
topics: [thesis, typst, target-selection, data-generation]
confidence: high
canonical_updates_needed:
  - docs/contents/thesis/questions.qmd
  - docs/contents/thesis/roadmap.qmd
  - .agents/memory/state/DECISIONS.md
  - .agents/memory/state/OPEN_QUESTIONS.md
  - .agents/memory/state/PROJECT_STATE.md
  - aria_nbv/aria_nbv/oracle/target_selection.py
  - .configs/build_rollouts_v1_realistic.toml
artifacts:
  - docs/typst/thesis/sections/03-oracle-and-data-generation/03-01-state-and-visibility.typ
  - docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ
  - docs/typst/thesis/sections/04-method/index.typ
  - docs/typst/thesis/sections/thesis-questions.md
  - .omx/specs/target-task-sampler-implementation-plan.md
---

## Task

Implemented the target-selection planning decision from 2026-06-18 in the
active thesis seed. The method chapter now has split files for formal state and
data generation. Target selection is framed as oracle target-task sampling for
supervised target-conditioned NBV, not deployable actor-visible target discovery.

## Findings

The previous active method prose still described OBS-SEL / PRED-Q / GT-EVAL and
actor-visible target-interest ranking as the core target protocol. The user
corrected that source-truth boundary: target selection belongs to oracle data
generation, and the learned model is conditioned on selected target tasks.

## Output

Moved the formal-state prose into `03-01-formal-state.typ`, moved target-task
sampling and target-specific RRI labels into `03-02-data-generation.typ`, and
kept `03-method.typ` as the Method chapter entrypoint. Added a follow-up
implementation plan under `.omx/specs/target-task-sampler-implementation-plan.md`.

## Verification

Run the Typst compile and agent-memory checks from the implementation turn
before treating the thesis seed as fully verified.
