---
id: 2026-07-26_graphify_query_wrapper_deletion
date: 2026-07-26
title: "Graphify Query Wrapper Deletion"
status: done
topics: [graphify, scaffold, simplification]
confidence: high
canonical_updates_needed: []
---

## Task

Delete the repository-local Graphify query, path, and explain implementation
without changing schema, extraction, refresh, history, or merge behavior.

## Outcome

Upstream Graphify 0.9.22 now owns `query`, `path`, and `explain` through its
public CLI after the repository freshness check. Exact-source fallback remains
guidance based on targeted `rg` and narrow source reads, not local traversal
code. The slice removed `scripts/graphify_query.py` and obsolete wrapper tests
and recipes for a net change of 42 additions and 612 deletions (net -570 LOC).
No TODOs were introduced.

## Verification

Python compilation, focused Graphify freshness/integration/WP7 fixtures,
`make graphify-integration-self-test PYTHON_INTERPRETER=python3`, the
`aria-nbv-context` skill validator, and
`make check-agent-memory PYTHON_INTERPRETER=python3` passed. Ruff check and
format-check also passed for the three changed Python files using
`/home/jd/repos/ARIA-NBV/aria_nbv/.venv/bin/ruff`. Canonical Graphify artifacts
were unchanged; freshness failure before the paired graph child is expected.

## Canonical State Impact

No further canonical updates are needed. The already changed `AGENTS.md`,
`.agents/references/graphify_contract.md`, and
`.agents/skills/aria-nbv-context/SKILL.md` own the upstream-CLI routing and
exact-source fallback guidance.
