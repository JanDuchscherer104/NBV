---
scope: module
applies_to: aria_nbv/aria_nbv/lightning/**
summary: Lightning lifecycle, QH optimization, certification, and bundle publication boundary.
---

# Lightning Boundary

Lightning owns data-stage admission, optimization, metric lifecycle, checkpoint
selection, fitted-Q certification, and immutable experiment publication.
One-step composition lives in `lit_*` and `aria_nbv_experiment.py`; finite-horizon
composition lives in `qh_datamodule.py`, `qh_module.py`, `qh_experiment.py`, and
`qh_q2_certification.py`. VIN owns scorer architecture and bundle types.

## Local Hazards

- Keep raw conditional Q and feasibility action-mask independent. Lightning
  owns hard masking for loss support, Double-Q backup, and metrics.
- Q labels, candidate materialization, action validity, and padding are distinct
  masks. Unsupported or invalid rows never receive fabricated targets or enter
  bootstrap selection.
- Preserve exact scalar-horizon recursion and fail-closed stage, manifest,
  geometry, representation, and calibration identities.
- A fitted bundle is immutable and inference-only. Warm starts restore verified
  scorer weights, not optimizer or target-network state.

## Procedure And Proof

- Run Ruff on touched Lightning files and the narrowest test under
  `tests/lightning/`.
- For scorer-output or mask changes, include `test_qh_module.py`; for stage
  admission include `test_qh_datamodule.py`; for fit, bundle, or decoder
  identity include `test_qh_experiment.py`; for longer-horizon evidence include
  `test_qh_q2_certification.py`.
