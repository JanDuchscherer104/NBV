# ARIA-NBV Package Boundary Cleanup Context

Timestamp: 2026-07-02T16:20:44Z

Task: run autoresearch plus ralplan for `improve-codebase-architecture` on the
`aria_nbv` package, using the user's bounded PR #15 cleanup context.

## Source constraints

- Current thesis direction comes from `docs/contents/thesis/roadmap.qmd`,
  `docs/contents/thesis/questions.qmd`, and canonical agent memory.
- The thesis target is target-conditioned finite-candidate NBV, not online RL
  or continuous control as current core.
- Cleanup budget is narrow: make PR #15 easier to merge and safer for the next
  target-conditioned PR.
- Forbidden work: target descriptors, target-conditioned scoring, Q_H
  implementation, new scene-memory packages, broad `data_handling` or `utils`
  restructuring, and broad app rewrites.

## Worktrees inspected

- Primary checkout: `/home/jd/repos/ARIA-NBV`, branch
  `codex/full-rri-rollout-worktree`.
- PR #15 integration worktree:
  `/home/jd/repos/ARIA-NBV-packages/vin-modular-scaffold`, branch
  `codex/vin-cleanup-pr15-integration`.
- Diverse metrics worktree:
  `/home/jd/repos/ARIA-NBV-packages/rollout-diverse-metrics-models`, branch
  `codex/rollout-diverse-metrics-models`.

## Local evidence

- `aria_nbv/aria_nbv/pose_generation/__init__.py` exports
  `counterfactuals` and `target_counterfactuals` contracts from the candidate
  generation package.
- `aria_nbv/aria_nbv/rollouts/trace.py` imports rollout result contracts from
  `pose_generation.counterfactuals`.
- `aria_nbv/aria_nbv/rollouts/zarr_store.py` owns rollout replay and Q-store
  persistence but still type-checks against `pose_generation.counterfactuals`.
- `aria_nbv/aria_nbv/rollouts/AGENTS.md` currently says
  `pose_generation` owns finite candidate pose sampling and counterfactual
  candidate expansion. If counterfactual modules move, this nested guide needs
  a wording update.
- `aria_nbv/aria_nbv/rl/__init__.py`,
  `aria_nbv/aria_nbv/rl/counterfactual_env.py`,
  `aria_nbv/tests/rl/test_counterfactual_env.py`, and app-panel tests prove
  the RL package is active, not trivially unused.
- The PR #15 VIN scaffold has clearer model-family names:
  `scene_myopic`, `target_myopic`, and `target_finite_horizon`.
- The rollout-diverse worktree still uses the less precise
  `target_conditioned_myopic` and `multi_step` names.
- The PR #15 VIN type surface is cleaner: it exports
  `VinV3ForwardDiagnostics` without keeping legacy diagnostics as normal
  public exports.
- App-panel cleanup remains real but risky: `counterfactual_rollouts.py` is
  large and mixes UI with pure reducers, but moving all of it would expand the
  PR beyond the requested cleanup budget.

## Architectural reading

The strongest package seam is:

1. `pose_generation` produces finite candidate tables, candidate masks, and
   pose geometry.
2. `rollouts` owns selected-transition replay, target-specific RRI replay
   evidence, rollout traces, and Q-store persistence.
3. `vin` owns scorer architectures and diagnostics, with model names that
   describe the scientific contract without implying implemented Q_H.
4. `app` owns Streamlit/Rerun glue only; pure reducers can move later when
   directly adjacent to a tested cleanup.

## Recommended stop line

Default to the counterfactuals move first. If it stays low-risk, execute it and
verify imports/tests. Treat RL removal and broad app extraction as follow-up
work unless they become directly required by the move.
