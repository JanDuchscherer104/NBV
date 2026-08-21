---
id: 2026-08-21_pr65_routing_trials
date: 2026-08-21
title: "PR 65 bounded routing trials"
status: done
topics: [agent-scaffold, routing, context7, graphify, verification]
confidence: high
canonical_updates_needed: []
codex_thread: codex://threads/019fff4c-cc77-7351-bb81-9759852617c6
artifacts:
  - .agents/work/routing-trials/5808dd49c4e7/
  - .agents/work/routing-trials/750e2850c35e/
  - .agents/work/routing-trials/7fcc19032a03/
---

## Task

Exercise the PR #65 routing changes with prompt/rubric separation and fresh,
read-only Codex processes before publication.

## Method

Frozen prompt-only JSONL was executed with Codex CLI 0.147.0,
`gpt-5.6-luna`, and medium reasoning against detached exact-head checkouts.
Each run captured raw JSONL, a schema-constrained report, runtime flags, token
usage, and worktree cleanliness. Separate high-reasoning verifier runs compared
the raw events with the hidden static rubric after execution.

## Findings

- The first broad run exposed real misses in failure-first, rendering, semantic
  recall, and Context7 routing, plus an Oracle fixture that conflated evidence
  construction with private scoring.
- Oracle evidence/private scoring and pose/rendering/VIN geometry now route to
  separate source and test owners.
- The final selective rerun used the Context7 plugin rather than web search,
  opened the reviewed semantic-memory boundary before recall, and selected the
  focused pose-orientation owner and proof.
- Every detached checkout remained clean. Read-only package-test attempts that
  needed environment writes were recorded as blocked rather than successful.

## Verification

The final verifier report at
`.agents/work/routing-trials/7fcc19032a03/verification.json` passed all three
previously failing routes. The preceding verifier at
`.agents/work/routing-trials/750e2850c35e/verification.json` passed the repaired
failure-first, rendering, Oracle-evidence, and Oracle-scoring routes. The first
run preserves the unaffected passing routes and the exact failure evidence that
triggered remediation.

## Canonical-State Impact

Routing prompts, static rubrics, context-map leaves, and two branch selectors
changed. Raw trial and verifier artifacts remain ignored evidence; this dated
debrief is their only committed summary.
