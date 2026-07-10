---
id: 2026-07-08_rri_metrics_hierarchy_refactor
date: 2026-07-08
title: "RRI Metrics Hierarchy Refactor"
status: done
topics: [aria-nbv, rri-metrics, package-architecture, refactor]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/rri_metrics/AGENTS.md
  - aria_nbv/aria_nbv/rri_metrics/
  - docs/reference/
---

## Task

Implemented the 2026-07-08 clean-rename hierarchy refactor for
`aria_nbv.rri_metrics`, replacing flat metric/oracle/objective/logging files
with explicit submodules for metric computation, oracle evidence/scoring,
ordinal objectives, logging names, reporting, and single-step vs multi-step
evaluation.

## Method

Moved the old flat modules into the new hierarchy, split the previous mixed
`logging.py` into `logging/names.py`, `metrics/single_step.py`, and
`metrics/torchmetrics_single.py`, and updated imports across package code,
tests, scripts, and reference docs. The current root API remains compact.

One existing flat file, `rri_metrics/rollout.py`, was preserved as
`metrics/multi_step_tables.py` because it owns selected-rollout mapping
summaries that are distinct from tensor reducers in `metrics/multi_step.py`.

## Verification

- `cd aria_nbv && uv run ruff format --check ...` on touched Python files.
- `cd aria_nbv && uv run ruff check ...` on touched Python files.
- `cd aria_nbv && uv run pytest tests/rri_metrics tests/vin/test_rri_binning.py tests/vin/test_coral.py tests/lightning/test_vin_batch_collate.py tests/rollouts/test_counterfactuals.py tests/data_handling/test_vin_offline_store.py` passed with 171 tests.
- Strict stale old-module scan found no remaining old flat `rri_metrics` module paths.
- `graphify update .` completed and refreshed `graphify-out/`.

## Canonical State Impact

No thesis or semantic metric meaning changed. The durable package owner map was
updated in `aria_nbv/aria_nbv/rri_metrics/AGENTS.md`.
