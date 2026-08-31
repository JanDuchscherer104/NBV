---
id: 2026-08-30_thesis_q_h_claim_admissibility_figure
date: 2026-08-30
title: "Thesis Q_H claim-admissibility figure"
status: done
topics: [thesis, typst, figures, q-h, scientific-review]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - Makefile
  - docs/typst/thesis/experiment_data.typ
  - docs/typst/thesis/figures/qh_learning_evidence_loop.typ
  - docs/typst/thesis/sections/01-research-questions.typ
  - docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ
  - docs/typst/thesis/sections/05-experimental-design/index.typ
  - docs/typst/thesis/sections/05-experimental-design/05-01-objectives-and-hypotheses.typ
  - docs/typst/thesis/sections/05-experimental-design/05-02-learning-objective-and-replay-evidence.typ
  - docs/typst/thesis/sections/05-experimental-design/05-03-policy-comparison-and-failure-interpretation.typ
  - docs/typst/thesis/sections/06-results.typ
  - docs/typst/thesis/sections/07-discussion.typ
  - docs/typst/thesis/sections/08-conclusion.typ
  - docs/typst/thesis/tests/evidence_gate_state.typ
  - docs/typst/thesis/tests/learning_gate_evidence_contract.typ
  - docs/typst/thesis/tests/recovery_evidence_contract.typ
  - docs/typst/thesis/tests/results_full_profile_render.typ
  - scripts/tests/test_typst_report_data_contract.py
codex_thread: codex://threads/01a04fd9-0c7c-7813-a9c5-dc49f2f867a6
repo_object_format: sha1
repo_head: 6ba2e3fbb122b0ae51f10fd48fdec2289aab3a1f
repo_branch: "codex/thesis-figure-qh-evidence-gates"
worktree_kind: linked
---

## Task

Replace the serial Q_H evidence-gate diagram and matching thesis interpretation
with a scientifically correct claim-dependency graph that keeps evidence,
decision, and claim admissibility distinct.

## Method

Located the exact Experimental Design and Results owners, froze standalone and
page-size baselines, applied Fletcher and Typst guidance to a bounded DAG,
synchronized the report-data state helpers, rendered color and grayscale
evidence, and iterated independent professor/scientific and student/visual
reviews until zero P0--P2 findings remained.

## Findings

- Measurement and population/action support are shared foundations; oracle
  headroom and actor-visible learned-value evidence are parallel claim paths.
- Endpoint recovery requires admissible headroom and learned-versus-exact
  `Q_2` agreement. A measured non-pass remains reportable and does not suppress
  evidence from the other lane.
- `docs/typst/thesis/experiment_data.typ` now requires exact boolean decision
  passage and derives claim admissibility separately from evidence presence.
- `docs/typst/thesis/figures/qh_learning_evidence_loop.typ` and the Experimental
  Design, Results, Discussion, and Conclusion prose now share this dependency
  model and reader-facing terminology.
- Exact-head Codex review found one valid residual P2: the failure-attribution
  matrix still conflated unavailable headroom evidence with an observed
  negative result. Its six prerequisite rows now distinguish unresolved
  evidence from a measured decision non-pass explicitly.
- Exact-head rereview found a second valid P2: the recovered-headroom ratio
  could be printed while its headroom denominator was inadmissible. Ratio
  publication now requires admissible headroom.
- A third exact-head P2 showed that ratio rows did not prove independently
  auditable matched endpoints. The accepted contract now keeps the 12-row
  aggregated per-policy endpoint family separate from 7-row headroom and 8-row
  recovery families. One canonical validator owner freezes counts, units, value
  kinds, aggregation, interval identity and ordering, SHA-256 cohort binding,
  and common sidecar provenance before any ratio or decision is reportable.
- The production predicates and executable fixture share those exact validators.
  Negative cases cover malformed count, digest, unit, value type, interval,
  aggregation, source, cross-family lineage, and incomplete bundles; measured
  headroom non-pass retains endpoint estimates but makes ratio evidence
  unavailable and its decision not decided.
- Final exact-head review found one further P2: a malformed string or integer
  decision could be interpreted as a measured non-pass. The central decision
  helper and all non-contracted gate families now require boolean values;
  explicit negative fixtures preserve malformed decisions as unavailable and
  not decided.
- The subsequent exact-head review found a Q1 denominator-value P2: positive
  row metadata could coexist with a zero or mistyped scene-count fact. A shared
  positive-integer/count-binding helper now binds all Q1 rows to the declared
  scene count and all Q2 rows to the declared independent-unit count; zero,
  string, and mismatched-row fixtures are rejected.
