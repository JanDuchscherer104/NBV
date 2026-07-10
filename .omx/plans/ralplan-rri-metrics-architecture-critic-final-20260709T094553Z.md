# Critic Final Verification: `aria_nbv.rri_metrics` Architecture Plan

Verdict: APPROVE

The prior required edits are addressed:

- `selected_path_length_tensor` is now in `rollout/diagnostics.py` as an
  acquisition-cost diagnostic, not `returns.py`.
- TorchMetric state documentation is now enforced by a focused
  `test_torchmetric_state_contracts.py` plan and validation command.
- `DistanceBreakdown` placement is consistent: kept in `types.py` for the first
  pass in both plan and HTML.
- Private helper placement is specified: keep helpers leaf-local, allow tiny
  duplication, and avoid `rollout/utils.py` unless a real cycle or repeated
  helper body appears.
- Cross-surface edits are narrowed to mechanical import retargeting only, with
  explicit no behavior changes for app, Lightning, VIN, rollout, or data.

No new blocker was introduced.
