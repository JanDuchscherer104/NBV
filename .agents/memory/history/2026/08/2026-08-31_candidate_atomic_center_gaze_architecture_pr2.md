---
id: 2026-08-31_candidate_atomic_center_gaze_architecture_pr2
date: 2026-08-31
title: "Candidate atomic center gaze architecture PR2"
status: done
topics: [candidate-generation, architecture, center-gaze, parity, cuda]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/pose_generation
  - aria_nbv/tests/pose_generation/test_candidate_interface.py
codex_thread: codex://threads/01a05903-535c-7c21-8ae7-e7c17079427c
repo_object_format: sha1
repo_head: 5ed0ba044d5d0c6143d6d5bf27e086e5f1cede5b
repo_branch: "codex/candidate-center-gaze-pr2"
worktree_kind: linked
---

## Task
Implement Architecture PR 2 as a behavior-preserving split of candidate-center
sampling, gaze assignment, and per-variant admission behind the final PR 1
interface.

## Method
Introduced private atomic center and gaze batches, adapted the shipped numerical
kernels to private fact protocols, and compared the new interpreter with the
legacy generator across active profiles, direct and rollout seeds, target orbit,
uncapped spherical jitter, stores, and two real CUDA scenes.

## Findings
- `aria_nbv/aria_nbv/pose_generation/_candidate_centers.py` samples one center
  table per semantic group.
- `aria_nbv/aria_nbv/pose_generation/_candidate_gaze.py` assigns each ordered
  gaze variant to the exact same center tensor without resampling.
- `aria_nbv/aria_nbv/pose_generation/program_generator.py` retains one RNG
  context for primary center plus gaze, derives only paired-gaze substreams,
  and runs admission independently for each gaze variant while reusing the
  composition-owned prepared query.
- The PR 1 `CandidateProgram`, request, result, facade, hash, row order, seeds,
  rule evidence, legacy projection, nonzero 60/30 seminar jitter, and zero-cap
  uncapped-spherical semantics remain unchanged.

## Commits
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/5ed0ba044d5d0c6143d6d5bf27e086e5f1cede5b

## Verification
- Pose-generation suite: 123 passed, 1 skipped.
- Rollout suite: 516 passed; the two linked-worktree data-resolution cases
  passed separately after supplying the existing local data and EFM3D roots.
- Candidate interface plus rollout/store integration: 95 passed.
- Package-config mypy for the new atomic modules and interpreter, public typing
  contract, and full Ruff format/lint: passed.
- RTX 3080 Ti, CUDA 12.1, Torch 2.4.1, scenes 81283 and 81807: exact
  shell/view/mask equality, five cold starts and five 30-call warm batches,
  one center call per group, zero warm prepared-query acquisition, and no
  host/device transfer increase. Warm p50 ratios were 0.953 and 0.969 versus
  the legacy generator; all benchmark gates passed.
- Independent exact-diff architecture review reported no actionable P0-P2
  findings after orbit, zero-cap jitter, and post-call RNG-state regressions.

## Canonical Owner Impact
Current truth is updated in the Python and test owners listed above. No further
canonical updates are required for Architecture PR 2; production replay remains
on the legacy facade until the planned PR 6 composition migration.
