---
scope: module
applies_to: aria_nbv/aria_nbv/vin/**
summary: VIN scorer, batch contract, candidate-frame, and validation boundary.
---

# VIN Boundary

This module owns one-step and finite-horizon scorer behavior.
`models/scene_myopic.py` owns the one-step control;
`models/target_finite_horizon.py` owns structured conditional-Q and feasibility
outputs; `modules/qh_*` own swappable history, scene, fusion, and value-decoder
contracts; `qh_bundle.py` owns immutable inference identity. Shared actor/batch
contracts remain in `data_handling`; Lightning owns optimization and mask use.

## Local Hazards

- Scorer inputs, prediction semantics, and shared container shapes cross VIN,
  Lightning, diagnostics, and documentation; change them together.
- Finite-horizon raw outputs are action-mask independent. Preserve padding-zero
  behavior, candidate permutation equivariance, scalar-horizon bounds, and the
  separation between feasibility prediction and authoritative hard masking.
- Preserve candidate-versus-rig frame semantics. Display rotations and plotting
  conveniences must not leak into model inputs, training, or caches.
- Add cached/raw fields through the owning `data_handling` leaf contract, not
  ad-hoc payloads or package-root expansion. Prefer the active VIN v3 path.

## Procedure And Proof

- Run `ruff format` and `ruff check` on touched VIN/Lightning files, then the
  nearest `tests/vin/` test; include Lightning batch/datamodule coverage when
  shared containers or training selection changes.
- For frame or candidate evidence changes, run the matching rendering test, such
  as `cd aria_nbv && uv run pytest tests/vin/test_vin_plotting_v3.py`.
- For QH changes, run `tests/vin/test_target_finite_horizon.py` plus the focused
  history, scene, state-fusion, or decoder test, and include Lightning/bundle
  tests when output or configuration identity changes.
