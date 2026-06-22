# Ralplan: First-Class Rollout App Inspection

## Goal

Make rollout sample generation and stored rollout-Zarr inspection first-class
inside the existing ARIA-NBV Streamlit/Rerun workflow while preserving rollout
data contracts and avoiding ad hoc plotting scripts.

## Plan

1. Clean the invalid plotting detour.
   - Delete the untracked `aria_nbv/scripts/plot_rollout_validation.py` file.
   - Do not add Matplotlib usage to this delivery path.

2. Wire stored rollout inspection into the app.
   - Import `render_stored_rollouts_panel` in `aria_nbv/aria_nbv/app/app.py`.
   - Add a top-level `Stored Rollout Zarr` page next to `Counterfactual
     Rollouts`.
   - Re-export the panel from `aria_nbv/aria_nbv/app/panels.py` so dispatcher
     imports and tests can use the same public surface.

3. Extend stored rollout QA with Plotly/helper surfaces.
   - Add helper rows for per-step rollout objectives:
     `cumulative_target_rri`, marginal target RRI, selected target RRI,
     target root gain, scene RRI, selected probability, entropy, valid fanout,
     invalid fraction, policy, chain, and step.
   - Derive these rows from existing `rollouts/`, `steps/`, `candidates/`,
     `candidate_diagnostics/`, `lineage/`, and dictionary arrays only. No
     rollout-Zarr schema migration or Rerun logger rewrite is in scope.
   - Define marginal target RRI as the step-to-step difference of
     `steps/cumulative_target_rri`; also expose the selected candidate's
     one-step `target_rri` as `selected_target_rri` for comparison.
   - Add Plotly charts in `stored_rollouts.py`:
     objective curves by rollout/chain/step, marginal gains, selected
     probability/entropy, valid fanout/invalid fraction, and branch/fanout
     comparisons.
   - Reuse `plotly.express`/`graph_objects` and existing panel helpers; do not
     introduce a new plotting module unless tests show duplication.

4. Keep live page central.
   - Verify `counterfactual_rollouts.py` already provides first-class live
     controls for source target selection, candidate mixture, horizon, branch
     factor, beam width, policy, scorer controls, and target audit.
   - Only make narrow UI/label additions if required to connect live generation
     to stored inspection; avoid broad rewrite.

5. Preserve Rerun as dense replay.
   - Keep Rerun launch commands in the stored panel.
   - Reuse existing `_rollout_zarr.py` logging for target OBBs, time series,
     candidate metadata, and branch series.
   - If missing overlay data is not persisted, report it explicitly rather than
     fabricating plots.

## Acceptance Criteria

- App navigation includes both `Counterfactual Rollouts` and `Stored Rollout
  Zarr`.
- Importing app panel dispatchers exposes `render_stored_rollouts_panel`.
- The stored rollout page can display validation, manifest/source lineage,
  target summary, candidate groups, per-step objective curves, branching/
  sampling provenance, suspicious rows, and Rerun commands.
- No new Matplotlib usage is added, and the untracked script is gone.
- Targeted tests pass for app exports, rollout inspection helpers, and Rerun
  rollout logger behavior.

## Risks

- Older rollout stores may not contain every requested objective/branching
  field. The UI must show clear warnings and use available fields.
- The worktree contains many unrelated edits. Keep this slice narrow and avoid
  reverting or reshaping unrelated changes.
- Full Streamlit screenshot QA may be environment-dependent; use import/helper
  tests and app smoke checks as the baseline.

## Implementation Handoff

Proceed only after architect then critic consensus approval is recorded.
