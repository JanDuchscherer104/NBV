---
id: 2026-06-20_rollout_zarr_streamlit_inspection
date: 2026-06-20
title: "Rollout Zarr Streamlit Inspection"
status: done
topics: [rollouts, streamlit, inspection, qa]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/app/app.py
  - aria_nbv/aria_nbv/app/panels.py
  - aria_nbv/aria_nbv/app/panels/__init__.py
  - aria_nbv/aria_nbv/app/panels/stored_rollouts.py
  - aria_nbv/aria_nbv/rollouts/__init__.py
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py
  - aria_nbv/tests/rollouts/test_inspection.py
artifacts:
  - .omx/context/session-019edf35-rollout-app-autopilot-20260620T195122Z.md
  - .omx/plans/session-019edf35-rollout-app-deep-interview-20260620T195122Z.md
  - .omx/plans/session-019edf35-rollout-app-ralplan-20260620T195122Z.md
  - .omx/specs/session-019edf35-rollout-app-test-spec-20260620T195122Z.md
  - .omx/plans/session-019edf35-rollout-app-ultragoal-20260620T195122Z.md
  - .omx/plans/session-019edf35-rollout-app-code-review-20260620T195122Z.md
  - .omx/plans/session-019edf35-rollout-app-ultraqa-20260620T195122Z.md
---

## Task

User asked to continue the 2026-06-19 Codex session goals for rollout validation and inspection. The current correction was to stop using an external `plot_rollout_validation.py` script, avoid Matplotlib in the rollout QA surfaces, and make the Streamlit app the first-class place for stored rollout Zarr inspection.

## Method

The implementation added a package-level inspection helper, `rollout_step_objective_rows`, that derives per-step objective and branching rows from existing rollout Zarr arrays. The Streamlit app now registers a `Stored Rollout Zarr` page and the stored rollout panel renders Plotly tables/charts for cumulative target RRI, marginal target RRI, selected candidate labels, probability/entropy, candidate fanout, invalid fraction, and selected sampling-family provenance.

The rejected external script path `aria_nbv/scripts/plot_rollout_validation.py` is absent.

## Verification

Focused gates passed on 2026-06-20:

- `cd aria_nbv && uv run ruff check aria_nbv/app/app.py aria_nbv/app/panels.py aria_nbv/app/panels/__init__.py aria_nbv/app/panels/stored_rollouts.py aria_nbv/rollouts/inspection.py aria_nbv/rollouts/__init__.py tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py tests/test_streamlit_entry.py tests/app/test_rerun_launch.py tests/rerun_inspector/test_rollout_zarr_logger.py`
- `cd aria_nbv && uv run pytest tests/test_streamlit_entry.py tests/app/test_rerun_launch.py tests/app/panels/test_counterfactual_rollouts_panel.py tests/rollouts/test_inspection.py tests/rerun_inspector/test_rollout_zarr_logger.py -q`
- `rg -n "matplotlib|plt\\." aria_nbv/aria_nbv/app aria_nbv/aria_nbv/pose_generation aria_nbv/aria_nbv/rerun_inspector`
- `test ! -e aria_nbv/scripts/plot_rollout_validation.py`
- public import smoke for `NbvStreamlitApp`, `render_stored_rollouts_panel`, and `rollout_step_objective_rows`
- live Streamlit startup on `http://localhost:8503` with host-side `HTTP/1.1 200 OK` probe

The combined focused pytest run reported `45 passed, 15 warnings`. The warnings came from dependency imports, including package-level Matplotlib warnings, not from new repo Matplotlib usage in the checked surfaces.

## Canonical State Impact

No canonical thesis, roadmap, or package contract update is required for this slice. The change is an app and inspection utility improvement that keeps rollout schema ownership in the existing rollout Zarr implementation.