- The next exact-head review found that derived point values could disagree
  with the endpoint means that define them. The canonical owner now verifies
  the headroom difference and recovered-headroom fraction numerically before
  admission; inconsistent point-value fixtures are rejected.
- Two further exact-head findings showed that candidate-support decisions and
  Q1/Q2 learned-gate payloads could carry malformed values, metadata, or
  denominators. Their canonical contracts now bind every metric and decision
  to typed values, explicit ranges, fixed units and aggregations, positive
  populations, and one immutable confirmatory sidecar.
- Adjacent regression review then closed the same fail-open class for study
  population and metric repeatability. Population counts are integer and
  scene-bound. Repeatability binds discrepancy, declared tolerance, repeat
  count, frozen decision-rule identity, and the exact boolean comparison under
  one source. A measured tolerance non-pass remains evidence; inconsistent
  decisions are unavailable.
- Analysis provenance now resolves to exactly one complete confirmatory
  sidecar row with a valid identifier, digest, format, and name/path identity;
  empty, unknown, malformed, or duplicate bindings fail closed.
- The final exact-head P1 showed that a structurally valid sidecar could still
  assert headroom passage independently of its effect and interval. Headroom
  now records a positive manifest-frozen minimum and the rule identity
  `effect_gte_minimum_and_ci_low_gt_zero_v1`; its decision must equal the
  literal point-estimate and lower-bound comparison. The RQ, design, Results,
  Discussion, and Conclusion now distinguish a subthreshold magnitude from an
  interval that does not establish a positive mean effect.
- The closing contract audit repaired the same Boolean-identity gap for
  candidate support, actor-$Q_1$, learned-versus-exact $Q_2$, and endpoint
  recovery. Each decision now equals every declared conjunct; adversarial
  fixtures fail when any point threshold, interval bound, calibration bound,
  selected-chain receipt, support stratum, unit, or rowwise tolerance fails.
- The final actor-boundary audit showed that valid Q1 scores alone could still
  be labelled actor-visible. Q1 admission now requires one versioned
  `q1-actor-protocol-v1` analysis sidecar whose typed payload records held-out
  scene role, observation-derived target input, successful target matching,
  absent actor/oracle leakage, hard-mask use, and strictly causal history.
  Every promoted Q1 row is matched back to the same sidecar's exact store, key,
  value, unit, denominator, aggregation, and provenance leaf; an unrelated
  immutable file or a payload-level mutation fails closed.
- Candidate-support P05 is now a scene-balanced estimand: actor-valid counts are
  averaged over attempted roots within each scene and nearest-rank P05 is taken
  across those scene means. Failed-root rate is the macro-average of per-scene
  failure fractions. Because the current writer lacks passing-root counts, the
  thesis blocks confirmatory admission until an immutable per-attempt sidecar
  provides scene/root identity, valid count, threshold, and outcome.
- The 44-row confirmatory Results surface is split into bounded foundation,
  policy, exact-$Q_2$, and resource tables. A layout-only fixture imports the
  canonical fact contracts, asserts exact units and value kinds, exercises all
  production family specifications, and fails unless the render remains exactly
  two A4 pages.
- Every promoted analysis family now binds its exact typed fact payload to one
  content-addressed sidecar rather than treating a sidecar digest as sufficient
  evidence. Candidate-support admission additionally compares the observed
  per-attempt receipt against an independently frozen scene/root roster and
  recomputes scene-balanced P05 support and failed-root rate.
- Measurement repeatability now compares the observed receipt against an
  independent Cartesian plan over exact repeat identifiers, measurement
  identities, and ranking-group membership. It derives competition ranks from
  bound gains under frozen direction and tie semantics, recomputes maximum
  matched-unit discrepancy, and rejects self-adjusted repeat or unit truncation.
- Adversarial fixtures cover payload mutations, roster truncation, shared
  artifact contradictions, stable ties and tie-breaking, nonuniform scene
  aggregation, 100-attempt support, and multi-repeat/multi-unit measurement.
  Map/flatten construction keeps the focused contract at about 19 seconds
  instead of the initial quadratic 77-second scale regression.
- Exact-$Q_2$ admission now requires the report fact to name one canonical
  certification receipt. Sidecar identifiers are recomputed as SHA-256 over
  `logical_name + NUL + payload_digest` at provenance, payload-binding, and
  receipt lookup boundaries, so a forged but internally consistent identifier
  fails closed.
- The receipt binds the exact ordered test-store manifest roster, learned-
  recursion semantics, dense-valid objective profile, selected chains, factual
  rows, population census, support strata, independent units, and final gate.
  The Typst validator independently recomputes row errors and relative errors,
  aggregate and per-unit statistics, thresholds, and every gate conjunct rather
  than accepting a self-attested boolean or aggregate.
