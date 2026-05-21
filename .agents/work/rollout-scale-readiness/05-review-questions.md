# Review Decisions For Next Plan-Grill

Use these decision cards after external review of the plan pack. Each card
names the recommended answer and the gate it controls.

## A. Reviewed Ref And Plan Pack

Decision: should external review always target a pushed branch/ref that contains
the exact `.agents/work/rollout-scale-readiness/*` plan pack and linked DB IDs?

Recommended answer: yes. Push or expose the exact commit SHA before asking for
another external review.

Gate: no further plan acceptance until reviewers can fetch the same artifacts.

## B. Invalidity

Decision: do we accept all-reasons `invalid_reason_bitset` plus a fixed-priority
`primary_invalid_reason`?

Recommended answer: yes. Diagnostic masks that mean hard infeasibility must map
to invalidity bits; soft diagnostics must be named audit-only.

Gate: collision-aware rollout probes cannot validate until this is fixed.

## C. Low-Valid Roots And Sampler Contribution

Decision: what minimum valid-action support makes a state trainable?

Recommended answer: production requires
`num_valid_candidates >= max(12, ceil(0.25 * N_q))`; with `N_q=60`, require at
least 15 valid actions, plus at least three valid non-forward target-aware
actions per state. Smoke may warn with one.

Gate: low-valid roots are skipped or marked non-training before Q_H views
consume them.

## D. Flat Target-Gain Signal

Decision: when is target-root-gain too flat for production evidence?

Recommended answer: smoke warns; production fails if median absolute valid
`target_root_gain < 1e-4` and p90 `target_root_gain < 1e-3`, unless a
realistic-vs-free-shell diagnostic proves the profile is intentionally
signal-limited.

Gate: broad generation should not produce mostly numerical-noise rewards.

## E. Production Preflight Surface

Decision: extend `nbv-rollouts-info` or add a new command?

Recommended answer: extend `nbv-rollouts-info` with
`--preflight --profile production --json` if the options stay readable; split to
a new command only if source/render/scorer checks make the interface too dense.

Gate: LRZ/broad generation commands must depend on machine-readable preflight.

## F. Scene Splits And Stochastic Replay

Decision: what lineage is mandatory for thesis-scale stores?

Recommended answer: scene-level split manifest overrides sample-key split before
shard grouping, and stochastic training traces persist rollout/job seed, shard
order, per-step or derivable branch seeds, sampled outcomes, RNG-state hash, and
selection-policy params hash.

Gate: missing split override or incomplete stochastic replay provenance keeps
stores smoke/audit-only.

## G. Storage And Scope Control

Decision: what belongs in training-core stores by default?

Recommended answer: selected/parent depth stays training-core successor state
history; target-eval crop point payloads and richer Rerun/UI artifacts stay
sampled/audit retention. Factual arrays use byte-budget chunks with row caps,
while stale stores are regenerated, not migrated.

Gate: schema `1.0-target-rollout-core` is production-final only after optional
audit groups, chunking, manifest fields, H=1 role/profile, split, invalidity,
and stochastic provenance are frozen.
