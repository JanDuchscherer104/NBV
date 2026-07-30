---
scope: module
applies_to: aria_nbv/aria_nbv/data_handling/**
summary: ASE/ATEK EFM snippet and immutable VIN-store contract guidance for work under aria_nbv/aria_nbv/data_handling/.
---

# Data Handling Boundary

Apply this file when working under `aria_nbv/aria_nbv/data_handling/`.

## Public Contracts
- Public package surface: `aria_nbv/aria_nbv/data_handling/__init__.py`
- ASE/ATEK EFM snippet access: `ase_efm/dataset.py` and `ase_efm/loader.py`;
  typed zero-copy payloads live in `ase_efm/views.py`; shared ID conversion lives in
  `identifiers.py`
- Immutable VIN store contracts: `vin_store/format.py`, `vin_store/store.py`,
  `vin_store/writer.py`, and `vin_store/dataset.py`
- Immutable VIN training source config: `vin_store/source.py`
- VIN batch and adapter contracts: `vin_store/batch.py` and `vin_store/adapter.py`
- Online label generation belongs to `oracle/pipelines/online_vin.py`; the
  online/offline discriminated union belongs to `lightning/lit_datamodule.py`
- Narrative surfaces: `aria_nbv/aria_nbv/data_handling/README.md`, generated API docs under `docs/reference/`, `docs/contents/ase_dataset.qmd`, `docs/typst/seminar_paper/sections/12h-appendix-offline-cache.typ`

## Boundary Rules
- `aria_nbv.data_handling` is the active owner of raw snippets, VIN oracle batches, and the immutable VIN offline store.
- `raw/views.py` owns consumed EFM keys and actor-visible versus oracle-only
  boundaries; use the typed `PoseTW`, `CameraTW`, and `ObbTW` wrappers at
  those boundaries instead of parallel schema names or raw matrix contracts.
- The removed oracle-cache and VIN-snippet-cache compatibility modules must not be reintroduced.
- Writers own manifest, sample-index, split, shard, and optional-record maintenance. Readers should validate strictly and fail with rebuild guidance rather than mutate derived artifacts.
- Do not hand-edit store manifests, `sample_index.jsonl`, split arrays, shards, or payloads to silence failing tests; fix the writer, reader, or generator instead.
- Keep one canonical path from `ase_efm.views.EfmSnippetView` through the
  adapter to `vin_store.views.VinSnippetView`; do not duplicate VIN-adapter
  logic in unrelated modules.
- Do not add new Oracle or pipeline imports under `data_handling`. The remaining
  labeler import in `vin_store/writer.py` is temporary and owned by RWP03B.
- When offline-store payload, metadata, or split semantics change, update the public surface, docs, and targeted tests together.
- When the on-disk dataset format changes, bump `OFFLINE_DATASET_VERSION`, update tests, and fail fast for older stores.

## Verification
- Run `ruff format` and `ruff check` on touched data-handling files.
- Run the most direct targeted pytest from `aria_nbv/tests/data_handling/`, especially `test_vin_offline_store.py` and `test_public_api_contract.py` for store/API changes.
- Run the relevant Lightning datamodule or integration coverage when the change affects dataset selection or training-facing batch assembly.

## Completion Criteria
- Manifest, sample-index, split, and payload semantics are validated by targeted tests.
- No failing check is fixed by hand-editing derived store artifacts.
- Docs reflect any changed snippet or dataset contract visible outside the module.
