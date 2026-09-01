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
Added one discriminated center config and one private positional-sampling branch, retained existing gaze/admission/result seams, and verified geometry with synthetic and real ASE data on CPU and CUDA. Review remediation replaced conditional support fields with a nested discriminated support union and moved sampling/plot boundaries to one shared Torch geometry owner.

## Findings
- `pose_generation/config.py` now owns angular-box and actor-facing-cap variants whose serialized identities contain only active fields; upper support is an angular box with nonnegative elevation bounds.
- `pose_generation/positional_sampling.py` samples uniform radius and uniform solid angle without rejection.
- `pose_generation/plotting.py` exposes only rows carrying canonical target-shell position provenance, plus attempted validity, configured support, gaze rays, component identity, seed, and counts.
- The opt-in TOML replaces no production default and retains the 60/30-degree seminar jitter invariant.
- The matched CUDA tracer on ASE scene 81283 used the same V0 GT OBB, seed 73, 60-row budget, active admission rules, PyTorch3D renderer, scorer, and RTX 3080 Ti for baseline and challenger. Both yielded 21 valid rows; best target-RRI was `1.5805e-6` for the baseline and `1.2086e-6` for the challenger, with both best/selected rows from `forward_local`. This single target therefore does not establish a target-shell quality gain; the family remains opt-in pending broader evidence. The complete receipt is `.agents/work/pose-generation-revision/09--target-shell-matched-receipt--09-01.json`.

## Commits
- [3a9e046c66e21a1d1d53283d999f17382820856a](https://github.com/JanDuchscherer104/ARIA-NBV/commit/3a9e046c66e21a1d1d53283d999f17382820856a)
- [a55573cdc389cc8c4eb0aa7160d79336964c4529](https://github.com/JanDuchscherer104/ARIA-NBV/commit/a55573cdc389cc8c4eb0aa7160d79336964c4529)
- [d8193a2740ebf93b73754c0c179f84a0599013a1](https://github.com/JanDuchscherer104/ARIA-NBV/commit/d8193a2740ebf93b73754c0c179f84a0599013a1)

## Verification
- Ruff format/check: pass.
- Focused pose-generation, plotting, read-model, and campaign-projection suite: 114 passed, 1 skipped.
- Real ASE/ATEK integration with explicit repository data root: 3 passed on CPU and CUDA.
- Focused mypy for the new config and sampler owners: pass; broader touched-module mypy retains pre-existing errors outside the new target-shell branch.

## Canonical Owner Impact
The listed Python/configuration owners now define the opt-in target-shell behavior. No further canonical update is required by this workpackage.
