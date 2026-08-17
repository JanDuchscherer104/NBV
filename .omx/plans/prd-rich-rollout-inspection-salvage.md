# PRD: Selective rich rollout inspection salvage

Status: locally approved by Ralplan Architect and Critic; execution authorized by the user's explicit 2026-08-17 Ultragoal and Team launch receipt
Context: `.omx/context/rich-rollout-inspection-salvage-20260817T130157Z.md`  
Historical evidence: PR #32 `70fc7fcb`, PR #38 `a8ff3d6b`  
Current implementation baseline: `823a945da19852e4ac2b6ac8750ca9c5abfe0263`

## Outcome

Ship one separate read-only inspection PR that selectively restores the useful
missing scientific and store-local Q_H evidence views from PRs #32/#38. The result
must deepen the current presentation-free inspection, reporting, read-model,
and Q_H seams; preserve all current inspection features; and avoid importing
historical generation, collection, session-service, schema, or confirmatory
audit architecture.

The implementation branch starts in a fresh worktree after PR #62 is merged
into `origin/main`. If work must start earlier, it may be stacked on exact PR
#62 head but must not target `main` until the generation seam is available.

## RALPLAN-DR summary

### Principles

1. One scientific fact has one presentation-free owner.
2. Historical code is behavioral evidence, not merge authority.
3. Every displayed aggregate exposes its denominator, exclusions, units, and
   cohort identity.
4. Expensive reads are explicit, bounded, cached by validated store identity,
   and never run on initial page load.
5. Generation and inspection remain separate: inspection reads validated
   promoted artifacts and cannot control campaign execution.

### Decision drivers

1. Scientific correctness and fail-closed provenance.
2. Minimal change to the already-capable current inspector.
3. Reviewable delivery without schema, dependency, or service expansion.

### Viable options

#### Option A — Deepen current seams incrementally (chosen)

- Add typed projections to `rollouts/inspection.py`, deterministic report
  frames to `rollouts/reporting.py`, store-local Q_H evidence through current
  validation/readers,
  and lazy sections to the current stored-rollout page.
- Pros: smallest ownership change; preserves current query, paired-comparison,
  export, and Rerun functionality; permits owner-disjoint commits.
- Cons: `_stored_rollouts_page.py` remains large unless small presentation-only
  extraction becomes justified during implementation.

#### Option B — Port PR #38's modular `StoredRolloutSession` UI

- Pros: clear section modules and centralized cache surface.
- Cons: duplicates current data-access ownership, imports obsolete audit/session
  assumptions, risks regression of current features, and produces a broad
  rewrite rather than selective salvage.
- Rejected for this PR.

#### Option C — Cherry-pick or rebase PR #32/#38 wholesale

- Pros: fastest apparent feature count.
- Cons: revives `rollouts.collection`, mixes generation and inspection,
  overwrites newer contracts, and obscures which behavior remains valid.
- Invalidated by the two-PR boundary and current source ownership.

## Requirements

### R1. Validated read-only boundary

- All scientific and Q_H views accept only stores admitted by the current Zarr
  validator and current campaign/store binding checks.
- Missing, stale, malformed, ambiguous, unsupported, or tampered evidence is
  displayed as unavailable or blocking; it is never coerced into a numeric zero
  or successful status.
- No write is made to rollout stores, manifests, campaign status, or source VIN
  stores.

Owners:

- `aria_nbv/aria_nbv/rollouts/zarr_store.py`
- `aria_nbv/aria_nbv/rollouts/read_model.py`
- `aria_nbv/aria_nbv/rollouts/inspection.py`

### R2. Header, reference coverage, and storage footprint

Extend current inventory/statistics projections around
`rollout_store_inventory_rows()` and `runtime_storage_statistics()` to expose:

- scenes, targets, rollouts, and candidate rows; Q_H trainable rows only when
  persisted metadata proves them or after an explicit deep mask-count action;
- reference-source coverage and explicit coverage gaps when provenance provides
  a valid denominator;
- per-source logical row counts plus whole-store physical bytes and normalized
  whole-store byte costs;
- unavailable reasons when reference coverage is not provable.

Normalized storage means exactly two whole-store diagnostic fields:
`physical_bytes_per_rollout = physical_store_bytes / rollout_rows` and
`physical_bytes_per_candidate = physical_store_bytes / candidate_rows`, both
in bytes. Emit `unavailable` when the respective denominator is zero or not
provable. These ratios describe the whole store and are never partitioned or
attributed to a source.

