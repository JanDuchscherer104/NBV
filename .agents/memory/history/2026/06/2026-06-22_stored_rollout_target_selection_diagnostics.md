---
id: 2026-06-22_stored_rollout_target_selection_diagnostics
date: 2026-06-22
title: "Stored Rollout Target Selection Diagnostics"
status: done
topics: [rollouts, streamlit, target-selection, zarr, inspection]
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

Implemented the sixth Ralph iteration for rollout visual inspection: target
selection QA in the stored rollout Targets tab.

## Method

Added target-pool health metrics, a field-level info popover, rank versus
selection-score plotting, selection-score versus support/area plotting, target
score-component scatter matrix, and class/source/invalid-reason breakdowns.
The diagnostics use existing `target_audit_rows` fields and keep invalid GT
targets as audit evidence rather than labels.

## Verification

- `cd aria_nbv && uv run ruff format aria_nbv/app/panels/stored_rollouts.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `cd aria_nbv && uv run ruff check aria_nbv/app/panels/stored_rollouts.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `cd aria_nbv && uv run pytest tests/app/panels/test_counterfactual_rollouts_panel.py -q`
- `cd aria_nbv && uv run pytest tests/rollouts/test_inspection.py tests/rendering/test_rendering_plotting_helpers.py tests/app/panels/test_counterfactual_rollouts_panel.py -q`
- `git diff --check`
- `cd aria_nbv && uv run streamlit run aria_nbv/streamlit_app.py --server.port 8507 --server.address 0.0.0.0 --server.headless true`
- `curl -I --max-time 10 http://127.0.0.1:8507`

## Canonical State Impact

No rollout schema, target-selection policy, or thesis claim changed. This
iteration improves inspection of stored target-pool validity and selection-score
composition.
