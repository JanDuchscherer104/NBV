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
graph, rebuild only the local projection when needed, and admit bounded pending
semantic state as `usable-stale`. Kept AST/code drift and malformed or
unbounded state unusable.

## Findings
`graphify-out/needs_update` is an upstream semantic-refresh signal, not a
reason to prevent a new Codex task from starting. The active Codex task is the
host that can follow Graphify's agent-based semantic extraction route; a shell
setup script cannot invoke that session capability.

The setup owner now preserves and copies the marker, validates `--usable` after
deterministic preparation, and does not run `graphify extract` during worktree
creation. Focused regressions prove an actual temporary linked worktree starts
with a locally copied graph and reports `usable-stale` for the marker.

## Commits
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/f65990a06da09e57624fedef2dc8b83603ab32b0

## Verification
Passed the Graphify projection, freshness, seeding, reconciler, session
readiness, upstream command/skill, and shell worktree-setup tests. The session
readiness regression creates a real temporary Git-linked child, runs the exact
Codex environment bridge, and confirms `usable-stale` Graphify admission.

## Canonical Owner Impact
Updated the Graphify setup, admission, and seed owners plus their tests and the
ARIA Graphify boundary guidance. No upstream Graphify bundle files changed.
