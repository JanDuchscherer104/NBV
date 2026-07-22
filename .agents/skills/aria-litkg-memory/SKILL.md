---
name: aria-litkg-memory
description: Use for temporary WP6-bound ARIA-NBV KG retrieval, routing, claim checks, backlog lookup, and consolidation proposals.
metadata:
  mode: router
  not_when:
    - "deterministic local discovery is sufficient"
    - "litkg-rs implementation, KG config, or backend behavior changes"
  handoff_to:
    - "aria-nbv-context for local-only discovery or KG fallback"
    - "semantic-scholar-litkg for LitKG implementation or config edits"
    - "specialized diagnostic capability for KG ingestion failures"
  evidence_required:
    - "LitKG command output with source locator"
    - "canonical source inspection before promoting retrieved truth"
    - "claim-check output for advisor-facing claims"
  applies_to:
    - "**"
  triggers:
    - "KG route or search"
    - "LitKG claim check"
    - "KG-backed consolidation"
  must_read:
    - ".agents/references/source_order.md"
    - ".agents/references/litkg_quick_reference.md"
  canonical_sources:
    - ".agents/references/source_order.md#role-split"
    - ".agents/references/litkg_quick_reference.md#probation-lane"
    - ".agents/references/litkg_quick_reference.md#fallback"
    - ".agents/references/litkg_quick_reference.md#mandatory-claim-checks"
    - ".agents/references/alignment_tools_contract.md#tool-boundaries"
    - ".configs/litkg.toml"
  literature_refs:
    - "docs/contents/literature/index.qmd"
    - "docs/literature/sources.jsonl"
    - "docs/references.bib"
  tool_refs:
    - "mcp__code_index.search_code_advanced"
    - "mcp__MCP_DOCKER.list_papers"
  verification:
    - "make kg-status"
    - "make kg-route KG_TASK=\"<task>\" KG_FORMAT=json"
    - "make kg-claim-check KG_CLAIM=\"<claim>\" KG_FORMAT=json"
---

# ARIA LitKG Memory

LitKG remains a temporary probationary evidence router through WP5; WP6 owns
its capability disposition. Follow the exact commands, health checks, fallback,
and claim rules in `litkg_quick_reference.md`.

Use search for retrieval, route for a context pack, and claim-check for
advisor-facing synthesis. Inspect cited canonical sources before treating a
result as current truth. If health or retrieval fails, fall back immediately to
`aria-nbv-context` plus targeted source reads; record debt only when it blocks
the task or reveals durable scaffold drift.

Consolidation output is a proposal. Promote it only through the owning docs,
package, reference, or agents-DB workflow.
