---
id: 2026-08-19_pr_51_and_pr_65_guidance_consolidation
date: 2026-08-19
title: "PR 51 and PR 65 guidance consolidation"
status: done
topics: [agent-scaffold, source-order, graphify, context7, pull-request]
confidence: high
canonical_updates_needed: []
---

## Task

Consolidate PR #51 into PR #65 on current `origin/main`, address both review
sets, and preserve the human owner's source-order and progressive-disclosure
priorities without growing a monolithic behavior skill.

## Method

Replayed both branches semantically onto `origin/main`, inspected every open
review thread, compared the project Graphify bundle with upstream 0.9.47, and
routed each durable rule to its smallest scaffold owner. Added focused routing
fixtures and contract tests for the review-sensitive pointers.

## Findings

- `.agents/references/source_order.md` is now a compositional owner tree with
  shared Typst terminology owners and subordinate Graphify/Context7 evidence.
- `aria-nbv-context` owns Graphify-first traversal, worktree lifecycle detail,
  exact Context7 IDs, and focused query seeds; the Graphify skill remains
  byte-identical to upstream.
- `agent-behavior` remains a compact router. Durable capture and external-action
  detail stay in its branch references.
- Canonical Python docstring examples moved behind
  `python-standards/references/canonical-examples.md`.
- `docs/AGENTS.md` now points to exact RQ3, RQ5, and promotion-queue labels.

## Verification

Passed `make scaffold-audit-self-test`, the Graphify upstream, freshness,
worktree-seed, and setup tests, `scripts/tests/test_ci_impact.py`,
`make check-agent-memory`, Ruff on affected Python, JSON parsing, and
`git diff --check`. Hosted checks remain a publication-time proof.

## Canonical Owner Impact

Current guidance owners, routing fixtures, Graphify version gates, CI dependency
pin, accepted target-state supersession, and their focused tests were updated.
No Typst scientific claim or Python runtime behavior changed.
