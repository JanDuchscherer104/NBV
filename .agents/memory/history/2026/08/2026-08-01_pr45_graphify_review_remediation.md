---
id: 2026-08-01_pr45_graphify_review_remediation
date: 2026-08-01
title: "PR45 Graphify Review Remediation"
status: done
topics: [graphify, scaffold, code-review, worktrees]
confidence: high
canonical_updates_needed:
  - .agents/references/human_owner_intent.md
  - .agents/skills/aria-nbv-context/SKILL.md
  - .omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md
files_touched:
  - .agents/skills/graphify/
  - .agents/skills/aria-nbv-context/SKILL.md
  - scripts/build_graphify_projection.py
  - scripts/check_graphify_freshness.py
  - scripts/setup_worktree_env.sh
  - scripts/tests/
---

## Task

Resolve the six unresolved PR #45 review findings while keeping Graphify's
content-addressed caches as standard linked-worktree prerequisites. The human
owner explicitly required the upstream Graphify skill to remain unmodified and
placed all ARIA-NBV-specific instructions in `aria-nbv-context`.

## Method

- Reinstalled the Graphify 0.9.31 `agents` bundle and verified every file
  against upstream commit `4fe11092ccbe9f543608f140c790f68d5d83cae4`.
- Deleted the downstream Codex semantic checker and moved eligibility,
  current-client compatibility, coverage, provenance, and exact-source fallback
  instructions into `aria-nbv-context`.
- Hardened projection owner reads against symlink escapes.
- Extended freshness validation to compare recorded owner digests with live
  owner bytes and fail on dirty owner paths.
- Preserved standard worktree creation and linking of only the shared
  `semantic` and `semantic-deep` cache namespaces.

## Findings

The invalid `spawn_agent` recipe and incomplete custom semantic merge were
consequences of patching the upstream skill. Removing that downstream lifecycle
surface is the durable fix. ARIA guidance now prefers upstream CLI behavior and
leaves a graph stale when the current client cannot satisfy upstream semantic
coverage and scope reconciliation.

Graphify itself remains optional derived navigation. Cache availability is a
standard environment capability, not freshness evidence: projections, graphs,
manifests, AST state, and semantic run state remain worktree-local.

## Verification

- upstream skill byte-identity test
- 42 projection tests, including every readable owner family's symlink boundary
- 13 freshness tests, including dirty Typst, style, both bibliography, and
  literature-manifest owners
- linked-worktree cache setup smoke
- CI-impact tests
- agent-memory and scaffold-audit validation

## Canonical-state impact

The owner intent, source order, and accepted scaffold target state now record
the upstream-skill/ARIA-companion boundary and mandatory cache-environment
contract. No scientific or package-runtime state changed.
