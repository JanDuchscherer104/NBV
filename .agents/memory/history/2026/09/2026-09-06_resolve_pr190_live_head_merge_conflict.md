---
id: 2026-09-06_resolve_pr190_live_head_merge_conflict
date: 2026-09-06
title: "Resolve PR190 live-head merge conflict"
status: done
topics: [pr190, merge-conflict, typst, verification]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - docs/typst/thesis/sections/04-method/index.typ
  - scripts/tests/test_typst_authoring_hygiene.py
codex_thread: codex://threads/01a077ef-87c9-7f13-a281-4336f2dc3d02
repo_object_format: sha1
repo_head: ca55089d71f0bc86fcadef38334f7a15a4c58722
repo_branch: "codex/pr190-merge-resolution-live"
worktree_kind: linked
---

## Task
Resolve the live PR #190 head against current `main` without rewriting the remote branch.

## Method
Fetched the PR ref, reproduced its merge with current `main` in a dedicated
linked worktree, and selected the newer `main` Method opening for the sole
overlapping source hunk. Rebuilt notation projections and recalibrated the
table-inventory assertion to the merged active source set.

## Findings
The live PR head `b420d20` has one textual conflict in the Method opening.
Current `main` provides the newer model-first reader orientation and unchanged
section include graph. The merged active thesis has 33 publication tables,
which is now asserted by the Typst hygiene test.

## Commits
- [ca55089d71f0bc86fcadef38334f7a15a4c58722](https://github.com/JanDuchscherer104/ARIA-NBV/commit/ca55089d71f0bc86fcadef38334f7a15a4c58722) — merge current `main` into the live PR branch and resolve the Method conflict.

## Verification
Passed `make glossary`, `python -m unittest scripts.tests.test_typst_authoring_hygiene`, `make typst-authoring-contract`, `make thesis-marker-contract`, and `make thesis-pdf-ci`. Rendered Method pages 47--49 from the CI PDF had no clipped equations, overlaps, or malformed table/status layouts. The linked worktree used the established shared ARIA Python interpreter because it has no local virtual environment.

## Canonical Owner Impact
`docs/typst/thesis/sections/04-method/index.typ` remains the canonical Method opening; `scripts/tests/test_typst_authoring_hygiene.py` owns the active table-inventory assertion.
