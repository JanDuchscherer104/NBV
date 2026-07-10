---
id: 2026-07-09_aria_nbv_module_pruning_autoresearch
date: 2026-07-09
title: "ARIA-NBV Module Pruning Autoresearch"
status: done
topics: [aria-nbv, architecture, oracle, rollouts, rri-metrics, data-handling]
confidence: high
canonical_updates_needed: []
artifacts:
  - .omx/specs/autoresearch-aria-nbv-module-pruning-20260709/report.md
  - .omx/specs/autoresearch-aria-nbv-module-pruning-20260709/architecture-pruning-map.html
  - .omx/specs/autoresearch-aria-nbv-module-pruning-20260709/completion.json
---

## Task

Aggregated prior `.omx` refactor plans and current code evidence into a coherent module-ownership proposal for `data_handling`, a new `oracle` package, `rollouts`, current `rri_metrics`/future `metrics`, and historical `pipelines`.

## Method

Used Graphify first for architecture overlap evidence, then integrated existing plans and current source scans. Spawned independent `architect`, `code-simplifier`, and `code-reviewer` lanes for architecture and pruning evidence. No source code was changed.

## Findings

The key correction is that metric formulas must have a single owner in metrics. `oracle` owns evidence preparation and label/scorer semantics, but calls metrics for RRI, root/log/endpoint gains, and selected returns. `rollouts` should shrink to replay, storage, and inspection. `data_handling` should own raw/offline/target source semantics. Top-level `pipelines` should become historical compatibility only.

## Verification

Artifacts were written under `.omx/specs/autoresearch-aria-nbv-module-pruning-20260709/`. JSON syntax, required artifact headings, and agent-memory validation were run after writing.

## Canonical State Impact

No canonical state files were updated. The artifact recommends future nested package guide updates during implementation.
