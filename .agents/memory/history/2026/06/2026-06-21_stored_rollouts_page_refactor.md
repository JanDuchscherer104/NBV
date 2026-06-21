---
id: 2026-06-21_stored_rollouts_page_refactor
date: 2026-06-21
title: "Stored Rollouts Page Refactor"
status: done
topics: [streamlit, rollouts, zarr, inspection]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/app/panels/stored_rollouts.py
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/aria_nbv/rollouts/__init__.py
  - aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py
  - aria_nbv/tests/rollouts/test_inspection.py
---

## Task

Refactor `_page_stored_rollouts` into a first-class rollout Zarr inspection page, using `PathConfig` for path handling, Streamlit-native controls, Plotly charts, and existing ARIA-NBV inspection helpers rather than external plotting scripts.

## Outputs

- Added rollout-store discovery and inventory helpers for `*.zarr` stores under `PathConfig.offline_cache_dir`.
- Split the page into overview, validation, objectives, branching, targets, candidates, geometry, suspicious, and metadata tabs.
- Preserved stale-store diagnostics by showing observed row counts even when current-schema validation fails.
- Added help popovers for store discovery, schema validation, counts, objective metrics, branching provenance, masks, targets, geometry, and Rerun launch.
- Added feature-focused Streamlit `AppTest` coverage for current-schema and stale-store page behavior.

## Verification

- `cd aria_nbv && uv run pytest tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py -q`
- `cd aria_nbv && uv run ruff format --check aria_nbv/app/panels/stored_rollouts.py aria_nbv/rollouts/inspection.py aria_nbv/rollouts/__init__.py tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `cd aria_nbv && uv run ruff check aria_nbv/app/panels/stored_rollouts.py aria_nbv/rollouts/inspection.py aria_nbv/rollouts/__init__.py tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `git diff --check -- aria_nbv/aria_nbv/app/panels/stored_rollouts.py aria_nbv/aria_nbv/rollouts/inspection.py aria_nbv/aria_nbv/rollouts/__init__.py aria_nbv/tests/rollouts/test_inspection.py aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py`
- `rg -n "matplotlib|plot_rollout_validation" aria_nbv/app/panels/stored_rollouts.py aria_nbv/rollouts/inspection.py tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- Streamlit smoke: `uv run nbv-st --server.address 0.0.0.0 --server.port 8503 --server.headless true`; `curl -I http://127.0.0.1:8503` returned `200 OK`.

## Canonical State Impact

No thesis, roadmap, or durable project-state source changed. This was an implementation and inspection-surface refactor only.
