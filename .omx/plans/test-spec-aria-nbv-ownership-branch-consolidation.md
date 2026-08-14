# Regression test specification: ownership and branch consolidation

The migration lane emits the frozen inventory JSON under
`.omx/specs/ownership-branch-consolidation-inventory.json`, with named
`disposition_ledger` and `theory_qmd_matrix` sections. The validator in
`scripts/ownership_consolidation_validator.py` checks those receipts without
becoming an owner of migrated content.

## Gates

- Every ledger row has a unique id, source, disposition, canonical destination,
  and `destination_verified`; materialized destinations must exist and may not
  be agents-DB files. Deferred actions additionally name backlog id/owner/gate.
- Legacy-state references are accepted only when classified as dated history,
  resolved provenance, or an explicit migration receipt.
- Transcript/debrief files cannot contain generic `DECISIONS.md` or memory-state
  promotion sinks.
- Every theory QMD appears exactly once in the migration matrix and is classified
  as deprecated archive, navigation, or background material; each page identifies
  its canonical destination, inbound links, and citation disposition.
- The expected Quarto page manifest is compared as an exact set.
- Typst marker checks run through `make thesis-marker-contract`: development and
  submission fixtures must compile, while invalid promotion fixtures and the
  submission-mode TODO fixture must fail.
- The frozen migration proof runs in hosted and local root CI through
  `make ownership-consolidation-contract`, covering both validator modes and
  the focused ownership/retired-memory regression tests.

The CLI has two modes: `--mode schema` validates shape, section coverage, and
the merged-baseline receipt SHA/tree; `--mode deletion-ready` additionally
checks ledger/matrix readiness, live consumers, and pending owner gates. Both
modes pass for the current frozen inventory. Tests derive required fields and
readiness checks from inventory rows so future changes remain visible without
making stale error counts authoritative.

## Current interface needed from inventory

Inventory should provide stable ledger `id`s, current Git `source_blob_id`s,
`destination_locator`, removal evidence, and deferred-action `backlog_id`,
`owner`, `gate`, and post-migration `tracking_record`, plus matrix rows with
array-valued inbound links/citation dispositions and an expected-page manifest.
The validator intentionally does not infer those fields.
