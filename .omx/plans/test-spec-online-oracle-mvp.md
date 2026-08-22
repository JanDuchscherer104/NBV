---
kind: test-spec
status: locally-approved-receipt-blocked
slug: online-oracle-mvp
baseline: a121cd821f7748f979c2cddf0f7c3af0e0b6a5a7
---

# Test specification: online oracle and hierarchical pose-policy MVP

## Objective

Prove each owner-local interface independently, then prove the composed loop
without weakening actor/oracle separation, finite-candidate support, immutable
evidence, or thesis gates. Functional correctness precedes performance
measurement; performance candidates use a frozen measured-autoresearch
evaluator rather than changing the evaluator after results are observed.

## WP0a — mandatory functional golden parity

Before environment or replay-kernel edits, freeze:

- deterministic source/target/root fixture and representative CUDA sample IDs;
- current `CounterfactualPoseGenerator + TargetRriScorer` candidate, transition,
  reward, endpoint, and stored-row outputs;
- field-specific equality/tolerance rules;
- a candidate-independent parity command; and
- source, contract, implementation, and device identity.

WP0a cannot pass as "measurement blocked." Its fixture is the mandatory
functional oracle for WP4.

## WP0b — measured performance contract

Create an active autoresearch/autoresearch-goal mission only when an executable
candidate is ready. Before any performance edit, freeze:

- baseline commit and clean worktree identity;
- deterministic source/target/root fixture and representative GPU sample IDs;
- current `CounterfactualPoseGenerator + TargetRriScorer` candidate, transition,
  reward, endpoint, and stored-row outputs;
- numerical tolerances by field;
- evaluator command/fingerprint and package/CUDA/device identity;
- fixed warmup/repeat counts and synchronization rules;
- reset, render, target-crop, per-table score, selected-update, endpoint, wall
  time, and peak GPU-memory metrics;
- hard gates for actor/oracle leakage, candidate identity, masks, and store
  equality; and
- keep/discard rule plus one required sample artifact.

The same evaluator must score baseline and every environment candidate. Append
one row per attempted candidate to the mission-owned `experiments.tsv`; do not
run the measured sidecar when the mission or evaluator is absent. WP0b may
remain blocked while functional work proceeds, but no performance result may be
accepted without its baseline row.

## WP1 — finite-horizon scorer unit contract

Primary files:

- new `aria_nbv/tests/vin/test_target_finite_horizon.py`;
- integration additions in `aria_nbv/tests/lightning/test_qh_module.py`.

Required cases:

1. `test_qh_scorer_output_matches_actor_candidate_axes`
   - unbatched/batched fixture construction reaches `[B,S,N]` exactly;
   - output dtype/device follow the scorer input/module policy.
2. `test_qh_scorer_permutation_equivariance`
   - jointly permuting candidate poses and aligned masks permutes outputs;
   - no candidate-index embedding or order-sensitive reduction is present.
3. `test_qh_scorer_invalid_rows_are_isolated`
   - arbitrary values in masked/padded rows cannot change admitted-row values;
   - an all-invalid realized state fails before selection, not inside `argmax`.
4. `test_qh_scorer_rejects_actor_profile_mismatch`
   - missing required EVL fields, wrong CF0/CF+ profile, or selected-observation
     mismatch fails closed.
5. `test_qh_scorer_has_no_supervision_or_audit_dependency`
   - construction and forward accept only actor views;
   - dependency/static inspection rejects oracle/GT imports in the model path.
6. `test_qh_scorer_encodes_observed_target`
   - changing an admitted actor target descriptor changes candidate values;
   - target row/GT association fields are unavailable to the scorer.
7. `test_qh_scorer_uses_causal_history_and_budget`
   - changing causal selected-pose history or remaining budget changes values;
   - changing future or masked history slots does not.
8. `test_qh_scorer_backward_updates_only_online_scorer`
   - selected-action loss changes online scorer parameters;
   - target scorer, actor DTOs, masks, and persisted EVL carriers remain detached.
9. `test_qh_scorer_deterministic_eval`
   - repeated CPU evaluation is bitwise equal where deterministic operators are
     promised;
   - CUDA uses a named field-specific tolerance and recorded device/runtime
     identity, never the ambiguous phrase "byte equality within tolerance."

Candidate-pose input gradients are a non-blocking compatibility probe in WP1.
They become a mandatory acceptance test only in WP8 before pathwise refinement.

Run existing Q_H unit tests unchanged to prove the new scorer does not alter
Double-Q admission, empty-batch no-op, target sync, or distributed transaction
semantics.

