---
id: 2026-08-23_g002_pr2_proposal_review_lifecycle
date: 2026-08-23
title: "G002 PR2 Proposal Review Lifecycle"
status: done
topics: [scaffold, intent, memory, agents-db, routing]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - .agents/issues.toml
  - .agents/memory/README.md
  - .agents/refactors.toml
  - .agents/resolved.toml
  - .agents/todos.toml
  - .agents/skills/agent-behavior/SKILL.md
  - .agents/skills/agent-behavior/references/external-actions.md
  - .agents/skills/agent-behavior/references/intent-and-follow-up.md
  - .agents/skills/agents-db/SKILL.md
  - .agents/skills/agents-db/references/modes.md
  - scripts/new_debrief.py
  - scripts/scaffold/fixtures/routing.json
  - scripts/scaffold/fixtures/routing_prompts.jsonl
  - scripts/scaffold/run_routing_trials.py
  - scripts/tests/test_agent_governance_g002.py
  - scripts/tests/test_debrief_index.py
  - scripts/tests/test_routing_trials.py
  - scripts/validate_agent_memory.py
codex_thread: codex://threads/019fff4c-cc77-7351-bb81-9759852617c6
repo_object_format: sha1
repo_head: 31d484d45e22bf946cc57091618c3aae7795bde1
repo_branch: "codex/scaffold-intent-pr2"
worktree_kind: linked
---

## Task

Complete the G002 PR2 proposal-review lifecycle closeout at the exact clean
head. Resolve `todo-044` after the routing proof, retain `issue-025` open and
`refactor-016` in progress, and record the lifecycle evidence without changing
implementation owners.

## Method

- Inspected the exact Agents DB records before editing and used the existing
  `scripts/agents_db.py resolve todo todo-044` command so resolution history is
  retained rather than deleted.
- Preserved the current bytes of `issue-025` and `refactor-016`; neither record
  had a missing planned disposition requiring an edit.
- Recorded the native debrief against the final pre-debrief
  implementation/review-fix anchor `31d484d45e22bf946cc57091618c3aae7795bde1` and
  regenerated the derived debrief index after this source edit. The debrief and
  index-only commits `46cae9f2f81b41fe63b13dad357d748405abb3f8` and
  `2b35f323d46f20d96f43c7a8db782141bb56d45c` remain excluded from the evidence
  links below.

## Findings

- Review fixes corrected proposal-disposition routing in `6a3cdab`, required
  debrief commit provenance and a refactor receipt in `b8dcd7c`, hardened the
  initial runner evidence path in `a3cd5e7`, authenticated artifacts and
  canonical checkout/serialization receipts in `bd50eba`, and retained
  bounded complete evidence in `a285097`.
- The initial new-run snapshot
  `.agents/work/routing-trials/6a3cdab23aba-bd50eba153b9/index.json` recorded
  `3/4`: the 64-item event-evidence bound truncated a required trace. This
  snapshot is preserved as defect evidence. The corrected baseline
  `.agents/work/routing-trials/6a3cdab23aba-a285097dfe5e/index.json` records
  `4/4`, and the candidate
  `.agents/work/routing-trials/a285097dfe5e-a285097dfe5e/index.json` records
  `4/4` with `comparison.matched=true`.
- The candidate comparison uses runner revision
  `abe5a1c9e9e4abde9712a07cd31f5dc5914c62a7`, Codex CLI `0.147.0`, identical
  per-ID prompt hashes, no caps or timeouts, and clean canonical trial
  checkouts. Both the corrected baseline and candidate use the same four trial
  IDs; the candidate tests `a285097dfe5ed30fe02fd30563cee7b7bccfd2e9`.
- Historical under the prior rubric, the original controlled snapshots remain
  recorded as `.agents/work/routing-trials/dae2171918b9-96b01d7679b3/index.json`
  with `1/4` and `.agents/work/routing-trials/96b01d7679b3-96b01d7679b3/index.json`
  with `4/4`; that historical `1/4→4/4` evidence is not replaced by the
  corrected rerun.
