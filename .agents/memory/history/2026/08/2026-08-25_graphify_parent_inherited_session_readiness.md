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
  - scripts/check_graphify_freshness.py
  - scripts/graphify_worktree_seed.py
  - scripts/reconcile_graphify_worktree.py
  - scripts/setup_codex_worktree_env.sh
  - scripts/setup_worktree_env.sh
  - scripts/tests/test_graphify_freshness.py
  - scripts/tests/test_reconcile_graphify_worktree.py
  - scripts/tests/test_graphify_session_readiness.py
  - scripts/tests/test_setup_worktree_env.sh
codex_thread: codex://threads/01a038aa-8929-7621-9832-0e7f9aea953f
repo_object_format: sha1
repo_head: 00d4f91787cc5ef57009e440041e6749dca52d13
repo_branch: "codex/graphify-parent-session-readiness"
worktree_kind: linked
---

## Task
Make Codex-created linked worktrees inherit Graphify state only from a valid,
query-admissible parent, without treating inherited semantic artifacts as proof
of current freshness.

## Method
The Codex bridge resolves either the explicit fork parent or Git's canonical
primary checkout. Before it runs a parent executable or changes the child,
setup proves both paths are registered worktrees in the same Git common
directory and checks the selected source with the repository-owned usable gate.
The former reconciliation receipt bypass was removed because its counts and
input hashes did not prove semantic graph content. Reconciliation preserves
semantic item counts across an upstream incremental update and restores the
projection and Graphify output after an ordinary failure.

## Findings
The selected parent's content-addressed semantic and semantic-deep caches remain
the only shared Graphify state; generated projection, graph, manifest, and run
state stay child-local. Setup never invokes a foreign or Graphify-unusable
parent runtime. It fails before child seeding when the source gate is unusable;
it does not manufacture freshness from a receipt, matching counts, or matching
Git revisions.

## Commits
- [c9676277eb01c95ef9029d6ac27015a7abe2999e](https://github.com/JanDuchscherer104/ARIA-NBV/commit/c9676277eb01c95ef9029d6ac27015a7abe2999e)
- [00d4f91787cc5ef57009e440041e6749dca52d13](https://github.com/JanDuchscherer104/ARIA-NBV/commit/00d4f91787cc5ef57009e440041e6749dca52d13)

## Verification
Passed `bash scripts/tests/test_setup_worktree_env.sh`, the focused freshness,
session-readiness, reconciler, seed, upstream-skill, and CI-impact tests, plus
shell syntax, Ruff, and diff checks. A real disposable worktree executed the
exact empty-source Codex bridge and correctly failed before creating
`graphify-out`, `graphify-input`, or a child venv: the canonical parent
`/home/jd/repos/ARIA-NBV` is currently Graphify-unusable because its detector
reports an unbounded stale-source set (alongside local projection-owner drift).
An externally completed, verified semantic refresh of that parent remains the
prerequisite for an admitted parentless session.

## Canonical Owner Impact
Updated the ARIA Graphify boundary guidance, setup, freshness, reconciliation,
and focused test owners listed in the front matter. The earlier receipt-based
admission evidence and its reported retained semantic counts are superseded and
must not be used as final readiness evidence.
