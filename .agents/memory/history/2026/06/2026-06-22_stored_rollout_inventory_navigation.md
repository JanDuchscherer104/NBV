---
id: 2026-06-22_stored_rollout_inventory_navigation
date: 2026-06-22
title: "Stored Rollout Inventory Navigation"
status: done
topics: [rollouts, streamlit, zarr, inspection]
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

Implemented the fourth Ralph iteration for rollout visual inspection: clearer
rollout-store inventory navigation and field help.

## Method

Added inventory-level health metrics before the detailed table so operators can
see discovered, current-valid, blocked, and observed rollout/step totals before
choosing a store. Expanded the inventory info popover with concrete field-level
meaning for schema, validation, observed/validator counts, mask fractions,
lineage columns, missing groups, and first errors.

## Verification

- `cd aria_nbv && uv run pytest tests/app/panels/test_counterfactual_rollouts_panel.py -q`
- `cd aria_nbv && uv run pytest tests/rendering/test_rendering_plotting_helpers.py tests/rollouts/test_zarr_store.py tests/rollouts/test_info_cli.py tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py tests/test_panels_dispatcher.py tests/test_streamlit_entry.py -q`
- `cd aria_nbv && uv run ruff check aria_nbv/app/panels/stored_rollouts.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `cd aria_nbv && uv run ruff format --check aria_nbv/app/panels/stored_rollouts.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `git diff --check`

## Canonical State Impact

No rollout schema or thesis contract changed. This is UI navigation and help
text around existing inventory data.
