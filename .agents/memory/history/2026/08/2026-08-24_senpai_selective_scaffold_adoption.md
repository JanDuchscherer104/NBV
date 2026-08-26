---
id: 2026-08-24_senpai_selective_scaffold_adoption
date: 2026-08-24
title: "SENPAI selective scaffold adoption"
status: done
topics: [scaffold, senpai, autoresearch, upstream]
confidence: high
canonical_updates_needed:
  - .agents/skills/agent-behavior/SKILL.md
  - .agents/skills/agent-behavior/references/senpai-performance.md
  - .agents/skills/agent-behavior/references/senpai-adoption-updates.md
touched_owner_paths:
  - .agents/skills/agent-behavior/SKILL.md
  - .agents/skills/agent-behavior/references/senpai-performance.md
  - .agents/skills/agent-behavior/references/senpai-adoption-updates.md
  - scripts/tests/test_agent_governance_g002.py
codex_thread: codex://threads/01a0347c-583c-74c1-ad74-b67d5f78326a
repo_object_format: sha1
repo_head: a2df5476a81338e6c49ac402689128d8b17cc657
repo_branch: "codex/intent-candidate-capture"
worktree_kind: linked
---

## Task
Selectively adopt reusable W&B SENPAI research-harness mechanics without
adopting its Kubernetes/OpenHands/GitHub-writing runtime.

## Method
Pinned and inspected `wandb/senpai` at
`772acc597f29065ccad012c749334a287d89badd`, compared its source contracts to
ARIA's existing evaluator and OMX ownership boundaries, then captured only the
local routing and provenance rules.

## Findings
`agent-behavior` now routes external research-scaffold adoption to a pinned
SENPAI reference. The reference retains concise mission contracts, exact
baseline/revision identity, immutable evidence, event-driven supervision, and
clean-baseline promotion; it explicitly excludes the upstream runtime and
provides the standard `git ls-remote` plus compare-review update route.

## Commits
- `a1399a4772d71fa90d106b25d72ac684bf57bfba` — selective SENPAI adoption
- `5b72103f778bbe93932d0df417325b28e8e3e9fe` — consolidate the SENPAI routing and upstream-update references
- `c1cc148180fe28d4b9f7955a6d1b61a060d26b56` — reduce SENPAI references to their operational contract

## Verification
`python3 scripts/tests/test_agent_governance_g002.py`; `make check-agent-memory`;
and `git diff --check` passed before the implementation commit.

## Canonical Owner Impact
The agent-execution guidance now owns the SENPAI pattern-library boundary and
its repeatable upstream-update route. No scientific, Python, W&B, Streamlit, or
external runtime contract changed.
