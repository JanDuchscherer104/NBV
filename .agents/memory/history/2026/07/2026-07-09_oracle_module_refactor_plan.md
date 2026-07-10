---
id: 2026-07-09_oracle_module_refactor_plan
date: 2026-07-09
title: Oracle module refactor plan
status: done
topics:
  - aria_nbv
  - oracle-rri
  - rollouts
  - rri_metrics
  - architecture
confidence: medium
canonical_updates_needed:
  - aria_nbv/AGENTS.md
  - aria_nbv/aria_nbv/rri_metrics/AGENTS.md
  - aria_nbv/aria_nbv/rollouts/AGENTS.md
artifacts:
  - .omx/plans/plan-aria-nbv-oracle-module-refactor-20260709T123231Z.md
---

## Summary

Created a new planning artifact that supersedes the previous rri/rollouts/pipelines plan. The new plan accepts the user-directed architecture decision to create a dedicated `aria_nbv.oracle` module where scene and target RRI scorers, oracle evidence/input preparation, and oracle-label data-generation pipelines live.

## Key Decisions

- `aria_nbv.oracle` becomes the deep module for oracle label semantics and oracle data-generation pipelines.
- `aria_nbv.pipelines` is deleted as an active package after moving the current Oracle-RRI labeler.
- `aria_nbv.rri_metrics` becomes metric/objective computation only.
- `aria_nbv.rollouts` becomes replay/storage/inspection only.
- The execution plan requires net active LOC reduction, generated limited rollout dataset validation, Streamlit page validation, PR creation, and green GitHub CI.

## Evidence

- Graphify query surfaced the current dense cluster around `rollouts`, `rri_metrics.oracle`, `pipelines`, and app rollout readers.
- Source inspection found duplicated scorer skeletons, reward/eval helpers under rollouts, generation orchestration under rollouts, and mixed core/diagnostic rollout metrics under `rri_metrics/metrics/multi_step.py`.

## Validation

- Plan artifact was written to `.omx/plans/`.
- No package source code was edited.
