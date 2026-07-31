---
id: 2026-07-31_upstream_mempalace_codex_integration
date: 2026-07-31
title: "Upstream MemPalace Codex Integration"
status: done
topics: [scaffold, codex, mempalace]
confidence: high
canonical_updates_needed: []
---

## Task

Replace PR #41's repository-owned MemPalace launcher with the maintained
upstream Codex plugin while preserving ARIA's source-of-truth boundaries.

## Method

Removed the local plugin, marketplace, mining target, and stale Gemini MCP
entry; documented the version-matched upstream installation; and converted
G002 coverage to static ownership, corpus-policy, and live-runtime-config
assertions.

## Findings

MemPalace remains optional operator tooling. The `aria-nbv` wing may contain
reviewed project documents and upstream hook checkpoints, while raw transcript
stores, downloaded PDF corpora, runtime state, data, secrets, caches, and
generated artifacts remain excluded by default. Retrieved content is evidence,
not repository truth. Tracked live runtime configs do not invoke MemPalace;
operators install and configure the upstream Codex plugin outside the
repository instead.

## Verification

- `python3 scripts/tests/test_agent_governance_g002.py`
- `make scaffold-audit-self-test`
- `make check-agent-memory`
- `python3 -m json.tool .gemini/settings.json`
- `git diff --cached --check`

## Canonical-State Impact

The durable corpus and authority preference is recorded in
`.agents/references/human_owner_intent.md`; no canonical scientific or package
state changed.
