# Ralplan: PR15 Review Finding Validity

## Decision

Implement a narrow, staged subset of the handoff findings on the actual PR15 branch/head (`e2ac5a7` or a descendant), starting with correctness defects. Treat the red Root Verification job as a separate repository-contract merge gate that must be cleared before merge, but do not mix that scaffold repair into the VIN code-change scope. Do not implement the whole proposed package-layout rewrite as one batch.

## RALPLAN-DR Summary

Principles:
- Validate advisory review findings against the reviewed commit before editing.
- Fix user-visible correctness and merge gates before moving modules.
- Prefer deletion, narrowing, or inlining over new abstractions.
- Preserve the implemented one-step CORAL/RRI scorer and hard invalid masks.
- Keep speculative target-conditioned / finite-horizon work out of public runtime APIs until runnable.

Decision drivers:
- Merge safety: CI is red and PR #15 remains unstable, but the observed CI failure is agent-memory scaffold hygiene rather than a VIN implementation failure.
- Behavioral risk: diagnostics/checkpoint, metric aggregation, and forward mutation can produce wrong or misleading results.
- Reviewability: the PR is large and exposes speculative APIs beyond current implemented scope.

Viable options:
- Option A, minimal correctness only: fix P0/P1 correctness blockers, leave most cleanup. Pros: fastest path to a safer branch. Cons: leaves public API and ownership slop in a large refactor.
- Option B, correctness plus migration-backed API contraction: fix P0/P1 correctness blockers, remove truly non-runnable public runtime surfaces, narrow public APIs, and apply small behavior-preserving cleanup with compatibility/preset paths where current configs are runnable. Pros: best balance for PR15; reduces risk and review scope. Cons: more churn than pure bug fixes.
- Option C, full handoff layout: execute every move/decomposition target. Pros: maximally clean architecture. Cons: too broad for a review-response pass and likely creates new review risk.

Chosen option: Option B.

## Finding Validity And Recommendation

Implement immediately:
- P0-1 Root Verification failed and CI coverage gap. Status: valid merge gate, but split ownership. Root Verification still fails on PR #15 at `e2ac5a7`; the observed failure is `check-agent-memory` pointing at missing canonical paths, so that is a repo-scaffold repair rather than a VIN-code finding. Separately, package smoke does not cover the new VIN/checkpoint/diagnostic/rollout-metric surfaces. Implement both before merge, but keep them as two lanes: scaffold CI repair and PR15 coverage expansion.
- P0-2 VIN diagnostics can ignore configured checkpoint. Status: valid. Diagnostics constructs via `setup_target()` and never calls `load_for_inference()` on `cfg.ckpt_path`; preparation failure is warning-and-continue. Implement.
- P1-1 Table metric aggregation denominator. Status: valid. `_step()` logs top-k, selected-comparison, and valid-table-rate metrics with the same `selected_oracle.valid_table.sum()` batch size. Implement by using stateful numerator/count metrics or separate correct counts.
- P1-2 Forward-time module/device mutation. Status: valid. `VinModelV3` lazily registers a backbone in forward and calls `self.to(device)` inside forward. Implement; stable module graph and no forward-time `.to()` should be a hard invariant.
- P1-3 Inference lifecycle conflation. Status: valid. `prepare_for_inference()` resolves fallback poorly and can initialize state before strict load; bias init overwrites priors. Implement.
- P1-4 Non-runnable public runtime APIs. Status: valid. Remove public config/class exports for deliberately non-runnable target-conditioned positive-descriptor and finite-horizon scorers; keep theory in docs/backlog.
- P1-9 Diagnostic correlations. Status: valid. Fix with joint finite masks and shape checks.

Implement as part of the same cleanup wave, after correctness tests are in place:
- P1-6 CandidateScorer protocol leakage. Status: valid, but should be narrowed after removing scaffold configs. Make it explicit and ordinal/CORAL-scoped or delete it until there is a second real implementation.
- P1-7 VIN root API over-export. Status: valid. Narrow roots after removing unsupported classes and updating internal imports.
- P1-8 Scene-field semantic ownership. Status: valid. Consolidate naming/ownership with a parity test, but avoid moving every geometry file.
- P2-1 Duplicate semidense aliases/log keys. Status: valid. Remove aliases and duplicate metrics once `rg` confirms active callers or provides a serialization-boundary migration.
- P2-6 Smoke rollout config name. Status: valid. Rename/split to make smoke vs production explicit.
- P2-7 Stale docs/PR narrative. Status: valid. Refresh last, after code ownership stabilizes.
- P2-8 Reviewability. Status: valid. Rebuild or reorder the final commit stack by responsibility; do not mix correctness, moves, and docs.

