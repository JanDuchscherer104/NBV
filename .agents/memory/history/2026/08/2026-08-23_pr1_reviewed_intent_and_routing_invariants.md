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
  - .agents/skills/agent-behavior/references/intent-and-follow-up.md
  - AGENTS.md
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

Complete PR1 of the scaffold-intent plan by activating reviewed-intent
consultation only for material choices that exact owners do not settle or for
scaffold/tool-policy changes, and by installing only the thesis-code
synchronization and lowest-shared-owner universal invariants. Proposal and
residual-work routes remain inactive until PR2.

## Method

- WP1 froze four PR1 routing prompts and rubrics before changing guidance.
- WP2 added the conditional root pointer, the reviewed-intent reference, and
  the two universal invariants without changing the reviewed human-intent
  owner or weakening exact-source authority.
- WP3 hardened the exact-head trial snapshot, bounded event evidence, strict
  adjudication, and clean-checkout proof. The helper executed a Graphify
  query against the fresh, evaluator-free, code-only graph before opening
  exact sources for proof. Graph state from the primary worktree was not used
  as authority for the linked trial snapshot.
- The reviewed input was limited to Core Principles, Ownership, Scaffold
  Preferences, Non-Goals, and Instruction Capture in
  .agents/references/human_owner_intent.md. Open Choices was excluded.

## Findings

- PR1 activates reviewed-intent consultation through
  .agents/skills/agent-behavior/references/intent-and-follow-up.md only when
  current exact owners leave a material choice unsettled or scaffold/tool
  policy is changing. Settled exact-owner work stays on the owner-first path.
- The only new universal implementation invariants are thesis-code
  synchronization and placement at the lowest shared domain owner.
  Non-obvious consumer discovery may use Graphify, but exact sources remain
  the proof and authority.
- PR1 does not advertise or activate proposal capture, intent promotion, or
  verified residual-work routing. Those leaves remain deferred until PR2
  installs their complete debrief, Agents-DB, review, validation, and external
  action contracts.
- The routing-trial baseline at
  a815f5bb03ded6d7215a5a88f49e5cd7e9026cf0 had one adjudicated pass and
  three unadjudicated trials. The final exact head
  a9ca7a3be964860a26402630ab87d53d519a6f02 had four of four adjudicated
  passes, exit zero, and clean trials.
- The exhaustive disposition below records where each reviewed statement
  survives. A deferred proof is not a PR1 completion claim.

## Verification

- Baseline evidence: a815f5bb03ded6d7215a5a88f49e5cd7e9026cf0 — one
  adjudicated pass and three unadjudicated trials.
- Final evidence: a9ca7a3be964860a26402630ab87d53d519a6f02 — four of four
  adjudicated passes, process exit zero, and clean trial checkouts.
- The final helper path used the fresh evaluator-free code-only Graphify graph
  for navigation, ran graphify query before exact-source inspection, and did
  not treat primary-worktree graph state as authoritative.
- PR1 proof is limited to the reviewed-intent consultation seam, its settled
  exact-owner near miss, the two universal invariants, the frozen four-trial
  corpus, and exact-head adjudication. PR2-PR5 acceptance proofs remain
  deferred as identified below.

## Canonical-State Impact

PR1 changed the executable guidance and proof owners listed in
touched_owner_paths. It did not modify
.agents/references/human_owner_intent.md, promote Open Choices, or create a
second policy owner. This debrief is episodic evidence only; it requires no
further canonical update, so canonical_updates_needed is empty. PR2-PR5 remain
responsible for their proposal, owner-specific preference, behavioral
Graphify, and Graphify setup/maintenance proofs.

## Trusted Intent Disposition

The 48 source rows below reproduce the PRD disposition ledger, including
Instruction Capture and excluding Open Choices. Surviving-owner cells use
exact repository paths. The final column distinguishes PR1 proof from work
deferred to PR2-PR5 or to a later exact-owner change.

