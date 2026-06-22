---
id: 2026-06-22_rollout_tree_live_inspection
date: 2026-06-22
title: "Rollout Tree And Live Inspection"
status: done
topics: [rollouts, streamlit, zarr, inspection]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/aria_nbv/rollouts/__init__.py
  - aria_nbv/aria_nbv/app/panels/stored_rollouts.py
  - aria_nbv/aria_nbv/app/panels/counterfactual_rollouts.py
  - aria_nbv/tests/rollouts/test_inspection.py
  - aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py
artifacts:
  - .omx/context/rollout-visual-inspection-20260622T095933Z.md
  - .omx/plans/handoff-visual-patterns-20260621T172534Z.json
---

## Task

Implemented the second Ralph iteration for rollout visual inspection:
selected-branch tree/provenance summaries for stored rollout stores, live
selected-depth availability inspection, and useful live rollout log rendering.

## Method

Added `rollout_tree_summary_rows` to the rollout inspection layer so the app can
visualize selected-branch provenance without owning Zarr joins. Wired Stored
Rollouts with tree summary tables, sunburst provenance, validity/objective
diagnostic plots, and section-level info popovers. Wired Counterfactual Rollouts
with a `Selected Depth` result tab that previews retained selected-step depth
images when present and explicitly reports when live runs did not retain depth.
The existing Logs tab now renders captured Console output.

No standalone plotting scripts or matplotlib paths were added.

## Verification

- `cd aria_nbv && uv run pytest tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py -q`
- `cd aria_nbv && uv run pytest tests/rollouts/test_zarr_store.py tests/rollouts/test_info_cli.py tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py tests/test_panels_dispatcher.py tests/test_streamlit_entry.py -q`
- `cd aria_nbv && uv run ruff check aria_nbv/rollouts/inspection.py aria_nbv/rollouts/__init__.py aria_nbv/app/panels/stored_rollouts.py aria_nbv/app/panels/counterfactual_rollouts.py tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `cd aria_nbv && uv run ruff format --check aria_nbv/rollouts/inspection.py aria_nbv/rollouts/__init__.py aria_nbv/app/panels/stored_rollouts.py aria_nbv/app/panels/counterfactual_rollouts.py tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `git diff --check`
- Streamlit server started locally on `http://127.0.0.1:8507`; host-side `curl -I` returned `200 OK`.

## Canonical State Impact

No durable thesis or rollout schema contract changed. The implementation exposes
existing stored selected-step provenance and makes live selected-depth retention
state explicit.
