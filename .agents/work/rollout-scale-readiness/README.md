# Rollout Scale Readiness Plan Pack

Date: 2026-05-20

This pack turns the fresh rollout-probe findings into reviewable implementation
plans. It is intentionally internal: the goal is to prepare a plan-grill and
code-review round before broad offline rollout generation, not to add another
public thesis narrative.

## Scope

Linked backlog records:

- `issue-032`: target-first RRI rollout contract needs scale-ready alignment.
- `todo-087`: fix rollout path-collision invalidity consistency.
- `todo-088`: make the three-family sampler pass per-family validity preflight.
- `todo-089`: add a rollout generation preflight gate.
- `refactor-021`: streamline rollout Zarr chunking and manifest payload.

Evidence base:

- Collision-aware schema-1.0 rollout probes failed validation because
  `candidate_diagnostics/path_collision_mask` rows lacked the
  `PATH_SEGMENT_COLLISION` invalidity bit.
- The validating structural probe required disabling path collision, produced
  only 30 valid candidates out of 600, and all valid/selected candidates came
  from `forward_local`.
- Selected `target_root_gain` values in the structural probe were near
  numerical noise.
- Local default rollout stores were stale relative to
  `1.0-target-rollout-core`.
- Candidate pose arrays created row-per-candidate chunk/file bloat.

## Plan Files

- [01-path-collision-invalidity-plan.md](01-path-collision-invalidity-plan.md)
  resolves the invalidity/diagnostic consistency blocker.
- [02-three-family-sampler-preflight-plan.md](02-three-family-sampler-preflight-plan.md)
  makes sampler validity and target-aware family contribution measurable before
  retuning.
- [03-rollout-generation-preflight-plan.md](03-rollout-generation-preflight-plan.md)
  defines the go/no-go gate for broader rollout generation.
- [04-zarr-chunking-manifest-plan.md](04-zarr-chunking-manifest-plan.md)
  reduces chunk/file and manifest bloat without changing learning semantics.

## Recommended Execution Order

1. Fix path-collision invalidity consistency. This unblocks normal
   collision-aware probe validation.
2. Add the preflight metrics substrate: per-position validity, reward summaries,
   stale-schema checks, and file/chunk counts.
3. Retune or gate the three-family sampler using those metrics on a small
   multi-scene subset.
4. Streamline Zarr chunking and manifest payload once the validating small
   stores expose realistic row counts and access patterns.
5. Make broad-generation commands depend on the preflight gate.

## Shared Open Decisions For Next Plan-Grill

1. **Invalidity semantics.** Recommended: `invalid_reason_bitset` stores all
   applicable hard invalidity reasons, while a separate primary reason stores
   the first or most-actionable reason. Alternative: keep first-reason bitsets
   and demote rule masks to independent diagnostics, but that weakens training
   masks and validator consistency.
2. **Low-valid-root threshold.** Recommended: require more than a single global
   minimum, including a non-forward target-aware-family contribution for the
   production profile. The exact thresholds should be chosen after a multi-scene
   audit.
3. **Flat-reward blocker.** Recommended: preflight should report near-zero gain
   distributions immediately, but fail only when a configured minimum signal
   criterion is not met for production profiles. The numeric criterion needs
   review.
4. **Chunking target.** Recommended: use row-block or byte-budget chunks for
   factual candidate arrays, keep `q_h/` and selected-depth chunk policies
   separate, and record the policy. The row count/byte budget needs benchmark
   confirmation.
5. **Stale default stores.** Recommended: keep old stores as local artifacts
   only, fail production preflight on them, and regenerate rather than migrate.
6. **Sampler retuning authority.** Recommended: make preflight evidence decide
   whether to adjust target-bearing/lateral-bypass geometry, relax realism
   constraints, skip poor roots, or run an upper-bound/free-shell diagnostic.

