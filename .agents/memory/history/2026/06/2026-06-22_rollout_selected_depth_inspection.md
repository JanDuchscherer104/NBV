---
id: 2026-06-22_rollout_selected_depth_inspection
date: 2026-06-22
title: "Rollout Selected-Depth Inspection"
status: done
topics: [rollouts, streamlit, zarr, inspection]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/aria_nbv/rollouts/__init__.py
  - aria_nbv/aria_nbv/app/panels/stored_rollouts.py
  - aria_nbv/tests/rollouts/test_inspection.py
  - aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py
artifacts:
  - .omx/context/rollout-visual-inspection-20260622T095933Z.md
  - .omx/plans/handoff-visual-patterns-20260621T172534Z.json
---

## Task

Implemented the first Ralph iteration for the rollout visual inspection plan:
selected-action depth summaries and quicklook support for stored rollout Zarr
inspection.

## Method

Added bounded `aria_nbv.rollouts.inspection` helpers for selected-depth summary
rows and single-step preview payloads. Wired `Stored Rollout Zarr` with an
additive `Selected Depth` tab that uses existing Plotly depth-grid utilities.
No standalone plotting scripts or matplotlib paths were added.

## Verification

- `cd aria_nbv && uv run pytest tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py -q`
- `cd aria_nbv && uv run pytest tests/rollouts/test_zarr_store.py tests/rollouts/test_info_cli.py tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py -q`
- `cd aria_nbv && uv run ruff check aria_nbv/rollouts/inspection.py aria_nbv/rollouts/__init__.py aria_nbv/app/panels/stored_rollouts.py tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `cd aria_nbv && uv run ruff format --check aria_nbv/rollouts/inspection.py aria_nbv/rollouts/__init__.py aria_nbv/app/panels/stored_rollouts.py tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `git diff --check`
- Streamlit server started locally on `http://127.0.0.1:8507`; host-side `curl -I` returned `200 OK`. Browser MCP access to the host port was blocked by container networking, so Streamlit `AppTest` smoke coverage was used for the page interaction gate.

## Canonical State Impact

No durable thesis or package contract changed. This is an app/inspection
implementation slice under the existing rollout Zarr selected-depth contract.
