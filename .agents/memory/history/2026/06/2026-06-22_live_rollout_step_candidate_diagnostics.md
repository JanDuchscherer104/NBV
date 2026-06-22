---
id: 2026-06-22_live_rollout_step_candidate_diagnostics
date: 2026-06-22
title: "Live Rollout Step Candidate Diagnostics"
status: done
topics: [rollouts, streamlit, target-rri, candidate-generation, inspection]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/app/panels/counterfactual_rollouts.py
  - aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py
artifacts:
  - .omx/context/rollout-visual-inspection-20260622T095933Z.md
  - .omx/plans/handoff-visual-patterns-20260621T172534Z.json
---

## Task

Implemented the seventh Ralph iteration for rollout visual inspection: richer
live per-step candidate fanout diagnostics on the Counterfactual Rollouts page.

## Method

Added a step candidate diagnostics info popover, compact valid-candidate score
rows, selection probability/logit fields, decoded position/strategy provenance,
and Plotly score plots for selection score versus target metric, target metric
by position family, and selection probability mass. The score-row helper accepts
both compact-valid and full-shell aligned vectors to avoid mask-alignment errors.

## Verification

- `cd aria_nbv && uv run ruff format aria_nbv/app/panels/counterfactual_rollouts.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `cd aria_nbv && uv run ruff check aria_nbv/app/panels/counterfactual_rollouts.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `cd aria_nbv && uv run pytest tests/app/panels/test_counterfactual_rollouts_panel.py -q`
- `cd aria_nbv && uv run pytest tests/rollouts/test_inspection.py tests/rendering/test_rendering_plotting_helpers.py tests/app/panels/test_counterfactual_rollouts_panel.py -q`
- `git diff --check`
- `cd aria_nbv && uv run streamlit run aria_nbv/streamlit_app.py --server.port 8507 --server.address 0.0.0.0 --server.headless true`
- `curl -I --max-time 10 http://127.0.0.1:8507`

## Canonical State Impact

No rollout schema, generation policy, or target-RRI definition changed. This
iteration improves live qualitative QA for candidate-family diversity and
selected-action score support.
