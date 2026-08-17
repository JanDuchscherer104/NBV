# Test specification: Selective rich rollout inspection salvage

PRD: `.omx/plans/prd-rich-rollout-inspection-salvage.md`  
Baseline: `823a945da19852e4ac2b6ac8750ca9c5abfe0263`

## Test principles

1. Test presentation-free rows before plots.
2. Use hand-calculated fixtures for scientific reducers.
3. Missing or invalid evidence must fail closed, never become zero.
4. Assert laziness with call counts and bounded reads.
5. Preserve current schema and current user workflows exactly.

## Fixture matrix

Create or extend small deterministic Zarr fixtures covering:

- valid V0 and admitted `v1_observed` targets;
- matched random/softmax/oracle roles with identical exact cohort identity;
- mismatched profile, temperature, horizon, seed, source, target, and config hash;
- finite and nonfinite selected gains;
- declared `return_semantics == "cumulative_target_root_gain"`, gamma values
  1.0 and 0.5, plus missing/unsupported return contracts;
- component/family populations with unequal candidate counts across states and
  scenes;
- collision booleans, clearance values, missing collision evidence;
- Q_H trainable/nontrainable/padding rows and sparse identifiers;
- ambiguous row lineage and tampered campaign/store binding;
- missing reference-source coverage and a valid known denominator.

All fixtures must remain small enough for CPU-only unit tests. Real CUDA is not
required for read-only inspection tests.

## T1. Validation and schema immutability

Tests:

- validated V0 and V1 stores admit inspection projections;
- invalid schema, missing completion evidence, tampered manifest binding, and
  unsupported target validity block scientific and Q_H projections;
- running every new projection leaves all store bytes and array schemas
  unchanged;
- `TargetLineage`, target arrays, source IDs, and Q_H arrays remain unchanged;
- no test imports `rollouts.collection`.

Acceptance:

- every invalid case raises the existing typed failure or returns an explicit
  unavailable/blocking row;
- byte and schema snapshots match before and after inspection.

## T2. Header, reference coverage, and storage footprint

Hand-calculated cases:

- 2 scenes, 3 targets, 4 rollouts, 12 candidate rows, 5 trainable Q_H rows;
- source A owns 8 logical rows and source B owns 4 logical rows;
- known reference denominator 5 with 2 covered scenes produces 40% and gap 3;
- absent denominator produces `unavailable`, not 0%.
- physical store size 1,200 bytes with 4 rollout rows and 12 candidate rows
  produces 300 bytes/rollout and 100 bytes/candidate.

Tests assert:

- counts and byte totals match fixture arrays/files;
- logical source rows sum to total rows where the contract declares a partition;
- physical bytes remain whole-store facts and are never attributed to sources;
- normalized storage exposes only bytes/rollout and bytes/candidate, uses the
  exact whole-store denominators, and is unavailable for a zero/unproved
  denominator;
- reference coverage never infers a denominator from observed rows;
- reporting and UI receive the same typed rows.

## T3. Reconstruction and discounted return

Hand-calculated chains:

- selected gains `[1, 2, 3]`, gamma 1.0 => return 6;
- selected gains `[1, 2, 3]`, gamma 0.5 => return 2.75;
- endpoint reconstruction uses the final factual step only;
- missing and nonfinite gains make return unavailable;
- an incomplete trajectory uses only persisted factual steps and exposes its
  terminal status.

Tests assert:

- return uses `selected_target_root_gain` for each factual transition and never
  substitutes cumulative target/scene root-gain columns;
- endpoint and discounted return remain different fields and labels, including
  at gamma 1;
- no inferred future step is created;
- row ordering is deterministic under input permutation.

## T4. Oracle headroom and exclusions

Construct exact role pairs with known endpoint values.

Tests assert:

- only the frozen `(policy, branch_schedule)` semantic-role mapping admits
  rows; aliases or unsupported tuples fail closed;
- matching tokens present only in `rollout_recipe` or synthesized
  `comparison_label` cannot assign a semantic role;
- the headroom reducer works directly from policy projection rows and neither
  consumes nor changes current `comparable_policy_cohorts()` eligibility;
- its invariant key binds source/target/protocol/horizon/budget,
  candidate/oracle config hashes, validated manifest digest, writer hash, and
  available campaign/profile/work-unit binding;