## WP2 — experiment, inference bundle, and resume

Primary files:

- new `aria_nbv/tests/lightning/test_qh_experiment.py`;
- extend `test_qh_module.py`, `test_resume_checkpoint.py`, and
  `test_interrupt_checkpoint.py` only for shared lifecycle facts.

Required cases:

1. `test_qh_bundle_round_trip_preserves_values_and_ranking`
   - train one deterministic step, export, destroy objects, load in a new process,
     and compare valid-row values plus masked selected indices.
2. `test_qh_checkpoint_restores_target_and_optimizer_state`
   - resume produces the same next update, scheduler state, optimizer-update
     count, and target-sync behavior as uninterrupted training.
3. `test_qh_bundle_manifest_binds_complete_contract_identity`
   - the public ref contains only bundle path, schema version, and manifest hash;
   - the verified manifest contains scorer, actor, learning, geometry,
     candidate, target, EVL config, EVL checkpoint, dependency, and
     implementation identities.
4. `test_qh_bundle_rejects_stale_contracts`
   - change each identity independently and require a field-specific error
     before scorer forward.
5. `test_qh_inference_loader_is_strict_and_eval_ready`
   - missing/unexpected state keys fail;
   - loaded module is on requested device, in evaluation mode, and used under
     inference mode by the pipeline-local score Adapter.
6. `test_qh_inference_does_not_require_hidden_caller_config`
   - the immutable bundle ref alone verifies the manifest and reconstructs the
     scorer;
   - replay/oracle modules do not import Lightning checkpoint DTOs.
7. `test_qh_bundle_hash_detects_content_change`
   - path reuse or byte mutation changes/rejects identity.
8. `test_qh_bundle_profile_is_v1_cf0_by_default`
   - privileged CF+ or GT target inputs require a distinct explicit cohort and
     cannot load through the deployable default.
9. `test_qh_fit_request_preserves_ordered_store_identity`
   - permuting otherwise identical `train.rollout_store_dirs` changes canonical
     chain/store identity and the resulting manifest deterministically;
   - validation/test dataset configs and their held-out manifests are recorded
     without entering training updates.
10. `test_qh_fit_resume_identity_is_explicit`
    - `resume_from=None` and a verified prior bundle are distinct manifest
      inputs;
    - a stale resume bundle fails before trainer construction.
11. `test_qh_fit_result_is_immutable_and_receipted`
    - an existing output directory fails closed;
    - the result names the new bundle plus hashed training and held-out
    checkpoint-selection receipts.
12. `test_replay_remains_oracle_independent`
    - no module under `rollouts/replay` imports oracle, the online-Q_H pipeline,
      Lightning, or the inference-bundle loader;
    - the pipeline Adapter reaches replay only through its existing generic
      score callback and `CandidateScores` DTO.
13. `test_qh_checkpoint_selection_is_closed_and_deterministic`
    - V1 accepts only the existing `QhLightningModule` aggregate `val/loss`
      minimization with earliest-optimizer-update tie breaking;
    - the checkpoint callback reads the logged `val/loss` value used in the
      manifest and selection receipt;
    - a changed metric, mode, or tie break is rejected rather than silently
      changing the manifest identity.
14. `test_qh_configs_follow_target_config_factory_contract`
    - scorer and experiment configs expose the exact concrete `target_type` and
      `setup_target()` constructs without running fit;
    - `QhExperiment.fit(request)` remains the only training run entrypoint.

## WP3 — offline M5 evidence

Before RQ5 or proposal work, produce a scene-paired held-out report over one
frozen population and candidate contract.

Required policies:

- random-valid;
- existing one-step learned scorer where compatible;
- one-step oracle greedy;
- bounded oracle lookahead;
- production finite-horizon Q_H.

Required metrics:

- cumulative root-normalized target gain and endpoint target gain;
- recovered oracle-lookahead headroom;
- selected-action regret/rank and calibration;
- invalid, label-missing, no-successor, and unsupported-backup fractions;
- results by horizon, scene, target, family, support, and profile;
- candidate/proposal, rendered, oracle-scored, and acquired counts;
- path length, wall/GPU time, peak memory, and failure denominators;
- scene-paired uncertainty intervals.

Hard gates:

- exact scene-disjoint train/validation/test manifests;
- no pooling of incompatible candidate/oracle/return contracts;
- no RQ5 continuation when lookahead headroom is nonpositive, Q_H support is
  inadequate, or #79/#80 fidelity evidence is invalid;