- Report storage is intentionally lexical while QH dataset order defines
  `store_index`. Admission therefore requires exact order-independent roster
  inclusion at the report boundary, then verifies the receipt's own ordered
  roster digest and bounds every selected-chain and census store index against
  that roster. Adversarial tests cover roster omission and duplication,
  reordered rosters without a matching digest, out-of-range indices, mutated
  scientific identity, contradictory aggregates and gates, and 100-row scale.
- Exact-head review then exposed a cross-lane composition gap: valid actor-
  $Q_1$, exact-$Q_2$, and learned-policy endpoints could originate from three
  different selected models. Each learned family now records the verified
  inference-bundle manifest SHA-256; exact-$Q_2$ additionally matches its fact
  back to the canonical receipt. Claim composition requires one identity across
  the full store-by-lane rectangle, so per-store consistency cannot hide model
  drift between report profiles. Oracle endpoints and headroom remain separate
  because they do not use learned weights.
- A final exact-head robustness finding showed that malformed exact-$Q_2$
  receipt numbers and identity components could reach arithmetic or string
  operations before the validator returned false. Lineage, specification,
  selected-chain, row, and census checks now short-circuit before dependent
  operations. Support-stratum, row-stratum, and independent-unit key components
  retain explicit types, so stringification cannot erase an invalid identity.
  Adversarial malformed-value fixtures now fail closed without aborting Typst,
  while measured non-passes remain admissible evidence.

## Commits

- https://github.com/JanDuchscherer104/ARIA-NBV/commit/9897e0f4709ca9ca3ec9c5933fd0e2de2ba1dccf
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/f1ddfdef8f37c287158fdfa8501a729c2e1089fc
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/72a1136a11e4fe751893ad606fcc923882e7ecb3
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/fb31b12cbc7fb92acb9f4f203395ced99d50407e
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/c8880786c7ea9456672a06188330102fa0b09a22
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/1190e5e7bc4863f46221edee20a693198a23a9ae
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/b09b32fd5d71ba1d58ac3a635095565f4563eb82
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/56122614724bd73787cd816483dd51f67b4ef15f
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/e28bc6234b319de39ea5637068df601ff46d9895
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/fa2f1699a9bd4828585976ed95a12d77c8be8b53
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/3b1a2e4dae1c1fe0ac86739ed1374ccbf9023abf
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/0c81a475ed3af85d3a21f9a68d970f0a4c52ea77
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/ae85a33ab218d943c837599f3dbf836fccf64686
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/8dcd0cb539997bd41788a0190ec0c2ae7a009691
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/6ba2e3fbb122b0ae51f10fd48fdec2289aab3a1f

## Verification

