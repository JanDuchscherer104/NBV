---
id: 2026-08-23_g002_pr2_proposal_review_lifecycle
date: 2026-08-23
title: "G002 PR2 Proposal Review Lifecycle"
status: in_progress
topics: [scaffold, intent, memory, agents-db, routing]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - .agents/memory/README.md
  - .agents/proposals.toml
  - .agents/proposals_resolved.toml
  - .agents/resolved.toml
  - .agents/skills/agent-behavior/SKILL.md
  - .agents/skills/agent-behavior/references/external-actions.md
  - .agents/skills/agents-db/SKILL.md
  - .agents/skills/agents-db/references/modes.md
  - .agents/skills/agents-db/references/proposal-routing-fixtures.md
  - .agents/todos.toml
  - scripts/agents_db.py
  - scripts/new_debrief.py
  - scripts/scaffold/fixtures/routing.json
  - scripts/scaffold/fixtures/routing_prompts.jsonl
  - scripts/scaffold/run_routing_trials.py
  - scripts/tests/test_agent_governance_g002.py
  - scripts/tests/test_agents_db_proposals.py
  - scripts/tests/test_debrief_index.py
  - scripts/tests/test_routing_trials.py
  - scripts/validate_agent_memory.py
codex_thread: codex://threads/019fff4c-cc77-7351-bb81-9759852617c6
repo_object_format: sha1
repo_head: 39dfbb1a02d123cca28f0a6b32480e75a38df1e6
repo_branch: "codex/scaffold-intent-pr2"
worktree_kind: linked
---

## Task

Provide one executable, auditable proposal lifecycle without turning episodic
debrief evidence into accepted policy.

## Method

- Rebased onto PR #105's controlled source-order evaluator and retained trace
  bundles.
- Added typed active and resolved proposal TOML owners plus explicit open,
  review, defer, and resolve commands.
- Kept debrief proposals immutable at `Disposition: proposed`; review receipts,
  owner-edit commits, and proof live in the lifecycle record.
- Replaced abstract proposal prompts with fixed eligible, near-miss, residual,
  defer, and adversarial self-accept cases.

## Findings

- `accept` and `narrow` require a current-user receipt, an exact target-owner
  commit, and proof before resolution.
- `reject` requires a reason; `defer` stays active. No command edits policy.
- New debriefs omit proposal fields unless `--intent-proposal TARGET_OWNER` is
  selected.
- Native validation uses the immutable pre-feature cutover tree for
  grandfathering, validates exact proposal target owners, and requires linked
  commits to cover every declared touched owner path.
- `todo-044` is active until a real lifecycle and published matched evidence
  satisfy its acceptance criteria.

## Verification

- `ruff check` passed for changed Python and tests.
- `154` focused governance, lifecycle, debrief, and evaluator tests passed.
- `make scaffold-audit` reported `skills=12 errors=0 warnings=0`.
- `make agents-db AGENTS_ARGS='validate'` passed.
- Final matched proposal-routing evidence is pending after this committed
  candidate; no pass-rate claim is made here.

## Canonical-State Impact

The typed TOML files and `scripts/agents_db.py` own lifecycle state. The debrief
is episodic evidence, the fixed routing reference is evaluator input, and exact
policy owners remain authoritative.

## Commits

- [39dfbb1a02d123cca28f0a6b32480e75a38df1e6](https://github.com/JanDuchscherer104/ARIA-NBV/commit/39dfbb1a02d123cca28f0a6b32480e75a38df1e6) — WP1: implement typed proposal lifecycle and fixed routing cases
