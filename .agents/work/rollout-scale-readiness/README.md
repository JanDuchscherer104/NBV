# Rollout Scale Readiness Plan Pack

Date: 2026-05-20

This pack turns the fresh rollout-probe findings into reviewable implementation
plans. It is intentionally internal: the goal is to prepare a plan-grill and
code-review round before broad offline rollout generation, not to add another
public thesis narrative.

## Scope

Linked backlog records:

- `issue-032`: target-first RRI rollout contract needs scale-ready alignment.
- `todo-081`: harden schema `1.0-target-rollout-core`.
- `todo-084`: require scene-level split manifests before thesis-scale rollout generation.
- `todo-087`: fix rollout path-collision invalidity consistency.
- `todo-088`: make the three-family sampler pass per-family validity preflight.
- `todo-089`: add a rollout generation preflight gate.
- `todo-090`: expose this plan pack and current backlog on the reviewed branch/ref.
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

## External Review Consolidation

The latest external review is a **no-go** for broad offline rollout generation,
and that verdict matches the local scale-readiness plans. The review also
contained a review-target mismatch: the accessible GitHub ref was PR #14 at
`74b7be2190f147da490875c4c3fd7d2f4a34dbe2`, while this local checkout is ahead
and already contains the readiness plan pack, `issue-032`, `todo-087` through
`todo-089`, `refactor-021`, and `aria_nbv/aria_nbv/rollouts/inspection.py`.

Consolidated triage against the current checkout:

- **Still valid blockers:** publish/expose the reviewed ref, scene-level split
  override before shard grouping, production preflight JSON, all-hard-diagnostic
  invalidity validation, low-valid-root gating, stochastic seed provenance,
  optional audit payload policy, byte-budget chunking, H=1 target-label profile,
  and stale-store/schema handling.
- **Partly stale review findings:** schema is already
  `1.0-target-rollout-core`, candidate-major q_h bootstrap/scene-RRI arrays are
  already pruned, `position_id` is hot in `candidates/` and `q_h/`, and current
  target-selection tests already assert geometry-only GT match after
  eligibility.
- **Still needs tightening:** operator docs and configs must not present
  old five-family smoke settings, stale default stores, or audit-heavy payloads
  as production defaults.

## Plan Files

- [01-path-collision-invalidity-plan.md](01-path-collision-invalidity-plan.md)
  resolves the invalidity/diagnostic consistency blocker for every hard
  diagnostic, not only path collision.
- [02-three-family-sampler-preflight-plan.md](02-three-family-sampler-preflight-plan.md)
  makes sampler validity and target-aware family contribution measurable before
  retuning.
- [03-rollout-generation-preflight-plan.md](03-rollout-generation-preflight-plan.md)
  defines the go/no-go gate for broader rollout generation.
- [04-zarr-chunking-manifest-plan.md](04-zarr-chunking-manifest-plan.md)
  reduces chunk/file and manifest bloat without changing learning semantics.

## Recommended Execution Order

1. Expose the current local plan pack/backlog on the reviewed branch or provide
   an exact commit SHA/ref. External review cannot accept artifacts it cannot
   fetch.
2. Fix all-hard-diagnostic invalidity consistency. This unblocks normal
   collision-aware probe validation and gives preflight trustworthy reason
   counts.
3. Add the preflight metrics substrate: per-position validity, reward summaries,
   stale-schema checks, file/chunk counts, split/seed lineage, and optional
   group retention.
4. Gate and retune the three-family sampler using a small multi-scene subset;
   do not silently relax constraints per root.
5. Streamline Zarr chunking and manifest payload once validating stores expose
   realistic row counts and access patterns.
6. Make broad-generation commands depend on scene-level split manifests and the
   production preflight gate.

## Shared Open Decisions For Next Plan-Grill

1. **Invalidity semantics.** Recommended: `invalid_reason_bitset` stores all
   applicable hard invalidity reasons, while `primary_invalid_reason` stores a
   deterministic fixed-priority reason.
2. **Low-valid-root threshold.** Recommended: production requires
   `num_valid_candidates >= max(12, ceil(0.25 * N_q))`, plus target-aware
   non-forward contribution.
3. **Flat-reward blocker.** Recommended: smoke warns, production fails when
   robust target-root-gain signal is numerical noise after a realistic-vs-free
   shell sanity comparison.
4. **Preflight command shape.** Recommended: extend `nbv-rollouts-info` with
   `--preflight --profile production --json` unless the source/render checks
   make the interface too dense.
5. **Chunking target.** Recommended: byte-budget chunks with row-count
   floor/ceiling for factual arrays; keep `q_h/` and selected-depth policies
   separate.
6. **Stale default stores.** Recommended: fail production preflight on old
   schemas and regenerate; keep stale stores only as explicit fixtures or local
   artifacts.
7. **Scope control.** Recommended: defer UI/Rerun richness, Gumbel, continuous
   simulator work, and full audit payload retention until the production
   preflight gate passes.
