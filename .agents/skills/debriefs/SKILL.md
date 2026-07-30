---
name: debriefs
description: Close non-trivial ARIA-NBV work with concise durable execution evidence and commit pointers to its owning records.
metadata:
  mode: maintenance
  not_when:
    - "temporary cross-session context transfer with no durable repository outcome"
    - "a trivial one-line edit with no finding, verification, or ownership change"
  handoff_to:
    - "agents-db when a finding creates, changes, or resolves maintenance work"
  evidence_required:
    - "task-owned changed paths or an explicit no-change result"
    - "fresh verification output or an explicit blocker"
    - "canonical owner paths for every claimed durable update"
  applies_to:
    - ".agents/memory/history/YYYY/MM/*.md"
    - ".agents/memory/README.md"
  triggers:
    - "debrief"
    - "task closeout"
    - "handoff"
    - "commit traceability"
  must_read:
    - ".agents/memory/README.md"
    - ".agents/AGENTS_INTERNAL_DB.md"
  canonical_sources:
    - ".agents/memory/README.md#current-policy"
    - ".agents/AGENTS_INTERNAL_DB.md"
  verification:
    - "make check-agent-memory"
    - "make agents-db AGENTS_ARGS='validate' when Agents DB records change"
    - "make agents-db when Agents DB records change"
---

# Debriefs

Use this skill to close non-trivial work without turning historical evidence
into a competing source of truth.

## Read First

1. `.agents/memory/README.md`
2. `.agents/AGENTS_INTERNAL_DB.md` when the work creates, changes, or resolves
   an actionable item

## Rules

- `$handoff` is a temporary, local context bridge for a fresh session. Do not
  check it in and do not use it as a substitute for a debrief.
- A debrief records only task, method, findings, verification, and canonical
  state impact. Link to code, tests, documents, and DB records instead of
  copying their contents.
- Create the debrief with `make new-debrief TITLE="..."`; retain the required
  frontmatter and state `canonical_updates_needed` explicitly, including `[]`.
- Put durable truth in its exact owner and actionable follow-up in the Agents
  DB. A debrief is evidence and history, never the sole owner of either.
- Commit coherent verified slices frequently. For a meaningful slice, include
  `Debrief: <repo-relative path>` and, when relevant, `Agents-DB: <record IDs>`
  in the commit footer. Do not duplicate the debrief prose in the commit body.

## Workflow

1. Decide whether the outcome is temporary context transfer, a durable task
   record, an Agents DB change, or a combination.
2. Update the exact canonical owner and/or Agents DB record before writing the
   debrief; reference it from the debrief.
3. Scaffold and complete the concise native debrief.
4. Run `make check-agent-memory`; when the DB changed, also run
   `make agents-db AGENTS_ARGS='validate'` and `make agents-db`.
5. Commit only the coherent slice with the appropriate footer pointers.

## Completion

- The debrief has valid native frontmatter, fresh verification evidence, and a
  literal canonical-state impact.
- Every new durable claim or task has an owner outside the debrief.
- The meaningful commit can be traced to its debrief and affected DB records.