- no policy conclusion from training loss alone.

## WP4 — bound oracle decision context and shared transition kernel

Primary files:

- new `aria_nbv/tests/oracle/test_environment.py`;
- focused integration with current rollout fixtures and store tests.

Required cases:

1. `test_environment_dense_matches_existing_scorer`
   - candidate order/mask, per-valid RRI, root gain, selected evidence,
     transition, endpoint, and reason fields match the frozen baseline.
   - the episode facade and the existing rollout writer both call the same
     extracted transition kernel; neither reconstructs transition semantics.
2. `test_environment_subset_preserves_shell_and_valid_indices`
   - arbitrary ordered subsets retain exact identity;
   - duplicate, invalid, or unknown indices fail explicitly.
3. `test_environment_selected_only_materializes_one_action`
   - only the selected action is oracle-scored/materialized;
   - successor actor state matches dense-mode selection under the same action.
4. `test_decision_context_actor_view_cannot_expose_oracle_fields`
   - ordinary `context.to_qh_actor()` has no GT mesh/crop, candidate render,
     target error, RRI, or association-result path;
   - actor tensors are identical before/after separate dense evaluation.
5. `test_environment_incremental_state_matches_full_history`
   - selected evidence, crop/fusion order, root-relative gain, and endpoint agree
     within frozen tolerance for every step.
6. `test_environment_commit_is_atomic`
   - injected failures at render, validation, fusion, and transition assembly
     leave the prior state/hash unchanged and write no transition.
7. `test_environment_commit_is_idempotent_or_typed_consumed`
   - repeat state/table/action returns the committed result or an explicit
     already-consumed error; no second mutation occurs.
8. `test_environment_cache_identity_and_invalidation`
   - source, target, camera, renderer, crop, fusion, metric, and implementation
     changes invalidate only the affected cache;
   - alternating targets in one scene cannot reuse target-local state.
9. `test_environment_reset_isolation_and_restart_replay`
   - scene/target episodes share no mutable state;
   - serialized request plus stored decisions reproduces transitions after a
     process restart.
10. `test_environment_endpoint_telescopes_when_contract_allows`
    - with gamma one and the canonical additive root-gain contract, cumulative
      rewards equal independent endpoint gain within tolerance.
11. `test_environment_context_cleanup_on_success_and_exception`
    - renderer/GPU resources are bounded and released by close/context exit.
12. `test_existing_writer_consumes_environment_transitions_without_schema_drift`
   - the resulting immutable store and Q_H read model preserve existing
     semantics and lineage.
13. `test_prepare_evaluate_commit_rejects_stale_or_foreign_context`
    - `prepare_decision()` binds episode ID, state hash, candidate-table hash,
      actor view, and the exact candidate table in one context;
    - `evaluate(context, query)` rejects a context from another episode, an
      expired state, or a mismatched table before scoring;
    - `commit(context, evaluation, selection)` rejects an evaluation or
      selection produced from any other bound context.
    - mutating a nested trajectory step, candidate mask/pose/extras, or actor
      tensor after binding changes its recomputed hash and fails before oracle
      work or state mutation.
14. `test_episode_facade_and_rollout_kernel_are_stepwise_equivalent`
    - replaying identical selections through the existing writer and through
      the episode facade yields identical state hashes, transitions, rewards,
      endpoint reasons, and store rows at every step.
15. `test_repeated_episode_resources_remain_bounded`
    - a fixed number of sequential open/evaluate/commit/close cycles has no
      monotonic CPU/GPU allocation growth beyond a named tolerance;
    - cache hit/miss, render, query, and close counters remain attributable to
      an episode and decision context.
16. `test_episode_request_and_context_hashes_bind_existing_owners`
    - source/sample manifests, target, root, candidate/replay/scorer configs,
      successor mode, trajectory prefix, and candidate table each perturb only
      their documented episode/state/table identity;
    - rich sample/mesh attachments are not serialized into a public receipt.
    - canonical detached CPU hashing is identical for the same admitted facts
      constructed on CPU or CUDA and after a fresh-process round trip; dtype,
      shape, or value changes perturb the appropriate hash.
17. `test_oracle_query_closed_modes_and_existing_evaluation_dto`
    - dense requires no indices, subset requires a unique ordered nonempty valid
      subset, and selected-only requires exactly one valid shell row;
    - evaluation returns the existing `OracleCandidateEvaluation` aligned to
      `CandidateSamplingResult`, not a second label DTO.
