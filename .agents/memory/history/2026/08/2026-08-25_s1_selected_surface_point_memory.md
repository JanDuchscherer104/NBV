---
id: 2026-08-25_s1_selected_surface_point_memory
date: 2026-08-25
title: "S1 selected-surface point memory"
status: done
topics: [qh, scorer, scene-memory, selected-depth, point-set]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/data_handling/qh_contracts.py
  - aria_nbv/aria_nbv/vin/models/target_finite_horizon.py
  - aria_nbv/aria_nbv/vin/modules/qh_scene_encoders.py
  - docs/typst/shared/equations/model.typ
  - docs/typst/shared/glossary.typ
  - docs/typst/thesis/sections/04-method/04-01-scene-representation-requirements.typ
  - docs/typst/thesis/sections/04-method/04-02-descriptor-and-encoding-plan.typ
  - docs/typst/thesis/sections/04-method/04-05-finite-candidate-value-model.typ
codex_thread: codex://threads/01a033b8-ed20-76a0-9627-2679b556cbff
repo_object_format: sha1
repo_head: e81762a6acb7841554d03ebf64069a9cb4b49110
repo_branch: "codex/scorer-s1-selected-surface"
worktree_kind: linked
---

## Task
Add the first executable S1 selected-surface scene memory as an isolated, privileged control behind the modular finite-horizon scorer seam.

## Method
Kept H0 and all downstream scorer widths fixed; canonically backprojected only the strict causal CF-GT prefix; transformed surface points into the factual current camera; pooled a shared point MLP by masked mean and maximum with explicit support diagnostics; updated active Typst owners; and evaluated both regression and CORAL on the same bounded GPU smoke population.

## Findings
`aria_nbv/aria_nbv/vin/modules/qh_scene_encoders.py` now owns a discriminated S0/S1 carrier family and a chunk-bounded, density-weighted S1 residual. `aria_nbv/aria_nbv/vin/models/target_finite_horizon.py` adapts static `[B,F]` and dynamic `[B,S,F]` carriers without changing the scorer interface or allowing `action_mask` into raw predictions. A CUDA epoch exposed that differentiable chunk accumulators cannot be mutated across autograd nodes; rebinding `index_add` and `scatter_reduce` outputs repaired the failure, and the regression now forces multiple chunks. Active equations, glossary entries, and method prose record the exact geometry, information exclusions, and evidence boundary.

## Commits
- [e81762a6acb7841554d03ebf64069a9cb4b49110](https://github.com/JanDuchscherer104/ARIA-NBV/commit/e81762a6acb7841554d03ebf64069a9cb4b49110) — S1 implementation, tests, equations, glossary, and method alignment

## Verification
`make qh-ci` passed Ruff/format and 583 tests. `make thesis-pdf-ci` passed. `make quarto-docs-ci` rendered 30 pages with only pre-existing unresolved-link warnings. Professor-critic review approved with no P0-P2. Exact clean head `e81762a6acb7841554d03ebf64069a9cb4b49110` completed one seeded RTX 3080 Ti epoch for regression and CORAL; each performed one optimizer update and evaluated eight validation rows. No held-out CF+ test shard exists, so these runs establish trainability rather than representation gain.

## Canonical Owner Impact
Python owners now define S1 runtime behavior and representation identity. Shared Typst equations/glossary and active method sections now define the same causal transform, fixed-width residual, density weighting, privileged source profile, and deferred candidate-local/ray-aware interactions. No competing architecture source of truth was added.
