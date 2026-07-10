---
scope: module
applies_to: aria_nbv/aria_nbv/rri_metrics/**
summary: Oracle RRI, binning, and metric-contract guidance for work under aria_nbv/aria_nbv/rri_metrics/.
---

# RRI Metrics Boundary

Apply this file when working under `aria_nbv/aria_nbv/rri_metrics/`.

## Public Contracts
- Canonical metric and oracle surface: `aria_nbv/aria_nbv/rri_metrics/oracle_rri.py`, `point_mesh.py`, `types.py`
- Binning and ordinal surfaces: `ordinal.py`, `coral.py`
- Diagnostics and plotting helpers: `logging.py`, `plotting.py`
- Narrative surfaces: `docs/typst/seminar_paper/sections/05-oracle-rri.typ`, `docs/typst/seminar_paper/sections/07a-binning.typ`, generated API docs under `docs/reference/`, `docs/contents/theory/rri_theory.qmd`

## Boundary Rules
- Treat oracle-label semantics, binning definitions, and reported metric meaning as contract changes, not local refactors.
- If a change alters supervision meaning, decoded target semantics, or reported metric interpretation, update docs and targeted tests in the same change.
- Keep metric names, logged summaries, and paper terminology aligned with the underlying definitions; do not silently reinterpret an existing name.
- Prefer additive diagnostics over changing canonical RRI behavior unless the task explicitly asks for a semantic change.
- Plotting helpers are secondary surfaces; core oracle and metric functions own the semantics.

## Verification
- Run `ruff format` and `ruff check` on touched metrics files.
- Run the most direct targeted pytest for the touched semantics, typically `aria_nbv/tests/vin/test_rri_binning.py`, `test_coral.py`, and any affected data, rendering, or integration tests when oracle geometry or labels change.
- Update the relevant Quarto or paper text when equations, supervision meaning, or metric terminology changes.

## Completion Criteria
- Canonical metric semantics remain explicit and synchronized across code and docs.
- Targeted tests covering the changed oracle, binning, or ordinal behavior were run.
- No metric rename or meaning change is left implicit.
