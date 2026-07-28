---
name: aria-litkg-memory
description: Use for KG-backed ARIA-NBV retrieval, task routing, claim checks, current-truth checks, backlog lookup, and consolidation proposals.
metadata:
  mode: router
  not_when:
    - "local file discovery alone is enough"
    - "litkg-rs implementation, KG config, or backend contracts are changing"
    - "a concrete failure loop owns the task"
  handoff_to:
    - "aria-nbv-context for local-only discovery"
    - "semantic-scholar-litkg for litkg-rs, KG config, or backend edits"
    - "diagnose-aria for KG ingestion failures"
  evidence_required:
    - "litkg command output or cited KG result"
    - "canonical source inspection before promoting retrieved truth"
    - "claim-check command for advisor-facing claims"
  applies_to:
    - "**"
  triggers:
    - "kg-route"
    - "claim check"
    - "source-backed"
    - "consolidate memory"
  must_read:
    - "AGENTS.md"
    - ".agents/references/source_order.md"
    - ".agents/references/litkg_quick_reference.md"
  canonical_sources:
    - "AGENTS.md"
    - ".agents/references/source_order.md#role-split"
    - ".agents/references/litkg_quick_reference.md#probation-lane"
    - ".agents/references/litkg_quick_reference.md#fallback"
    - ".agents/references/litkg_quick_reference.md#mandatory-claim-checks"
    - ".agents/references/alignment_tools_contract.md#tool-boundaries"
    - ".configs/infrastructure/litkg.toml"
  literature_refs:
    - "docs/contents/literature/index.qmd"
    - "docs/literature/sources.jsonl"
    - "docs/references.bib"
  tool_refs:
    - "mcp__code_index.search_code_advanced"
    - "mcp__MCP_DOCKER.list_papers"
  verification:
    - "make kg-capabilities KG_FORMAT=json"
    - "make kg-route KG_TASK=\"<task>\" KG_FORMAT=json"
    - "make kg-claim-check KG_CLAIM=\"<claim>\""
---

# ARIA litkg Memory

Use this skill when litkg should act as a probationary source-backed router,
claim-check layer, or research-memory retrieval surface for work that crosses
source families.

## Protocol

1. Read `AGENTS.md`, `.agents/references/source_order.md`, and
   `.agents/references/litkg_quick_reference.md`.
2. Use the exact command shapes, health checks, fallback policy, and mandatory
   claim-check rules from `.agents/references/litkg_quick_reference.md`.
3. Use `kg-search` for source-backed retrieval, `kg-route` for a context pack,
   and `kg-claim-check` for advisor-facing proposal, roadmap,
   research-question, or literature-synthesis claims.
4. When KG output looks degraded or empty, run `make kg-status`; if unavailable,
   fall back to `aria-nbv-context` plus targeted reads and record the outage
   only when it blocks the task or exposes durable scaffold debt.
5. Inspect cited canonical sources before treating retrieved statements as
   current truth.
6. Use `make kg-consolidate` for proposal-style memory/backlog updates; do not
   silently promote episodic notes.

## Source Authority

Until litkg retrieval exposes explicit authority/freshness metadata everywhere,
rank sources with `.agents/references/source_order.md` and inspect cited
canonical sources before treating retrieved statements as current truth.

## Fallback

If litkg is stale, unavailable, or too noisy for a localized task, fall back to
`aria-nbv-context` plus targeted file reads. Record KG debt only when the failure
blocks the task or exposes durable scaffold drift.

## Verification

- `make kg-status` first as a fast 0/1 probe; if non-zero, fall back to
  `aria-nbv-context` plus targeted reads and record the KG outage in the
  debrief instead of waiting for the heavier commands below.
- `make kg-capabilities KG_FORMAT=json`
- `make kg-search KG_QUERY="<terms>" KG_FORMAT=json` for retrieval verification.
- `make kg-route KG_TASK="<task>" KG_FORMAT=json` for context-pack verification.
- `make kg-claim-check KG_CLAIM="<claim>" KG_FORMAT=json` for advisor-facing
  claims; expect `verdict` and `confidence` populated.
- `make check-agent-memory` after non-trivial memory or guidance changes.