- `todo-044` is resolved with the proof note below; `issue-025` remains open;
  `refactor-016` remains `in_progress`.
- Final review found that `todo-044`'s resolution note conflated historical
  old-rubric `1/4→4/4` evidence with corrected authenticated `4/4→4/4`
  matched receipts; commit `31d484d` corrected the distinction.
- The proposal route is evidence-backed and proposal-only: helpers identify
  and validate candidate owner updates, while ordinary repository edits and
  explicit review dispositions are required for durable policy changes.
  Helpers never auto-install policy or backlog state.

## Verification

- The final focused routing suite passed `84` tests with
  `aria_nbv/.venv/bin/python -m pytest scripts/tests/test_routing_trials.py -q`.
- `make check-agent-memory` passed after index regeneration.
- `make agents-db AGENTS_ARGS='validate'` passed.
- Fresh live baseline and candidate routing trials ran immediately before this
  debrief update. Their authenticated snapshots are
  `.agents/work/routing-trials/6a3cdab23aba-a285097dfe5e/index.json` and
  `.agents/work/routing-trials/a285097dfe5e-a285097dfe5e/index.json`; both
  recorded `4/4`.
- The fresh broader gate passed `175` tests with
  `aria_nbv/.venv/bin/python -m pytest scripts/tests/test_debrief_index.py scripts/tests/test_routing_trials.py scripts/tests/test_agent_governance_g002.py -q`.
- `make scaffold-audit` reported `skills=12 errors=0 warnings=0`;
  `make scaffold-audit-self-test` passed `33` self-tests and `27` migration
  tests; Agents DB validation passed.
- The full G002 work changed Python, guidance, memory, tests, and Agents DB
  owners; only the earlier closeout commit had no Python changes.
- The final pre-debrief implementation/review fix was committed at
  `31d484d45e22bf946cc57091618c3aae7795bde1`; after that commit, only this
  debrief source and its derived index remain modified.

## Canonical-State Impact

The full G002 work changed Python, guidance, memory, tests, and Agents DB
owners, but this closeout records no additional canonical update;
`canonical_updates_needed` remains empty. The debrief and index are
episodic/derived navigation evidence, and the resolved todo retains the
completed lifecycle history.

## Commits

