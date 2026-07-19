---
id: 2026-07-19_stored_rollout_inspector_regression_repair
date: 2026-07-19
title: "Stored Rollout Scientific Inspector And Regression Repair"
status: done
topics: [streamlit, rollouts, inspection, performance, rich, ralplan, ultragoal]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/aria_nbv/utils/rich_summary.py
  - aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py
  - aria_nbv/tests/rollouts/test_inspection.py
  - aria_nbv/tests/utils/test_rich_summary.py
  - docs/contents/setup.qmd
---

## Task

Repair Stored Rollouts UI regressions and complete the consensus-planned
scientific workflow: interpretable temporal population summaries, factual
candidate-provenance flow, and flexible row querying/promotion into Inspect and
Rerun.

## Method and findings

- Replaced the segmented workspace selector with Streamlit 1.57 lazy tabs using
  `on_change="rerun"` and each tab's `open` state.
- Restored endpoint, branching, fanout, family-provenance, target-score,
  candidate-breakdown, root-relative geometry, angle, motion, and reward plots
  with complete scientific explanation popovers.
- Kept expensive branching/rank and candidate-level traces explicitly
  loadable, then cached by immutable store path.
- Changed discovery to skip deep validation for every store and validate only
  the selected store. Preloaded candidate arrays once instead of rereading
  whole Zarr arrays per candidate row.
- Made evidence-bundle construction lazy through callable download data.
- Repaired stale Streamlit download URLs exposed by the direct browser run. The
  root cause was eager `download_button` payload registration: a rerun replaced
  the media-file entry before the browser fetched its generated URL, producing
  a 404. CSV and JSON downloads now use deferred callable payloads with
  `on_click="ignore"`, so serialization and URL registration happen only when
  the user downloads the artifact.
- Forced `capture_tree` to use an ANSI-free Rich console for Streamlit and log
  text surfaces.
- Ran the requested Ralplan consensus gate and persisted the approved plan,
  Architect review, Critic approval, and test specification under `.omx/plans/`.
- Ultragoal G001 added exact temporal-summary rows and a narrow, count-conserving
  candidate flow. Temporal statistics use finite-only deterministic linear
  quartiles and explicit total/finite/missing counts. The candidate flow reads
  categorical provenance and masks without materializing geometry, reward,
  depth, oracle-label, or `q_train` arrays.
- Ultragoal G002 replaced default multi-rollout traces with one-metric
  median/IQR summaries, honest upstream versus selected-action-provenance
  grouping, a one-rollout raw drill-down, and the candidate provenance/support
  Sankey. Heavy restored candidate-audit plots remain explicit.
- Ultragoal G003 added store/scope/population-namespaced trusted-local pandas
  querying, deterministic complete CSV exports, last-valid-result recovery, and
  validated pending promotion into rollout/step selectors before widget
  instantiation. Explicit full-store candidate queries remain opt-in.
- Ultragoal G005 repaired the independent-review findings. The headline endpoint
  statistic now selects one terminal factual step per rollout, retains mixed
  horizons, uses finite values only, and reports the exact finite/total rollout
  denominator. It summarizes the already-loaded step projection rather than
  rereading the store. Temporal roles are explicit: selection probability,
  entropy, fanout, and invalid fraction are actor-visible; gain/RRI and
  rank/regret are oracle/evaluation; derived training-data badges are reserved
  for actual cache/label evidence. The unreachable endpoint renderer was
  deleted.
- Ultragoal G006 routed the restored selected-probability/entropy branching
  plot through the same explicit temporal evidence-role owner, closing the last
  duplicated `derived training data` badge on actor-visible selection evidence.
  A direct render-path test captures the plot explanation and asserts the
  actor-visible role.

On the local 9,600-candidate store, AppTest timings changed from approximately
23.5 seconds to 7.9 seconds for Scientific Evidence, more than 60 seconds to
8.3 seconds for Targets & Action Support, and more than 60 seconds to 12.0
seconds for Inspect, Export & Rerun. Trust & Topology remained approximately
16 seconds on a cold process because selected-store validation and invariant
checks are intentionally complete.

## Verification

- Focused Ruff format/check passed.
- Rollout inspection, Rich summary, and Stored Rollouts AppTests passed.
- Real-store AppTest exercised all five outer tabs without exceptions; restored
  expensive plot groups were also exercised by fixture AppTests.
