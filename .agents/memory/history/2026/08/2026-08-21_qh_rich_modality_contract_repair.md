---
id: 2026-08-21_qh_rich_modality_contract_repair
date: 2026-08-21
title: "Q_H Rich Modality Contract Repair"
status: done
topics: [qh, dataset, datamodule, provenance, tensor-shapes]
confidence: high
canonical_updates_needed: []
codex_thread: codex://threads/01a02339-86df-7f13-a17b-fbd6626ab8c4
files_touched:
  - aria_nbv/aria_nbv/data_handling/qh_data/views.py
  - aria_nbv/aria_nbv/data_handling/qh_data/dataset.py
  - aria_nbv/aria_nbv/data_handling/qh_data/batching.py
  - aria_nbv/aria_nbv/rollouts/qh_reader.py
  - aria_nbv/aria_nbv/lightning/qh_datamodule.py
---

## Task

Repair the Q_H rich-modality tensor boundary and make stage compatibility cover
the scorer-visible actor state without changing persisted schemas or model code.

## Method and findings

- Canonicalized only the optional singleton VIN source axis at the VIN-to-Q_H
  join and rejected malformed or inconsistent EVL geometry.
- Kept lean reads metadata-only while rich reads require root EVL and selected
  CF-GT evidence.
- Added typed actor-state and selected-depth contracts so heterogeneous stages
  fail before DataLoader construction.
- Preserved recorded renderer provenance in audit views without reading depth
  payloads, and prevented collation from padding incompatible spatial geometry.
- Preserved SE(3) semantics at the public Q_H view boundary with ``PoseTW`` for
  root, target, candidate, history, selected-camera, and voxel-frame poses;
  collation and transfer unwrap only at tensor operations and reconstruct the
  typed pose container before returning public views.
- Declared the actor-state contract on injected Lightning test datasets so the
  test seam obeys the same fail-closed DataModule boundary as production data.
- Reused the already-collated VIN snippet for both actor and rich static views,
  removing duplicate object construction without changing tensor ownership.
- Moved chain, prefix, and EVL materialization into one internal module and
  replaced reflective access to known typed fields with direct access.
- Bounded selected-depth reads to the validated factual-chain slice instead of
  rescanning the store-wide identifier column for every rich chain.

## Verification

- Rebased focused Q_H dataset, VIN-store, reader, DataModule, and Lightning
  module tests: 144 passed.
- Post-review Q_H CI: 323 passed. Package smoke: 116 passed. Targeted mypy for
  the dataset/materialization boundary, Ruff checks, and diff checks passed.
- Ruff format/check, compileall, and `git diff --check` passed.
- Targeted mypy remains baseline-non-clean in pre-existing Zarr/tensor indexing
  sites; no new error is attributable to the new typed views, dataset contract,
  or DataModule seam.

## Canonical-state impact

The code and focused tests are the sole behavioral owners. No agent-memory state
file, persistence schema, generation contract, or model contract changed.
