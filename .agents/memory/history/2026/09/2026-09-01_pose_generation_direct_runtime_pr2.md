---
id: 2026-09-01_pose_generation_direct_runtime_pr2
date: 2026-09-01
title: "Pose Generation Direct Runtime PR2"
status: done
topics: [pose-generation, deep-module, runtime, seeding]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/pose_generation/candidate_generation.py
  - aria_nbv/aria_nbv/pose_generation/candidate_mixture.py
  - aria_nbv/aria_nbv/pose_generation/positional_sampling.py
  - aria_nbv/aria_nbv/pose_generation/orientations.py
  - aria_nbv/aria_nbv/utils/seeding.py
codex_thread: codex://threads/01a04842-7454-7353-9a6b-f59cc99302b5
repo_object_format: sha1
repo_head: 2b1856a5fcbd3494d09d542ea26abccf87122573
repo_branch: "codex/pose-generation-runtime-pr2"
worktree_kind: linked
---

## Task
Implement PR2 of the config-first pose-generation plan by consuming nested center and gaze configs directly without changing public generation behavior.

## Method
Narrowed helper inputs, prebuilt immutable mixture leaf runtimes, moved request-specific target/query facts into private call channels, extracted the stable seed primitive, and independently reviewed the stacked diff.

## Findings
`PositionSampler` now owns only a center config and device; `OrientationBuilder` owns only a gaze config and verbosity. `CandidateMixtureViewGenerator` constructs children once and reuses them without retaining request targets or mesh queries. The legacy public generator preserves independent position and gaze target channels, while mixed generation supplies one request-local target to both. The transitional `_legacy_leaf_config` and pose-to-rollout dependency were deleted.

## Commits
- [2b1856a5fcbd3494d09d542ea26abccf87122573](https://github.com/JanDuchscherer104/ARIA-NBV/commit/2b1856a5fcbd3494d09d542ea26abccf87122573)

## Verification
The stacked focused suite passed with 185 passed and 1 skipped, including exact active-profile full-rule fingerprints. Ruff format/check, compileall, focused mypy for the shared seed owner and rollout wrapper, and `git diff --check` passed. Independent review approved with no findings after a regression for separate legacy position/gaze targets was repaired.

## Canonical Owner Impact
The pose-generation runtime now consumes PR1's nested authoring values directly. Admission, result, persistence, plotting, app, and rollout-selection ownership remain unchanged.
