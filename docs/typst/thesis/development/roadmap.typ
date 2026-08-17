#import "../draft_markers.typ": development_only, promotion_entry, thesis_status

// Development-only schedule and gate view. Scientific prose, equations, and
// implementation contracts remain owned by the active thesis and package
// sources named below.
#development_only[
  #heading(level: 1, numbering: none)[Development roadmap] <ch:roadmap>
  #metadata("roadmap-outcome") <outcome>
  This page records schedule, status, evidence pointers, and promotion gates.
  It is omitted from submission output. The active thesis owns claims; Python,
  tests, configuration, and immutable artifacts own behavior and measurements.

  #thesis_status(
    implementation: "partial",
    evidence: "pending",
    source: [`docs/typst/thesis/sections/`; `docs/typst/thesis/development/m1-contract-report.typ`; `aria_nbv/`; `aria_nbv/tests/`; active configuration],
    gate: [M1 correctness and M5 headroom evidence],
  )[Planning status only; this view promotes no policy-improvement claim.]

  #heading(level: 2, numbering: none)[Outcome] <ssec:outcome-detail>
  The development outcome is a reproducible, evidence-backed thesis package.
  Canonical narrative and equation labels live in `docs/typst/thesis/sections/`;
  this page tracks readiness and gates only.

  #heading(level: 2, numbering: none)[Milestones] <ssec:milestones>
  - *M0 — scope and foundation (2026-04-29–2026-05-10):* #strong[status: complete]; gate: thesis scope, source policy, and citation owners aligned. Evidence: `docs/typst/thesis/main.typ`, `docs/typst/thesis/sections/01-research-questions.typ`, `docs/references.bib`.
  - *M1 — data, cache, and oracle correctness (2026-05-11–2026-05-31):* #strong[status: blocked]; gate: fresh store, scene split, frame/depth, candidate alignment, Rerun, and throughput evidence. Evidence: `docs/typst/thesis/development/m1-contract-report.typ#ssec:m1-status`, `aria_nbv/tests/data_handling/`, `aria_nbv/tests/pose_generation/`, `aria_nbv/tests/rollouts/`, `.configs/offline_only.toml`.
  - *M2 — VIN baseline and scale gate (2026-06-01–2026-06-21):* #strong[status: blocked by M1]; gate: reproducible baseline, diagnostics, and scale receipt. Evidence: `aria_nbv/tests/vin/`, `aria_nbv/tests/lightning/`, `docs/typst/thesis/sections/05-experimental-design/05-01-objectives-and-hypotheses.typ`, `docs/typst/thesis/sections/05-experimental-design/05-03-policy-comparison-and-failure-interpretation.typ`.
  - *M3 — target-RRI and generation readiness (2026-06-22–2026-07-12):* #strong[status: blocked by M1]; gate: trusted target subset, actor-visible protocol, and deterministic generation checks. Evidence: `docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ`, `aria_nbv/tests/oracle/test_target_selection.py`, `aria_nbv/tests/pose_generation/`, `aria_nbv/tests/rollouts/`.
  - *M4 — target-conditioned one-step scorer (2026-07-13–2026-08-09):* #strong[status: pending M3 evidence]; gate: held-out ranking, calibration, oracle selections, and grouped failures. Evidence: `docs/typst/thesis/sections/04-method/04-02-descriptor-and-encoding-plan.typ`, `aria_nbv/tests/oracle/test_scoring.py`, `aria_nbv/tests/lightning/test_candidate_scorer_contract.py`.
  - *M5 — lookahead headroom and Q_H (2026-08-10–2026-08-30):* #strong[status: pending prerequisite gates]; gate: equal-budget rollout comparisons, measured headroom, and supported Q_H evidence. Evidence: `docs/typst/thesis/sections/04-method/04-05-finite-candidate-value-model.typ`, `docs/typst/thesis/sections/05-experimental-design/05-02-learning-objective-and-replay-evidence.typ`, `aria_nbv/tests/data_handling/test_qh.py`, `aria_nbv/tests/rollouts/`.
  - *M6 — scale and bridge decisions (2026-08-31–2026-09-13):* #strong[status: pending M5]; gate: scale decision and explicit bridge scope. Evidence: `docs/typst/thesis/sections/07-discussion.typ`, `aria_nbv/tests/oracle/test_online_vin.py`, `aria_nbv/tests/rollouts/test_reporting.py`.
  - *M7 — final experiments and writing (2026-09-14–2026-09-27):* #strong[status: pending M5/M6]; gate: immutable run/config links, coverage statement, final tables, and failure cases. Evidence: `docs/typst/thesis/sections/06-results.typ`, `docs/typst/thesis/sections/07-discussion.typ`, `aria_nbv/tests/rollouts/test_reporting.py`.
  - *M8 — release freeze (2026-09-28–2026-09-30):* #strong[status: pending M7]; gate: reproducible configs, docs, demo path, and smoke checks. Evidence: `Makefile`, `docs/README.md`, CI workflows, final evidence bundle.

  #heading(level: 2, numbering: none)[Ablations] <ssec:ablations>
  Comparison axes remain in canonical owners; this page records pointers and gates only.
  - *Target input:* `docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ`; gate: V0/V1 protocol tests and actor-visible boundary.
  - *Candidate mixture:* `docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ`, `aria_nbv/aria_nbv/pose_generation/`; gate: validity and provenance diagnostics.
  - *Objective/planner:* `docs/typst/thesis/sections/05-experimental-design/05-01-objectives-and-hypotheses.typ`, `docs/typst/thesis/sections/05-experimental-design/05-03-policy-comparison-and-failure-interpretation.typ`; gate: equal budget and oracle receipt.
  - *Invalidity/learning:* `docs/typst/thesis/sections/04-method/04-04-architecture-contract.typ`, `docs/typst/thesis/sections/05-experimental-design/05-02-learning-objective-and-replay-evidence.typ`; gate: masks, reason codes, replay tests.
  - *State/scale:* `docs/typst/thesis/sections/04-method/04-01-scene-representation-requirements.typ`, `docs/typst/thesis/sections/03-oracle-and-data-generation/03-03-replay-stores-and-diagnostics.typ`; gate: support and coverage accounting.

  #heading(level: 2, numbering: none)[Evidence] <ssec:evidence>
  - M1: `docs/typst/thesis/development/m1-contract-report.typ`, focused data/geometry/rollout tests, `.configs/offline_only.toml`, immutable store/Rerun receipts.
  - M2–M4: `aria_nbv/tests/vin/`, `aria_nbv/tests/oracle/`, `aria_nbv/tests/lightning/`, and `docs/typst/thesis/sections/05-experimental-design/` plus saved calibration/ranking artifacts.
  - M5–M7: rollout manifests, reports, configs, result tables, and exact support/coverage gaps in those artifacts.
  - M8: CI, `make qmd-frontmatter-check`, `make thesis-pdf`, and final smoke receipts; tracked PDF remains a development artifact.

  #heading(level: 2, numbering: none)[Risks] <ssec:risks>
  Active risk state is pointer-only: frame/depth `aria_nbv/tests/rendering/test_depth_backprojection_conventions.py`, target validity `aria_nbv/tests/oracle/test_target_selection.py`, rollout support `aria_nbv/tests/rollouts/test_zarr_store.py`. Open blockers remain in `docs/typst/thesis/development/m1-contract-report.typ` and `.agents/issues.toml`/`.agents/todos.toml`; no duplicate risk narrative is maintained here.

  #heading(level: 2, numbering: none)[Freeze] <ssec:freeze>
  Freeze gate: clean reproducible smoke matrix, immutable run/config links, final coverage statement, and no stale paths or placeholders. The exact submission evidence gate remains owned by `docs/typst/thesis/main.typ` and its report bundle; this development projection does not satisfy it.

  #heading(level: 2, numbering: none)[Promotion queue] <ssec:promotion-queue>
  #promotion_entry(
    [Promote M5 lookahead/Q_H results after paired held-out evidence is immutable.],
    source: [docs/typst/thesis/sections/05-experimental-design/; aria_nbv/tests/rollouts/test_reporting.py],
    target-section: [docs/typst/thesis/sections/06-results.typ and docs/typst/thesis/sections/07-discussion.typ],
    gate: [positive headroom, oracle re-scoring, uncertainty, and coverage],
    disposition: "candidate",
  )
  #promotion_entry(
    [Resolve the scale fallback before claiming population coverage.],
    source: [docs/typst/thesis/development/m1-contract-report.typ; aria_nbv/tests/data_handling/; aria_nbv/tests/rollouts/],
    target-section: [docs/typst/thesis/sections/05-experimental-design/05-03-policy-comparison-and-failure-interpretation.typ],
    gate: [throughput and scene-level held-out coverage],
    disposition: "blocked",
  )
  #promotion_entry(
    [Keep online discrete Q_H and continuous target-then-pose work as bridge scope until offline gates close.],
    source: [docs/typst/thesis/sections/07-discussion.typ; .agents/issues.toml],
    target-section: [docs/typst/thesis/sections/07-discussion.typ],
    gate: [stable offline Q_H and explicit scope decision],
    disposition: "deferred",
  )
  #promotion_entry(
    [Do not promote unsupported continuous, VLM, semantic-global, or real-device claims into the thesis core.],
    source: [docs/typst/thesis/main.typ; docs/typst/thesis/sections/07-discussion.typ],
    target-section: [docs/typst/thesis/sections/08-conclusion.typ],
    gate: [bounded non-claim retained],
    disposition: "rejected",
  )

  #heading(level: 2, numbering: none)[Priorities] <ssec:priorities>
  Gate order is M1 correctness, M2–M4 target/scorer readiness, M5 headroom, M6 bridge decision, then M7/M8 freeze. Each transition requires the evidence pointer and exit gate above; no scale or bridge work bypasses a blocked prerequisite.

  #heading(level: 2, numbering: none)[Issues and blockers] <ssec:issues-and-blockers>
  - M1 store, scene split, Rerun, and throughput: `docs/typst/thesis/development/m1-contract-report.typ#m1-blockers`.
  - M5 support and headroom: `docs/typst/thesis/sections/05-experimental-design/05-02-learning-objective-and-replay-evidence.typ`, `docs/typst/thesis/sections/05-experimental-design/05-03-policy-comparison-and-failure-interpretation.typ`.
  - Actionable follow-up: `.agents/issues.toml` and `.agents/todos.toml`; these records do not replace canonical owners.
]
