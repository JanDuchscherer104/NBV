---
id: 2026-08-20_default_3d_candidate_geometry
date: 2026-08-20
title: "Default 3D Candidate Geometry"
status: done
topics: [streamlit, rollouts, candidate-geometry]
confidence: high
canonical_updates_needed: []
---

## Task

Show bounded candidate geometry by default and add a root-relative three-dimensional view.

## Method

Reused the existing bounded candidate audit and root-relative coordinates; removed only its outer UI toggle and rendered Plotly's native 3D scatter beside the existing ground-plane plot.

## Findings

- `aria_nbv/aria_nbv/app/panels/_stored_rollouts/validity_support.py` now always dispatches the bounded geometry diagnostics.
- `aria_nbv/aria_nbv/app/panels/_stored_rollouts/candidate_generation.py` adds a finite-X/Y/Z 3D root-relative plot with the existing family/selected encodings and scientific context.
- `aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py` verifies default visibility and a `scatter3d` trace.

## Verification

- `uv run pytest -q tests/app/panels/test_counterfactual_rollouts_panel.py` — 55 passed.
- Ruff format/check, compileall for changed modules, and `git diff --check` passed.

## Canonical Owner Impact

Only Streamlit presentation owners and focused UI tests changed; no rollout schema, generation, configuration, or training contract changed.