Passed `make thesis-pdf`, `make thesis-pdf-ci`,
`make thesis-report-data-contract`, `make typst-authoring-contract` (22 tests),
`make thesis-marker-contract`, Ruff check/format, Python byte compilation, PDF
page-size checks, and `git diff --check`. Exact standalone and embedded renders
were inspected in color and grayscale. Independent exact-candidate scientific
and visual reviews each approved with zero P0--P2 findings. After the recovery-
contract repair, two fresh independent reviews again approved with zero P0--P2.
The derived-identity repair received another independent exact-candidate
approval with zero P0--P2.
The final admission-contract candidate additionally passed adversarial
population, repeatability, support, Q1, Q2, sidecar-uniqueness, and decision-
identity mutations. Two independent reviews approved it with zero P0--P2, and
the focused Q_H model/certification suite passed all 72 tests.
The subsequent headroom-decision repair passed threshold equality, zero lower-
bound, measured non-pass, contradictory boolean, nonpositive/mistyped/missing
threshold, wrong rule/unit/aggregation, and malformed-decision cases. Two fresh
independent reviews approved the exact candidate with zero P0--P2, and rendered
A4 pages 35, 94--95, 99, and 102 were visually inspected without layout or
semantic regression.
The closing repair passed `make thesis-results-full-profile-render`,
`make thesis-report-data-contract`, `make thesis-pdf-ci`,
`make typst-authoring-contract`, `make thesis-marker-contract`,
`make thesis-pdf`, `make check-agent-memory`, and `git diff --check`. The
full-profile fixture is exactly two A4 pages and was visually inspected in
color and grayscale; the 129-page thesis Results and support pages were also
inspected at final size. The focused Q_H behavior suite passed all 632 tests
when the shared environment was bound to the current worktree source; the one
initial provenance failure came from the shared interpreter importing the main
checkout and passed after setting the current-worktree `PYTHONPATH`. Two fresh
independent exact-candidate reviews reported zero P0--P2 findings. Exact final
artifacts before the debrief update were: tracked-diff
`c94c85bc78e004e1a5557edd426fefa471d0cfa9951942472f405a54c137ddbb`,
layout fixture
`c20debe9fcf16e4c2b6d25738ddf5687b4fb33327eeee27efdbaabfaaf8d07a4`,
layout PDF
`5a68563a452a5c39f1fc60787ffcc65b9f88c944a2becf865d28c71930e215e1`,
and thesis PDF
`f90910e241796be5fa4f3a11e7ba127fb7bcaf7be63751b68c64d6742776fea5`.
The final Q1 protocol-receipt repair passed the adversarial Typst contract,
`make thesis-report-data-contract`, `make typst-authoring-contract`,
`make thesis-marker-contract`, `make thesis-results-full-profile-render`,
`make thesis-pdf-ci`, `make thesis-pdf`, the focused report-writer
content-address regression, `make check-agent-memory`, and `git diff --check`.
The thesis remains 129 A4 pages; physical Results pages 68--69 were inspected
at final size in color and grayscale. Independent scientific re-review first
identified and then approved the exact source-to-payload binding with zero
remaining P0--P2 findings.
The frozen-roster repair passed `make docs-render-core`, including the Quarto
render, Typst report contract, 22 authoring checks, marker contract, and 31
literature-provenance tests. `make thesis-report-data-contract` passed in
18.6 seconds; `make thesis-results-full-profile-render`, `make thesis-pdf`, and
`git diff --check` passed. The thesis remains 129 A4 pages. Physical pages 39,
60, and 68--69 were inspected at final size. Independent contract and scientific
reviewers approved the final candidate with zero P0--P2 findings.
The canonical exact-$Q_2$ receipt repair passed `make docs-render-core`,
`make thesis-report-data-contract`, `make thesis-results-full-profile-render`,
`make thesis-pdf`, and `git diff --check`. The full-profile fixture remains two
A4 pages, the thesis remains 129 A4 pages, and physical Results page 69 plus
both full-profile pages were inspected at final size without clipping or
overflow. Independent contract and scientific reviewers approved the exact
text diff `dede045cc3bcab172a364a38f9ad9344ca723d2069ff8118f7bf8e2a5b682046`
with zero P0--P2 findings. The final thesis and layout-fixture PDF SHA-256 values
were `3a5761176e4b9ddef8f8f1b8122b53b2a78812937169162d657e5db6d6a5bf2b`
and `47ba07f113e30ce3281530b670f34190bfe18776ea57a3d434bc3577746b9070`.
The learned-bundle lineage repair passed `make docs-render-core`,
`make thesis-report-data-contract`, `make thesis-results-full-profile-render`,
`make thesis-pdf-ci`, `make typst-authoring-contract`, `make thesis-pdf`, and
`git diff --check`. Adversarial cases cover within-store and cross-store drift,
missing, duplicate, malformed, alternate-valid, receipt-mismatched, and
payload-mismatched identities. Oracle-only endpoint and headroom evidence stays
valid without learned-policy rows. The thesis remains 129 A4 pages; physical
Results pages 68--69 and Discussion page 70 were inspected at final size.
Independent contract and scientific reviewers approved source diff
`27fe3616ed38fde46e2c747f7afa1465721178728d5a430215ae28aa775b6e7b`
with zero P0--P2 findings. The final thesis PDF SHA-256 was
`05e3dfa1d765913973029983ef6d5d145a8cc93b64ee2f2b0c1c985b20ba10eb`.
The numeric and identity fail-closed repair passed
`make thesis-report-data-contract`, `make thesis-results-full-profile-render`,
`make thesis-pdf-ci`, `make typst-authoring-contract`, `make thesis-pdf`, and
`git diff --check`. The thesis remains 129 A4 pages and its PDF SHA-256 is
`00570be86cd6fcf0c4c4ea51a3211222a687709b0381e47b7f2dff7c0e95822d`.
Independent contract and scientific reviewers approved exact two-source-file
diff `861c4db105a7ccff85050d303f1fc0b93b44590e21c6d0383bb6dc30d234609b`
with zero P0--P2 findings; eleven dynamic malformed-value cases returned false
without a Typst evaluation abort.

## Canonical Owner Impact

Current thesis truth now lives in the touched Typst figure, report-data,
Experimental Design, Results, Discussion, and Conclusion owners. The new Typst
fixture and report-data contract test preserve false-decision versus missing-
evidence behavior. No package runtime or experiment artifact was changed.