The Streamlit Trust & Topology workspace adds compact cards and two plots:
reference coverage and logical per-source row footprint. Reporting exports the
same typed rows; the UI does not recompute them. Zarr chunk bytes are never
attributed to individual sources.

Historical behavior reference:

- PR #38 `overview_topology.py:87-365`
- PR #38 `inspection.py:273-472`

### R3. Reconstruction and declared return

Add presentation-free projections equivalent in behavior to PR #38:

- `reconstruction_metric_summary_rows()`;
- `reconstruction_endpoint_rows()`;
- `reconstruction_endpoint_summary_rows()`;
- `discounted_rollout_return_rows()`.

Semantics:

- reconstruction trajectories use persisted factual steps only;
- endpoint values use the greatest valid persisted factual step;
- discounted return is admitted only for the declared
  `return_semantics == "cumulative_target_root_gain"` contract and uses factual
  per-transition `selected_target_root_gain` with persisted `discount_gamma`;
  it never substitutes cumulative root-gain columns;
- discounted return remains distinct from endpoint gain, including at gamma 1;
- missing/nonfinite gains or undeclared gamma make the affected result
  unavailable with a reason.

The Scientific Evidence workspace adds compact temporal and endpoint plots plus
downloadable typed tables.

Historical behavior reference:

- PR #38 `inspection.py:708-854`
- PR #32 richer reconstruction plot variants are presentation references only.

### R4. Oracle headroom with honest denominators

Add an `oracle_headroom_evidence()`-equivalent projection beside current
`rollout_endpoint_metric_summary()`, `comparable_policy_cohorts()`, and
`paired_policy_comparison_rows()`.

This is explicitly diagnostic proxy evidence over the persisted
`final_cumulative_target_root_gain`; it is not the audited confirmatory return
J. Build it directly from the current policy projection rows without using or
changing `comparable_policy_cohorts()` eligibility. Map frozen semantic roles
from the exact
`(policy, branch_schedule)` identifier tuple as follows:

- `("oracle_greedy", "oracle_greedy")` -> `oracle_one_step`;
- `("oracle_greedy", "oracle_lookahead")` and
  `("oracle_greedy", "oracle_lookahead_diverse")` -> `oracle_lookahead`;
- `("q_h", "q_h")` -> `q_h`;
- `("learned_one_step", "learned_one_step")` -> `learned_one_step`.

Neither `rollout_recipe` nor a synthesized `comparison_label` participates in
role assignment, even when its string value matches a branch-schedule token.
Unsupported or incomplete `(policy, branch_schedule)` tuples fail closed.

Headroom uses a new local invariant key; it does not modify
`_POLICY_COHORT_KEY_FIELDS` or current paired-policy semantics. The invariant
key contains source sample key/index, target ID/protocol, horizon/acquisition
budget, candidate-config hash, oracle-config hash, validated store
`manifest_sha256`, shard `writer_config_hash`, and, when present, campaign
binding fields `campaign_id`, `plan_hash`, `work_unit_hash`, `profile_hash`,
and `explicit_target_hash`.

Semantic treatment fields are deliberately not invariant-key fields:
`policy`, `branch_schedule`, `branch_factor`, `beam_width`, and
`rollout_recipe` define or describe the treatments being contrasted. Each is
retained verbatim as role evidence, and more than one row for the same semantic
role and comparison condition is an explicit duplicate-role exclusion. This
permits the intended one-step/lookahead/Q_H/learned contrasts without silently
equating their treatment configurations.

Normalize persisted policy-inapplicable temperature (`NaN`) and random seed
(`-1`/missing only when the policy contract declares it inapplicable) to the
typed sentinel `not_applicable`; malformed nonfinite values for an applicable
policy fail closed. For a contrast, all applicable temperature values must
match each other exactly, as must all applicable random seeds. A
`not_applicable` value is ignored only for its definitionally inapplicable
role; it is never a wildcard for missing evidence on an applicable role. The
result carries the normalized comparison condition plus every role's treatment
identity.

A validated legacy store without campaign binding remains store-local through
its manifest digest and persisted invariant/config identities and cannot be
paired across stores. Any invariant/provenance mismatch excludes the contrast.