- policy, branch schedule, branch factor, beam width, and rollout recipe remain
  per-role treatment evidence rather than invariant fields;
- a reader-backed positive fixture with different exact role schedules,
  rollout-config hashes, and policy-inapplicable temperatures produces nonempty
  `delta_look` evidence;
- policy-inapplicable temperature and seed normalize to `not_applicable`, while
  malformed applicable values fail closed;
- applicable temperature/seed or invariant profile, manifest, candidate/oracle
  config, writer, and campaign-binding mismatches exclude a contrast;
- duplicate rows for one semantic role/comparison condition are excluded even
  when their treatment recipes differ;
- legacy stores without campaign binding remain store-local and cannot be
  paired across distinct manifest digests;
- `delta_look = J_proxy(oracle_lookahead) - J_proxy(oracle_one_step)` and
  `delta_Q = J_proxy(q_h) - J_proxy(learned_one_step)` match hand calculations
  over `final_cumulative_target_root_gain`;
- `eta_Q` uses the raw
  `J_proxy(oracle_lookahead) - J_proxy(learned_one_step)` denominator and is
  emitted only when that denominator is strictly greater than `1e-8`;
- no epsilon is added to the denominator;
- total = included + excluded for every cohort;
- exclusion reasons distinguish missing role, duplicate role, identity mismatch,
  nonfinite value, incomplete endpoint, unsupported semantics, and
  `nonpositive_or_weak_headroom` for `eta_Q`;
- equal compatible endpoints are included as valid zero deltas; zero/weak
  headroom excludes only `eta_Q` and never fabricates a ratio;
- invariant profile, horizon, source, target, candidate/oracle config, writer,
  manifest, or campaign-binding mismatches never pair; applicable temperature
  or seed mismatches never pair; treatment recipe/schedule/search fields are
  reported per role rather than falsely required to be equal;
- scene-level support and denominator appear beside every aggregate;
- an empty eligible set produces unavailable evidence rather than NaN/zero.

## T5. Candidate composition and calibration

Tests assert:

- `candidate_audit_rows()` is materialized once per store and reused by every
  candidate reducer/report group;
- component/family counts conserve allocated, actor-valid, oracle-valid,
  trainable, selected, and rejected populations;
- unsupported grouping keys fail closed;
- exact generation cohorts are never pooled;
- scientific summaries macro within state then equally across states and scenes,
  not by raw candidate mass;
- deterministic display samples are order-invariant, bounded, and visibly
  marked descriptive only;
- existing geometry and collision/support fixtures match hand-calculated bins
  and availability/rate values;
- missing geometry/collision evidence is unavailable, not zero;
- missing geometry/collision evidence remains explicit and unavailable.

## T6. Store-local Q_H evidence

Tests assert:

- evidence accepts only stores admitted by current validation/Q_H readers;
- `q_train_mask == actor_action_mask & oracle_label_mask` for valid admitted V1
  rows and legacy V0 behavior is unchanged;
- persisted metadata counts are used when available; otherwise counts remain
  unavailable until an explicit deep mask-count action;
- ambiguous row lineage and tampered binding cannot hand off a row;
- canonical validation remains the mandatory existing payload scan;
- after validation, initial render performs zero additional Q_H count
  projections;
- explicit deep counting performs at most one additional bounded projection over
  the current validated store masks when validated evidence lacks the count;
- no experiment-config discovery, `QhDataModule`, stage split/disjointness
  decision, loader materialization, training loop, optimizer, or worker pool is
  imported or started.

## T7. Streamlit behavior and laziness

Use the existing fake Streamlit harness.

Tests assert:

- new sections render only after store validation;
- after the validator returns, initial page render invokes neither the full
  normalized candidate-audit projection nor an additional Q_H count projection;
- activating one scientific control invokes its heavy projection once and cache
  identity includes canonical store path, projection arguments, and lightweight
  validated manifest/metadata identity;
- changing stores clears store-scoped selections and cannot display stale rows;
- every plot has a `ScientificExplanation` describing semantics, denominator,
  exclusions, units, and limitations;
- Q_H deep mask counting requires a distinct explicit button;
- current query workbench, downloads, selected-depth preview, failure handoff,
  and Rerun launcher tests remain unchanged and passing;
- no campaign run/resume/kill/delete/monitor control appears on the page.

## T8. Reporting and export

Tests assert:

