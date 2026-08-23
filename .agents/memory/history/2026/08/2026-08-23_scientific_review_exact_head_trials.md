---
id: 2026-08-23_scientific_review_exact_head_trials
date: 2026-08-23
title: "Scientific review exact-head trials"
status: done
topics: [scientific-review, scaffold, trials, provenance]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - .agents/skills/scientific-review/references/review-protocol.md
  - Makefile
  - scripts/scaffold/fixtures/scientific_review_prompts.jsonl
  - scripts/scaffold/fixtures/scientific_review_rubric.json
  - scripts/scaffold/run_routing_trials.py
  - scripts/scaffold/run_scientific_review_trials.py
  - scripts/scaffold/schemas/scientific_review_adjudication.schema.json
  - scripts/scaffold/schemas/scientific_review_verdict.schema.json
  - scripts/scaffold/trial_harness.py
  - scripts/tests/test_routing_trials.py
  - scripts/tests/test_scientific_review_trials.py
codex_thread: codex://threads/01a02ab6-c75e-7313-be12-e5f90ae0cde3
repo_object_format: sha1
repo_head: 4516075c8bd6f572e03edd5b8728f3f8f1975578
repo_branch: "detached"
worktree_kind: linked
---

## Task
Record the G004 scientific-review exact-head trial work and its durable
scaffold lessons without changing canonical implementation owners.

## Method
Reviewed the protocol, shared harness, runners, fixtures, schemas, and focused
tests at the detached linked-worktree HEAD. The work is represented by
[b35a2e7](https://github.com/JanDuchscherer104/ARIA-NBV/commit/b35a2e7e72c31c8ebf6a16820dbb655e04473ccb),
[9d5df9c](https://github.com/JanDuchscherer104/ARIA-NBV/commit/9d5df9c4cbd21c0c393f35346016718ec412b725),
[623a115](https://github.com/JanDuchscherer104/ARIA-NBV/commit/623a11502fa028ef9028c9e26895f007ad3b546d), and
[4516075](https://github.com/JanDuchscherer104/ARIA-NBV/commit/4516075c8bd6f572e03edd5b8728f3f8f1975578).

## Findings
The shared harness is the sole lifecycle owner; candidates use exact-byte and
principal identity checks plus bounded adapter metadata. Prompt-only suites
permit clean bounded zero-execution items while routing remains strict. A
hidden adjudicator cannot rescue a bad primary response; unsupported
`uniqueItems` remains runtime-enforced, the exact trial ID must be prompted,
negative controls are isolated, evidence uses candidate-relative 1-based line
spans with bounded severities, and corrections are two-phase with links to
persisted original report hashes. The exact live outputs remain ignored at
`.agents/work/scientific-review-trials/{initial,corrected}/4516075c8bd6-4516075c8bd6`.

## Verification
48 science tests, 117 combined tests, and 84 thesis-routing tests passed;
Ruff, mypy, and `git diff --check` passed. The exact live suite at
`4516075c8bd6f572e03edd5b8728f3f8f1975578` ran 18 initial and 7 corrected
trials: every item returned code 0, left a clean checkout, and passed hidden
adjudication; resolution hashes were independently recomputed.

## Canonical Owner Impact
No canonical updates are needed. This debrief records completed G004
scientific-review/scaffold evidence and preserves the listed protocol,
runner, harness, fixture, schema, Makefile, and test owners as navigation
paths only.
