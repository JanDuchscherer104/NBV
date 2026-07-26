---
name: agents-db
description: Maintain ARIA-NBV backlog TOMLs.
metadata:
  mode: maintenance
  not_when:
    - "public documentation or thesis narrative is the primary output"
    - "ordinary source lookup without backlog edits"
    - "tiny cleanup that does not change active debt"
  handoff_to:
    - "aria-docs for public narrative"
    - "aria-nbv-context for source discovery"
  evidence_required:
    - "existing-record search before additions"
    - "compact context and stable references"
    - "agents-db validation output"
  applies_to:
    - ".agents/{issues,todos,refactors,resolved}.toml"
    - ".agents/memory/history/**"
  triggers:
    - "agents DB"
    - "backlog or resolved-work maintenance"
    - "debrief routing"
  must_read:
    - ".agents/AGENTS_INTERNAL_DB.md"
    - ".agents/skills/agents-db/references/schema.md"
  canonical_sources:
    - ".agents/AGENTS_INTERNAL_DB.md"
    - ".agents/skills/agents-db/references/schema.md"
    - ".agents/skills/agents-db/references/provenance.md"
    - ".agents/issues.toml"
    - ".agents/todos.toml"
    - ".agents/refactors.toml"
    - ".agents/resolved.toml"
  verification:
    - "make agents-db AGENTS_ARGS='validate'"
    - "make agents-db"
---

# Agents DB

## Workflow

1. Inspect `make agents-db` and search for an existing record.
2. Amend instead of duplicating; keep `context` and `references` auditable.
3. Use `references/modes.md` for `triage`, `to-issues`, or `to-prd` work.
4. Route active work to the matching backlog TOML and episodic narrative to a
   dated debrief under `.agents/memory/history/`.
5. Resolve completed records into `.agents/resolved.toml`; never delete their
   history.

## Commands

- `make agents-db`
- `make agents-db AGENTS_ARGS='validate'`
- `make agents-db AGENTS_ARGS='resolve <issue|todo|refactor> <ID> --note "..."'`

Do not churn the DB for cleanup that does not change active debt. Validate the
DB after every lifecycle or schema-facing edit.
