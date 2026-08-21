---
name: agents-db
description: Use when triaging or maintaining ARIA-NBV internal agent-memory and backlog TOML surfaces with the repository's agents-db workflow.
---

# AGENTS DB

Use this skill for internal agent-memory surfaces, active backlog ranking,
proposal or review consolidation, and durable maintenance-debt capture. Keep
the database as a compact, auditable work index; current implementation and
scientific truth stays with its smallest source owner.

## Invariants

- Search existing records before adding a new one.
- Prefer amending an existing record over creating a duplicate.
- Keep each record compact but auditable with context and stable references.
- Use vertical slices for concrete follow-up work.
- Keep `.agents/*.toml` local unless the user explicitly requests external
  publication.
- In parallel worktrees, check the target branch before allocating an ID and
  reconcile collisions explicitly.
- Resolve completed records into `.agents/resolved.toml`; retain their history.

## Branches

- **Any record change:** Read the
  [internal DB guide](../../AGENTS_INTERNAL_DB.md) and the
  [schema reference](references/schema.md) before editing a TOML surface.
- **Source-backed or literature-backed record:** Read the
  [provenance reference](references/provenance.md) and record stable source
  pointers plus the installed owner and focused proof when applicable.
- **Triage, issue conversion, or PRD synthesis:** Read the matching mode in
  [workflow modes](references/modes.md).
- **Public docs, thesis narrative, or ordinary retrieval:** Hand off to the
  nearest docs or scientific owner instead of changing the database.
- **Tiny cleanup with no active-debt change:** Keep the database unchanged.

## Workflow

1. Inspect the active ranking through the repository's `agents-db` target.
2. Select the smallest record owner and amend it with the requested outcome.
3. Capture acceptance and verification in the record when the slice is
   independently actionable.
4. Run the target's validation before handing off or completing the change.

## Completion

Report the changed record IDs, stable references, validation result, and any
unresolved ownership or publication handoff. When guidance, memory, or owner
pointers changed, include the repository's `check-agent-memory` result.