18. `test_commit_and_endpoint_are_storage_safe`
    - commit returns the existing `EvaluatedRolloutStep`/
      `CounterfactualStepResult` transition contract;
    - endpoint scalars serialize deterministically with their contract hash.
19. `test_pipeline_closure_preserves_replay_callback_signature`
    - the current `(CandidateSamplingResult, CounterfactualTrajectory, int) ->
      CandidateScores` callback accepts the pipeline closure unchanged;
    - the private binder and `prepare_decision()` produce the same context hash
      and actor view for the same state/table.

Production verification includes a bounded CUDA sample because CPU fixtures
cannot prove renderer/cache resource behavior. If CUDA is unavailable locally,
record the exact gap and require hosted/remote evidence before promotion.

## WP5 — concrete Q_H score adapter and dense-valid online round

Primary files:

- new `aria_nbv/tests/oracle/test_online_qh.py`;
- existing replay policy/engine tests for the generic score callback and
  `CandidateScores` contract;
- existing Q_H reader/store tests for immutable round integration.

Score-adapter cases:

1. `test_qh_score_adapter_preserves_context_candidate_axes`
   - inference mode returns the existing `CandidateScores` aligned to the exact
     bound context table and mask;
   - no probability distribution or second candidate identity is invented.
2. `test_existing_replay_selection_matches_qh_scores`
   - deterministic and generator-keyed stochastic selection use the existing
     replay policy and record exact shell/compact indices.
3. `test_qh_score_adapter_rejects_empty_valid_support`
   - empty support returns the existing typed no-action result before ranking.
4. `test_existing_selection_record_is_storage_safe`
   - stored scores/indices are detached CPU values with no autograd graph;
   - inference collection exposes no live-training conversion.
5. `test_behavior_bundle_and_policy_identity_round_trip`
   - bundle manifest hash, experiment-config hash, selection policy identity,
     and actor/learning contract hashes survive the existing store path.
6. `test_qh_score_adapter_rejects_stale_inputs`
   - stale actor, bundle, episode context, state hash, or table hash fails before
     scorer forward or selection.
7. `test_existing_random_and_oracle_baselines_are_unchanged`
   - the Q_H adapter adds one score source without replacing built-in replay
     policies or their selection records.

Collector cases:

1. one round loads one immutable inference bundle exactly once and every
   transition records its verified manifest hash;
2. proposal policy, oracle-query policy, and selected-action policy remain
   separate provenance fields;
3. training scenes only are admitted; any validation/test scene fails closed;
4. collection writes a new immutable shard and cannot mutate prior shards or
   the immutable VIN source;
5. partial round failure cannot promote a shard;
6. retry/resume preserves episode/state/action identity without duplicate
   committed transitions;
7. MVP training collection uses `dense_valid` only; subset/selected-only
   evaluation requests fail Q_H learning admission unless a future distinct
   objective and learning contract explicitly authorize them;
8. proposed, valid, queried, labeled, selected, persisted, and rejected counts
   plus resource costs are exact and cannot be inferred from one another;
9. the next training phase reads an explicit ordered tuple of immutable shards;
10. retraining emits a distinct bundle and leaves the round's behavior bundle
    bytes unchanged;
11. query mode and label-support semantics are hashed by `QhDataContract` and
    `QhLearningContract`; mixed sparse/dense shards fail admission;
12. train-only DAgger-style aggregation leaves held-out manifests byte-identical;
13. online-versus-offline comparison uses matched candidate, successor-state,
    query, acquisition, and endpoint contracts.

Dense-valid admission cases:

1. metadata must equal `dense_valid`,
   `equals_action_on_realized_steps_v1`, and
   `qh_dense_valid_fitted_q_v1` for the deployable online profile;
2. on every realized step,
   `label_mask == (action_mask & step_mask[..., None])` exactly;
3. dense-profile collation canonicalizes candidate reward and one-step target
   RRI to finite values on that exact support and NaN outside it after both
   candidate-width and step padding;
4. candidate-width padding, step padding, and hard-invalid realized rows are
   all excluded from `expected`; legacy collation retains its current finite-
   zero reward padding unchanged;
5. one missing valid-row label, one nonfinite supported value, a mixed shard,
   or a metadata/tensor disagreement fails during dataset/batch admission before
   first scorer forward;
6. legacy subset stores remain readable only under the legacy objective and
   cannot be exported as a dense-valid bundle.

Round-interface cases:

1. `OnlineQhRoundRequest` constructs with required selection policy and query
   budget before its defaulted dense-valid query mode;
