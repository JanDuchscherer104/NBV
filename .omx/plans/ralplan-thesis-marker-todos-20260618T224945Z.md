# Ralplan: Thesis Marker TODO Inclusion

Generated: 2026-06-18T22:49:45Z

## Goal

Include the further thesis TODOs found after the plain `// TODO` cleanup without
collapsing intentional thesis marker gates into accidental cleanup debt.

## Evidence

- The active thesis seed has no remaining plain `// TODO` or `TODO(...)` hits.
- The remaining TODO-like entries are explicit Typst marker macros:
  `#validation_todo`, `#research_todo`, `#decision_todo`, `#impl_todo`,
  `#question_todo`, and `#conflict_todo`.
- These markers describe final-writing, evidence, protocol, architecture, and
  bridge-scope gates that depend on existing active backlog owners.

## Plan

1. Preserve all marker macros in the thesis source.
2. Add a context artifact that inventories every remaining marker and maps it
   to existing agents-db owners.
3. Add one short-lived agents-db indexing todo so the inclusion work is visible,
   reviewable, and resolvable.
4. Resolve the indexing todo after validation; leave the real future work under
   the mapped active owners.

## Ralph Resolution Contract

The Ralph completion loop for this slice is complete when:

- `todo-094` exists with references to the marker inventory and owning active
  DB records.
- The marker inventory artifact exists and groups all remaining thesis markers.
- `make agents-db AGENTS_ARGS='validate'` passes.
- `make agents-db` renders the added item before resolution.
- `make check-agent-memory` passes after the debrief is added.
- `todo-094` is resolved with a note explaining that marker gates remain open
  through their mapped owners.

## Non-Goals

- Do not remove marker macros from Typst source.
- Do not invent final experiment evidence.
- Do not close existing active thesis/evidence/protocol owners.
