# Architect Review: `aria_nbv.rri_metrics` Architecture Plan

Verdict: APPROVE

Architectural status: CLEAR

## Summary

The plan is conceptually sound and matches the current smell: it collapses the
shallow `logging/` and `reporting/` folders into leaf modules, removes the
broad `metrics` barrel, and splits rollout code into core tensor returns,
diagnostics, table adapters, and stateful TorchMetric wrappers.

The typed-state requirement is justified: `torchmetrics_single.py` already uses
class-level typed state docs, while `torchmetrics_multi.py` relies on
`add_state(...)` without that pattern.

## Required Changes

None.

## Non-Blocking Recommendations

- Keep `objectives/` unchanged in the first pass. Renaming it to `ordinal/` is
  optional churn because callers already import `rri_metrics.objectives.*` in
  Lightning, app panels, and tests.
- Keep `rollout/__init__.py`, `oracle/__init__.py`, and `objectives/__init__.py`
  narrow or empty so the plan does not recreate a mid-level barrel.
- Keep `tables.py` as a report adapter only; current UI callers already treat
  rollout summaries that way.

## Execution-Order Risk

WP4 is the highest-blast-radius step because current callers still import from
`rri_metrics.metrics.*` in Lightning and tests. WP0's public-API contract tests
are the right guardrail, but the migration will look noisy until those leaf
imports are updated in the same branch.
