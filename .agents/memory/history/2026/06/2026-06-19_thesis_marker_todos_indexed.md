---
id: 2026-06-19_thesis_marker_todos_indexed
date: 2026-06-19
title: "Thesis Marker TODOs Indexed"
status: done
topics: [thesis, typst, agents-db, memory]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/todos.toml
  - .agents/resolved.toml
  - .omx/context/thesis-marker-todos-20260618T224945Z.md
  - .omx/plans/ralplan-thesis-marker-todos-20260618T224945Z.md
artifacts:
  - .omx/context/thesis-marker-todos-20260618T224945Z.md
  - .omx/plans/ralplan-thesis-marker-todos-20260618T224945Z.md
---

# Thesis Marker TODOs Indexed

## Summary

The latest thesis TODO refresh found no remaining plain `// TODO` comments in
the active Typst thesis seed. It did find remaining explicit draft-marker macros
such as `#validation_todo`, `#decision_todo`, `#research_todo`, `#impl_todo`,
`#question_todo`, and `#conflict_todo`.

I treated those marker macros as intentional evidence and decision gates rather
than prose defects. I added a context artifact and a compact agents-db todo so
future thesis cleanup can distinguish accidental inline TODO residue from
deliberate freeze/evidence/protocol gates.

## Changed Surfaces

- `.omx/context/thesis-marker-todos-20260618T224945Z.md`
- `.agents/todos.toml`

## Decisions

- Plain inline TODO comments remain the cleanup target for immediate prose fixes.
- Explicit thesis marker macros remain in the Typst source until their owning
  evidence, decision, or final-writing pass is complete.
- The marker inventory was tracked through `todo-094`, mapped to existing
  backlog owners where possible, and then resolved as a completed indexing
  pass instead of duplicating every marker as a separate active DB item.

## Evidence

- `rg -n '//\s*TODO|TODO\(|#(validation|research|decision|impl|question|conflict)_todo' docs/typst/thesis/main.typ docs/typst/thesis/sections`
- `make agents-db AGENTS_ARGS='validate'`
- `make agents-db`
- `make check-agent-memory`

## Canonical Updates Needed

- None. This debrief records indexing and backlog maintenance only; it does not
  change thesis method, protocol, or public narrative truth.
