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
- Every theory QMD appears exactly once in a keep/thin/delete matrix; retained
  pages identify their canonical destination, inbound links, and citation
  disposition.
- The expected Quarto page manifest is compared as an exact set.
- Typst marker checks are executable once the marker implementation lands; the
  current placeholder fixture may opt into `future_integration`.

The CLI has two modes: `--mode schema` validates shape, section coverage, and
the merged-baseline receipt SHA/tree; `--mode deletion-ready` additionally
reports each unresolved or unverified ledger/matrix row, live consumer
references, and pending Python-docstring gates. The current frozen inventory
passes schema mode and intentionally fails deletion-ready mode with structured
blockers (including ledger readiness, materialized destination, matrix,
consumer, coverage, and concrete transcript/debrief sink blockers). At the
current G003 inventory snapshot this produced 140 errors; that number is
observational evidence, not a fixed test invariant. Tests derive the required
ledger blocker set from inventory rows so readiness changes remain visible
without making stale counts authoritative.

## Current interface needed from inventory

Inventory should provide stable ledger `id`s, current Git `source_blob_id`s,
`destination_locator`, removal evidence, and deferred-action `backlog_id`,
`owner`, `gate`, and post-migration `tracking_record`, plus matrix rows with
array-valued inbound links/citation dispositions and an expected-page manifest.
The validator intentionally does not infer those fields.
