---
id: 2026-08-25_graphify_parent_inherited_session_readiness
date: 2026-08-25
title: "Graphify parent-inherited session readiness"
status: done
topics:
  - graphify
  - worktrees
  - developer-environment
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - .agents/skills/aria-nbv-context/references/graphify-aria-boundary.md
  - scripts/graphify_worktree_seed.py
  - scripts/reconcile_graphify_worktree.py
  - scripts/setup_worktree_env.sh
  - scripts/tests/test_graphify_session_readiness.py
codex_thread: codex://threads/01a038aa-8929-7621-9832-0e7f9aea953f
repo_object_format: sha1
repo_head: 7ba6faad3e1214a5c22dd55d1bbbf1211a5350df
repo_branch: "codex/graphify-parent-session-readiness"
worktree_kind: linked
---

## Task
Make every Codex-created linked worktree inherit its actual parent Graphify
generation and admit the session only when that child graph is query-usable.

## Method
Required the Codex-provided parent, copied only local graph artifacts, linked
the parent's resolved content-addressed semantic caches, and ran upstream's
no-LLM incremental update followed by the existing usable-state checker.

## Findings
The seed sentinel now binds both inherited cache targets. Setup no longer
guesses a sibling parent, and its incremental reconciliation retains the
inherited semantic projection so commit-provenance rewrites cannot make the
entire semantic corpus stale during bootstrap.

## Commits
- [7ba6faad3e1214a5c22dd55d1bbbf1211a5350df](https://github.com/JanDuchscherer104/ARIA-NBV/commit/7ba6faad3e1214a5c22dd55d1bbbf1211a5350df)

## Verification
Passed the focused seed, freshness, upstream-skill, setup, reconciler, and
new linked-worktree session-readiness tests; the latter invokes real setup,
the pinned upstream CLI, and `check_graphify_freshness.py --usable`.

## Canonical Owner Impact
Updated the ARIA Graphify boundary guidance and the setup, seed, reconciliation,
and focused test owners listed in the front matter.
