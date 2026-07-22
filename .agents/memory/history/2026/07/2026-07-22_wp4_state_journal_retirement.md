---
id: 2026-07-22_wp4_state_journal_retirement
date: 2026-07-22
title: "WP4 State Journal Retirement"
status: done
topics: [scaffold, source-ownership, memory, agents-db]
confidence: high
canonical_updates_needed:
  - AGENTS.md
  - .agents/references/source_order.md
  - .agents/references/agent_memory_templates.md
  - .agents/AGENTS_INTERNAL_DB.md
---

## Task

Implement approved WP4 after WP3 by salvaging source-backed journal facts,
migrating every active consumer, and retiring the four current-state journals.

## Method

Classified every journal heading in
`.agents/baselines/scaffold_wp4_state_salvage.csv`, moved live routing and
capture behavior to exact thesis, package, reference, test, config, or backlog
owners, and added a closed-ledger plus stale-reference gate to
`scripts/validate_agent_memory.py`.

## Findings

Most scientific and implementation facts were already owned by the active
thesis, package guidance, code, tests, LitKG config, or agents DB. The required
edits were consumer migration: guidance, skills, Claude adapters, transcript
review, generated agent docs, hooks, LitKG ingestion, current advisor material,
and stale agents-DB references. Transcript distillates now route durable
decision candidates to exact-source-owner review and actionable items to the
agents DB; no replacement generic journal was introduced.

Historical debriefs, transcript artifacts, archived material, accepted OMX
evidence, and the immutable WP0 inventory retain old path text only as dated or
baseline evidence. The four retired source files remain recoverable through Git
history at the pre-WP4 parent.

## Verification

- `python3 scripts/validate_agent_memory.py`
- `make agents-db AGENTS_ARGS='validate'`
- `make agents-db`
- targeted agent-memory transcript and retirement tests
- active-tree stale-reference scan and `git diff --check`

## Source Owner Impact

Root/source-order guidance now routes scientific direction to active thesis
owners, implementation contracts to code/tests/package guidance, active work to
the agents DB, and episodic evidence to dated debriefs. No current-state journal
or parallel ADR/context hierarchy remains.
