---
id: 2026-08-03_graphify_canonical_publication
date: 2026-08-03
title: "Graphify Canonical Publication"
status: done
topics: [graphify, scaffold, worktrees, publication]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/references/source_order.md
  - .agents/skills/aria-nbv-context/references/graphify-aria-boundary.md
  - .github/workflows/ci.yml
  - .gitignore
  - .omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md
  - .pre-commit-config.yaml
  - Makefile
  - graphify-out/GRAPH_REPORT.md
  - graphify-out/graph.html
  - graphify-out/graph.json
  - graphify-out/manifest.json
  - scripts/check_graphify_freshness.py
  - scripts/tests/test_ci_impact.py
  - scripts/tests/test_graphify_freshness.py
---

## Task

Adopt upstream Graphify's shared team topology with maximal navigation utility
and minimal local lifecycle machinery: one committed canonical snapshot, the
upstream primary-checkout hooks, and usable-stale consumption in linked
worktrees.

## Method And Findings

Upstream recommends committing Graphify output and installing its post-commit
hook, while its implementation deliberately skips both Git hooks in linked
worktrees. ARIA's prior per-worktree-only artifact policy therefore prevented
the recommended shared baseline and left new worktrees without a graph.

The accepted target state now records the newer human decision explicitly.
ARIA tracks only the query-critical graph, report, portable manifest, and HTML;
caches, projection, AST, semantic-run, cost, memory, and temporary state remain
ignored. The primary integration checkout publishes this snapshot. Linked
worktrees query it when usable and verify reported branch-local stale paths
directly.

The freshness checker no longer requires the local Graphify stat cache or
ignored projection to consider the committed snapshot usable. Pre-commit and
pre-push validate usable navigation, while strict freshness is retained through
explicit state and publication targets. The publication target reconstructs
the ignored projection at the graph revision, validates current owner bytes,
and rejects uncommitted snapshot changes. Main-branch CI runs that gate without
installing Graphify or invoking semantic extraction.

## Verification

- Graphify freshness regression tests pass.
- CI-impact and guidance regression tests pass.
- The project Graphify skill remains byte-identical to upstream.
- The canonical graph was rebuilt at the PR head with deep-cache coverage and
  strict freshness validation.
- Agent-memory, scaffold, formatting, and publication checks pass.

## Canonical-State Impact

The accepted scaffold target state contains the explicit 2026-08-03
supersession. No additional state file is required; the target specification,
context boundary, executable checks, and tracked snapshot own the decision.
