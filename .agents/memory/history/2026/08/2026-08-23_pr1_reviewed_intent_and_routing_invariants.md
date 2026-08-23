---
id: 2026-08-23_pr1_reviewed_intent_and_routing_invariants
date: 2026-08-23
title: "PR1 Reviewed Intent And Routing Invariants"
status: done
topics: [scaffold, intent, routing, graphify]
confidence: high
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
repo_head: bea876d39f172b1bd903d29bd641c82beb4797e2
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
  explicit production corpus and removed optional Graphify provisioning from
  this source-order suite.

## Findings

- Exact implementation owners remain first for current facts.
- `.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md` owns this
  scaffold rework's requirements; accepted plans may sequence but not override
  them.
- `.agents/references/human_owner_intent.md` is consulted only for a still-open
  cross-task preference. Its `Open Choices` remain unresolved.
- The earlier `1/4 -> 4/4` statement was not a matched experiment and is
  withdrawn. The final evaluator records a true pre-feature baseline at
  `a121cd821f7748f979c2cddf0f7c3af0e0b6a5a7` (0/4) and the candidate at
  `bea876d39f172b1bd903d29bd641c82beb4797e2` (4/4).

## Verification

- Focused deterministic evaluator and governance tests cover corpus exclusion,
  source precedence, event lifecycle completeness, isolated checkout digests,
  explicit runtime configuration, and evidence-bundle integrity.
- Both retained trace bundles use Codex CLI 0.147.0, `gpt-5.6-luna`, medium
  effort, one isolated unseeded trajectory per case, and the same final
  evaluator configuration. One repetition supports only these observed
  outcomes, not a stability claim.
- Baseline bundle:
  `.agents/work/routing-trials/a121cd821f77-1b63b3c040f7/`.
- Candidate bundle:
  `.agents/work/routing-trials/bea876d39f17-bea876d39f17/`; manifest SHA-256
  `94d367f813e9c8cca1f78bcc1ce7e7a281ab6f79f9c472d298017ad71fe21a84`.

## Canonical Owner Impact

The skill and its reviewed-intent reference own the active route. This debrief
is only an episodic review receipt and carries no requirement disposition
ledger.

## Commits

- [a815f5bb03ded6d7215a5a88f49e5cd7e9026cf0](https://github.com/JanDuchscherer104/ARIA-NBV/commit/a815f5bb03ded6d7215a5a88f49e5cd7e9026cf0) — WP1: freeze the original routing fixtures
- [2f25b770440b559e7f86b2f7a5e81bd4d671f8f3](https://github.com/JanDuchscherer104/ARIA-NBV/commit/2f25b770440b559e7f86b2f7a5e81bd4d671f8f3) — WP2: add reviewed intent and universal invariants
- [a9ca7a3be964860a26402630ab87d53d519a6f02](https://github.com/JanDuchscherer104/ARIA-NBV/commit/a9ca7a3be964860a26402630ab87d53d519a6f02) — WP3: add the original exact-head evaluator
- [38718e0add565d674ae25c6715f3d9042c2544ca](https://github.com/JanDuchscherer104/ARIA-NBV/commit/38718e0add565d674ae25c6715f3d9042c2544ca) — WP4: control reviewed-intent trials
- [f9ccb74ceb718d92f8d7c5e235416804903e7cdb](https://github.com/JanDuchscherer104/ARIA-NBV/commit/f9ccb74ceb718d92f8d7c5e235416804903e7cdb) — WP5: isolate source-order evaluation
- [91e7913f16ea1df878f0f2f8d3743237d63daf1a](https://github.com/JanDuchscherer104/ARIA-NBV/commit/91e7913f16ea1df878f0f2f8d3743237d63daf1a) — WP6: reject evaluator contamination
- [794e8e754f155260f053968d141d78439cd06cce](https://github.com/JanDuchscherer104/ARIA-NBV/commit/794e8e754f155260f053968d141d78439cd06cce) — WP7: exclude plan artifacts
- [7899030a592c7640f4f6ca43085cc3b50c227751](https://github.com/JanDuchscherer104/ARIA-NBV/commit/7899030a592c7640f4f6ca43085cc3b50c227751) — WP8: reconcile event lifecycles
- [1b63b3c040f7c8733d8a989f2d3a309703c4f3ef](https://github.com/JanDuchscherer104/ARIA-NBV/commit/1b63b3c040f7c8733d8a989f2d3a309703c4f3ef) — WP9: sharpen real routing cases
- [e617d8404ea6d3fd3eead3f73bc8b310ea514544](https://github.com/JanDuchscherer104/ARIA-NBV/commit/e617d8404ea6d3fd3eead3f73bc8b310ea514544) — WP10: route scoped policy first
- [bea876d39f172b1bd903d29bd641c82beb4797e2](https://github.com/JanDuchscherer104/ARIA-NBV/commit/bea876d39f172b1bd903d29bd641c82beb4797e2) — WP11: enforce accepted-spec precedence
