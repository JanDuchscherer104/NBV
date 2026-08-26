---
scope: module
applies_to: aria_nbv/aria_nbv/data_handling/**
summary: Raw EFM snippets and immutable VIN-store ownership and validation.
---

# Data Handling Boundary

`aria_nbv.data_handling` owns raw snippets, VIN batches, immutable VIN offline
stores, and the QH join from rollout source references to actor-visible tensors
and separately held supervision. The root public surface stays narrow; store
format/lifecycle live under `vin_store/`, while `qh_data/` owns QH views,
materialization, batching, and dataset admission.

## Local Hazards

- Preserve typed EFM/frame boundaries and the single adapter path into VIN;
  raw matrices and parallel adapter schemas are not substitutes.
- Prefer existing upstream implementations, including PyTorch3D, over local
  reimplementation. Import dataset keys from `efm3d.aria.aria_constants`; do
  not duplicate their string values.
- Writers maintain manifests, indices, splits, shards, and optional records.
  Readers validate and provide rebuild guidance: never hand-edit derived store
  artifacts to satisfy a test.
- A format change bumps `OFFLINE_DATASET_VERSION`, rejects older stores, and
  updates the public surface, documentation, and focused tests together.
- Oracle/pipeline behavior belongs outside this module; follow the owning leaf
  contract for online labeling or Lightning selection.
- Preserve the `QhActorTensors`/`QhSupervision` boundary. Oracle labels and
  audit payloads do not enter scorer inputs; padding, candidate, action, and Q
  label masks retain distinct meanings.

## Procedure And Proof

- For store/API changes, run `ruff format` and `ruff check` on touched files,
  then `cd aria_nbv && uv run pytest tests/data_handling/test_vin_offline_store.py
  tests/data_handling/test_public_api_contract.py`.
- For training-facing batch selection, add the nearest Lightning/datamodule test.
- For QH joins or views, run `tests/data_handling/test_qh.py` and the focused
  rollout-reader test; include Lightning admission tests when stage semantics
  change.