2. the round result binds shard, behavior-bundle, receipt hashes, and all seven
   explicit counters;
3. the receipt carries proposal-policy manifest hash, oracle-query-policy ID,
   and selected-action-policy hash as distinct non-interchangeable fields;
4. receipt serialization round-trips the request, endpoint summaries, failure
   denominators, resource/timing metrics, and promoted identities.

## WP6/WP7 — hierarchical bounded 5-DoF proposal

Primary files:

- new `aria_nbv/tests/pose_generation/test_hierarchical_proposer.py`;
- integration tests under `aria_nbv/tests/oracle/` and
  `aria_nbv/tests/rollouts/`.

Required cases:

1. `test_hierarchical_family_distribution`
   - categorical probabilities normalize, family floors/anchors hold, and
     sampled/logged family indices align.
2. `test_local_5d_parameters_are_bounded`
   - translation, yaw, and pitch use declared local-frame transforms and remain
     within bounds; roll is fixed by the active constructor.
3. `test_zero_residual_matches_anchor`
   - every family has a deterministic zero-residual reference pose.
4. `test_attempted_density_precedes_hard_selection`
   - log probability belongs to attempted `(family,z)` samples;
   - hard feasibility/reservoir inclusion is recorded separately.
5. `test_keyed_sampling_is_reproducible_and_state_specific`
   - same immutable state key reproduces; different root/history/replica changes
     the stream as intended.
6. `test_fixed_anchor_fraction_and_identity`
   - learned attempts cannot eliminate the configured canonical anchors.
7. `test_hard_invalid_rows_never_train_utility`
   - invalid attempts may support feasibility diagnostics but receive no RRI/Q
     regression target.
8. `test_materialized_result_preserves_candidate_contract`
   - full-shell order, compact valid mapping, reason codes, family/position IDs,
     and proposal provenance round-trip through existing storage.
9. `test_selector_and_proposer_alternate_frozen_phases`
   - proposer updates do not mutate the Q_H checkpoint and selector updates do
     not mutate the proposer checkpoint.
10. `test_cem_control_obeys_query_budget`
    - bounded CEM uses the same starts/budget accounting and cannot silently use
      unlimited hard-oracle calls.
11. `test_proposer_collapse_guard`
    - family entropy/survival, fixed anchors, and proposal regret expose a
      single-family/duplicate collapse fixture.
12. `test_qh_ranks_realized_hierarchical_table`
    - no alternate scorer path is introduced; realized rows go through the
   ordinary finite-candidate policy and hard endpoint evaluation.
13. `test_candidate_proposal_state_is_actor_safe_and_hash_bound`
    - exact root/target/history/scene-feature shapes and masks are admitted;
    - oracle labels, GT crops, and candidate evaluations are absent;
    - a changed feature schema/backbone changes the actor-state contract hash
      and proposer manifest.
14. `test_candidate_proposal_attempt_has_explicit_k_f_axes`
    - one call produces shared float32 logits `[F]`, int64 family indices `[K]`,
      float32 local parameters `[K,5]`, and float32 log probabilities `[K]` on
      one device with in-range family indices;
    - training-mode float tensors may carry gradients, while generator key and
      manifest hash do not.
15. `test_gradient_attempt_cannot_be_serialized_directly`
    - the runtime attempt exposes no writer/serializer path;
    - materialization detaches it before hard pose construction and storage.
16. `test_attempt_provenance_round_trips_through_candidate_result`
    - the five declared tensor extras align to the full shell, use exact anchor
      sentinels, contain no autograd graph, and survive the existing
      serializable round trip; the proposer manifest remains one constant
      string;
    - table hash changes with family, local parameters, log probability,
      generator key, or proposer-manifest identity.

Evidence reports proposal quality separately from selector quality:

- family survival and entropy;
- hard-valid and final-shell inclusion rates;
- target framing, diversity, reachability, and duplicate rate;
- best-of-K target gain and proposal regret against the reference reservoir;
- selector regret on frozen realized tables;
- attempted proposals, scorer queries, hard feasibility calls, oracle queries,
  acquisition count, wall time, and peak memory;
- descriptor-noise and cross-profile strata.

## WP8 — optional local surrogate refinement

This work package is absent from the MVP acceptance gate. If authorized later,
it requires:

1. continuous local 5-DoF pose construction and rotation-continuity tests;
2. surrogate autograd versus finite-difference agreement;
3. surrogate gradient direction versus positive/negative hard-oracle probes on
   every local axis;
4. support/OOD-aware trust-region shrink/fallback;
5. zero-step identity, bound projection, gradient clipping, and original-anchor
   fallback;
