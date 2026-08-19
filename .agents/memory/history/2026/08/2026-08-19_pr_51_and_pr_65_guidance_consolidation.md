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

- `aria-nbv-context` now owns the hierarchical source map, conflict/capture
  rules, Graphify-first traversal, and Context7 App route.
- Its initialization map briefly describes the shared symbol, equation, and
  glossary owners plus the manifest-to-bibliography-to-review-to-thesis
  literature chain. Exact scientific and executable files remain truth owners.
- `.agents/references/source_order.md` is an 18-line deprecated compatibility
  pointer, preserving old anchors without a second policy copy.
- Active skills and routing fixtures use Context7 App calls; MCP-Docker
  Context7 appears only as an explicit prohibited migration route.
- The Graphify skill remains byte-identical to upstream.
- `agent-behavior` remains a compact router. Durable capture and external-action
  detail stay in its branch references.
- Canonical Python docstring examples moved behind
  `python-standards/references/canonical-examples.md`.
- `docs/AGENTS.md` now points to exact RQ3, RQ5, and promotion-queue labels.

## Verification

Passed `make scaffold-audit`, `make scaffold-audit-self-test`, the Graphify
upstream, freshness, worktree-seed, and setup tests, the 14-test governance
suite, the 17-test ownership-consolidation contract, CI-impact self-tests,
`make check-agent-memory`, the skill-authoring validator, Ruff on affected
Python, JSON parsing, and `git diff --check`. Full `make ci` also passed after
initializing the clone's declared submodules, including the 267-test Q_H suite,
115-test package slice, Quarto render, both Typst compiles, authoring hygiene,
and thesis-marker contract. Hosted checks remain a publication-time proof.

## Canonical Owner Impact

Current guidance owners, routing fixtures, Graphify version gates, CI dependency
pin, accepted target-state supersession, and their focused tests were updated.
No Typst scientific claim or Python runtime behavior changed.
