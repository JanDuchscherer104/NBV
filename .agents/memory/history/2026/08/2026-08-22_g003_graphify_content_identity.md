---
id: 2026-08-22_g003_graphify_content_identity
date: 2026-08-22
title: "G003 Graphify content identity"
status: done
topics: [graphify, freshness, projection]
confidence: high
canonical_updates_needed: []
codex_thread: codex://threads/019fff4c-cc77-7351-bb81-9759852617c6
repo_object_format: sha1
repo_head: 7ee7ec7e7a5f89e2e74d346d48aa3de75d7da98f
repo_branch: codex/graphify-content-identity
worktree_kind: linked
---

## Task
Implement Ultragoal G003 so Graphify freshness survives corpus-preserving
rebases and worktrees while remaining fail-closed for tree, artifact, owner,
manifest, and detector drift.

## Method
Inspected the nearest ARIA owners and Graphify boundary while keeping the
existing freshness result/CLI seam. Added deterministic `source_tree` metadata,
canonical commit/tree validation, corpus-preserving admission, pinned-detector
checks for the worktree and immutable HEAD snapshot, exact missing-object
repair, and focused hermetic regressions without rebuilding live artifacts. The
seeder anchors marker validation to the independently discovered CLI shebang
and validates source/destination graph revisions as canonical commit objects.

## Findings
The builder emits `source_tree` beside `source_revision`. The checker admits
non-ancestors only through full-tree equality or detector-proven corpus
equality, preserving owner, detector, artifact, and state fail-closed checks.
The boundary documents immutable-snapshot and trusted-interpreter contracts;
tests cover rebases, ignored and committed drift, canonical identities,
malicious markers, zero-delta freshness, builder output, and seeder provenance.

## Verification
Focused Graphify pytest passed 94 tests with 60 subtests in the linked venv;
the four direct unittest entrypoints also passed 94 tests. Targeted Ruff and
implementation mypy passed; the projection live check validated 511 Markdown
files, scaffold audit reported 12 skills with 0 errors/warnings, agent-memory
validation and CI-impact self-test passed, and compilation/diff checks passed.
Live freshness remained `unusable` with 12 stale sources and the exact
projection-first action; no graph, Git, or worktree state was updated.

## Canonical Owner Impact
Updated Python/test owners, the Graphify worktree seeder trust seam, and the
ARIA Graphify boundary reference only; no Typst, configuration, or live
Graphify state was changed.
