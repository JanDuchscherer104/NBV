---
id: 2026-07-30_qh_data_deep_module_followup
date: 2026-07-30
title: "Q_H Data Deep-Module and Ownership Follow-up"
status: done
topics: [qh, data-handling, vin-store, api, typing]
confidence: high
canonical_updates_needed: []
artifacts:
  - "commit:09bd56c8"
  - "commit:refactor(data): deepen Q_H data ownership"
---

## Task

Clarify data ownership after the scorer-independent fitted-Q infrastructure
landed, without changing its fixed-horizon learning semantics or introducing a
production scorer, objective family, corpus abstraction, or horizon-query API.

## Outputs

- Replaced `aria_nbv.data_handling.qh` with the deep `qh_data` package split
  into factual DTO views, batching/collation helpers, and dataset/config logic.
- Deliberately hard-renamed `data_handling.raw` to `ase_efm` and
  `data_handling.offline` to `vin_store`; no compatibility packages or import
  aliases were retained.
- Moved `VinSnippetView` and its structural predicate to `vin_store.views`.
  `ase_efm` now owns only ASE/ATEK EFM snippet access and views.
- Added only private representation/doc-field support shared by ASE/EFM and VIN
  dataclasses. It defines no transfer, collation, serialization, indexing,
  persistence, or lifecycle contract; Q_H DTOs remain independent and
  `QhBatch.to` remains specialized.
- Documented all Q_H DTO/config fields and non-trivial helpers with their
  shapes, dtypes, frames, mask relations, causal-history meaning, remaining
  acquisition budget, factual actions, TD boundaries, and padding/support
  semantics.
- Removed Jaxtyping from active code, dependencies, the lockfile, documentation
  tooling, and the active Python-docstring guidance. Historical archives and
  transcripts remain unchanged.
- Regenerated the API reference navigation for `ase_efm`, `vin_store`, and
  `qh_data`, removing the obsolete `raw`, `offline`, and `qh` pages.

The dependency/type migration is commit `09bd56c8`; the package and ownership
migration is the following `refactor(data): deepen Q_H data ownership` commit.

## Verification

- Q_H CI passed repeatedly during the slices, ending at 266 tests passed after
  the ownership move; focused data-handling, public-API, representation, and
  doc-contract suites also passed.
- The Jaxtyping slice passed its active-source scan, lock check, Ruff checks,
  skill validation, 50 targeted tests, Quartodoc harness, agent-memory check,
  and `git diff --check`.
- Full API generation completed successfully. Its pre-existing non-blocking
  docstring warnings were reported, while generated navigation contains only
  the new data-handling module paths.
- Glossary generation and validation refreshed the ASE/EFM API links in the
  compatibility YAML and KG JSONL outputs; the public QMD render and thesis
  Typst compile completed successfully.
- Agents-DB validation/rendering, API self-test, agent-memory validation, and
  final diff whitespace validation were run for this follow-up.

## Canonical State Impact

No canonical-state or backlog update is needed. This debrief records the
completed ownership refactor; the existing fixed-horizon scorer-independent
training contract and deferred scientific scorer work remain unchanged.