- [dae2171918b9fd01115d84b1b6ce6f5d5f51f710](https://github.com/JanDuchscherer104/ARIA-NBV/commit/dae2171918b9fd01115d84b1b6ce6f5d5f51f710) — WP1: freeze intent follow-up routing trials
- [48f76f37cc27b8a3f681e0ab83d421b8dcb1baf1](https://github.com/JanDuchscherer104/ARIA-NBV/commit/48f76f37cc27b8a3f681e0ab83d421b8dcb1baf1) — WP2: validate intent proposals and debrief commit links
- [6e2b95f169d5273851e9bd65425f915cdb8810f1](https://github.com/JanDuchscherer104/ARIA-NBV/commit/6e2b95f169d5273851e9bd65425f915cdb8810f1) — WP3: activate the proposal review lifecycle
- [6e9b34d503e482ad04550a80283a9cd5996ffeea](https://github.com/JanDuchscherer104/ARIA-NBV/commit/6e9b34d503e482ad04550a80283a9cd5996ffeea) — WP4: enforce durable proposal evidence
- [c9bcd86265444bd570887e0ebc90e1c1d27c5ca7](https://github.com/JanDuchscherer104/ARIA-NBV/commit/c9bcd86265444bd570887e0ebc90e1c1d27c5ca7) — WP5: reject debrief index commits
- [a773c930350209782587568e3ef95d033357ff31](https://github.com/JanDuchscherer104/ARIA-NBV/commit/a773c930350209782587568e3ef95d033357ff31) — WP6: route proposal lifecycle proof
- [f67ae86fca001c23fc6235ce1f827579e429b3bc](https://github.com/JanDuchscherer104/ARIA-NBV/commit/f67ae86fca001c23fc6235ce1f827579e429b3bc) — WP7: enforce human review and residual follow-up routing
- [8955cc75cf0f48125dc24bc1b4a290f74ffa4b9c](https://github.com/JanDuchscherer104/ARIA-NBV/commit/8955cc75cf0f48125dc24bc1b4a290f74ffa4b9c) — WP8: require human proposal disposition
- [20d24904ad88407a451ed0bc0c78d165978bf78c](https://github.com/JanDuchscherer104/ARIA-NBV/commit/20d24904ad88407a451ed0bc0c78d165978bf78c) — WP9: clarify eligible intent proposal leaf requirements
- [e4776224978348d774ddade83b1f7bcea1218c18](https://github.com/JanDuchscherer104/ARIA-NBV/commit/e4776224978348d774ddade83b1f7bcea1218c18) — WP10: bound routing output and admit larger event streams
- [e17d8a87fc57a706c8f7420aa9bbbd315b2798ca](https://github.com/JanDuchscherer104/ARIA-NBV/commit/e17d8a87fc57a706c8f7420aa9bbbd315b2798ca) — WP11: cover total event evidence bounds
- [fc9e59c3b906f1806ee7030650de334643c74dd6](https://github.com/JanDuchscherer104/ARIA-NBV/commit/fc9e59c3b906f1806ee7030650de334643c74dd6) — WP12: allow repeated routing evidence citations
- [bfcb295a51cfb3aad84e39c87dc6b06b2b01a2b8](https://github.com/JanDuchscherer104/ARIA-NBV/commit/bfcb295a51cfb3aad84e39c87dc6b06b2b01a2b8) — WP13: harden the abstract proposal review protocol
- [8acb111155c7632f2314ae0050cf13e1e2fc24f9](https://github.com/JanDuchscherer104/ARIA-NBV/commit/8acb111155c7632f2314ae0050cf13e1e2fc24f9) — WP14: repair debrief template and proposal-review SSOT
- [86ef395e0a56a52278a2f3493b9a005f92830fae](https://github.com/JanDuchscherer104/ARIA-NBV/commit/86ef395e0a56a52278a2f3493b9a005f92830fae) — WP15: freeze/compare prompts and bound subprocess output
- [96b01d7679b33a668a3f37827f533585afa9338d](https://github.com/JanDuchscherer104/ARIA-NBV/commit/96b01d7679b33a668a3f37827f533585afa9338d) — WP16: strengthen residual triage
- [6a3cdab23aba1c40aa888930797085fdd3fb7907](https://github.com/JanDuchscherer104/ARIA-NBV/commit/6a3cdab23aba1c40aa888930797085fdd3fb7907) — review fix: correct proposal disposition routing
- [b8dcd7cee4e42ab278a2b2d181d0bd6606d7cdd5](https://github.com/JanDuchscherer104/ARIA-NBV/commit/b8dcd7cee4e42ab278a2b2d181d0bd6606d7cdd5) — review fix: require debrief commit provenance
- [a3cd5e7b0987a0c14d5174cd00ca680ab15e9a5c](https://github.com/JanDuchscherer104/ARIA-NBV/commit/a3cd5e7b0987a0c14d5174cd00ca680ab15e9a5c) — review fix: harden routing trial evidence
- [bd50eba153b91ba2d371cc5691baa0184f3090cc](https://github.com/JanDuchscherer104/ARIA-NBV/commit/bd50eba153b91ba2d371cc5691baa0184f3090cc) — review fix: authenticate routing trial receipts
- [a285097dfe5ed30fe02fd30563cee7b7bccfd2e9](https://github.com/JanDuchscherer104/ARIA-NBV/commit/a285097dfe5ed30fe02fd30563cee7b7bccfd2e9) — review fix: retain complete routing evidence
- [31d484d45e22bf946cc57091618c3aae7795bde1](https://github.com/JanDuchscherer104/ARIA-NBV/commit/31d484d45e22bf946cc57091618c3aae7795bde1) — review fix: distinguish corrected routing receipts
