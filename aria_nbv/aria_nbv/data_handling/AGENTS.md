---
scope: module
applies_to: aria_nbv/aria_nbv/data_handling/**
summary: Raw EFM snippets and immutable VIN-store ownership and validation.
---

# Data Handling Boundary

`aria_nbv.data_handling` owns raw snippets, VIN batches, and immutable VIN
offline stores. The public surface is `__init__.py`; store format and lifecycle
are owned by `vin_store/format.py`, `store.py`, `writer.py`, and `dataset.py`.

## Local Hazards

- Preserve typed EFM/frame boundaries and the single adapter path into VIN;
  raw matrices and parallel adapter schemas are not substitutes.
- Writers maintain manifests, indices, splits, shards, and optional records.
  Readers validate and provide rebuild guidance: never hand-edit derived store
  artifacts to satisfy a test.
- A format change bumps `OFFLINE_DATASET_VERSION`, rejects older stores, and
  updates the public surface, documentation, and focused tests together.
- Oracle/pipeline behavior belongs outside this module; follow the owning leaf
  contract for online labeling or Lightning selection.

## Procedure And Proof

- For store/API changes, run `ruff format` and `ruff check` on touched files,
  then `cd aria_nbv && uv run pytest tests/data_handling/test_vin_offline_store.py
  tests/data_handling/test_public_api_contract.py`.
- For training-facing batch selection, add the nearest Lightning/datamodule test.