For one exact compatible cohort, require exactly one finite endpoint row for
each role used by a contrast, then compute:

- `delta_look = J_proxy(oracle_lookahead) - J_proxy(oracle_one_step)`;
- `delta_Q = J_proxy(q_h) - J_proxy(learned_one_step)`;
- `headroom_denominator = J_proxy(oracle_lookahead) -
  J_proxy(learned_one_step)`;
- `eta_Q = delta_Q / headroom_denominator` only when the raw denominator is
  strictly greater than the frozen diagnostic threshold `1e-8`.

No epsilon is added to the denominator. Equal compatible endpoints are valid
zero deltas. A nonpositive or weak denominator excludes only `eta_Q` with the
reason `nonpositive_or_weak_headroom`; it does not turn valid delta rows into
missing evidence.

Every contrast reports the exact eligible-cohort count, included count,
excluded count, and reason counts, with `eligible = included + excluded`.
Reasons cover missing role, duplicate role, nonfinite endpoint, incompatible
invariant/provenance identity, incompatible applicable temperature/seed, and
weak/nonpositive headroom where applicable. Every row carries the local
invariant identity, each role's treatment fields, and exact scene support. No
pooled headline is displayed without those denominators.

Historical behavior reference:

- PR #38 `inspection.py:867-1001`, `4051-4653`
- PR #38 `aria_nbv/aria_nbv/app/panels/_stored_rollouts/oracle_headroom.py:28-76`

### R5. Candidate composition, calibration, collision, and support

Reuse one materialized `candidate_audit_rows()` projection per validated store.
New reducers must accept those rows rather than reread Zarr data.

Salvage only the bounded useful behavior of:

- component/family composition by allocated, actor-valid, oracle-valid,
  trainable, and selected populations;
- proposal calibration and selection enrichment;
- existing geometry fields plus collision/support availability;
- deterministic bounded display samples that are visibly labeled descriptive;
- state-then-scene macro aggregation for these bounded summaries;
- exact generation-cohort separation and explicit missing evidence.

Use the existing ordered typed grouping vocabulary in `rollouts.inspection`.
Unsupported grouping keys fail closed. A display sample must never become the
scientific denominator.

Novel directional reference grids, spherical-cap statistics, broad motion
reducers, and other historical scientific-audit projections are deferred until
a concrete debugging question requires them.

Historical behavior reference:

- PR #38 `inspection.py:1438-1777` plus only collision/support behavior from
  `2057-4011`
- PR #32 exploratory plot variants may guide visual form, not aggregation truth.

### R6. Store-local Q_H evidence

Expose only Q_H facts owned by one validated rollout store:

- persisted contract/provenance and array availability;
- actor-valid, oracle-valid, trainable, padding, and admitted-chain counts when
  persisted metadata proves them or after an explicit deep mask-count action;
- source/target/rollout/step lineage for a selected row already handled by the
  current inspector;
- explicit unavailable/blocking reasons for V1 label failure, binding mismatch,
  malformed arrays, or ambiguous row lineage.

Canonical full-store validation remains the mandatory existing payload scan.
After that validation, initial UI rendering performs no additional Q_H count
scan. An explicit deep-count action may perform one additional bounded mask
projection only when the validated result or manifest does not already provide
the count. This PR does not inspect experiment configs, construct
`QhDataModule`, decide train/validation/test stage admission, prove scene
disjointness, materialize a loader batch, or launch training. Those behaviors
remain owned by Training Dataset, `QhDatasetConfig`, and `QhDataModule`, and may
be enhanced in a later Training Dataset PR.

Current owner references:

- current `qh_reader.py:65-490`
- current `training_dataset.py:338+`
- current `lightning/qh_datamodule.py:35+`

### R7. Physical topology and export

Retain the current textual topology/tree, evidence-bundle, CSV/JSON,
selected-depth, query, and Rerun features unchanged. A new physical Zarr
topology visualization is explicitly deferred because current validation and
textual topology already cover the debugging need; it is not a deliverable of
this PR.

All new projection tables are included in the existing deterministic report
bundle. Existing acknowledged `pilot` and `confirmatory` export labels remain
unchanged; this PR adds no sealing or confirmatory-audit infrastructure.

### R8. Lazy presentation structure

Keep `read_model.py`, `inspection.py`, `reporting.py`, and `qh_reader.py`
Streamlit-free. The page remains a client.

