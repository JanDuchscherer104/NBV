# Autoresearch Mission: ARIA-NBV Module Pruning And Ownership

Date: 2026-07-09

## Goal

Aggregate the recent ARIA-NBV refactor plans, current code evidence, Graphify evidence, and independent review lanes into one coherent architecture direction for:

- `aria_nbv.data_handling`
- the proposed top-level `aria_nbv.oracle`
- `aria_nbv.rollouts`
- `aria_nbv.rri_metrics`, whose long-term logical name should be `aria_nbv.metrics`
- the historical `aria_nbv.pipelines`

The target result is not a source-code refactor. It is an execution-ready research artifact that decides module responsibilities, exposes redundancies, proposes pruning workpackages, and makes formula/scorer/storage ownership unambiguous before implementation.

## Non-Goals

- Do not implement the refactor in source code in this pass.
- Do not add target descriptors, new Q_H semantics, scene memory, or online RL behavior.
- Do not preserve broad compatibility wrappers as a default design choice.
- Do not move formulas into `oracle`; `oracle` may emit labels, but metric and gain math has a single owner in metrics.
- Do not move rollout replay storage into `data_handling`; rollout replay is not the same category as the VIN offline cache.

## Primary Inputs

- `.omx/plans/ralplan-rri-rollouts-oracle-pipelines-architecture-20260709T115007Z.md`
- `.omx/plans/plan-aria-nbv-oracle-module-refactor-20260709T123231Z.md`
- `.omx/specs/autoresearch-aria-nbv-oracle-boundaries-20260709/report.md`
- `.omx/specs/autoresearch-aria-nbv-refactor-evidence-20260708/report.md`
- Current code under `aria_nbv/aria_nbv/data_handling`, `rollouts`, `rri_metrics`, `pipelines`, `data`, and `rl`

## Validation Mode

`prompt-architect-artifact`

The artifact is considered complete for this pass when it:

1. States one coherent owner for each concept.
2. Resolves the metric formula vs oracle scorer conflict.
3. Provides proposed module trees and interactions.
4. Lists pruning targets and implementation workpackages in dependency order.
5. Includes an HTML map with user-facing diagrams, open decisions, and validation gates.
6. Records independent architect/code-review/simplification evidence.
