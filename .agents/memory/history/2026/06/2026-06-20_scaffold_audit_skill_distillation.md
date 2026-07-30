---
id: 2026-06-20_scaffold_audit_skill_distillation
date: 2026-06-20
title: "Scaffold Audit Skill Distillation"
status: done
topics: [scaffold, skills, validation]
confidence: high
canonical_updates_needed: []
files_touched:
  - Makefile
  - scripts/scaffold_audit.py
  - .agents/references/scaffold_routing_fixtures.json
  - .agents/references/skill_style_guide.md
  - .agents/skills/code-review-aria-nbv/SKILL.md
  - .claude/agents/aria-reviewer.md
  - .claude/skills/code-review-aria-nbv
  - .claude/skills/aria-nbv-mermaid
---

## Task

Implemented the conservative first pass of the ARIA-NBV skill prune/merge
verdict: add a scaffold audit, normalize skill metadata, repair review skill
identity, and preserve deletion/merge gates.

## Output

`make scaffold-audit` now validates skill frontmatter, accepted
`metadata.mode` values, directory/name identity, blocked machine-facing
handoff namespaces, and routing fixtures. The review skill directory now matches
the canonical `code-review-aria-nbv` skill name. Missing skill modes were added
without deleting or merging any skill.

The Claude mirror was refreshed so the repo-local review agent points at the
canonical `code-review-aria-nbv` path.

## Verification

Run:

- `make scaffold-audit`
- `make agents-db AGENTS_ARGS='validate'`
- `make check-agent-memory`
