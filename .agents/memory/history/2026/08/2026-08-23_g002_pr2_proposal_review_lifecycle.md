---
id: 2026-08-23_g002_pr2_proposal_review_lifecycle
date: 2026-08-23
title: "G002 PR2 Proposal Review Lifecycle"
status: done
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
repo_head: 3d7a9eb21d478b04e5516b6e0b6631a223d1bd30
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
- `162` focused governance, lifecycle, debrief, and evaluator tests passed.
- `make scaffold-audit` reported `skills=12 errors=0 warnings=0`.
- `make agents-db AGENTS_ARGS='validate'` passed.
- The final evaluator ran the same five fixed cases against the pre-feature
  PR #105 head and the committed candidate with Codex CLI 0.147.0,
  `gpt-5.6-luna`, medium effort, one isolated unseeded trajectory per case,
  and identical resolved evaluation configuration. The baseline passed 1/5;
  the candidate passed 5/5. One repetition supports only these observed
  outcomes, not a stability claim.
- Baseline bundle:
  `.agents/work/routing-trials/3752c1181864-3f1401bbda64/`; manifest SHA-256
  `44dd09c8536256f54a7b9ce551441090030e12e0600cf348c730be0784e2c2c5`.
- Candidate bundle:
  `.agents/work/routing-trials/3d7a9eb21d47-3d7a9eb21d47/`; manifest SHA-256
  `44578c1fcc8137a0b28ffcd5c253e38ed661ef266e16e3027890160aa89f6648`.

## Canonical-State Impact

The typed TOML files and `scripts/agents_db.py` own lifecycle state. The debrief
is episodic evidence, the fixed routing reference is evaluator input, and exact
policy owners remain authoritative.

## Commits

- [06a7c8864bdfe9b0df938d7699cc72b08b379571](https://github.com/JanDuchscherer104/ARIA-NBV/commit/06a7c8864bdfe9b0df938d7699cc72b08b379571) — WP1: implement the typed proposal lifecycle and fixed routing cases
- [3d7a9eb21d478b04e5516b6e0b6631a223d1bd30](https://github.com/JanDuchscherer104/ARIA-NBV/commit/3d7a9eb21d478b04e5516b6e0b6631a223d1bd30) — WP2: make proposal review load the current-user authority boundary
