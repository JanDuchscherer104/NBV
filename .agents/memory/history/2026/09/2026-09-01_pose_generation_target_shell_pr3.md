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
repo_head: 66327831ac4d341174da2aa89f0f6c973ab29feb
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
- The repaired opt-in profile keeps the 60-row budget while assigning 12 target-shell centers two gaze variants: forward-rig and target-point. Its 2.25–3.10 m standoff range is feasible for the observed 2.693 m actor-target distance and the active 1 m step limit.
- The matched CUDA tracer on ASE scene 81283 used the same V0 GT OBB, seed 73, active admission rules, PyTorch3D renderer, scorer, and RTX 3080 Ti for baseline and challenger. The baseline admitted 21/60 rows. The challenger admitted 29/60 rows, including 8/24 target-shell gaze rows, while its unchanged 24-row `forward_local` shell and validity mask remained bit-identical to the baseline.
- Best target-RRI was `1.7664426650298992e-6` for the baseline and `1.673471501817403e-6` for the challenger; both best/selected rows remained `forward_local`. This single target establishes feasible additional support, not a quality gain, so the family remains opt-in pending broader evidence. The complete receipt is `.agents/work/pose-generation-revision/09--target-shell-matched-receipt--09-01.json`.

## Commits
- [d0299d049f](https://github.com/JanDuchscherer104/ARIA-NBV/commit/d0299d049f) — opt-in target-shell support.
- [6aa8b7f03a](https://github.com/JanDuchscherer104/ARIA-NBV/commit/6aa8b7f03a) — shared support geometry and review remediation.
- [c7f25dd93d](https://github.com/JanDuchscherer104/ARIA-NBV/commit/c7f25dd93d) — target-dependency and finite-support repairs.
- [66327831ac](https://github.com/JanDuchscherer104/ARIA-NBV/commit/66327831ac) — feasible matched-tracer profile and evidence.

## Verification
- Ruff format/check: pass.
- Focused pose-generation, plotting, read-model, benchmark, and campaign-projection suite: 135 passed.
- Real ASE/ATEK integration with explicit repository data root passed on CPU and CUDA, including deterministic 60-row output, nonzero target-shell admission, and bit-identical unchanged forward support.
- Focused mypy for the new config and sampler owners: pass; broader touched-module mypy retains pre-existing errors outside the new target-shell branch.

## Canonical Owner Impact
The listed Python/configuration owners now define the opt-in target-shell behavior. No further canonical update is required by this workpackage.
