# Critic Review 2: First-Class Rollout App Inspection

verdict: approve

architectural_status: watch

## Findings

- Prior Matplotlib blocker is resolved: the test spec narrows the guard to
  rollout app/package paths and separately asserts
  `aria_nbv/scripts/plot_rollout_validation.py` is absent.
- Prior schema/Rerun-scope blocker is resolved: the ralplan and test spec now
  require deriving rows from existing rollout-Zarr arrays only, with no schema
  migration or Rerun logger rewrite.
- Prior marginal-vs-selected target RRI blocker is resolved: marginal target
  RRI is defined as the step-to-step difference of `steps/cumulative_target_rri`
  while `selected_target_rri` remains separate.
- Architect lane is clear.
- Watch only: the first critic review remains a historical block artifact, but
  its required changes are now reflected in the patched ralplan/test spec.

## Required Plan Changes

None.

## Native Subagent Evidence

- agent_id: `019ee6a8-a5cf-7ad0-a941-1dc14cd80e8f`
- agent_role: `critic`
- verdict: `approve`