Implementation may extract new presentation-only renderers under
`app/panels/_stored_rollouts/` if and only if:

- they receive already-created readers/projection rows or shallow callbacks;
- they cannot instantiate Zarr readers or own cache identity;
- existing current-page sections are not rewritten merely for symmetry.

Every new heavy projection is routed through the existing cache functions with
the canonical store path, projection arguments, and a lightweight validated
manifest/metadata identity. No session or cache service is introduced.

## Explicit exclusions

- `rollouts.collection` or any collection abstraction;
- wholesale cherry-pick, merge, or rebase of PR #32/#38;
- a generic inspection service, reader protocol, or plotting framework;
- rollout Zarr schema, target arrays, `TargetLineage`, or V0/V1 changes;
- campaign generation/status/control, automatic polling, daemon, kill/delete,
  or Rerun monitoring;
- automatic Q_H materialization or training launch;
- new dependency;
- full `scientific_audit.py` sealing, confirmatory export gating, or automatic
  six-metric reconstruction plan.

## PR #32 visual parity and disposition

This table is the exhaustive PR #32 salvage boundary. “Retain” means the
current equivalent remains unchanged; “salvage” means rebuild the behavior on
current typed projections; “defer” and “reject” are deliberately outside this
PR.

| PR #32 behavior | Decision | Current owner/target | Required proof |
|---|---|---|---|
| Temporal reconstruction small multiples | Retain | current `_render_temporal_explorer` | existing temporal-explorer regression remains green |
| Factual endpoint histogram plus marginal box | Salvage | reconstruction endpoint rows plus presentation-only renderer | hand-calculated endpoint fixture and plot-field snapshot |
| Endpoint policy-by-horizon summary | Salvage | reconstruction endpoint summary rows | stable typed-row and UI table assertions |
| Raw factual rollout drilldown | Reject as duplicate | current query workbench and step table | current drilldown tests remain green; no second browser |
| Marginal generator composition | Salvage | reducers over one `candidate_audit_rows()` projection | population-conservation fixture |
| Actor-validity support bars | Salvage | candidate support reducer | allocated/valid/rejected conservation fixture |
| Joint component/recipe table | Salvage | typed component/family grouping vocabulary | exact grouping/order fixture |
| Proposal calibration scatter | Salvage | calibration rows | hand-calculated proposal/selection fixture |
| Target-normalized motion/reference grid | Defer | current geometry rows remain available | explicit absence from PR diff |
| Collision/support plot | Salvage | current collision/support fields | availability and missing-evidence fixture |
| Selection preference/enrichment | Salvage | proposal-versus-selection reducer | exact numerator/denominator fixture |
| Rank/regret/gain diagnostics | Retain | current target/candidate scientific views | current regressions remain green |
| Semantic-role endpoint distributions/by horizon | Salvage when exact roles exist | oracle-headroom proxy rows | role and exact-cohort admission fixtures |
| `delta_look` cards/histogram/horizon curve | Salvage | exact formulas in R4 | hand-calculated delta fixtures |
| `eta_Q` histogram/table | Salvage | exact thresholded formula in R4 | positive, zero, weak, and negative denominator fixtures |
| Epsilon-stabilized `eta_Q` | Reject | none | regression proves raw-denominator rule |

## PR #38 source parity and disposition

