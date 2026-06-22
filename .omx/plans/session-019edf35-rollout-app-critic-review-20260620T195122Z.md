# Critic Review: First-Class Rollout App Inspection

verdict: block

architectural_status: watch

## Findings

- The original test spec used an over-broad Matplotlib guard over
  `aria_nbv/scripts`, which already contains unrelated tracked VIN plotting
  scripts. That would false-fail after deleting only the untracked rollout
  validation script.
- Deleting `aria_nbv/scripts/plot_rollout_validation.py` is safe as scoped: it
  is untracked, has no references outside itself, and is a Matplotlib detour.
- Helper-level Plotly rows can be tested without Streamlit because the repo
  already has pure reader-to-row helper seams and synthetic rollout-Zarr
  fixtures.
- The store already persists rollout/branch fields, per-step cumulative fields,
  and candidate objective/provenance/probability fields, so this should not
  trigger schema work.
- The plan does not inherently broaden into Rerun or schema rewrites as long as
  existing Rerun helpers are reused.

## Required Plan Changes

- Narrow the Matplotlib verification command to rollout app/package paths and
  explicitly assert the rejected script is absent.
- Add a plan/test-spec line that per-step objective rows are derived from
  existing rollout-Zarr arrays only; no schema migration or Rerun logger rewrite.
- Clarify that marginal target RRI is the step-to-step difference of cumulative
  target RRI and that selected candidate target RRI is exposed separately.

## Native Subagent Evidence

- agent_id: `019ee6a6-2340-7441-825b-62e3c42c4b9f`
- agent_role: `critic`
- verdict: `block`
