---
id: 2026-08-26_vectorize_root_relative_rollout_candidate_projection
date: 2026-08-26
title: "Vectorize root-relative rollout candidate projection"
status: done
topics: [rollouts, inspection, performance]
confidence: high
canonical_updates_needed:
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/aria_nbv/rollouts/read_model.py
  - aria_nbv/tests/rollouts/test_inspection.py
touched_owner_paths:
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/aria_nbv/rollouts/read_model.py
  - aria_nbv/tests/rollouts/test_inspection.py
codex_thread: codex://threads/01a03eda-0ffb-78a3-b1f7-4a6549bbd0bd
repo_object_format: sha1
repo_head: 3bff47c8f40889c6df33f53f4b75a1a507057059
repo_branch: "codex/rollout-root-relative-vectorization"
worktree_kind: linked
---

## Task
Reduce unnecessary stored-candidate materialization in the root-relative
geometry projection without changing its scientific rows, filters, or order.

## Method
Reuse the reader-local shell-order index to gather only the candidate columns
needed by the root-relative projection, vectorize center offsets and distances,
and retain the legacy scalar row order when emitting dictionaries.

## Findings
`root_relative_candidate_rows` no longer constructs complete `StoredStep`
payloads (including unused labels and diagnostics) for every step. Candidate
mixture-name decoding is factored at the typed read-model boundary so both
projections retain identical manifest-derived names. The regression compares
the new rows against the former scalar traversal for all rows, the actor-valid
filter, and a step filter, while failing if the optimized path materializes a
`StoredStep` payload.

## Commits
- [e823e424464f228bbf8a7c83b4561e13b4810ff7](https://github.com/JanDuchscherer104/ARIA-NBV/commit/e823e424464f228bbf8a7c83b4561e13b4810ff7)
- [d7b5fc40bf1b24f40c977993f47bfd6d32463a5d](https://github.com/JanDuchscherer104/ARIA-NBV/commit/d7b5fc40bf1b24f40c977993f47bfd6d32463a5d)

## Verification
Passed `ruff format` and `ruff check` on the three touched files. Passed
`pytest -q tests/rollouts/test_inspection.py -k root_relative_candidate_rows`
(2 tests). The adjacent combined inspection/read-model suite was started with
a repository-scoped temporary directory because `/tmp` is quota constrained;
its completion output was not captured before the command runner detached.

## Canonical Owner Impact
The persisted rollout inspection and typed read-model owners now share the
same mixture-name decoding rule. No generation, rollout-store schema, or
scientific coordinate convention changed.
