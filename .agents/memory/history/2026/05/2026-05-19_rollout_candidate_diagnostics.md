---
id: 2026-05-19_rollout_candidate_diagnostics
date: 2026-05-19
title: "Rollout Candidate Diagnostics Schema"
status: done
topics: [rollouts, rerun, candidate-generation, data-layout]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/pose_generation/candidate_generation_rules.py
  - aria_nbv/aria_nbv/rollouts/zarr_store.py
  - aria_nbv/aria_nbv/rerun_inspector/_rollout_zarr.py
  - aria_nbv/aria_nbv/rerun_inspector/_blueprint.py
  - aria_nbv/aria_nbv/data_handling/README.md
  - docs/typst/shared/data-layout-trees.typ
---

## Task

Implemented rollout schema `0.9-candidate-diagnostics` with a typed
`candidate_diagnostics/` group aligned to `candidates/candidate_row_id`.
The group retains candidate-generation audit metrics such as mesh distance,
path clearance, free-space margin, motion diagnostics, and target distance.

## Method

Diagnostics are recorded at the generation-rule source, persisted as typed Zarr
arrays, and kept out of `q_h/`. Rerun camera metadata was pruned to curated
human-facing fields, while selected depth and point-cloud entities remain logged
but are hidden by the default blueprint. `/world/efm/obbs/detected` is also
hidden by default.

## Verification

- `cd aria_nbv && uv run pytest tests/pose_generation tests/rollouts tests/rerun_inspector -q`
  passed with 160 tests.
- `cd aria_nbv && uv run ruff check aria_nbv/pose_generation aria_nbv/rollouts aria_nbv/rerun_inspector tests/pose_generation tests/rollouts tests/rerun_inspector`
  passed.

## Canonical State Impact

No additional canonical memory update is needed. The active schema and layout
were updated in the rollout code, data-handling README, Typst layout tree, and
rollout contract reference.
