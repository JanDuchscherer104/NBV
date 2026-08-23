---
id: 2026-08-23_pr1_reviewed_intent_and_routing_invariants
date: 2026-08-23
title: "PR1 Reviewed Intent And Routing Invariants"
status: in_progress
topics: [scaffold, intent, routing, graphify]
confidence: medium
canonical_updates_needed: []
touched_owner_paths:
  - .agents/skills/agent-behavior/SKILL.md
  - .agents/skills/agent-behavior/references/reviewed-intent.md
  - scripts/scaffold/fixtures/routing.json
  - scripts/scaffold/fixtures/routing_prompts.jsonl
  - scripts/scaffold/run_routing_trials.py
  - scripts/tests/test_agent_governance_g002.py
  - scripts/tests/test_routing_trials.py
codex_thread: codex://threads/019fff4c-cc77-7351-bb81-9759852617c6
repo_object_format: sha1
repo_head: a9ca7a3be964860a26402630ab87d53d519a6f02
repo_branch: "codex/scaffold-intent-pr1"
worktree_kind: linked
---

## Task

Route reviewed intent only after exact owners and accepted scoped requirements
leave a material choice unsettled; retain thesis-code synchronization and
lowest-shared-owner invariants.

## Method

- Added the reviewed-intent branch behind `agent-behavior`.
- Replaced abstract routing prompts with concrete ARIA-NBV owner decisions.
- During review remediation, replaced the evaluator-wide checkout with an
  explicit production corpus and isolated mixed-source Graphify snapshots.

## Findings

- Exact implementation owners remain first for current facts.
- `.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md` owns this
  scaffold rework's requirements; accepted plans may sequence but not override
  them.
- `.agents/references/human_owner_intent.md` is consulted only for a still-open
  cross-task preference. Its `Open Choices` remain unresolved.
- The earlier `1/4 -> 4/4` statement was not a matched experiment and is
  withdrawn. Reviewable baseline/candidate evidence remains pending a repeated
  run under the remediated evaluator.

## Verification

- Focused deterministic evaluator and governance tests cover corpus exclusion,
  source precedence, event lifecycle completeness, isolated checkout digests,
  explicit runtime configuration, and evidence-bundle integrity.
- No behavioral pass-rate claim is made until a bounded immutable bundle is
  produced for both conditions under one evaluator configuration.

## Canonical Owner Impact

The skill and its reviewed-intent reference own the active route. This debrief
is only an episodic review receipt and carries no requirement disposition
ledger.

## Commits

- [a815f5bb03ded6d7215a5a88f49e5cd7e9026cf0](https://github.com/JanDuchscherer104/ARIA-NBV/commit/a815f5bb03ded6d7215a5a88f49e5cd7e9026cf0) — WP1: freeze the original routing fixtures
- [2f25b770440b559e7f86b2f7a5e81bd4d671f8f3](https://github.com/JanDuchscherer104/ARIA-NBV/commit/2f25b770440b559e7f86b2f7a5e81bd4d671f8f3) — WP2: add reviewed intent and universal invariants
- [a9ca7a3be964860a26402630ab87d53d519a6f02](https://github.com/JanDuchscherer104/ARIA-NBV/commit/a9ca7a3be964860a26402630ab87d53d519a6f02) — WP3: add the original exact-head evaluator
