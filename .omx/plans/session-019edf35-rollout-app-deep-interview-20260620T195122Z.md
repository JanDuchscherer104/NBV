# Deep Interview Handoff: Session 019edf35 Rollout App Alignment

## Interview Source

No new interactive question was needed in this turn because the current session
contains explicit corrections and hard constraints:

- validation plots are insufficient;
- more candidates and target OBB overlays are required;
- objective curves and branching/sampling-rule visualizations are required;
- Streamlit integration must be first class;
- a detailed rollout-Zarr dataset inspection page is required;
- no Matplotlib or external one-off validation script is allowed;
- existing `aria_nbv` Plotly/builder and Rerun functionality must be used.

## Clarified Requirements

1. Promote the existing app-native rollout surfaces.
   - `Counterfactual Rollouts` remains the central live configuration and
     generation page.
   - A stored rollout-Zarr page must be wired into app navigation for detailed
     post-generation inspection.

2. Reuse repo-owned plotting and visualization.
   - Plotly and existing builder-pattern utilities are the app plotting stack.
   - Rerun remains the dense 3D/time-series replay surface.
   - The untracked external `plot_rollout_validation.py` script is out of
     bounds and should be removed.

3. Improve qualitative and quantitative rollout QA.
   - Stored rollout inspection should expose objective progress per step,
     cumulative/marginal target and scene metrics where available.
   - Stored rollout inspection should expose branching/fanout and sampling
     provenance: policy, chain, branch factor, strategy, position, mixture,
     sampler probability, and selection probability.
   - Candidate validity/invalidity views must keep hard masks/reasons distinct
     from low-RRI labels.
   - Rerun launch commands must remain available for selected rows.

4. Keep strategic decisions out of this pass.
   - No `Q_H` training.
   - No full thesis/scaffold restructuring.
   - No new external plotting or visualization dependency.

## Non-Goals

- Do not add a second plotting framework.
- Do not mutate rollout stores or offline VIN datasets just to satisfy display.
- Do not hide missing fields; older stores should report missing visual inputs
  clearly.
- Do not claim production rollout readiness from app wiring alone.

## Interview-Complete Rationale

The ambiguity that materially changed implementation has already been resolved
by the user in this session: app-native Streamlit/Rerun integration supersedes
the external script approach, and Matplotlib is forbidden for this path. The
remaining questions are implementation details that can be resolved from repo
evidence and test feedback.

## Ralplan Handoff Summary

Plan a narrow app/inspection slice:

- wire `render_stored_rollouts_panel` into the Streamlit app and compatibility
  dispatcher;
- remove the external Matplotlib script;
- extend stored rollout inspection with reusable Plotly helper rows/figures for
  per-step objectives and branching/sampling provenance;
- improve or verify live counterfactual rollout page affordances without
  broad rewrite;
- add focused tests for imports/navigation/helper outputs and existing Rerun
  rollout logger coverage.
