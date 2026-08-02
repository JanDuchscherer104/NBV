---
scope: module
applies_to: aria_nbv/aria_nbv/rri_metrics/**
summary: RRI semantic, binning, and metric-validation boundary.
---

# RRI Metrics Boundary

This module owns prepared RRI, returns, ranking, stateful metrics, binning, and
metric-facing plots. Oracle scorer evidence belongs to `aria_nbv.oracle`; CORAL
model/loss behavior belongs to `aria_nbv.vin.ordinal`.

## Local Hazards

- Oracle-label semantics, binning, decoded target meaning, and reported metrics
  are contracts, not local refactors. Keep names and paper terminology aligned.
- Prefer additive diagnostics to altering canonical RRI behavior. Tensor kernels
  own semantics; scalar/table adapters and plotting remain secondary.
- Operational invalidity, provenance, path, entropy, and order checks belong in
  `aria_nbv.rollouts.audits`.

## Procedure And Proof

- Run `ruff format` and `ruff check` on touched files and the nearest semantics
  test (commonly `tests/vin/test_rri_binning.py` or `test_coral.py`).
- Update the owning documentation when equations, supervision, or terminology
  changes.
