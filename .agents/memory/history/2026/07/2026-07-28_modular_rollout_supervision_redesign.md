---
id: 2026-07-28_modular_rollout_supervision_redesign
date: 2026-07-28
title: "Modular Rollout Supervision Redesign"
status: done
topics: [streamlit, rollouts, qh, topology, inspection, ultragoal]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts/
  - aria_nbv/aria_nbv/dataset_topology/
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/tests/app/panels/test_stored_rollouts_panel.py
  - aria_nbv/tests/app/panels/test_qh_admission.py
  - aria_nbv/tests/test_dataset_topology_runtime.py
---

## Task

Replace the monolithic stored-rollout Streamlit inspector with a modular,
science-first page while preserving its stable entry point, direct inspection,
and Rerun workflow.

## Outcome

- Reduced `_stored_rollouts_page.py` to a thin coordinator over seven lazy,
  independently removable sections.
- Added a typed `StoredRolloutSession` that owns reader lifecycle, validation,
  capabilities, inventory fallback, named projections, and complete cache
  invalidation.
- Replaced the single topology module with one import-compatible
  `dataset_topology` package owning semantic, physical Zarr, and runtime DTO
  topology plus shared rendering.
- Added automatic reconstruction/return summaries and exact, fail-closed oracle
  headroom evidence. Invalidity remains a hard mask/reason contract.
- Added lightweight candidate composition by default and explicit opt-in heavy
  sampling, geometry, motion, selection, and rank/regret evidence.
- Added experiment-TOML-only QH admission with all-stage preflight and bounded
  one-chain/one-batch topology inspection.
- Deleted the pandas query/promotion workbench while retaining direct lineage,
  depth, export, and Rerun inspection. The test split now isolates stored-rollout
  behavior, and `counterfactual_rollouts.py` production code was left untouched.
- The final cleaner removed a net 101 lines after review repairs, without
  reopening deleted query machinery or adding compatibility wrappers.
- Preserved all unrelated pre-existing worktree changes.

## Review repairs

- Real-store oracle headroom now resolves policy roles explicitly and isolates
  treatment-aware exact cohorts before comparing endpoints.
- QH lineage handoff is source-exact within one store and transfers the complete
  direct-inspection state keys rather than matching a partial identity.
- Candidate evidence owns and applies exact cohort isolation before calculating
  composition, geometry, selection, or rank/regret summaries.
- Persisted and runtime inspectors consume one shared topology contract, and all
  17 new modules pass strict typing. The legacy `rollouts/inspection.py` module
  remains outside that strict-mypy claim.
- A bounded test-only fixture drift repair aligned synthetic fixtures with the
  production store contract; it did not change runtime behavior.

## Verification

- Targeted Ruff formatting and lint checks passed.
- Strict mypy passed for the 17 new modules only; no claim is made for the
  legacy `rollouts/inspection.py` module.
- The final affected-surface suite passed with `152 passed`; the broader
  verification suite passed with `88 passed, 1 skipped`, where the skip was an
  explicit dependency-availability condition.
- Headless Streamlit health returned `ok`.
- `make check-agent-memory` and task-scoped `git diff --check` passed.
- Graphify structural refresh succeeded. Its freshness command remains nonzero
  by design while corpus changes are uncommitted and semantic extraction is
  pending.
- Independent code review returned `APPROVE` with no findings, and the
  independent architect review returned `CLEAR`.

## Canonical state impact

None. The redesign changes read-only inspection and presentation ownership; it
does not change persisted VIN/rollout schemas, generation policy, or the QH
training contract.
