---
id: 2026-07-31_direct_aria_skills_and_aria_grill_migration
date: 2026-07-31
title: "Direct ARIA skills and Aria Grill migration"
status: done
topics: [scaffold, skills, aria-grill, mempalace]
confidence: high
canonical_updates_needed: []
---

## Task

Make ARIA skills directly discoverable, specialize the planning gateway as
Aria Grill, and keep MemPalace integration within its actual plugin boundary.

## Method

Moved repository skills out of plugin-prefixed discovery, renamed Plan Grill
to Aria Grill, updated its inbound routes, and retained the MemPalace plugin as
an MCP-only launcher. Narrowed angle-bracket instruction capture to deliberate
current user prose and locked the migration with focused governance tests.

## Findings

- `.agents/skills/aria-grill/` is the direct ARIA planning gateway and
  progressively invokes only the smallest material external design or
  visualization capability.
- Competing public interface shapes route through the maintained
  `codebase-design` `DESIGN-IT-TWICE` workflow; deprecated
  `design-an-interface` remains skipped.
- `plugins/mempalace-aria-nbv/` owns the repository-rooted MemPalace launcher;
  it does not duplicate ARIA skills, hooks, or applications.
- Implicit ARIA planning routes through Aria Grill, while explicit user skill
  invocation remains authoritative.
- Durable instruction capture excludes control-plane text, quoted history,
  transcripts, markup, tool output, and template placeholders.
- G002 adds no commit-transcript provenance mechanism. Its owner-intent update
  is conditional policy for the downstream G005 provenance workflow, which
  must implement and verify the sanitization and commit-binding contract before
  any conversation slice is tracked.
- Hosted scaffold CI runs the focused G002 governance migration tests through
  `scaffold-audit-self-test`.

## Verification

- `make check-agent-memory scaffold-audit scaffold-audit-self-test`: passed;
  scaffold audit retained 23 existing advisory warnings and reported no errors.
- `python3 scripts/tests/test_agent_governance_g002.py`: passed (7 tests).
- Strict mypy on `scripts/tests/test_agent_governance_g002.py`: passed.
- `git diff --check`: passed.

## Canonical State Impact

No `.agents/memory/state` update was needed. A conditional transcript-provenance
preference was recorded in `.agents/references/human_owner_intent.md`, the
existing owner for durable human scaffold preferences. Its executable and
security contracts remain a downstream G005 responsibility.
