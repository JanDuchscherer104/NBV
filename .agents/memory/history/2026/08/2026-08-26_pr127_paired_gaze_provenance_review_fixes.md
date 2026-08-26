---
id: 2026-08-26_pr127_paired_gaze_provenance_review_fixes
date: 2026-08-26
title: "PR127 paired gaze provenance review fixes"
status: done
topics: [candidate-generation, paired-gaze, zarr, replay, streamlit]
confidence: high
canonical_updates_needed:
  - aria_nbv/aria_nbv/pose_generation/types.py
  - aria_nbv/aria_nbv/pose_generation/candidate_mixture.py
  - aria_nbv/aria_nbv/pose_generation/plotting.py
  - aria_nbv/aria_nbv/rollouts/zarr_store.py
touched_owner_paths:
  - aria_nbv/aria_nbv/pose_generation/types.py
  - aria_nbv/aria_nbv/pose_generation/candidate_mixture.py
  - aria_nbv/aria_nbv/pose_generation/plotting.py
  - aria_nbv/aria_nbv/rollouts/zarr_store.py
  - aria_nbv/tests/pose_generation/test_candidate_mixture.py
  - aria_nbv/tests/pose_generation/test_plotting_helpers.py
  - aria_nbv/tests/rollouts/test_zarr_store.py
codex_thread: codex://threads/01a03a5c-ff92-7e03-8cd3-fde05269a56f
repo_object_format: sha1
repo_head: c8ab0e41489961e9b871e7ca7a820051da1effff
repo_branch: "codex/g002-pr127-impl"
worktree_kind: linked
---

## Task
Rebased the PR127 paired-center gaze implementation onto live ``origin/main``
and repaired all four review findings without changing production mixture
configuration or seminar jitter behavior.

## Method
Used a dedicated linked worktree, rebased onto ``origin/main`` (already
containing PR126), and retained the paired-gaze commits. Stable mixture IDs
now use original serialized component indices for both variants. Pair and
gaze-variant provenance is typed on ``CandidateSamplingResult``, mirrored to
legacy extras aliases, and persisted as candidate-table Zarr columns with
``-1`` sentinels. Paired seeds derive from the resolved primary component seed
for both explicit replay and base-config direct generation. The public paired
gaze plot returns an annotated empty figure for all-sentinel inputs.

## Findings
``candidate_mixture.py`` preserves decoder-compatible component IDs and
resolves paired seed lineage. ``types.py`` adds typed aligned provenance.
``zarr_store.py`` persists pair and variant IDs, reads old stores with virtual
sentinel arrays, and rejects unsupported or uncoupled provenance. ``plotting.py``
handles legacy and typed provenance and no-pair tables. Regression coverage
includes component decode alignment, direct/replay seed derivation, typed pair
provenance, all-sentinel plotting, legacy Zarr reads, malformed provenance,
and Zarr round-trip persistence.

## Commits
- [4c6bca860c027c6f55743db107cb6b6b60444eb5](https://github.com/JanDuchscherer104/ARIA-NBV/commit/4c6bca860c027c6f55743db107cb6b6b60444eb5) — paired provenance contract after rebase
- [5d5111ebcacabc2eee995416793482e8bd44cf29](https://github.com/JanDuchscherer104/ARIA-NBV/commit/5d5111ebcacabc2eee995416793482e8bd44cf29) — legacy Zarr compatibility and validation
- [c8ab0e41489961e9b871e7ca7a820051da1effff](https://github.com/JanDuchscherer104/ARIA-NBV/commit/c8ab0e41489961e9b871e7ca7a820051da1effff) — exact-source replay golden identity refresh

## Candidate Owner Intent
<!-- Omit this section unless the agent-behavior candidate-intent branch applies. -->
- Statement: <precise reusable preference>
- Evidence: <direct instruction or bounded recurring evidence>
- Scope and target owner: <scope and exact owner path>
- Status: proposed for current-user review

## Verification
``uv run ruff format`` and ``uv run ruff check`` passed for all seven changed
owners/tests. Focused pose-generation, plotting, and Zarr tests passed:
68 passed. Replay tests passed: 38 passed. ``make check-agent-memory`` and
``git diff --check`` passed. External publication, PR comments,
thread resolution, and merge remain coordinator-owned; this lane did not push.

## Canonical Owner Impact
Updated Python pose-generation and rollout-Zarr owners plus their focused
regression tests. No Typst or Chapter 2 files were touched.
