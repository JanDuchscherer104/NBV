---
scope: module
applies_to: aria_nbv/aria_nbv/rri_metrics/**
summary: Oracle RRI, binning, and metric-contract guidance for work under aria_nbv/aria_nbv/rri_metrics/.
---

# RRI Metrics Boundary

Apply this file when working under `aria_nbv/aria_nbv/rri_metrics/`.

## Public Contracts
- Prepared RRI: `rri.py`; point-mesh primitives: `point_mesh.py`.
- Differentiable gains/returns: `returns.py`; evaluation-only ranking: `ranking.py`.
- Stateful evaluation: `torchmetrics_single.py` and `torchmetrics_multi.py`.
- Binning: `ordinal.py`; CORAL model/loss behavior lives in `aria_nbv.vin.ordinal`.
- Names and lightweight plots: `logging.py`, `plotting.py`.
- `oracle_rri.py` and `eval_pointclouds.py` are temporary owners until WP08.
- Narrative surfaces: `docs/typst/seminar_paper/sections/05-oracle-rri.typ`, `docs/typst/seminar_paper/sections/07a-binning.typ`, generated API docs under `docs/reference/`, `docs/contents/theory/rri_theory.qmd`

## Boundary Rules
- Treat oracle-label semantics, binning definitions, and reported metric meaning as contract changes, not local refactors.
- If a change alters supervision meaning, decoded target semantics, or reported metric interpretation, update docs and targeted tests in the same change.
- Keep metric names, logged summaries, and paper terminology aligned with the underlying definitions; do not silently reinterpret an existing name.
- Prefer additive diagnostics over changing canonical RRI behavior unless the task explicitly asks for a semantic change.
- Plotting helpers are secondary surfaces; core metric functions own the semantics.
- Operational provenance, invalidity, path, entropy, and order checks belong in `aria_nbv.rollouts.audits`.
- Tensor return kernels are authoritative; scalar/table adapters delegate to them.

## Verification
- Run `ruff format` and `ruff check` on touched metrics files.
- Run the most direct targeted pytest for the touched semantics, typically `aria_nbv/tests/vin/test_rri_binning.py`, `test_coral.py`, and any affected data, rendering, or integration tests when oracle geometry or labels change.
- Update the relevant Quarto or paper text when equations, supervision meaning, or metric terminology changes.

## Completion Criteria
- Canonical metric semantics remain explicit and synchronized across code and docs.
- Targeted tests covering the changed oracle, binning, or ordinal behavior were run.
- No metric rename or meaning change is left implicit.
