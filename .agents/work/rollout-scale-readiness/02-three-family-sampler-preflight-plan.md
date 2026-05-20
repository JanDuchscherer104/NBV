# Plan: Three-Family Sampler Validity Preflight

Backlog: `todo-088`, linked to `issue-032`, `issue-020`, and `issue-021`.

## Problem

The first validating structural probe of the target-first three-family sampler
produced only 30 valid candidates out of 600, exactly three valid actions per
step, and every valid/selected action came from `forward_local`.
`target_bearing_local` and `lateral_target_bypass` contributed no valid
actions in that probe.

That failure mode undermines the thesis contract: a nominally target-aware
finite-candidate dataset degenerates into forward-only local motion.

## Desired Contract

The production sampler should remain simple, but it must be measurable:

- Each candidate row has `position_id`, strategy/mixture provenance, invalidity
  reasons, and target gain diagnostics.
- Preflight reports validity and selected-action statistics by position family.
- Low-valid roots are skipped or marked non-training before Q_H views consume
  them.
- Target-aware families either contribute valid actions or the root/profile is
  blocked with an explicit reason.

## Implementation Plan

1. Extend the rollout inspection/preflight path to aggregate by `position_id`:
   valid count, invalid-reason histogram, selected count, target-root-gain
   summary, and scene/target/source coverage.
2. Add profile-level gating config:
   - global minimum valid actions per state,
   - optional minimum valid actions from non-forward target-aware families,
   - optional minimum per-family or grouped-family contribution.
3. Run a small multi-scene audit for the current three-family profile before
   retuning; do not tune from a single scene.
4. If target-aware families are still dead, retune in this order:
   - target-bearing/lateral-bypass direction construction,
   - radius and height/yaw realism bounds,
   - clearance and path-collision constraints,
   - root skip policy,
   - upper-bound/free-shell diagnostic to separate feasibility from target prior
     issues.
5. Keep `rich_local_five_family` and `upper_bound_free_shell` as explicit
   ablations, not default production profiles.

## Tests And Verification

- `cd aria_nbv && uv run pytest tests/pose_generation/test_candidate_mixture.py tests/rollouts/test_dataset_writer.py tests/rollouts/test_inspection.py -q`
- Run `nbv-rollouts-info --validate --stats --json` on a fresh schema-1.0
  probe and inspect per-position validity/selection.
- Add a regression fixture where non-forward families are invalid and assert the
  production preflight blocks the store unless explicitly configured as a
  forward-only ablation.

## Open Decisions For Review

1. What minimum valid-action count should production require per state?
   Recommended: choose after a multi-scene audit rather than locking a number
   from the single probe.
2. Should production require at least one valid non-forward target-aware
   candidate per state, or only per rollout/root aggregate? Recommended: per
   state for Q_H training quality, with an ablation that relaxes this.
3. How aggressively should realism constraints be relaxed before skipping a
   root? Recommended: skip roots first if the failure is scene/target-specific;
   relax constraints only if many scenes fail.
4. Should target-root-gain flatness block generation immediately? Recommended:
   report it first, then fail production profiles once a reviewed signal
   threshold is accepted.