6. stop-gradient semantics at hard projection/mask/dedup/final-shell decisions;
7. hard-invalid refined-candidate rejection;
8. equal-start/equal-query random, coordinate-search, and CEM controls;
9. candidate-set proposal regret and endpoint improvement after hard-oracle
   rescoring; and
10. a separate metric/provenance name for any soft-oracle ablation.

Reject the path if good global ranking does not produce local hard-oracle
directional agreement or matched-budget candidate-set improvement.

## Deferred score-function policy-gradient gate

Same-step collection never persists a live autograd graph. If a later policy-
gradient work package is authorized, it must prove that training mode
reconstructs the policy distribution from the stored actor-safe context and
selected action, recomputes the selected log probability, and obtains a
non-zero parameter gradient even when the hard reward is nondifferentiable.
The stored behavior bundle identity and action support must make that
reconstruction auditable; a detached inference record is never treated as a
training graph.

## Cross-level verification matrix

| Contract | Unit proof | Integration proof | End-to-end proof | Observability proof |
| --- | --- | --- | --- | --- |
| actor-only Q_H scoring | mask, axes, causality, scorer gradient | Lightning Double-Q and bundle export | held-out ranking after fresh-process load | contract/profile/bundle hashes |
| oracle transition semantics | transition-kernel golden fixture | facade/writer stepwise equivalence | multi-step episode and restart replay | state/table/context hashes and reason counts |
| dense-valid online round | shard admission and immutable promotion | bundle -> score adapter -> collector | source -> fit -> bundle -> round -> shard -> refit -> new bundle -> held-out evaluation | proposed/valid/queried/labeled/selected/persisted/rejected counters |
| hierarchical 5-DoF proposal | bounds, density, anchors, materialization | realized table through Q_H adapter | alternating frozen proposer/scorer phases | family survival, entropy, proposal/selection regret |
| resource lifecycle | cache keys and close idempotence | repeated CUDA episodes | bounded multi-round sample | render/query/cache/close timings and peak memory |

The dense-valid loop is the required MVP end-to-end test. It starts from an
immutable source, fits Q_H, exports an inference bundle, destroys the training
process, loads that bundle in a fresh process, runs one bound-context episode
round, promotes one immutable shard, refits from an explicit ordered shard
tuple, exports a new bundle, and evaluates the new bundle on unchanged held-out
manifests.

## Static and ownership checks

For every implementation PR:

```bash
git diff --check
ruff check <changed Python files and focused tests>
mypy <changed package modules>
pytest -q <focused tests>
make check-agent-memory
```

Use the repository's canonical environment/Make seams where available. A
targeted mypy/test result proves only the targeted contract. Run broader
owner-level suites when the diff crosses public imports, storage schemas,
Lightning lifecycle, or rollout/oracle behavior.

Add an import/dependency assertion or focused static scan proving:

- `vin/models/target_finite_horizon.py` does not import oracle supervision;
- `oracle/environment.py` does not import Lightning, optimizer, or store-writer
  orchestration;
- `rollouts/replay/**` does not import `oracle/**`, Lightning, or the Q_H
  pipeline;
- `online_qh.py` privately adapts bound contexts to existing `CandidateScores`
  and composes without reimplementing renderer/RRI/store schemas;
- `pose_generation/hierarchical_proposer.py` does not import hard-oracle
  internals; and
- no new generic `rl`, registry, simulator, replay-service, or dashboard package
  appears.

WP0a refreshes the machine-readable schema and concrete rows at
`.omx/specs/online-oracle-issue-acceptance.md`. A test or review assertion
rejects unknown dispositions, missing required row fields, or
`closed`/`satisfied` status for either issue while any broader reset/step or
live-policy-decision row is `needs_issue_amendment` or
`needs_follow_up_issue`.

## Review and publication gate

For each PR-sized implementation slice:

1. focused tests and static checks pass;
2. changed behavior has an immutable evidence artifact or an explicit gap;
3. an independent code reviewer reports no actionable P0-P2 findings;
4. an independent verifier checks the claimed contract and test adequacy;
5. exact branch/head/diff/checks are re-read before push;
6. only request-owned paths are staged; and
7. the draft PR is updated with completed work-package evidence and remaining
   scientific gates.

The Ralplan planning artifacts and local Architect/Critic reviews are not an
execution receipt. Source implementation, Ultragoal activation, and execution
publication remain blocked until an official host-issued consensus receipt is
verified through a documented host surface.