| PR #38 surface | Decision | Historical exact source | Current owner/proof |
|---|---|---|---|
| Header, reference coverage, logical/physical storage summary | Salvage selectively | `aria_nbv/aria_nbv/app/panels/_stored_rollouts/overview_topology.py:87-380`; `aria_nbv/aria_nbv/rollouts/inspection.py:273-472` | R2 typed rows plus T2 arithmetic/availability tests |
| Reconstruction and declared return | Salvage | `aria_nbv/aria_nbv/app/panels/_stored_rollouts/reconstruction_return.py:1-103`; `aria_nbv/aria_nbv/rollouts/inspection.py:708-854` | R3/T3 current-reader reducers |
| Oracle headroom diagnostics | Salvage under stricter local key | `aria_nbv/aria_nbv/app/panels/_stored_rollouts/oracle_headroom.py:1-79`; `aria_nbv/aria_nbv/rollouts/inspection.py:867-1001,4051-4653` | R4/T4 exact-role proxy contract |
| Candidate evidence | Salvage bounded subset | `aria_nbv/aria_nbv/app/panels/_stored_rollouts/candidate_generation.py:1-249`; `aria_nbv/aria_nbv/rollouts/inspection.py:1438-4011` | R5/T5 one-audit-row projection; broad audit reducers remain deferred |
| Store-local Q_H masks/counts/provenance | Salvage | `aria_nbv/aria_nbv/app/panels/_stored_rollouts/qh_admission.py:30-180` | R6/T6 current Q_H readers, no dataset-stage claim |
| Q_H experiment-config discovery, stage admission, DataModule/loaders | Reject from this PR; defer to Training Dataset owner | `aria_nbv/aria_nbv/app/panels/_stored_rollouts/qh_admission.py:1-639` | static no-import/no-launch checks and current Training Dataset tests |
| Physical Zarr topology visualization | Defer | `aria_nbv/aria_nbv/app/panels/_stored_rollouts/overview_topology.py:382-538` | retain current textual topology regression only |
| Confirmatory audit, sealing, metric-plan execution | Reject from this PR | `aria_nbv/aria_nbv/rollouts/scientific_audit.py:1-1485` | existing pilot/confirmatory labels unchanged; static absence checks |
| Collection abstraction | Reject | `aria_nbv/aria_nbv/rollouts/collection.py:1-642` | no production import regression |
| `StoredRolloutSession` and modular lifecycle/cache UI | Reject as obsolete duplicate owner | `aria_nbv/aria_nbv/app/panels/_stored_rollouts/session.py:1-937` | deepen current page/cache seam; no new session/service |

## Implementation work packages and commit boundaries

### WP0 — Branch and behavior baseline

1. Wait for PR #62 merge, fetch exact `origin/main`, and create a fresh
   `codex/rich-rollout-inspection-salvage` worktree/branch.
2. Record base SHA, PR #32/#38 SHAs, and existing focused-test baseline.
3. Add characterization fixtures only where current behavior lacks coverage.

Commit: tests/docs only if a behavior lock is needed.

### WP1 — Coverage and reconstruction projections

Owner: `rollouts/inspection.py`, `tests/rollouts/test_inspection.py`.

1. Add header/reference/storage projections through current inventory helpers.
2. Add reconstruction and declared-return projections.
3. Use hand-calculated fixtures and explicit unavailable reasons.

Commit: `feat(rollouts): restore coverage and reconstruction evidence`.

### WP2 — Oracle headroom and reporting

Owner: `rollouts/inspection.py`, `rollouts/reporting.py`, their focused tests.

1. Add the exact semantic-role and formula contract from R4 with typed
   denominator/exclusion rows.
2. Add all WP1/WP2 tables to deterministic reporting.
3. Prove reporting reuses projections and never executes an audit pipeline.

Commit: `feat(rollouts): restore oracle headroom reporting`.

### WP3 — Bounded candidate evidence reducers

Owner: `rollouts/inspection.py`, candidate evidence tests.

1. Reuse one candidate audit projection.
2. Add population conservation, proposal-versus-selection enrichment, and
   collision/support availability over existing geometry fields.
3. Preserve exact cohorts, state-then-scene macros, and deterministic display
   sampling.

Commit: `feat(rollouts): restore candidate evidence projections`.

### WP4 — Store-local Q_H evidence

Owner: `rollouts/inspection.py`, existing `qh_reader.py` validation helpers when
needed, and focused inspection/Q_H reader tests.

1. Add metadata-first store-local Q_H availability/provenance rows.
2. Add an explicit deep action for mask counts only when metadata lacks them.
3. Reject invalid V1 labels, binding mismatch, malformed arrays, and ambiguous
   row lineage without entering dataset-stage ownership.

Commit: `feat(rollouts): expose store-local QH evidence`.

### WP5 — Lazy Streamlit views

Owner: `_stored_rollouts_page.py`, optional presentation-only section modules,
`tests/app/panels/test_stored_rollouts_scientific_views.py` (new), and the
existing `test_counterfactual_rollouts_panel.py` regression owner.

1. Add header/coverage/storage plots.
2. Add reconstruction/return and oracle-headroom views.
3. Add candidate evidence workspace controls.
4. Add store-local Q_H metadata and explicit deep-count controls.
5. Preserve query, export, selected-depth, and Rerun behavior.

Commit: `feat(app): restore rich rollout inspection views`.

### WP6 — Integration and publication gate

