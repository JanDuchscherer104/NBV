---
id: 2026-06-22_live_depth_obb_projection
date: 2026-06-22
title: "Live Depth OBB Projection"
status: done
topics: [rollouts, streamlit, rendering, geometry]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/rendering/plotting.py
  - aria_nbv/aria_nbv/app/panels/counterfactual_rollouts.py
  - aria_nbv/tests/rendering/test_rendering_plotting_helpers.py
  - aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py
artifacts:
  - .omx/context/rollout-visual-inspection-20260622T095933Z.md
  - .omx/plans/handoff-visual-patterns-20260621T172534Z.json
---

## Task

Implemented the third Ralph iteration for rollout visual inspection: projected
target OBB overlays on retained live selected-depth images.

## Method

Added shared Plotly rendering helpers for projecting world-frame points into
selected-depth image coordinates and drawing projected OBB wireframes over the
existing `FrameGridBuilder` depth-grid path. Wired Counterfactual Rollouts so
the live `Selected Depth` tab can overlay actor-visible and matched GT target
OBBs when the selected step retained depth and camera metadata.

Stored rollout Zarr stores currently persist selected-depth rasters and target
projection scalar diagnostics, but not actor/GT OBB tensors or 2D box corners.
The stored page therefore does not synthesize fake boxes; full stored overlay
support requires persisting the required target geometry or linking back to the
source VIN sample.

## Verification

- `cd aria_nbv && uv run pytest tests/rendering/test_rendering_plotting_helpers.py tests/app/panels/test_counterfactual_rollouts_panel.py tests/rollouts/test_inspection.py -q`
- `cd aria_nbv && uv run pytest tests/rendering/test_rendering_plotting_helpers.py tests/rollouts/test_zarr_store.py tests/rollouts/test_info_cli.py tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py tests/test_panels_dispatcher.py tests/test_streamlit_entry.py -q`
- `cd aria_nbv && uv run ruff check aria_nbv/rendering/plotting.py aria_nbv/app/panels/counterfactual_rollouts.py tests/rendering/test_rendering_plotting_helpers.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `cd aria_nbv && uv run ruff format --check aria_nbv/rendering/plotting.py aria_nbv/app/panels/counterfactual_rollouts.py tests/rendering/test_rendering_plotting_helpers.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `git diff --check`
- Streamlit server started locally on `http://127.0.0.1:8507`; host-side `curl -I` returned `200 OK`.

## Canonical State Impact

No thesis or rollout schema contract changed. This implementation exposes the
current live data contract and documents that stored overlay support needs
additional persisted geometry or source-sample lookup.
