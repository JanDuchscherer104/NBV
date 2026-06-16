---
id: 2026-06-09_agent_scaffold_alignment_tools_contract
date: 2026-06-09
title: "Agent Scaffold Alignment Tools Contract"
status: done
topics: [scaffold, omx, memory, litkg]
confidence: high
canonical_updates_needed: []
---

## Task

Cleaned up the ARIA-NBV agent scaffold so optional operator tools, KG backends,
graph/memory systems, MCP servers, and external autoresearch harnesses remain
replaceable evidence producers rather than repo truth owners.

## Changes

- Added `.agents/references/alignment_tools_contract.md` as the thin
  cross-surface boundary contract.
- Linked the contract from root `AGENTS.md`,
  `.agents/references/source_order.md`, and
  `.agents/references/verification_matrix.md`.
- Extended `scripts/validate_agent_memory.py` with deterministic scaffold
  checks for required links and forbidden tracked runtime state.
- Added a pointer-only ARIA-NBV block to `/home/jd/.codex/AGENTS.md` without
  making user-local guidance an ARIA policy owner.

## Verification

- `make check-agent-memory`
- `make agents-db AGENTS_ARGS='validate'`
- `aria_nbv/.venv/bin/ruff check scripts/validate_agent_memory.py`
- `git check-ignore -v .omx .codex/config.toml .codex/hooks.json`
- Exact marker-block check for `/home/jd/.codex/AGENTS.md`
