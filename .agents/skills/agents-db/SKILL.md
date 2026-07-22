---
name: agents-db
description: Use when triaging or maintaining ARIA-NBV internal agent-memory and backlog TOML surfaces with `make agents-db`.
metadata:
  mode: maintenance
  not_when:
    - "public documentation or thesis narrative is the primary output"
    - "ordinary KG retrieval or claim checking without backlog edits"
    - "tiny cleanup that does not change active debt"
  handoff_to:
    - "aria-docs for public docs or thesis narrative"
    - "aria-litkg-memory for KG-backed consolidation proposals"
    - "external codebase-design capability for behavior-preserving pruning"
  evidence_required:
    - "existing record search before adding duplicates"
    - "compact context plus stable references for each changed record"
    - "agents-db validation output"
  applies_to:
    - ".agents/AGENTS_INTERNAL_DB.md"
    - ".agents/issues.toml"
    - ".agents/todos.toml"
    - ".agents/refactors.toml"
    - ".agents/resolved.toml"
    - ".agents/memory/README.md"
  triggers:
    - "agents DB"
    - "backlog"
    - "memory consolidation"
    - "issue triage"
    - "resolved work"
  must_read:
    - ".agents/AGENTS_INTERNAL_DB.md"
    - ".agents/skills/agents-db/references/schema.md"
    - ".agents/skills/agents-db/references/provenance.md"
  canonical_sources:
    - ".agents/AGENTS_INTERNAL_DB.md"
    - ".agents/skills/agents-db/references/schema.md"
    - ".agents/skills/agents-db/references/provenance.md"
    - ".agents/issues.toml"
    - ".agents/todos.toml"
    - ".agents/refactors.toml"
    - ".agents/resolved.toml"
  literature_refs:
    - "docs/contents/thesis/questions.qmd"
  verification:
    - "make agents-db AGENTS_ARGS='validate'"
    - "make agents-db"
    - "make check-agent-memory when memory or guidance changed"
---

# AGENTS DB

Use this skill when work depends on the internal agent-memory surfaces under
`.agents/`, active backlog ranking, proposal/review requirement consolidation,
or durable maintenance debt capture.

## Read First

1. `.agents/AGENTS_INTERNAL_DB.md`
2. `.agents/skills/agents-db/references/schema.md`
3. `.agents/skills/agents-db/references/provenance.md`
4. `.agents/skills/agents-db/references/modes.md` for `triage`,
   `to-issues`, or `to-prd` style work

## Workflow

1. Run or inspect `make agents-db` to understand active ranking.
2. Prefer amending existing records over creating duplicates.
3. Add or amend a record only when the work materially changes the repo's
   maintenance picture.
4. Keep records compact but auditable with `context` plus stable `references`.
5. Route extracted requirements to the smallest owner: `.agents/*.toml` for
   active work, thesis/package/reference owners for durable current facts, and
   dated history debriefs for episodic task records.
6. Resolve or retire completed records into `.agents/resolved.toml`; do not
   delete records outright.

## Commands

- `make agents-db`
- `make agents-db AGENTS_ARGS='validate'`
- `make agents-db AGENTS_ARGS='resolve issue issue-XXXX --note "..."'`
- `make agents-db AGENTS_ARGS='resolve todo todo-XXXX --note "..."'`
- `make agents-db AGENTS_ARGS='resolve refactor refactor-XXXX --note "..."'`

## Rules

- Use vertical slices for concrete follow-up work.
- Keep `.agents/*.toml` as the local source of truth unless the user explicitly
  asks to publish GitHub issues.
- Do not churn the DB for tiny local cleanup that does not change active debt.
- For broad or literature-backed additions, include source-backed evidence
  before changing records.

## Verification

- `make agents-db AGENTS_ARGS='validate'`
- `make agents-db`
- `make check-agent-memory` when skills, debriefs, guidance, or source owners
  changed