- deterministic report frames include coverage, storage, reconstruction,
  discounted return, headroom, exclusions, candidate composition/calibration,
  and store-local Q_H evidence tables;
- rows have stable schemas and order under store/input permutation;
- reporting reuses the current candidate audit projection;
- CLI output and direct serialization are byte-equivalent;
- malformed sidecars and tampered identities block affected facts;
- existing acknowledged `pilot` and `confirmatory` export labels remain
  unchanged; no new seal or confirmatory-audit claim is introduced;
- reporting imports neither Streamlit nor an audit execution pipeline.

## T9. Historical behavior parity

For each salvaged feature, port the smallest relevant PR #38 fixture or recreate
it against the current reader. Where PR #32 has a richer plot, snapshot the
intended visual fields rather than copying obsolete implementation.

Required parity map:

| Capability | Historical reference | Current target |
|---|---|---|
| Header/coverage | PR38 `inspection.py:273-472` | current inventory/statistics rows |
| Reconstruction/return | PR38 `inspection.py:708-854` | new current inspection rows |
| Oracle headroom | PR38 `inspection.py:867-1001` | exact-cohort headroom rows |
| Candidate evidence | PR38 `inspection.py:1438-4011` | reducers over current audit rows |
| Store-local Q_H evidence | PR38 Q_H mask/provenance displays | current inspection/Q_H reader rows |

PR #38 disposition is also locked by static/source-owner assertions: stage and
DataModule Q_H admission, physical topology, scientific-audit sealing,
`rollouts.collection`, and `StoredRolloutSession` are absent from the new
production path, while header/coverage/storage, reconstruction/return,
headroom, bounded candidate evidence, and store-local Q_H rows have focused
semantic fixtures.

Required PR #32 visual disposition proofs:

- endpoint histogram/marginal box and policy-by-horizon fields are snapshotted;
- generator composition, actor-validity support, joint recipe, calibration,
  collision/support, and selection-enrichment rows match hand calculations;
- exact-role endpoint, `delta_look`, and thresholded `eta_Q` views use only the
  R4/T4 admitted rows;
- current temporal explorer, query drilldown, and rank/regret/gain regressions
  remain green instead of being duplicated;
- no target-normalized reference grid or epsilon-stabilized ratio is added.

Parity means semantic output for the fixture, not identical internal APIs.

## T10. Prohibited architecture checks

Static regressions assert:

- no production import of `rollouts.collection`;
- no new `StoredRolloutSession`, generic inspection service, generic reader
  protocol, or plotting framework;
- no new runtime dependency;
- no mutation calls against Zarr stores;
- no campaign-control import in the rich inspection page;
- no automatic polling, daemon, Q_H stage/config admission, loader/training
  launch, or new confirmatory seal path;
- presentation-free modules do not import Streamlit or Plotly.
- no new physical-topology visualization is required; the existing textual
  topology/tree remains covered by its current regression tests.

## T11. Integration and terminal verification

Run after each work package:

```text
cd aria_nbv
uv run pytest -q tests/rollouts/test_inspection.py tests/rollouts/test_reporting.py tests/rollouts/test_qh_reader.py
uv run pytest -q tests/app/panels/test_counterfactual_rollouts_panel.py tests/app/panels/test_stored_rollouts_scientific_views.py tests/app/panels/test_training_dataset_panel.py
```

Before review:

```text
cd aria_nbv
uv run pytest -q tests/rollouts
uv run pytest -q tests/app/panels/test_counterfactual_rollouts_panel.py tests/app/panels/test_stored_rollouts_scientific_views.py tests/app/panels/test_training_dataset_panel.py tests/app/test_app_router.py
uv run ruff format --check <touched-files>
uv run ruff check <touched-files>
uv run python -m compileall aria_nbv/rollouts aria_nbv/app/panels
git diff --check
```

After rebasing onto then-current `origin/main`, treat all prior results as stale
and repeat the full terminal set. Hosted CI, independent code-reviewer APPROVE,
and independent architect CLEAR are mandatory.

## Exit criteria

- All PRD acceptance criteria have a passing test or explicit exact-source proof.
- No P0-P2 review finding remains.
- The final PR diff contains only read-only inspection/reporting/Q_H/UI/test
  changes and no runtime campaign artifacts.
- PR #32/#38 remain historical evidence; neither branch is merged wholesale.
