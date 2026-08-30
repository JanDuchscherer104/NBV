---
id: 2026-08-30_thesis_q_h_claim_admissibility_figure
date: 2026-08-30
title: "Thesis Q_H claim-admissibility figure"
status: done
topics: [thesis, typst, figures, q-h, scientific-review]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - docs/typst/thesis/experiment_data.typ
  - docs/typst/thesis/figures/qh_learning_evidence_loop.typ
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
  - scripts/tests/test_typst_report_data_contract.py
codex_thread: codex://threads/01a04fd9-0c7c-7813-a9c5-dc49f2f867a6
repo_object_format: sha1
repo_head: 56122614724bd73787cd816483dd51f67b4ef15f
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

## Commits

- https://github.com/JanDuchscherer104/ARIA-NBV/commit/9897e0f4709ca9ca3ec9c5933fd0e2de2ba1dccf
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/f1ddfdef8f37c287158fdfa8501a729c2e1089fc
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/72a1136a11e4fe751893ad606fcc923882e7ecb3
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/fb31b12cbc7fb92acb9f4f203395ced99d50407e
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/c8880786c7ea9456672a06188330102fa0b09a22
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/1190e5e7bc4863f46221edee20a693198a23a9ae
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/b09b32fd5d71ba1d58ac3a635095565f4563eb82
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/56122614724bd73787cd816483dd51f67b4ef15f

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

## Canonical Owner Impact

Current thesis truth now lives in the touched Typst figure, report-data,
Experimental Design, Results, Discussion, and Conclusion owners. The new Typst
fixture and report-data contract test preserve false-decision versus missing-
evidence behavior. No package runtime or experiment artifact was changed.