Defer or narrow:
- P1-5 Zero-descriptor wrapper. Status: valid concern, but not the same severity as the always-raising scaffold because `target_descriptor_dim=0` is runnable and delegates to `VinModelV3`. Do not delete it blindly. Either keep it temporarily behind a compatibility alias while documenting the `VinModelV3Config` replacement, or replace it with a named preset plus migration tests for existing TOML/checkpoint expectations.
- P2-2 PolicyTableMetrics composite. Status: valid concern but not a correctness blocker. Defer broad deletion until production callers are confirmed; if retained, move under rollout evaluation with typed input later.
- P1-10 rri_metrics ownership leakage. Status: valid architecture smell. Implement only the high-value moves needed to keep rollout/Lightning concerns out of the stable root; avoid formula changes.
- P1-11 VinLightningModule monolith. Status: valid, but full decomposition should not block the first correctness pass. Extract only checkpoint lifecycle and metric-state/objective helpers when tests make the cut behavior-preserving.
- P2-3 Forwarding context mixin. Status: valid small cleanup. Delete inline in a later simplification pass if tests are green.
- P2-4 Feature-bank type fragmentation. Status: valid low-risk cleanup. Merge only if the PR remains large after higher-value deletions.
- P2-5 App `vin_utils.py` helper bucket. Status: valid. Inline/delete after diagnostics checkpoint loading and scorer-input adaptation are fixed.

Reject:
- No handoff finding should be fully rejected on current evidence. The main correction is priority: several valid findings are not immediate blockers.

## Implementation Sequence

1. Establish the exact PR15 branch/head in a clean worktree; do not edit from the current `codex/full-rri-rollout-worktree` checkout.
2. In a separate scaffold lane, fix the root CI `check-agent-memory` failure. In the PR15 code lane, add/route new VIN and rollout metric tests into CI.
3. Add failing regression tests for diagnostics checkpoint loading, binner fallback/idempotence, table-metric aggregation, forward graph/device stability, and joint-mask correlations.
4. Implement the five correctness fixes without module moves.
5. Remove truly non-runnable scorer runtime surfaces; handle the zero-descriptor wrapper only through a migration-backed preset/compatibility plan.
6. Narrow `CandidateScorer` and VIN root exports.
7. Consolidate scene-field and semidense alias/log-key ownership with parity/usage tests.
8. Do small behavior-preserving simplifications only where they delete or shrink an owner: context mixin, feature-bank one-dataclass files, residual app utility helper.
9. Refresh config naming, PR body, docs/debrief, and final commit stack.

## Verification Plan

- GitHub PR head/base check before editing.
- `make ci PYTHON_INTERPRETER=python` after scaffold/CI repair and at the final head.
- Targeted pytest for VIN namespace/API, checkpoint loading, diagnostics, Lightning table metric aggregation, VIN model forward stability, RRI/rollout metrics, and rollout config tests.
- `ruff format --check` / `ruff check` on touched Python files.
- Offline binner and two-epoch smoke only after correctness fixes.
- `make loc` before and after if LOC reduction remains a stated cleanup objective.

## ADR

Decision: Implement Option B, a correctness-first cleanup plus migration-backed public API contraction.

Drivers: PR #15 is still unstable; several findings can produce silently wrong diagnostics or biased metrics; speculative public APIs make the branch harder to review and harder to maintain; the runnable zero-descriptor wrapper creates migration risk if removed without a replacement path.

Alternatives considered:
- Minimal correctness only: rejected because the exported non-runnable scaffolds and protocol/root export shape are part of the reviewability problem.
- Full layout rewrite: rejected because it would conflate behavior fixes with broad module moves and likely increase review risk.

Consequences:
- The first execution pass should be test-first and mostly local to diagnostics, Lightning checkpoint/metrics, VIN forward, and public config/API surfaces.
- Root CI scaffold repair should be tracked separately from VIN code correctness even though both gate merge readiness.
- Some architectural cleanup remains deferred until the branch is green and the public runtime surface is smaller.

Follow-ups:
- Consider splitting the final PR history into correctness, API contraction, ownership cleanup, and docs/CI commits.
- If broad Lightning decomposition is still desired, make it a separate post-green refactor with invariant tests.

## Available Agent Types And Follow-Up Staffing

Available role types include `explore`, `debugger`, `executor`, `test-engineer`, `architect`, `critic`, `verifier`, `code-reviewer`, `code-simplifier`, `git-master`, and `writer`.

Recommended follow-up:
- `$ultragoal`: default durable execution, with subgoals matching the sequence above.
- `$team`: useful inside `$ultragoal` after tests are defined, with disjoint lanes for checkpoint/diagnostics, metrics aggregation, public API contraction, and docs/CI.
- `$ralph`: fallback only if a single-owner persistence loop is explicitly preferred.

Reasoning levels:
- High for checkpoint/metric/forward correctness and API contraction.
- Medium for low-risk cleanup/inlining once tests are green.
- High verifier/code-reviewer for final merge readiness.

Team verification path:
- Test-engineer defines regression tests first.
- Executor implements correctness fixes.
- Code-simplifier handles deletion/narrowing after tests pass.
- Verifier runs targeted commands plus `make ci`.
- Code-reviewer checks remaining blockers before PR body refresh.

## Goal-Mode Follow-Up Suggestions

- `$ultragoal` is the default next lane for durable implementation tracking.
- `$team` can be paired with `$ultragoal` for parallelized implementation lanes.
- `$performance-goal` is not appropriate; this is correctness/reviewability work, not optimization.
- `$autoresearch-goal` is not appropriate; no external research question blocks the plan.
