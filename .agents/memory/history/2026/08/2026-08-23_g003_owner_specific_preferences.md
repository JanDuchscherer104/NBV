---
id: 2026-08-23_g003_owner_specific_preferences
date: 2026-08-23
title: "G003 Owner-Specific Preferences"
status: done
topics: [scaffold, guidance, ownership, routing]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - .agents/skills/README.md
  - .agents/skills/aria-nbv-context/references/graphify-aria-boundary.md
  - .agents/skills/python-standards/SKILL.md
  - .agents/skills/python-standards/references/general_conventions.md
  - aria_nbv/AGENTS.md
  - aria_nbv/aria_nbv/app/AGENTS.md
  - aria_nbv/aria_nbv/app/references/scientific-interpretation.md
  - scripts/scaffold/fixtures/routing.json
  - scripts/scaffold/fixtures/routing_prompts.jsonl
  - scripts/tests/test_agent_governance_g003.py
  - scripts/tests/test_graphify_upstream_skill.py
  - scripts/tests/test_routing_trials.py
codex_thread: codex://threads/019fff4c-cc77-7351-bb81-9759852617c6
repo_object_format: sha1
repo_head: ec23d98b42c804dcc95fd0399964a6e3a9e6b525
repo_branch: "codex/scaffold-intent-pr3"
worktree_kind: linked
---

## Task

Resolve PR #108 review findings with single-owner guidance and behavior-level
routing evidence rather than historical lexical comparisons.

## Method

- Replaced the permanent stacked-base test with current-source structural and
  AST checks.
- Made pointer preservation mechanical and added concrete positive, near-miss,
  and forbidden-outcome routing cases.
- Used the pinned upstream commit and installed Graphify sources to record one
  accepted bundle manifest; the unusable local graph was not queried.

## Findings

- Config targets are constructed once per owning lifecycle at composition roots;
  hot paths receive dependencies. Framework lifecycle exceptions and teardown
  stay with the Python conventions owner.
- One-consumer helpers remain local; demonstrated app consumers share behavior
  at the lowest app owner.
- Scientific app explanations activate a focused rubric after a verdict-first
  sentence. Operational counts remain on the lightweight path.
- Graphify pinning applies only to its accepted bundle and does not establish a
  policy for other upstream skills.

## Verification

- Current-owner, AST, Graphify-integrity, evaluator, and governance tests passed;
  scaffold audit reported `skills=12 errors=0 warnings=0`.
- The seven-case owner suite used Codex CLI 0.147.0, `gpt-5.6-luna`, low effort,
  and one isolated unseeded trajectory per case. At rubric
  `64611ff03b7930fcb36c62dbef6209ca96ab0fda`, the pre-feature PR #107 head
  passed 5/7 and the candidate passed 6/7; the five non-interpretation cases and
  operational near-miss passed.
- The final interpretation pair at
  `ec23d98b42c804dcc95fd0399964a6e3a9e6b525` passed 2/2 versus 1/2 on the same
  pre-feature head. The positive loaded the scientific rubric; the operational
  near-miss stopped before it. One repetition supports only these observations,
  not a stability claim.
- Full-suite manifests: baseline
  `1cceb5e474493f081ff815f01acafcbb9e518b69721b5a4c8d3a1e6477ba9b2f`,
  candidate `eadb071d22804507df3fa1a5af7556b3450fe0499910cfed522bf84bbae7b446`.
- Final-pair manifests: baseline
  `ace117b06286634a6dc6da785335a68d3f67035edf1e415eec0505de5264858a`
  and candidate
  `be764b0c28eedda407ac47216b521091e9ac598887c3d0b1678442812e6f7b40`.

## Canonical-State Impact

The listed guidance and reference files own the active contracts. This debrief
and retained routing traces are evidence, not policy or implementation owners.

## Commits

- [7d17e32b76577ce51ea55c802934d061616d82dd](https://github.com/JanDuchscherer104/ARIA-NBV/commit/7d17e32b76577ce51ea55c802934d061616d82dd) — WP1: establish current-owner guidance and behavior tests
- [92db7ea233901da14e69f2f04cb1df6fadf3e345](https://github.com/JanDuchscherer104/ARIA-NBV/commit/92db7ea233901da14e69f2f04cb1df6fadf3e345) — WP2: activate Python lifecycle and helper ownership routing
- [64611ff03b7930fcb36c62dbef6209ca96ab0fda](https://github.com/JanDuchscherer104/ARIA-NBV/commit/64611ff03b7930fcb36c62dbef6209ca96ab0fda) — WP3: align routing cases with exact owners
- [1b81a03474d82aefd7e8557aa54b580eb00851c8](https://github.com/JanDuchscherer104/ARIA-NBV/commit/1b81a03474d82aefd7e8557aa54b580eb00851c8) — WP4: make the scientific explanation branch explicit
- [ec23d98b42c804dcc95fd0399964a6e3a9e6b525](https://github.com/JanDuchscherer104/ARIA-NBV/commit/ec23d98b42c804dcc95fd0399964a6e3a9e6b525) — WP5: freeze the final positive and near-miss interpretation cases