1. Run focused and package-level verification.
2. Run changed-files ai-slop-cleaner, then rerun verification.
3. Run independent code-reviewer and architect audits.
4. Rebase onto then-current `origin/main`; treat pre-rebase results as stale and
   rerun all gates.
5. Open one separate draft inspection PR. Do not modify PR #62 or historical
   PRs #32/#38.

Commit: only surgical review repairs, each owner-disjoint where practical.

## Acceptance criteria

1. Every new UI number/plot is produced from a presentation-free typed row and
   exposes denominator, exclusions, units, and cohort identity where applicable.
2. Invalid/tampered/unvalidated stores render no scientific or Q_H result.
3. Reconstruction endpoint and discounted-return fixtures match hand-calculated
   values; missing/nonfinite/gamma-absent cases are explicitly unavailable.
4. Oracle headroom rejects identity mismatch, duplicate semantic roles,
   nonfinite rows, and insufficient pairing; included plus excluded equals total.
5. Bounded candidate evidence reducers use one audit projection, exact cohorts,
   and equal-state then equal-scene macro weighting; display samples are
   descriptive only.
6. Store-local Q_H evidence uses canonical readers, preserves V0/V1 behavior,
   rejects ambiguous/tampered provenance, and never claims dataset-stage
   readiness.
7. Canonical validation remains unchanged; after validation, initial page render
   performs neither an additional Q_H count projection nor a full normalized
   candidate-audit projection. Tests count post-validation projection calls as
   zero until their deep controls are activated.
8. Current target/support, paired comparison, query workbench, evidence export,
   selected-depth, and Rerun tests remain green.
9. No changes occur to rollout schema, target arrays, `TargetLineage`, campaign
   status, generation controls, or source VIN stores.
10. No `collection.py`, generic service/protocol, new dependency, automatic
    polling, or confirmatory sealing infrastructure is introduced.
11. Deterministic report bundles contain the new tables with stable ordering and
    current CLI delegation remains byte-equivalent.
12. The final rebased SHA passes focused tests, all `tests/rollouts`, relevant
    app tests, Ruff format/check, compileall, `git diff --check`, independent
    code-reviewer APPROVE, independent architect CLEAR, and hosted CI.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Historical reducers encode stale schema assumptions | Port behavior test-first against current `RolloutZarrStoreReader`; never copy whole modules. |
| Scientific plots silently pool unequal candidate mass | Require exact cohorts and state-then-scene macro fixtures. |
| Page load becomes unusably expensive | Explicit controls, call-count tests, lightweight manifest identity in current cache keys, and bounded deep actions. |
| Giant page becomes harder to review | Extract only new presentation renderers when they remain reader-free clients. |
| Q_H display drifts into dataset-stage ownership | Limit it to one store's masks/provenance; defer config, stage, loader, and scene-disjointness behavior to Training Dataset. |
| Stacked branch obscures generation dependency | Prefer post-merge branch; otherwise target PR #62 explicitly and retarget only after merge. |
| Current features regress during historical salvage | Run current focused suite after every work package and retain behavioral owners. |

## Verification commands

```text
cd aria_nbv
uv run pytest -q tests/rollouts/test_inspection.py tests/rollouts/test_reporting.py tests/rollouts/test_qh_reader.py
uv run pytest -q tests/rollouts
uv run pytest -q tests/app/panels/test_counterfactual_rollouts_panel.py tests/app/panels/test_stored_rollouts_scientific_views.py tests/app/panels/test_training_dataset_panel.py
uv run ruff format --check <touched-files>
uv run ruff check <touched-files>
uv run python -m compileall aria_nbv/rollouts aria_nbv/app/panels
git diff --check
```

## ADR

### Decision

Selectively transplant behavior into the current presentation-free seams and
current lazy page, delivered as one separate inspection PR after PR #62.

### Drivers

- trustworthy scientific denominators and provenance;
- minimum architecture change;
- preservation of current functionality and schema.

### Alternatives considered

- Port PR #38's modular session/page architecture.
- Merge or cherry-pick either historical branch wholesale.
- Add only plots without presentation-free reducers.

### Why chosen

The current repository already has the reader, inspection, reporting, Q_H,
query, export, and Rerun seams. Deepening them adds missing behavior without a
second owner or historical generation coupling.

### Consequences

- More functions remain in `inspection.py`; cohesion must be reviewed after the
  feature work, but no speculative abstraction is authorized.
