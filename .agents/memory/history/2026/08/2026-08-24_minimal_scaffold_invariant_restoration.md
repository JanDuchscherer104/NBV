---
id: 2026-08-24_minimal_scaffold_invariant_restoration
date: 2026-08-24
title: "Minimal scaffold invariant restoration"
status: done
topics: [scaffold, agent-behavior, python-standards, memory]
confidence: high
canonical_updates_needed:
  - .agents/skills/agent-behavior/references/external-actions.md
  - .agents/skills/python-standards/references/general_conventions.md
  - .agents/skills/README.md
  - .agents/memory/README.md
touched_owner_paths:
  - .agents/skills/agent-behavior/references/external-actions.md
  - .agents/skills/python-standards/references/general_conventions.md
  - .agents/skills/README.md
  - .agents/memory/README.md
  - scripts/new_debrief.py
  - scripts/tests/test_agent_governance_g002.py
  - scripts/tests/test_debrief_index.py
codex_thread: codex://threads/019fff4c-cc77-7351-bb81-9759852617c6
repo_object_format: sha1
repo_head: 42af5a47f2e7878cad22e97c9e4f710e7bb4ed96
repo_branch: "codex/pr105-minimal-invariant-routing"
worktree_kind: linked
---

## Task
Restore the smallest owner-local scaffold preferences omitted by slim PR #105.

## Method
Recovered direct user requirements from the Codex transcript, kept universal
Git/review behavior in the existing external-action branch, and kept Python
construction/locality behavior in Python conventions.

## Findings
The patch adds exact-head review resolution, holistic review handoff, early
Ultragoal draft-PR routing, implementation-commit provenance, config-as-factory
composition-root construction, helper locality, and pointer-reachability rules.
It adds no proposal registry, routing runner, raw trial bundle, or Graphify
lifecycle mechanism.

## Commits
- [42af5a47f2e7878cad22e97c9e4f710e7bb4ed96](https://github.com/JanDuchscherer104/ARIA-NBV/commit/42af5a47f2e7878cad22e97c9e4f710e7bb4ed96) — implementation: restore concise workflow preferences

## Verification
- `pytest -q scripts/tests/test_agent_governance_g002.py scripts/tests/test_debrief_index.py` — 61 passed.
- Ruff check and format check — passed.
- Both modified skill validators, `make scaffold-audit`, and `make check-agent-memory` — passed.

## Canonical Owner Impact
The external-actions and Python-conventions references now own the restored
rules; `agent-behavior` remains their compact conditional router.
