---
id: 2026-09-01_allow_stale_graphify_semantics_during_worktree_setup
date: 2026-09-01
title: "Allow Stale Graphify Semantics During Worktree Setup"
status: done
topics: [graphify, worktree-setup, codex]
confidence: high
canonical_updates_needed:
  - scripts/setup_worktree_env.sh
  - scripts/check_graphify_freshness.py
  - scripts/graphify_worktree_seed.py
  - scripts/reconcile_graphify_worktree.py
  - .agents/skills/aria-nbv-context/references/graphify-aria-boundary.md
touched_owner_paths:
  - scripts/setup_worktree_env.sh
  - scripts/check_graphify_freshness.py
  - scripts/graphify_worktree_seed.py
  - scripts/reconcile_graphify_worktree.py
  - .agents/skills/aria-nbv-context/references/graphify-aria-boundary.md
codex_thread: codex://threads/01a05c9d-8b68-7141-ac06-3d25b0ff4631
repo_object_format: sha1
repo_head: 283f155ffb2ede84ce77cffe3026f035c8af862c
repo_branch: "codex/allow-stale-graphify-semantics"
worktree_kind: linked
---

## Task
Make Codex worktree creation succeed with a valid inherited Graphify graph when
only semantic or semantic-deep extraction is pending.

## Method
Separated deterministic bootstrap from semantic extraction: retain the seeded
graph, rebuild only the local projection when needed, run Graphify's upstream
no-LLM `update --no-cluster` path for the local AST/code layer, and admit
pending semantic state as `usable-stale`. Kept malformed state unusable.

## Findings
`graphify-out/needs_update` is an upstream semantic-refresh signal, not a
reason to prevent a new Codex task from starting. The active Codex task is the
host that can follow Graphify's agent-based semantic extraction route; a shell
setup script cannot invoke that session capability.

The setup owner now preserves and copies the marker, validates `--usable` after
deterministic preparation, and does not run `graphify extract` during worktree
creation. Focused regressions prove an actual temporary linked worktree starts
with a locally copied graph and reports `usable-stale` for the marker.

Follow-up reproduction found that rebuilding the projection can prune obsolete
generated `graphify-input` Markdown entries. Those are semantic-only stale
inputs, not source deletions; their removal and a large pending semantic set
now remain `usable-stale`. Re-running setup also accepts a seed whose manifest
still lists such pruned generated entries.

A later real Codex worktree exposed stale AST/code state in the seed. Calling
`graphify update <worktree> --no-cluster` during deterministic preparation is
the minimal upstream-supported repair: it updates the worktree-local code
graph without semantic extraction. The setup preserves an inherited
`needs_update` marker because that command clears Graphify's semantic-pending
signal even though the semantic work remains deferred.

## Commits
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/f65990a06da09e57624fedef2dc8b83603ab32b0
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/982c973c70530aaa201b5f62c8d32d7584fe8326
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/d083cce526c8d598fabb0a50277ced5d69d76e2c
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/824d43e65691333c4894bd415b17618ea6de9be9

## Verification
Passed the Graphify projection, freshness, seeding, reconciler, session
readiness, upstream command/skill, and shell worktree-setup tests. The session
readiness regression creates a real temporary Git-linked child, runs the exact
Codex environment bridge, and confirms `usable-stale` Graphify admission.
A stale-parent reproduction also reaches `usable-stale` after the upstream
no-LLM update, with matching child graph provenance and only semantic sources
pending.

## Canonical Owner Impact
Updated the Graphify setup, admission, and seed owners plus their tests and the
ARIA Graphify boundary guidance. No upstream Graphify bundle files changed.
