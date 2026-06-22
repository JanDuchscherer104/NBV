---
id: 2026-06-22_stored_rollout_distribution_diagnostics
date: 2026-06-22
title: "Stored Rollout Distribution Diagnostics"
status: done
topics: [rollouts, streamlit, zarr, inspection, visualization]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/app/panels/stored_rollouts.py
  - aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py
artifacts:
  - .omx/context/rollout-visual-inspection-20260622T095933Z.md
  - .omx/plans/handoff-visual-patterns-20260621T172534Z.json
---

## Task

Implemented the fifth Ralph iteration for rollout visual inspection: candidate
distribution and selection diagnostics in the stored rollout Geometry tab.

## Method

Added bounded Plotly diagnostics over existing `candidate_audit_rows` output:
world X/Z candidate-center scatter, candidate height versus forward position,
target-bearing and motion-yaw angle histograms, motion step-length versus yaw
scatter, and target-root-gain by selected family. Added an info popover that
explains what these plots diagnose and states that they summarize persisted
candidate rows rather than reconstructing unexpanded search-tree edges.

## Verification

- `cd aria_nbv && uv run ruff format aria_nbv/app/panels/stored_rollouts.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `cd aria_nbv && uv run ruff check aria_nbv/app/panels/stored_rollouts.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `cd aria_nbv && uv run pytest tests/app/panels/test_counterfactual_rollouts_panel.py -q`
- `cd aria_nbv && uv run pytest tests/rollouts/test_inspection.py tests/rendering/test_rendering_plotting_helpers.py tests/app/panels/test_counterfactual_rollouts_panel.py -q`
- `git diff --check`
- `cd aria_nbv && uv run streamlit run aria_nbv/streamlit_app.py --server.port 8507 --server.address 0.0.0.0 --server.headless true`
- `curl -I --max-time 10 http://127.0.0.1:8507`

## Canonical State Impact

No rollout schema, thesis contract, or target-selection policy changed. This
iteration only improves first-class inspection of stored rollout candidate
coverage and selection behavior.
