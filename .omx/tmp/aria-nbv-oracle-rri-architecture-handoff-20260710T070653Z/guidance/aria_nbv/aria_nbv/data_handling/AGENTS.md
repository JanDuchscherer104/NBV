---
scope: module
applies_to: aria_nbv/aria_nbv/data_handling/**
summary: Raw snippet and immutable VIN offline dataset contract guidance for work under aria_nbv/aria_nbv/data_handling/.
---

# Data Handling Boundary

Apply this file when working under `aria_nbv/aria_nbv/data_handling/`.

## Public Contracts
- Public package surface: `aria_nbv/aria_nbv/data_handling/__init__.py`
- Raw snippet and typed container surface: `efm_dataset.py`, `efm_views.py`, `efm_snippet_loader.py`
- Immutable offline store contracts: `_offline_format.py`, `_offline_store.py`, `_offline_writer.py`, `_offline_dataset.py`
- VIN datamodule source contracts: `_vin_sources.py`, `vin_adapter.py`, and `vin_oracle_types.py`
- Narrative surfaces: `aria_nbv/aria_nbv/data_handling/README.md`, generated API docs under `docs/reference/`, `docs/contents/ase_dataset.qmd`, `docs/typst/seminar_paper/sections/12h-appendix-offline-cache.typ`

## Boundary Rules
- `aria_nbv.data_handling` is the active owner of raw snippets, VIN oracle batches, and the immutable VIN offline store.
- The removed oracle-cache and VIN-snippet-cache compatibility modules must not be reintroduced.
- Writers own manifest, sample-index, split, shard, and optional-record maintenance. Readers should validate strictly and fail with rebuild guidance rather than mutate derived artifacts.
- Do not hand-edit store manifests, `sample_index.jsonl`, split arrays, shards, or payloads to silence failing tests; fix the writer, reader, or generator instead.
- Keep one canonical path from `EfmSnippetView` to `VinSnippetView`; do not duplicate VIN-adapter logic in unrelated modules.
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
