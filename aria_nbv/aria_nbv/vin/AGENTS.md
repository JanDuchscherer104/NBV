---
scope: module
applies_to: aria_nbv/aria_nbv/vin/**
summary: VIN scorer, batch-contract, and candidate-context guidance for work under aria_nbv/aria_nbv/vin/.
---

# VIN Boundary

Apply this file when working under `aria_nbv/aria_nbv/vin/`.

## Public Contracts
- Core scorer surface: `aria_nbv/aria_nbv/vin/models/scene_myopic.py`, `scorer_context.py`, `ordinal.py`, `diagnostics/summarize.py`
- Shared batch and snippet containers: `aria_nbv/aria_nbv/data_handling/raw/views.py`, `aria_nbv/aria_nbv/data_handling/offline/batch.py`
- Training integration: `aria_nbv/aria_nbv/lightning/lit_module.py`, `lit_datamodule.py`
- Narrative surfaces: `docs/typst/seminar_paper/sections/06-architecture.typ`, `docs/typst/seminar_paper/sections/07-training-objective.typ`, `docs/typst/seminar_paper/sections/12g-appendix-vin-v3-streamline.typ`

## Boundary Rules
- Treat scorer inputs, prediction semantics, and shared batch/container shapes as cross-surface contracts across VIN, Lightning, diagnostics, and docs.
- Preserve candidate-vs-rig frame semantics. Display-only rotations, plotting helpers, or UI conveniences must not leak into training, cache, or model inputs.
- If VIN needs new cached or raw data fields, extend the owning `data_handling.raw` or `data_handling.offline` leaf contract instead of reaching into ad hoc dict payloads or broadening the package root.
- Keep `VinSnippetView` and `VinOracleBatch` semantics aligned with the active scorer path; update docs and targeted tests together when those contracts change.
- Prefer the active VIN v3 path unless the task explicitly targets experimental or legacy modules.

## Verification
- Run `ruff format` and `ruff check` on touched VIN or Lightning files.
- Run targeted pytest in `aria_nbv/tests/vin/` plus the relevant Lightning coverage such as `aria_nbv/tests/lightning/test_vin_batch_collate.py` and `aria_nbv/tests/lightning/test_vin_datamodule_sources.py` when batch or training contracts change.
- If frame semantics or candidate evidence flow changes, run the most direct related rendering or integration test that covers the touched behavior.

## Completion Criteria
- Candidate-frame assumptions are explicit in code or docstrings when touched.
- Shared batch/container tests covering the changed VIN behavior were run.
- Paper or implementation docs were updated when scorer semantics or training-visible interfaces changed.
