---
id: 2026-08-22_avoid_lfs_filters_in_graphify_head_snapshots
date: 2026-08-22
title: "Avoid LFS filters in Graphify HEAD snapshots"
status: done
topics: [graphify, git, lfs, validation]
confidence: high
canonical_updates_needed: []
codex_thread: codex://threads/01a02a37-03a9-7402-b176-6554619a99e7
repo_object_format: sha1
repo_head: 34eb748a1af1e1ab4665592dffe768cc702ab98c
repo_branch: codex/graphify-content-identity
worktree_kind: linked
---

## Task
Resolve PR #99's open review finding: a HEAD snapshot must not trigger LFS smudge filters.

## Method
Replaced `git archive` materialization with `git ls-tree` plus `git cat-file blob`, which reads raw Git object bytes. Non-regular Git entries are omitted because Graphify does not follow them.

## Findings
`scripts/check_graphify_freshness.py` now constructs the detector snapshot from raw blobs, so ignored LFS assets remain pointers and no LFS download is requested. `scripts/tests/test_graphify_freshness.py` covers a configured smudge filter and a tracked symlink.

## Verification
`uv run --extra dev python ../scripts/tests/test_graphify_freshness.py` passed 25 tests. Targeted Ruff E/F and Python compilation passed. The live checker reached the pre-existing non-ancestor corpus result without snapshot-materialization failure.

## Canonical Owner Impact
Python and test owners were updated: `scripts/check_graphify_freshness.py` and `scripts/tests/test_graphify_freshness.py`.
