---
id: 2026-08-21_typst_first_notation_ownership
date: 2026-08-21
title: "Typst-first notation ownership"
status: done
topics: [typst, glossary, notation, documentation]
confidence: high
canonical_updates_needed:
  - docs/typst/shared/glossary.typ
  - docs/typst/shared/symbols.typ
  - docs/typst/shared/equations.typ
  - scripts/glossary_build.py
codex_thread: codex://threads/01a01f5c-062e-73b3-9f0e-35edddbfaa40
---

## Task
Make glossary, symbol, and equation Typst sources the only maintained notation owners.

## Method
Moved the cross-format metadata formerly maintained in `docs/notation.yml` into
the shared Typst facades, then regenerated the YAML, Quarto Lua, and Typst
notation adapters from Typst metadata queries.

## Findings
`docs/typst/shared/notation.generated.typ` remains necessary as a derived
input to `docs/typst/shared/notation.typ`; it is not a source of truth. The
migration also corrected the aggregate-error key to `oracle.err` and made
`rl.acquisition_cost` resolve to its dedicated shared symbol.

## Verification
Passed `python3 scripts/glossary_build.py all`, focused builder tests, Ruff,
shared Typst facade and fixture compilation, Quarto glossary rendering,
`make check-agent-memory`, and `git diff --check`.

## Canonical Owner Impact
The canonical inputs are `docs/typst/shared/glossary.typ`,
`docs/typst/shared/symbols.typ`, and `docs/typst/shared/equations.typ`.
`docs/notation.yml` and both generated notation adapters are derived consumers.
