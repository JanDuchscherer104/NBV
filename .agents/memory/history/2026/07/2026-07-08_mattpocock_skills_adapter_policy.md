---
id: 2026-07-08_mattpocock_skills_adapter_policy
date: 2026-07-08
title: "Matt Pocock Skills Adapter Policy"
status: done
topics: [skills, scaffold, mattpocock, codex]
confidence: high
canonical_updates_needed: []
files_touched:
  - .gitmodules
  - .codex/config.example.toml
  - .agents/references/mattpocock_skills_manifest.toml
  - .agents/references/scaffold_routing_fixtures.json
  - .agents/skills/plan-grill/SKILL.md
  - .agents/skills/diagnose-aria/SKILL.md
  - .agents/skills/code-review-aria-nbv/SKILL.md
  - .agents/skills/simplification/SKILL.md
  - .agents/skills/nbv-geometry-contracts/SKILL.md
  - .agents/skills/skills
  - .claude/skills/scientific-writing
  - .agents/skills/plan-grill/references/upstream-mattpocock.md
  - .agents/skills/diagnose-aria/references/upstream-mattpocock.md
  - .agents/skills/code-review-aria-nbv/references/upstream-mattpocock.md
  - .agents/skills/simplification/references/upstream-mattpocock.md
---

# Matt Pocock Skills Adapter Policy

## Task

Implemented the ARIA-NBV adapter-only plan for `mattpocock/skills`: upstream
installation stays outside the repo via `npx`, while ARIA keeps tracked policy,
source-owner mapping, and local routing fixtures.

## Method

Removed the stale `.agents/skills/skills` submodule declaration from
`.gitmodules` and recorded the reviewed upstream skill policy in
`.agents/references/mattpocock_skills_manifest.toml`. Added
The adapter mapped Matt assumptions such as `CONTEXT.md`, ADRs, and issue
tracker setup onto ARIA's glossary, decisions, roadmap/questions, nearest
`AGENTS.md`, and `agents-db` owners.

## Outputs

Added short upstream-reference files for `plan-grill`, `diagnose-aria`,
`code-review-aria-nbv`, and `simplification`. These files make Matt guidance
inspirational and explicit without putting Matt skill names into ARIA
`metadata.canonical_sources` or `metadata.handoff_to`.

Removed the stale `.agents/skills/skills` gitlink and the stale
`.claude/skills/scientific-writing` symlink pruned by `make claude-skills`.
While validating the scaffold, fixed a stale canonical source in
`nbv-geometry-contracts` from the removed `03-01-formal-state.typ` path to the
current thesis state-and-visibility file.

## Verification

- `make scaffold-audit` passed with 0 errors and existing warnings.
- `make scaffold-audit-self-test` passed with 13 fixtures and 0 failures.
- `make check-agent-memory` passed.
- `make claude-skills` passed; it removed one stale generated symlink and found
  20 current ARIA skill mirrors.

## Canonical State Impact

No thesis, glossary, package, or current-project-state update is required. The
new adapter policy is an operator/scaffold convention under `.agents/references/`.
