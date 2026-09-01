---
id: 2026-09-01_pose_generation_target_shell_pr3
date: 2026-09-01
title: "Pose generation target shell PR3"
status: done
topics: [pose-generation, target-shell, candidate-sampling, cuda]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/pose_generation/config.py
  - aria_nbv/aria_nbv/pose_generation/positional_sampling.py
  - aria_nbv/aria_nbv/pose_generation/candidate_mixture.py
  - aria_nbv/aria_nbv/pose_generation/types.py
  - aria_nbv/aria_nbv/pose_generation/plotting.py
  - .configs/build_rollouts_v3_target_shell_experiment.toml
codex_thread: codex://threads/01a04842-7454-7353-9a6b-f59cc99302b5
repo_object_format: sha1
repo_head: 3a9e046c66e21a1d1d53283d999f17382820856a
repo_branch: "codex/pose-generation-target-shell-pr3"
worktree_kind: linked
---

## Task
Implement the plan's opt-in PR3 target-centric shell family on top of the unmerged PR2 branch.

## Method
Added one discriminated center config and one private positional-sampling branch, retained existing gaze/admission/result seams, and verified geometry with synthetic and real ASE data on CPU and CUDA.

## Findings
- `pose_generation/config.py` now owns angular-box, upper-angular-box, and actor-facing-cap shell support.
- `pose_generation/positional_sampling.py` samples uniform radius and uniform solid angle without rejection.
- `pose_generation/plotting.py` exposes attempted validity, configured support, gaze rays, component identity, seed, and counts.
- The opt-in TOML replaces no production default and retains the 60/30-degree seminar jitter invariant.
- ASE scene 81283 produced repeatable CPU/CUDA candidate tables within each backend; CUDA generated 396 valid rows from 512 attempts for the matched cap experiment.

## Commits
- [3a9e046c66e21a1d1d53283d999f17382820856a](https://github.com/JanDuchscherer104/ARIA-NBV/commit/3a9e046c66e21a1d1d53283d999f17382820856a)

## Verification
- Ruff format/check: pass.
- Focused pose-generation, plotting, and read-model suite: 109 passed, 1 skipped.
- Real ASE/ATEK integration with explicit repository data root: 3 passed on CPU and CUDA.
- Focused mypy for the new config and sampler owners: pass; broader touched-module mypy retains pre-existing errors outside the new target-shell branch.

## Canonical Owner Impact
The listed Python/configuration owners now define the opt-in target-shell behavior. No further canonical update is required by this workpackage.