- Public setup documentation was updated to describe lazy tabs, cache refresh,
  temporal aggregation, candidate-flow semantics, query/promotion behavior,
  exact exports, restored plots, and lazy evidence bundles.
- The deferred-download regression test proves render-time serializers are not
  called, the callable returns the exact complete CSV/JSON bytes, and downloads
  do not trigger a rerun. Focused Ruff checks passed, and the combined rollout
  inspection plus Stored Rollouts AppTests passed with 64 tests.
- Direct Chrome/CDP stress testing against the real Streamlit app produced zero
  severe browser events and an empty final error log. The rollout query read 96
  rows, matched/displayed/exported 30, and promoted rollout/step 1/1. The
  selected-step candidate query read 60 rows and matched/displayed/exported 1;
  the explicit full-store candidate query read 9,600 rows and
  matched/displayed/exported 188. Candidate promotion selected rollout/step
  26/43. An invalid query preserved the last valid result.
- Warm interaction timings were 0.498 s for Scientific Evidence, 0.773 s for
  the target-flow view, and 0.536 s for Inspect. The eight rapid tab switches
  ranged from 0.634 s to 1.246 s. Query timings were 0.418 s for the valid
  rollout query, 0.427 s for invalid-query recovery, 0.628 s for the selected
  step candidate query, and 1.063 s for the explicit full-store candidate
  query.
- At a 900 px viewport, both the body width and inner width were exactly 900 px,
  proving there was no horizontal page overflow. The final evidence directory
  contains the temporal-summary, candidate-flow, query-workbench, and narrow
  viewport screenshots plus the exact 188-row CSV export.
- G005 regression tests cover unequal policy-group sizes, mixed rollout
  horizons, a non-finite terminal value, every selectable temporal evidence
  role, privileged rank/regret, and an exact zero count for candidate-heavy
  projections while their owning control remains unopened. The final combined
  rollout-inspection and Stored Rollouts AppTest suite passed 68 tests.
- The final performance contract used the current 96-rollout, 160-step,
  9,600-candidate store. Cold evidence comprises two phases of five independent
  cache-cleared AppTest processes. Baseline to verification p95 changed from
  11.422 to 11.559 seconds for Trust (+1.20%), 16.173 to 16.002 seconds for
  Scientific (-1.06%), 0.601 to 0.650 seconds for Targets/flow (+8.15%), and
  7.689 to 7.921 seconds for selected-step query (+3.02%); every surface stayed
  below the predeclared 20% material-regression boundary.
- The same-process warm matrix used one warm-up plus five measured repetitions
  per surface in both baseline and verification phases. Trust, Targets/flow,
  and selected-step query passed directly. Scientific contained one isolated
  0.230-second scheduling outlier among otherwise 0.040-0.044-second samples;
  an independent 1+5/1+5 confirmation moved the isolated outlier to its
  baseline and produced five clean verification samples with p95 0.0418
  seconds and no app exception. The retained judgment is
  `pass_with_explained_warm_scientific_outlier`, not a deletion of the failed
  first p95.
- Earlier approximate 16.0/7.9/8.3/12.0-second figures used the iterative
  AppTest environment without this final independent-process/cache-clear
  protocol. They remain contextual and are explicitly non-comparable; the
  final judgment uses only same-method fresh baseline and verification phases.

Direct browser evidence is recorded in
`.omx/ultragoal/g004-browser-stress.json`; raw cold/warm samples, p95 values,
deltas, and the outlier confirmation are recorded in
`.omx/ultragoal/g005-performance-evidence.json`. The final G006 independent
code review returned APPROVE with no unresolved findings, and the independent
architecture review returned CLEAR. Final verification passed 172 integrated
tests and 73 focused cleanup tests, Ruff format/lint, setup documentation
render, QMD frontmatter validation, Graphify refresh, agent-memory validation,
and diff whitespace checks. The terminal audit is recorded in
`.omx/ultragoal/g006-quality-gate.json`.

## Canonical state impact

No schema, model input, training behavior, or durable research decision
changed. No canonical state update is needed. Direct-app, performance,
cleanup, documentation, graph, memory, independent review, and architecture
gates are closed.

Ledger reconciliation G007/G008 preserved the original failed-review verdicts
and their resolved findings while recording the distinct terminal code-review
APPROVE and architecture CLEAR confirmations.
