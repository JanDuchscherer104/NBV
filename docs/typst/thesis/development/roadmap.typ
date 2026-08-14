#import "../draft_markers.typ": development_only, promotion_entry, thesis_status

// The roadmap is an operator-facing schedule and gate view.  Scientific
// definitions, equations, implementation contracts, and durable terminology
// remain owned by the thesis sections, package docs, tests, and configuration.
#development_only[
  #heading(level: 1, numbering: none)[Development roadmap] <roadmap>
  #metadata("roadmap-outcome") <outcome>
  This page records the development schedule for ARIA-NBV from the current
  correctness gates through release freeze. It is intentionally omitted from
  submission output. The thesis claim and research-question wording remain in
  `sections/01-introduction.typ` and `sections/05-experimental-design/`;
  implementation ownership remains in `aria_nbv/`, its tests, and active
  configuration.

  #thesis_status(
    implementation: "partial",
    evidence: "pending",
    source: [thesis sections; package tests and configs],
    gate: [M1 correctness and M5 headroom evidence],
  )[The schedule and gates are current planning state, not evidence that a
  learned policy has improved over its baselines.]

  #heading(level: 2, numbering: none)[Outcome] <outcome-detail>
  The intended outcome is a reproducible, target-conditioned NBV evaluation:
  trusted oracle labels, an actor-visible target protocol, finite candidate
  rollouts, a learned one-step comparator, and a finite-horizon candidate value
  model evaluated by oracle re-scoring under equal budgets. The authoritative
  target/RRI and Q_H contracts are in
  `sections/03-oracle-and-data-generation/`, `sections/04-method/`, and
  `sections/05-experimental-design/`; this page only tracks their gates.

  #heading(level: 2, numbering: none)[Milestones] <milestones>
  - *M0 — scope and foundation (2026-04-29–2026-05-10):* classify existing
    work, freeze the compact thesis boundary, and establish citation/source
    hygiene. Exit requires the thesis seed and scope decisions to be aligned.
  - *M1 — data, cache, and oracle correctness (2026-05-11–2026-05-31):* establish
    store, split, frame/CW90, candidate alignment, depth/backprojection, and
    oracle-throughput evidence. Scaling is blocked until these checks pass or
    their gaps are explicit in the M1 report.
  - *M2 — VIN baseline and scale gate (2026-06-01–2026-06-21):* reproduce the
    one-step baseline, calibration/ranking diagnostics, controlled ablations,
    and the Zarr/LRZ plan needed before generation.
  - *M3 — target-RRI and generation readiness (2026-06-22–2026-07-12):* validate
    GT-OBB target tasks and crops on a trusted subset, then separate the
    actor-visible OBS-SEL / PRED-Q / GT-EVAL protocol.
  - *M4 — target-conditioned one-step scorer (2026-07-13–2026-08-09):* compare
    scene-level and target-conditioned scoring with held-out ranking,
    calibration, oracle-evaluated selections, and grouped failures.
  - *M5 — lookahead headroom and Q_H (2026-08-10–2026-08-30):* compare
    random-valid, one-step, bounded oracle lookahead, and stochastic oracle
    traces under equal budgets. Train/evaluate Q_H only after headroom and
    rollout support are measured.
  - *M6 — scale and bridge decisions (2026-08-31–2026-09-13):* decide whether
    full offline scale, external mesh-compatible support, or the RQ5 online
    discrete bridge is justified. Continuous control remains time-permitting.
  - *M7 — final experiments and writing (2026-09-14–2026-09-27):* freeze final
    tables, figures, failure cases, and coverage accounting over the 100-scene /
    4,608-window target, or record an explicit scene-level fallback.
  - *M8 — release freeze (2026-09-28–2026-09-30):* complete reproducible
    configs, demo path, documentation links, and final smoke checks.

  #heading(level: 2, numbering: none)[Ablations] <ablations>
  Each axis is a scientific comparison, not an architecture backlog. The
  detailed metric and tensor contracts remain in the experimental-design
  sections and package tests.

  - *Target input:* V0 GT-OBB sanity; V1 observed/predicted OBB; optional crop
    descriptor and entity-token variants.
  - *Candidate mixture:* generic shell; target-point; mixed target plus
    exploration; later shortlist variants only with evidence.
  - *Objective:* scene RRI; cumulative target-root gain; diagnostic target RRI;
    log-gain as a diagnostic ablation.
  - *Planner:* random-valid; learned one-step; one-step oracle greedy; bounded
    oracle lookahead; Q_H.
  - *Invalidity and loss:* hard masks first; validity heads, scalar penalties,
    CORAL variants, and return losses only after the base contract is stable.
  - *State and scale:* geometry/ray memory, selected synthetic observations,
    visibility-gated descriptors, trusted subset, scene-level holdout, and full
    coverage. Record support and coverage rather than silently changing them.

  #heading(level: 2, numbering: none)[Evidence] <evidence>
  A thesis-grade comparison must identify its scene, snippet, target, candidate,
  transition, seed, split, invalid-rate, and coverage-gap counts. Report equal
  horizon, candidate budget, generation distribution, and validity constraints;
  pair endpoint gain with cumulative target-root gain, diagnostic target RRI,
  runtime/path cost, and uncertainty. The immutable measurement manifests,
  figures, and tests are the evidence owners; this page points to the gate.

  #heading(level: 2, numbering: none)[Risks] <risks>
  - Frame/CW90/projection mismatch can produce plausible but invalid labels;
    retain M1 frame and Rerun normal/boundary/failure checks.
  - Sparse or ambiguous targets can destabilise labels or leak GT into actor
    inputs; retain explicit eligibility, unmatched counts, and V0/V1 audits.
  - Low valid-candidate fractions can make Q_H learn feasibility artifacts;
    preserve reason codes, minimum-valid gates, and provenance diagnostics.
  - Narrow rollout support can overstate value on unsupported actions; use
    random-valid and masked temperature-softmax traces with scene-level splits.
  - Oracle throughput can block scale; use Zarr-first storage, deterministic
    LRZ sharding, subset intervals, and exact coverage reporting.
  - If lookahead headroom is near zero, report that bounded result for its
    split/horizon/branch factor and do not reinterpret it as a Q_H failure.
  - If positive headroom exists but Q_H fails, retain the defensible oracle and
    one-step study; do not replace it with unvalidated continuous RL.

  #heading(level: 2, numbering: none)[Freeze] <freeze>
  Release freeze requires a clean, reproducible smoke matrix; figures linked to
  immutable run/config identifiers; no stale paths or placeholders; and a
  final coverage statement. Full continuous control, VLM/global planning,
  semantic memory, external simulators, and real-device deployment remain
  bridge/future work unless separately justified by completed finite-candidate
  evidence. The exact submission evidence gate is owned by `main.typ` and its
  report bundle.

  #heading(level: 2, numbering: none)[Promotion queue] <promotion-queue>
  #promotion_entry(
    [Promote the M5 lookahead/Q_H comparison into thesis results after paired held-out evidence is immutable.],
    source: [sections/05-experimental-design/; package tests and configs],
    target-section: [06-results.typ and 07-discussion.typ],
    gate: [positive headroom, oracle re-scoring, uncertainty, and coverage report],
    disposition: "candidate",
  )
  #promotion_entry(
    [Resolve the current scale fallback before claiming full-population coverage.],
    source: [M1/M2 owners; storage and rollout tests],
    target-section: [05-experimental-design/05-03-policy-comparison-and-failure-interpretation.typ],
    gate: [LRZ/Zarr throughput and scene-level held-out coverage],
    disposition: "blocked",
  )
  #promotion_entry(
    [Keep online discrete Q_H and continuous target-then-pose control as bridge work until offline gates close.],
    source: [07-discussion.typ; advisor scope decision],
    target-section: [07-discussion.typ],
    gate: [stable offline Q_H plus explicit advisor scope decision],
    disposition: "deferred",
  )
  #promotion_entry(
    [Do not promote unsupported continuous, VLM, semantic-global, or real-device claims into the thesis core.],
    source: [thesis scope and discussion sections],
    target-section: [08-conclusion.typ],
    gate: [none; retain as bounded non-claim],
    disposition: "rejected",
  )

  #heading(level: 2, numbering: none)[Priorities] <priorities>
  1. Protect the thesis core: ASE/EFM oracle target-RRI, actor-visible target
     conditioning, finite candidates, and equal-budget evaluation.
  2. Close M1 correctness and M5 lookahead gates before scale or bridge work.
  3. Scale trusted supervision within the current ecosystem, reporting exact
     scene/snippet/target/trajectory/transition coverage.
  4. Keep VIN improvements bounded to calibration and required controls; avoid
     architecture search before Q_H evidence.

  #heading(level: 2, numbering: none)[Issues and blockers] <issues-and-blockers>
  - Fine-detail supervision is sensitive to aggressive mesh/point downsampling.
  - Calibration, stage dependence, and ordinal-collapse causes are not yet
    separated by decisive evidence.
  - Candidate realism versus exploratory coverage remains under-specified.
  - Oracle throughput and partial offline stores constrain training-scale work.
  - Counterfactual states do not yet contain full RGB, SLAM, or semantic
    modalities without synthesis; this limits claims about richer memory.
  - The held-out split, Q_H success threshold, and fallback coverage bar remain
    advisor-facing decisions that must be resolved before the final experiment
    gate.
]
