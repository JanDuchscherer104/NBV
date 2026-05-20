---
id: 2026-05-20_streamlit_rollout_page_stress_test
date: 2026-05-20
title: "Streamlit Rollout Page Stress Test"
status: done
topics: [streamlit, rollouts, target-selection, candidate-generation, diagnostics]
confidence: high
canonical_updates_needed: []
artifacts:
  - .artifacts/streamlit_stress/rollouts_current_smoke.zarr
  - .artifacts/streamlit_stress/screenshots/
---

## Task

Stress-tested the affected Streamlit pages after the rollout inspection fixes:
Counterfactual Rollouts, VIN Offline Dataset / Stored Rollouts, and Candidate
Poses.

## Method

Created a current-schema synthetic rollout store at
`.artifacts/streamlit_stress/rollouts_current_smoke.zarr` with 3 rollouts,
6 steps, and 96 candidates, then validated it with `validate_rollout_zarr_store`.
Started the Streamlit app locally and drove it with native Playwright using
`/usr/bin/google-chrome`; MCP_DOCKER browser tools could not reach the host
Streamlit port from their container network.

## Findings

- Counterfactual Rollouts loaded actor-visible targets, expanded the
  target-selection audit, and rendered the projected-area fallback warning for
  rows whose actor-visible OBB source has no valid EFM `bb2_*` projections.
- The live rollout "Run / refresh live rollouts" path completed the CUDA
  PyTorch3D target-RRI rollout and no longer raised the compact-valid metric
  shape error.
- Stored Rollouts now treats the stale default `rollouts_v1_smoke.zarr` as a
  validation failure without crashing or reading incompatible `q_h` arrays.
- Stored Rollouts renders the current-schema synthetic store, including the
  validation OK state and rollout QA tabs.
- Candidate Poses rendered and refreshed a live candidate shell with the
  target-conditioned/provenance controls visible and no page errors.
- Narrow viewport smoke checks for Counterfactual Rollouts and Stored Rollouts
  completed without tracebacks.

## Verification

- `cd aria_nbv && uv run --with playwright python ...` browser stress scripts
  against the live Streamlit app.
- `cd aria_nbv && uv run pytest tests/app/panels/test_counterfactual_rollouts_panel.py tests/app/panels/test_candidates_panel.py tests/rollouts/test_inspection.py tests/rerun_inspector/test_rollout_zarr_logger.py -q`
- `cd aria_nbv && uv run ruff check aria_nbv/app aria_nbv/rollouts aria_nbv/rerun_inspector tests/app/panels/test_counterfactual_rollouts_panel.py tests/app/panels/test_candidates_panel.py tests/rollouts/test_inspection.py`

## Canonical State Impact

No canonical updates are needed. The stale default rollout store remains stale
and should be regenerated before it is used as the default Stored Rollouts
example.
