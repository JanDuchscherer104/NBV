---
scope: package
applies_to: aria_nbv/**
summary: Shared package routing, cross-module hazards, and validation guidance.
---

# Package Guidance

Apply this file under `aria_nbv/`; open one deeper guide only for the contract
being changed.

## Owners And Hazards

- Code, tests, and active configuration own package behavior. Keep public roots
  narrow and add compatibility only for an active, explicit public contract.
- `data_handling` owns raw snippets and immutable VIN stores; `rollouts` owns
  replay/Zarr records; `rri_metrics` owns metric semantics; `vin` owns scorer and
  candidate-context contracts. Cross a boundary through its owning leaf contract.
- Preserve EFM3D/ATEK coordinate conventions and typed frame containers; make
  failures actionable rather than silently falling back.
- `python-standards` is the sole Python-contract guidance owner. Source
  docstrings, types, formatter configuration, and tests own the implementation
  details it routes to.

## Procedure And Proof

- Use config `.setup_target()` surfaces for runtime construction when present;
  do not substitute raw dictionaries or revive retired cache/training APIs.
- Run `ruff format` and `ruff check` on touched files, then
  `cd aria_nbv && uv run pytest <target>` for the smallest affected test seam.
  Run `make context-contracts` only when its contract index is relevant.

## Completion Criteria

- Package changes retain typed public contracts, document a changed public
  behavior at its source owner, and pass the focused formatter, lint, and test
  evidence for the touched seam.
