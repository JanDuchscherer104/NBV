---
id: 2026-08-30_training_dataset_evidence_and_promotion_trust
date: 2026-08-30
title: "Training Dataset Evidence And Promotion Trust"
status: done
topics: [streamlit, dataset, promotion, io, testing]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts/session.py
  - aria_nbv/aria_nbv/app/panels/training_dataset.py
  - aria_nbv/aria_nbv/dataset_bundle.py
  - aria_nbv/aria_nbv/oracle/pipelines/shard_promotion.py
  - aria_nbv/aria_nbv/oracle/pipelines/shards.py
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py
  - aria_nbv/tests/app/panels/test_training_dataset_panel.py
  - aria_nbv/tests/oracle/pipelines/test_shard_promotion.py
  - aria_nbv/tests/rollouts/test_dataset_writer.py
  - aria_nbv/tests/rollouts/test_inspection.py
  - aria_nbv/tests/test_dataset_bundle.py
codex_thread: codex://threads/01a033b8-ed20-76a0-9627-2679b556cbff
repo_object_format: sha1
repo_head: 1ee4b00af1a5f99bba41d6a934c4aaf3c91eab8a
repo_branch: "detached"
worktree_kind: linked
---

## Task
Capture the completed G002 training-dataset evidence and promotion-trust implementation as a reusable, auditable debrief.

## Method
Recorded the implementation range `f9a171da497f76983f4e0e23398cc8ba6a268337..1ee4b00af1a5f99bba41d6a934c4aaf3c91eab8a`, its exact changed truth owners, and immutable implementation commits; regenerated the derived debrief index and checked the memory contract.

## Findings
The Streamlit dataset path now guards cache-hit bodies, performs semantic special-file reads, and fingerprints symlink targets rather than link text. Dataset admission keeps canonical promotion-marker ownership, removes arbitrary size caps from valid production metadata, retains bounded caps only for tiny promotion and identity sidecars, and advertises typed shards. The owner writer no longer duplicates the potentially unbounded shard-row manifest in `_owner.json`; the rollout-store manifest remains its canonical owner. Acquisition presents concise expected errors while retaining diagnostics for unexpected exceptions. Promotion trust is established before array access, and broken marker aliases are classified as invalid rather than trusted. The changed Python sources and tests are the current truth owners.

## Commits
- [4e0a5f99f76dc5bd03f95eb1f203ba636864047f](https://github.com/JanDuchscherer104/ARIA-NBV/commit/4e0a5f99f76dc5bd03f95eb1f203ba636864047f)
- [4a4b2fdf46ddd3ba272d4981524b1ce5f2905b64](https://github.com/JanDuchscherer104/ARIA-NBV/commit/4a4b2fdf46ddd3ba272d4981524b1ce5f2905b64)
- [a593dee465fcbdb6549784187f72857847e26ee7](https://github.com/JanDuchscherer104/ARIA-NBV/commit/a593dee465fcbdb6549784187f72857847e26ee7)
- [d33050f633ecf156e9cad41099fd3bd841dacba1](https://github.com/JanDuchscherer104/ARIA-NBV/commit/d33050f633ecf156e9cad41099fd3bd841dacba1)
- [a00b3136090117c4c8d8315523d2f7127135c350](https://github.com/JanDuchscherer104/ARIA-NBV/commit/a00b3136090117c4c8d8315523d2f7127135c350)
- [b67706dd356ced07816b5a39407e511f0e297551](https://github.com/JanDuchscherer104/ARIA-NBV/commit/b67706dd356ced07816b5a39407e511f0e297551)
- [e98f24fc1c7337b93e21c72cb988b672bb2b8081](https://github.com/JanDuchscherer104/ARIA-NBV/commit/e98f24fc1c7337b93e21c72cb988b672bb2b8081)
- [4c6f323cd9f690cd281e78620c3e340fffde89e5](https://github.com/JanDuchscherer104/ARIA-NBV/commit/4c6f323cd9f690cd281e78620c3e340fffde89e5)
- [1ee4b00af1a5f99bba41d6a934c4aaf3c91eab8a](https://github.com/JanDuchscherer104/ARIA-NBV/commit/1ee4b00af1a5f99bba41d6a934c4aaf3c91eab8a)
- [71c3a581772b0d2b94f6e85a8040bc036eb30726](https://github.com/JanDuchscherer104/ARIA-NBV/commit/71c3a581772b0d2b94f6e85a8040bc036eb30726)

## Verification
- PASS — `git diff --name-only f9a171da497f76983f4e0e23398cc8ba6a268337..1ee4b00af1a5f99bba41d6a934c4aaf3c91eab8a` returned the twelve listed owner paths.
- PASS — all nine implementation SHAs resolve locally as commits in that range.
- PASS — `make PYTHON_INTERPRETER=/home/jd/repos/ARIA-NBV/aria_nbv/.venv/bin/python debrief-index` regenerated the derived index.
- PASS — `make PYTHON_INTERPRETER=/home/jd/repos/ARIA-NBV/aria_nbv/.venv/bin/python check-agent-memory` validated the debrief and index.
- PASS — the focused G002 suite completed with 314 tests passed and 40 warnings.
- PASS — Ruff format and lint checks passed for all twelve changed Python files.
- BASELINE GAP — repository-config mypy still reports its pre-existing aggregate errors; the changed `shards.py` source has zero diagnostics.

## Canonical Owner Impact
No further canonical updates are needed: the changed Python and test files above are current truth owners.