- Confirmatory audit sealing remains unavailable by design.
- The inspection PR depends on PR #62's validated artifact handoff.

### Follow-ups

- Consider confirmatory audit sealing only when a concrete thesis/export
  protocol requires it.
- Plan dataset-stage Q_H readiness, scene disjointness, and optional loader
  materialization separately under the existing Training Dataset owner.
- Consider candidate-seed diversity separately from inspection salvage.
- Reassess presentation extraction after behavior is stable, not before.

## Available agent roster and execution staffing

Available roles: `explore`, `executor`, `test-engineer`, `verifier`,
`code-reviewer`, `architect`, `code-simplifier`, `git-master`.

Recommended durable lane: `$ultragoal` with a phase-gated `$team`.

- Leader/Ultragoal: owns ledger, sequencing, integration, and PR boundary.
- Projection executor, medium reasoning: owns WP1-WP4 serially because they all
  modify `rollouts/inspection.py`; commits each work package and freezes the
  typed row schemas before UI work begins.
- UI executor, medium reasoning: starts after the row-schema freeze and owns
  WP5 presentation files only.
- Test engineer, medium reasoning: after the schema freeze, owns new focused
  fixture/test files and lazy-call proofs; it must not concurrently edit a test
  file owned by the projection executor.
- Verifier, high reasoning: exact-ref parity, schema invariants, rebased gates.
- Code reviewer, high reasoning: final P0-P2 review.
- Architect, xhigh reasoning: boundary and scientific-invariant audit.
- Git master, high reasoning: post-PR62 base creation and terminal rebase.

Launch hints after an official execution receipt:

```text
$oh-my-codex:ultragoal .omx/plans/prd-rich-rollout-inspection-salvage.md
omx team 3:executor "Implement the approved rich rollout inspection salvage plan with a serial WP1-WP4 projection lane and a schema-freeze barrier before UI/tests."
```

Team verification path:

1. Projection executor completes WP1-WP4 serially and returns one focused
   commit/evidence bundle per package.
2. Leader records a typed-row schema freeze and releases WP5 plus independent
   new-test-file work.
3. UI executor and test engineer return owner-disjoint commits, tests, and
   invariant evidence.
4. Leader integrates only owner-disjoint commits and checkpoints Ultragoal.
5. Git master rebases after PR #62/main synchronization.
6. Verifier reruns every test and CLI/export proof on the rebased SHA.
7. Independent code reviewer and architect gate publication.

Goal-mode guidance: use `$ultragoal` by default; combine with `$team` because
WP1-WP4 share one serial projection owner; only presentation and independent
test files parallelize after the interface freeze. `$performance-goal` is only
appropriate for a later measured
inspection-latency optimization. `$autoresearch-goal` is unnecessary because
the historical comparison is already evidence, not the product. `$ralph` is a
fallback only for an explicitly requested single-owner persistent repair loop.

## Planner changelog

- Chose current-seam deepening over historical session/module import.
- Added exact scope for all high-value missing features from the prior matrix.
- Made denominators, exclusions, lazy reads, and store-local Q_H deep counting
  explicit acceptance gates.
- Added post-PR62 branching, owner-disjoint commits, staffing, and rebased
  verification requirements.
- Applied Architect iteration: moved stage/config/materialization work to a
  later Training Dataset PR and corrected equality, return, footprint, export,
  cache, and candidate-scope contracts.
- Applied Architect iteration 2: defined laziness relative to mandatory
  validator reads and explicitly deferred new physical-topology visualization.
- Applied Critic iteration 1: froze the diagnostic oracle-role/formula and
  denominator contracts, corrected the historical UI path, added exhaustive
  PR #32 visual disposition/proofs, assigned a real new panel-test owner, and
  serialized all shared `inspection.py` work behind a schema-freeze barrier.
- Applied Architect iteration 3: named `(policy, branch_schedule)` as the sole
  semantic-role key and explicitly rejected recipe/label aliases.
- Applied Critic iteration 2: added a headroom-only strict compatibility key,
  exhaustive PR #38 source dispositions, and exact whole-store byte
  normalization formulas.
- Applied Architect iteration 5: replaced the impossible shared-cohort-derived
  key with a direct headroom invariant key, separated treatment identity from
  invariants, and defined typed policy-inapplicable temperature/seed handling.
