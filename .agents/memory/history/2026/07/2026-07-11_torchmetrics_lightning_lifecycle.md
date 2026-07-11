# TorchMetrics And Lightning Lifecycle

Date: 2026-07-11

## Outcome

- Added typed, documented state attributes and explicit distributed reductions
  for RRI and rollout-audit TorchMetrics.
- Replaced Lightning's batch-average epoch reduction for candidate ranking with
  stage-owned top-1, top-3, and selected-action accumulators.
- Preserved the existing training-step metric keys while making epoch values
  table-weighted and explicitly reset per stage.
- Kept `SelectedRolloutMetrics` available but disconnected from
  `VinOracleBatch`, which does not carry trajectory rewards or endpoint errors.
- Preserved checkpoint parameter keys because the new metric states are
  non-persistent TorchMetric state.
- Replaced manual TorchMetric resets with `super().reset()` so cached compute
  results and update bookkeeping cannot leak across epochs.
- Kept every distributed rank on the same epoch `compute()` path when local
  candidate validity differs.

## Verification

- Ruff format and check passed for all touched Python files.
- `tests/rri_metrics` and `tests/lightning`: 151 passed after temporarily
  exposing the populated EFM3D submodule from the main checkout.
- Added regression coverage for unequal batch weighting, stage isolation,
  reset behavior, state typing/docstrings, distributed reduction declarations,
  asymmetric two-rank Gloo reduction, and absence of new checkpoint state keys.

## Remaining Work

- Connect `SelectedRolloutMetrics` only in a future finite-horizon Lightning
  path whose batch contract supplies real rewards and endpoint errors.
- Join the independently committed WP07 target-ownership lane before WP08.

## Canonical Updates Needed

- None. The canonical report already records the WP06 ownership and lifecycle
  contract.
