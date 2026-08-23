---
id: 2026-08-23_thesis_release_ci_portability_closure
date: 2026-08-23
title: "Thesis release CI portability closure"
status: done
topics: [thesis, release, ci, typst, reproducibility]
confidence: high
canonical_updates_needed:
  - Makefile
touched_owner_paths:
  - Makefile
codex_thread: codex://threads/01a02ab6-c75e-7313-be12-e5f90ae0cde3
repo_object_format: sha1
repo_head: bc27949a79a225da54f60081aaa7ae657c8e450c
repo_branch: "codex/thesis-authoring-release-closure"
worktree_kind: linked
---

## Task
Publish the thesis-authoring release branch through a mergeable pull request and
repair exact-head hosted CI without weakening the locked final-release audit.

## Method
Inspected the exact failed GitHub Actions steps, restored the upstream writing
reference required by the scaffold governance contract, and separated portable
release behavior tests from the environment-locked release audit. The scaffold
repair is commit [bc27949a79](https://github.com/JanDuchscherer104/ARIA-NBV/commit/bc27949a79a225da54f60081aaa7ae657c8e450c).
The portable release-gate correction and this debrief are commit
[9c50a326ae](https://github.com/JanDuchscherer104/ARIA-NBV/commit/9c50a326ae4439fff4d5d6c7d110a6b42b3126ba).

## Findings
Hosted Ubuntu CI cannot satisfy `docs/typst/thesis/toolchain-lock.json` merely by
installing Poppler: the lock intentionally records the exact local `pdftoppm`
version and binary hash. `Makefile` now gives hosted `docs-render-core` the
portable `thesis-release-contract` target, while `thesis-release-audit` remains
the explicit final-release gate in the exact locked environment. The portable
target also removes inherited Git repository-selection variables before pytest,
so fixture repositories remain isolated when the target runs from pre-push.

## Verification
- `make thesis-release-contract ci-impact-self-test`: 55 release tests and 14 CI
  impact tests passed.
- The exact hosted documentation command (`make qmd-frontmatter-check
  api-docs-self-test docs-render-core`) passed locally.
- `make thesis-release-audit` passed independently with the locked comparator;
  submission remains externally blocked as recorded in the release ledger.
- The release-contract suite passed with `GIT_DIR`, `GIT_WORK_TREE`,
  `GIT_COMMON_DIR`, and `GIT_INDEX_FILE` deliberately set to the linked
  worktree, proving the target sanitizes hook-owned Git context.
- Graphify was incrementally refreshed after regenerating the branch projection:
  7,465 nodes and 15,464 edges, zero missing or dangling endpoints, self-loops,
  or duplicate edges, and both freshness/state gates reported `fresh`.

## Canonical Owner Impact
`Makefile` now owns the distinction between portable hosted release-contract
verification and the environment-locked final release audit. No scientific
claim, thesis source, report schema, or toolchain-lock identity changed.
