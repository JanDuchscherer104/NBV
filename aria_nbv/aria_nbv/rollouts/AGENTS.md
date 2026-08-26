---
scope: module
applies_to: aria_nbv/aria_nbv/rollouts/**
summary: Replay, rollout-Zarr/Q store, and finite-candidate rollout boundaries.
---

# Rollout Boundary

`aria_nbv.rollouts` owns multi-step replay records and rollout Zarr/Q stores;
`replay/`, `trace.py`, `zarr_store.py`, and their tests own persisted behavior.
`qh_reader.py` owns validated chain reads and data-contract identity;
`qh_geometry.py` owns stored-to-actor pose composition.
Generation belongs to `aria_nbv.oracle.pipelines`; finite candidate sampling and
provenance stay in `aria_nbv.pose_generation`.

`aria_nbv.targets.protocol` owns actor-safe target instructions, while
`aria_nbv.oracle.target_selection` owns privileged Oracle selection. Generation
consumes `data_handling.vin_store.dataset.VinOfflineSample` roots;
`data_handling.vin_store.batch.VinOracleBatch` remains the one-step VIN training
DTO.

## Local Hazards

- Replay data is standalone and source-row linked: do not mutate the immutable
  VIN offline store for multi-step rollout data.
- Invalid candidates and targets are hard mask/reason-code cases, never low-RRI
  labels; `q_train_mask` requires explicit target-RRI supervision.
- QH readers expose factual chains and supervision support. Lightning owns
  backup/loss masking, while online adapters return hard-masked
  `CandidateScores`; neither boundary fabricates invalid-row Q targets.
- `read_model.py` remains presentation-free. Rerun/Streamlit behavior belongs to
  its clients; use `rerun-nbv-inspector` for the Rerun procedure and current
  reference route.
- The package root is an exact eight-symbol allowlist. Import specialized
  contracts from their leaf owners; do not add compatibility re-exports.

## Procedure And Proof

- Run `ruff format` and `ruff check` on touched files, then
  `cd aria_nbv && uv run pytest tests/rollouts` for record/Zarr/writer changes.
- Add the nearest Oracle, Rerun, or Streamlit test when crossing that boundary;
  use the pipeline CLI help/dry run only for CLI/config wiring.
