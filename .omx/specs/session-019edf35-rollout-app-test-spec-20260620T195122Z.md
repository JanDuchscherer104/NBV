# Test Spec: First-Class Rollout App Inspection

## Static / Import Checks

- `cd aria_nbv && uv run ruff check aria_nbv/aria_nbv/app/app.py aria_nbv/aria_nbv/app/panels.py aria_nbv/aria_nbv/app/panels/__init__.py aria_nbv/aria_nbv/app/panels/stored_rollouts.py`
- Verify no new Matplotlib usage in touched rollout app surfaces:
  `rg -n "matplotlib|plt\\." aria_nbv/aria_nbv/app aria_nbv/aria_nbv/pose_generation aria_nbv/aria_nbv/rerun_inspector`
- Verify the rejected external rollout script is absent:
  `test ! -e aria_nbv/scripts/plot_rollout_validation.py`

## Targeted Tests

- `cd aria_nbv && uv run pytest tests/rollouts/test_inspection.py -q`
- `cd aria_nbv && uv run pytest tests/app/test_rerun_launch.py -q`
- `cd aria_nbv && uv run pytest tests/rerun_inspector/test_rollout_zarr_logger.py -q`

## New/Updated Test Expectations

- Add or extend an app import/navigation test so `render_stored_rollouts_panel`
  is exposed from both `aria_nbv.app.panels` and the compatibility dispatcher
  `aria_nbv.app.panels.py`.
- Add helper-level tests for per-step objective/branching rows using synthetic
  rollout fixtures.
- Validate helper output includes chain/policy/step identities, cumulative and
  marginal objective values when present, and sampling provenance when present.
- The helper rows must be derived from existing `rollouts/`, `steps/`,
  `candidates/`, `candidate_diagnostics/`, `lineage/`, and dictionary arrays
  only. Do not require rollout-Zarr schema migration or Rerun logger changes.
- Test that marginal target RRI is the step-to-step difference of
  `steps/cumulative_target_rri`, while selected per-step target RRI is exposed
  separately as `selected_target_rri`.

## Manual / Smoke Verification

- If a compatible rollout store exists:
  `cd aria_nbv && uv run nbv-rollouts-info --store ../.data/offline_cache/rollouts_v1_smoke.zarr --validate --stats --json`
- Rerun command for selected row should remain available from the stored panel;
  CLI equivalent:
  `cd aria_nbv && uv run nbv-rerun-inspect --config-path ../.configs/rerun_offline.toml --rollout-store ../.data/offline_cache/rollouts_v1_smoke.zarr --rollout-row-id 0 --save ../.artifacts/rerun/rollout_row_0.rrd`

## Completion Evidence

- Changed-file summary.
- Test/lint outputs.
- Code review verdict.
- UltraQA result or explicit runtime-QA blocker if Streamlit cannot be launched
  in this environment.