| Source bullet | Disposition | Surviving owner | Supersession basis | Required proof | Proof status at PR1 head |
|---|---|---|---|---|---|
| Core Principles / Predictable process | hot-path invariant | .agents/skills/agent-behavior/SKILL.md#owner-first-loop | none | exact-owner routing trial | PR1 complete — settled exact-owner near-miss adjudicated at the final head. |
| Core Principles / Context hygiene | hot-path invariant | .agents/skills/agent-behavior/SKILL.md#owner-first-loop; .agents/skills/agent-behavior/references/intent-and-follow-up.md#reviewed-intent | none | near-miss trial avoids irrelevant reads | PR1 complete — the known-owner trial did not load reviewed intent. |
| Core Principles / Single source of truth | hot-path invariant | .agents/skills/agent-behavior/SKILL.md#owner-first-loop | none | duplicate-owner negative fixture | Deferred — PR2-PR5 proof; PR1 does not claim this negative fixture. |
| Core Principles / Progressive disclosure | hot-path invariant | .agents/skills/agent-behavior/SKILL.md; .agents/skills/README.md#conditional-references | none | line/pointer audit | PR1 complete for the one-hop reviewed-intent reference and thin root pointer; broader skill audit remains deferred. |
| Core Principles / Upstream first | conditional intent | .agents/references/human_owner_intent.md#core-principles; .agents/skills/graphify/SKILL.md; scripts/tests/test_graphify_upstream_skill.py | none | upstream-byte and dependency-boundary tests | Deferred — PR5. |
| Core Principles / Evidence before assertion | hot-path invariant | .agents/skills/agent-behavior/SKILL.md#owner-first-loop; scripts/scaffold/run_routing_trials.py | none | routing adjudication requires exact proof | PR1 complete — four of four trials were adjudicated at the exact final head. |
| Core Principles / Qualified provenance | narrow owner | .agents/memory/README.md#debrief-contract; .agents/skills/aria-nbv-context/references/graphify-aria-boundary.md | none | stale/worktree/ambiguity fixtures | Deferred — PR4 and PR5. |
| Core Principles / Reviewability | hot-path invariant | .agents/skills/agent-behavior/SKILL.md#owner-first-loop; .agents/skills/agent-behavior/references/external-actions.md#local-git-scope | none | owner-scoped diff review | PR1 complete for its eight-path reviewed-intent and routing-proof scope. |
| Core Principles / Conceptual collaboration | conditional intent | .agents/references/human_owner_intent.md#core-principles; aria_nbv/aria_nbv/app/AGENTS.md | none | scientific-explanation fixtures | Deferred — PR3. |
| Ownership / Code, tests, active config | hot-path invariant | .agents/skills/aria-nbv-context/SKILL.md#owner-hierarchy and the selected nearest executable source/test/config owner | none | owner routing trials | PR1 complete for the exact-owner and lowest-shared-owner trials; broader owners remain exact-owner work. |
| Ownership / Active Typst thesis and papers | narrow owner | docs/AGENTS.md; .agents/skills/typst-authoring/SKILL.md; .agents/skills/aria-nbv-context/SKILL.md#owner-hierarchy | none | thesis/code synchronization fixture and exact citation proof | PR1 complete for the thesis-code synchronization routing fixture; citation proofs remain exact-owner work. |
| Ownership / Immutable manifests and evidence | conditional intent | .agents/references/human_owner_intent.md#ownership and the exact manifest/evidence schema owner selected for the task | none | measurement-source fixture | Deferred — later exact-owner proof; not a PR1 completion claim. |
| Ownership / Root and nearest AGENTS | hot-path invariant | AGENTS.md; .agents/skills/agent-behavior/SKILL.md#owner-first-loop | none | nearest-guide routing test | Deferred — PR4 behavioral routing proof. |
| Ownership / Skills own workflows | narrow owner | .agents/skills/README.md#ownership-and-handoffs and each .agents/skills/<skill>/SKILL.md | none | frontmatter, size, and one-hop pointer tests | PR1 complete for agent-behavior frontmatter, size, and one-hop reference; full-skill proof remains deferred. |
| Ownership / This file owns reviewed preferences | conditional intent | .agents/references/human_owner_intent.md#ownership; .agents/skills/agent-behavior/references/intent-and-follow-up.md#reviewed-intent | none | proposal cannot mutate it automatically | PR1 complete by construction — no proposal route exists and Open Choices is excluded. |
| Ownership / Accepted scaffold specification | conditional intent | .omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md; .agents/references/human_owner_intent.md#ownership | none | accepted-section locator audit | Deferred — PR2. |
| Ownership / Agents DB owns actionable work | narrow owner | .agents/skills/agents-db/SKILL.md; .agents/issues.toml; .agents/todos.toml; .agents/refactors.toml; .agents/resolved.toml | none | search-before-add and lifecycle tests | Deferred — PR2. |
| Ownership / Debriefs are evidence | narrow owner | .agents/memory/README.md | none | promotion E2E test | Deferred — PR2. |
| Ownership / Newer reviewed intent supersedes locally | conditional intent | .agents/references/human_owner_intent.md#ownership; .agents/skills/agent-behavior/references/intent-and-follow-up.md#follow-up-boundary | none | conflict/narrowing fixture | Deferred — PR2. |
| Ownership / Generated navigation is derived | hot-path invariant | .agents/skills/aria-nbv-context/SKILL.md#owner-hierarchy; .agents/skills/aria-nbv-context/references/graphify-aria-boundary.md | none | derived-output negative fixture | Deferred — PR4. |
| Scaffold Preferences / Canonical .agents/ and thin root | conditional intent | AGENTS.md; .agents/skills/README.md | none | scaffold audit | Deferred — PR3/PR5 full scaffold audit; PR1 only proved its conditional root pointer. |
| Scaffold Preferences / Graphify required in Codex worktrees | narrow owner | .agents/skills/aria-nbv-context/SKILL.md#branch-index; .agents/skills/aria-nbv-context/references/graphify-aria-boundary.md; scripts/setup_worktree_env.sh; scripts/check_graphify_freshness.py; scripts/graphify_worktree_seed.py | none | fresh/usable-stale/degraded setup fixtures | Deferred — PR4 and PR5. |
| Scaffold Preferences / Official MemPalace and user-local corpus | conditional intent | .agents/references/human_owner_intent.md#scaffold-preferences; official external MemPalace plugin | none | no repo wrapper/corpus audit | Deferred — later bounded audit; not a PR1 completion claim. |
| Scaffold Preferences / Corpus composition and source provenance | conditional intent | .agents/references/human_owner_intent.md#scaffold-preferences; docs/contents/literature/index.qmd; .agents/skills/aria-nbv-context/references/semantic-memory-boundary.md | none | corpus exclusion/provenance audit when touched | Deferred — when touched; not a PR1 completion claim. |
| Scaffold Preferences / PDF mining and opt-in history | conditional intent | .agents/references/human_owner_intent.md#scaffold-preferences; official external MemPalace configuration | none | scope fixture when touched | Deferred — when touched; not a PR1 completion claim. |
| Scaffold Preferences / Retrieval exclusions | hot-path invariant | .agents/skills/aria-nbv-context/SKILL.md#owner-hierarchy; .agents/skills/aria-nbv-context/references/semantic-memory-boundary.md | none | source-selection and exclusion fixtures | Deferred — PR4. |
| Scaffold Preferences / Graphify hierarchy and provenance | narrow owner | .agents/skills/aria-nbv-context/references/graphify-aria-boundary.md | none | query result provenance test | Deferred — PR4. |
| Scaffold Preferences / Accepted Graphify option 3 | narrow owner | .omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md; .agents/skills/graphify/SKILL.md; scripts/build_graphify_projection.py | none | exact-byte and bounded-projection tests | Deferred — PR5. |
| Scaffold Preferences / Replacement branch and operator boundary | superseded in part | scripts/setup_worktree_env.sh; scripts/check_graphify_freshness.py; scripts/graphify_worktree_seed.py; SETUP.md; .agents/references/human_owner_intent.md#scaffold-preferences | current task explicitly requires setup installation and pre-commit currency enforcement; it does **not** authorize a fork, semantic lifecycle owner, secrets, or generated-output patching | lock, setup, no-secret, and no-semantic-hook tests | Deferred — PR5. |
| Scaffold Preferences / Optional upstream hook only | narrow owner | scripts/setup_worktree_env.sh; .agents/skills/aria-nbv-context/references/graphify-aria-boundary.md | current task adds repository check/repair integration but does not make upstream hooks freshness authority | primary-vs-worktree hook fixtures | Deferred — PR5. |
| Scaffold Preferences / Transcript privacy and bounded slices | conditional intent | .agents/references/human_owner_intent.md#scaffold-preferences; scripts/codex_transcript_extract.py; aria_nbv/tests/agent_memory/test_codex_transcript_extract.py; .agents/memory/README.md | none | sanitization/commit-binding tests when touched | Deferred — PR2 or later explicit provenance work; not a PR1 completion claim. |
| Scaffold Preferences / Preserve measured-autoresearch | narrow owner | .agents/skills/measured-autoresearch/SKILL.md | none | skill contract tests when touched | Deferred — when touched; not a PR1 completion claim. |
| Scaffold Preferences / Agents DB plus concise debriefs | narrow owner | .agents/skills/agents-db/SKILL.md; .agents/memory/README.md | current task strengthens automatic routing, not storage authority | proposal/retrieval E2E test | Deferred — PR2. |
| Scaffold Preferences / Every actionable finding disposed | hot-path invariant | .agents/skills/agent-behavior/SKILL.md#completion; .agents/skills/agents-db/references/modes.md | none | residual-work routing trial | Deferred — PR2; residual-work routing is inactive at PR1. |
| Scaffold Preferences / Retire state only after migration | conditional intent | .agents/references/human_owner_intent.md#scaffold-preferences and the exact retiring owner selected for a migration | none | consumer/claim ledger when touched | Deferred — when touched; not a PR1 completion claim. |
| Scaffold Preferences / Immutable accepted plans/specs | conditional intent | .agents/references/human_owner_intent.md#scaffold-preferences; native .omx/specs and .omx/plans artifact lifecycle | none | no in-place rewrite audit when touched | Deferred — when touched; not a PR1 completion claim. |
| Scaffold Preferences / Small independent skills | hot-path invariant | .agents/skills/README.md; scripts/tests/test_agent_governance_g002.py; scripts/tests/test_routing_trials.py | none | size/overlap trials | Deferred — PR3 full proof; PR1 only verified the compact agent-behavior seam. |
| Scaffold Preferences / Shared Typst ownership | narrow owner | docs/AGENTS.md; docs/typst/shared; .agents/skills/typst-authoring/SKILL.md | none | Typst compile/link tests | Deferred — PR3. |
| Scaffold Preferences / README only for useful orientation | conditional intent | .agents/references/human_owner_intent.md#scaffold-preferences and the nearest package AGENTS.md/README.md owner | none | duplication audit when touched | Deferred — PR3. |
| Scaffold Preferences / Public docs renderable/current-vs-history | narrow owner | docs/AGENTS.md; Makefile documentation build targets | none | render/build and provenance checks | Deferred — PR3 or later docs-owner work. |
| Scaffold Preferences / Versioned artifacts through Git LFS | conditional intent | .gitattributes and the nearest versioned-artifact owner | none | LFS pointer audit when touched | Deferred — when touched; not a PR1 completion claim. |
| Scaffold Preferences / No compatibility-only cache APIs | conditional intent | .agents/references/human_owner_intent.md#scaffold-preferences and the exact package/API owner | none | no-consumer plus regression proof when touched | Deferred — when touched; not a PR1 completion claim. |
| Non-Goals / No replacements for maintained tools | hot-path invariant | .agents/skills/agent-behavior/SKILL.md#owner-first-loop; .agents/skills/graphify/SKILL.md; scripts/tests/test_graphify_upstream_skill.py | none | dependency-boundary negative fixture | Deferred — PR5. |
| Non-Goals / Derived evidence is not truth | hot-path invariant | .agents/skills/agent-behavior/SKILL.md#owner-first-loop; .agents/skills/aria-nbv-context/SKILL.md#owner-hierarchy; .agents/skills/aria-nbv-context/references/graphify-aria-boundary.md | none | exact-source proof required after retrieval | Deferred — PR4 full behavioral proof; PR1 helper preserved exact-source authority. |
| Non-Goals / No scaffold handbook/domain mirror | hot-path invariant | .agents/skills/agent-behavior/SKILL.md#owner-first-loop; .agents/skills/README.md | none | duplication/size audit | Deferred — PR3. |
| Non-Goals / No inferred acceptance | hot-path invariant | .agents/skills/agent-behavior/references/intent-and-follow-up.md#follow-up-boundary; .agents/references/human_owner_intent.md#ownership | none | recurrence/model-consensus rejection fixture | Deferred — PR2. |
| Non-Goals / No whole-scaffold PR | hot-path invariant | this debrief's touched_owner_paths and Commits sections | none | diff-scope audit | PR1 complete — the range is limited to reviewed-intent guidance and routing proof owners. |
| Instruction Capture / destination map and procedure | narrow owner | .agents/skills/aria-nbv-context/SKILL.md#capture-rule; .agents/skills/agent-behavior/references/durable-capture.md | none | explicit-capture routing trial | Deferred — PR2 proof; PR1 preserved the existing direct-review route unchanged. |

## Commits

- [a815f5bb03ded6d7215a5a88f49e5cd7e9026cf0](https://github.com/JanDuchscherer104/ARIA-NBV/commit/a815f5bb03ded6d7215a5a88f49e5cd7e9026cf0) — WP1: freeze reviewed-intent routing trials
- [2f25b770440b559e7f86b2f7a5e81bd4d671f8f3](https://github.com/JanDuchscherer104/ARIA-NBV/commit/2f25b770440b559e7f86b2f7a5e81bd4d671f8f3) — WP2: route reviewed intent and universal invariants
- [a9ca7a3be964860a26402630ab87d53d519a6f02](https://github.com/JanDuchscherer104/ARIA-NBV/commit/a9ca7a3be964860a26402630ab87d53d519a6f02) — WP3: harden exact-head routing proof
