---
scope: module
applies_to: aria_nbv/aria_nbv/vin/**
summary: VIN scorer, batch contract, candidate-frame, and validation boundary.
---

# VIN Boundary

This module owns VIN scorer and prediction behavior; `models/scene_myopic.py`,
`scorer_context.py`, `ordinal.py`, and `diagnostics/` are the defining sources.
Shared snippet/batch contracts remain in `data_handling`; Lightning owns training
integration.

## Local Hazards

- Scorer inputs, prediction semantics, and shared container shapes cross VIN,
  Lightning, diagnostics, and documentation; change them together.
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
