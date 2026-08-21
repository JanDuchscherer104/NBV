---
id: 2026-08-21_candidate_geometry_scientifically_consistent_normalization
date: 2026-08-21
title: "Candidate geometry scientifically consistent normalization"
status: done
topics: [rollouts, inspection, streamlit, geometry, typst]
confidence: high
canonical_updates_needed: []
codex_thread: codex://threads/019fffa4-b85c-7db1-8404-d69c73e6485e
---

## Task
Replace the ambiguous fixed-root candidate scatter with explicit proposal-support and factual-trajectory views using scientifically consistent, auditable normalization.

## Method
Deepened the presentation-free rollout inspection owner first, migrated both Streamlit renderers and caches to its typed projection, then registered the two normalization equations in the shared Typst notation owner.

## Findings
- `aria_nbv/aria_nbv/rollouts/inspection.py` now reconstructs each factual expansion pose, supports target-aligned and rig-forward Z-up proposal frames, and emits a separate initial-root factual trajectory projection.
- `aria_nbv/aria_nbv/app/panels/_stored_rollouts/` renders matched default-visible 2D/3D views from those projections; only factual selected trajectories are connected.
- `docs/typst/shared/equations/spatial.typ` and `docs/notation.yml` own the proposal and trajectory normalization formulas used by the scientific explanations.
- The old fixed-root projection functions and cache aliases were removed rather than retained as compatibility paths.

## Verification
- `uv run --project aria_nbv pytest -q ...test_inspection.py ...test_stored_rollouts_projection_laziness.py ...test_stored_rollouts_theory.py ...test_counterfactual_rollouts_panel.py`: 166 passed.
- Ruff format/check passed on all changed Python files.
- `make glossary` and `make typst-authoring-contract` passed.
- `uv run --project aria_nbv python -m compileall -q ...` and `git diff --check` passed.

## Canonical Owner Impact
- Python inspection, Streamlit presentation, focused tests, shared spatial equations, and generated notation artifacts were updated. No Zarr schema, generation, training, service, dependency, or Rerun control changed.
