#import "../../shared/symbols.typ": symb
#import "../draft_markers.typ": development_only, thesis_status, scientific_core_todo

#development_only(() => [
  #heading(level: 1, numbering: none)[Development Register: Method Alternatives]

  This register preserves executable but unpromoted controls and future
  hypotheses outside the thesis-core Method chapter. Entry here means that an
  idea has a named comparison and promotion gate; it does not mean that the
  thesis evaluates or recommends it.

  #thesis_status(
    implementation: "exploratory",
    evidence: "pending",
    source: [`aria_nbv/aria_nbv/vin/`; `aria_nbv/aria_nbv/lightning/`; `docs/contents/theory/`],
    gate: [promote only a one-factor comparison with an immutable receipt and untouched scene-disjoint evaluation],
  )[The thesis-core selection remains A1--H0--#symb.rl.s_pose with direct continuous regression. Executable controls, planned candidates, and exploratory ideas below remain available but are excluded from its central method claim.]

  #heading(level: 2, numbering: none)[State and history alternatives]

  - *#symb.rl.s_surface selected surfaces:* the executable privileged control backprojects only
    factual selected mesh depth, pools the causal point set, and initializes its
    residual at zero so a fresh S1 scorer matches H0. It lacks free/unknown
    evidence, is density weighted, and has no confirmatory receipt; it therefore
    cannot support a geometry-benefit or deployment claim.
  - *#symb.rl.s_ray ray-aware memory:* a planned state would distinguish observed surface,
    observed free, unknown, support, uncertainty, source, and recency. It
    requires deterministic fusion and no-future-observation tests before a model
    comparison.
  - *H1 ordered history:* an executable causal Transformer adds relative age to
    the same selected-pose tokens used by H0. It remains a pose-only capacity
    ablation until repeated-seed endpoint evidence justifies chronology.
  - *Other carriers:* target-centred EFM3D re-lifting, appearance-on-point,
    sparse TSDF/SDF encoders, object-aware 3D Gaussian splats, and SceneScript
    context are hypotheses for diagnosed representation failures, not parallel
    thesis methods.

  #heading(level: 2, numbering: none)[Interaction alternatives]

  A2 DeepSets context, A3 masked candidate self-attention, A4 query-local
  relation bias, A5 recurrent state reading, A6 residual value prediction, and
  A7+ graph or exact-equivariant layers are ordered escalation points. A level
  may enter the main method only after A0/A1 are measured under the same state,
  target protocol, decoder, objective, and evaluation contract and a concrete
  failure identifies the missing interaction. Candidate-set models must retain
  row equivariance, invalid-row isolation, duplicate tests, and absolute-value
  semantics.

  #heading(level: 2, numbering: none)[Objective and estimator alternatives]

  - *CORAL decoding* is executable over the same continuous fitted-Q targets,
    but its ordinal loss and fixed representatives add support-provenance and
    saturation questions. It is excluded until direct regression supplies the
    frozen control.
  - *Fixed-horizon or separate heads* alter parameter sharing and the public
    interface. They are ablations against the scalar requested-horizon family,
    not co-equal definitions of $Q_H$.
  - *Behavior-return Monte Carlo regression* estimates the continuation policy
    that generated each chain rather than greedy finite-support value unless
    those policies coincide. It must retain that distinct estimand.
  - *One-step plus residual prediction* can test whether calibrated immediate
    utility is a useful base, but the residual may not be mean-centred across a
    candidate table because unrelated or duplicate rows would then redefine an
    action's absolute target.
  - *Quantile regression* is justified only after stochastic return variation
    or state aliasing is measured and a distributional Bellman projection,
    support, decoding rule, and calibration protocol are frozen.

  The promotion sequence is: establish population/action support, measure
  oracle headroom, learn actor-visible $Q_1$, pass exact $Q_2$, and only then
  introduce the smallest alternative that addresses the observed failure.

  #heading(level: 2, numbering: none)[Ranked scientific-core work]

  Architecture and data TODOs use one extension of the thesis draft-marker
  contract rather than a separate backlog. Priority is ordinal and
  claim-centred: P0 protects a validity or information boundary shared by the
  central claims; P1 blocks the next principal-RQ inference; P2 discriminates
  a diagnosed alternative explanation; P3 is an exploratory extension outside
  the core claim. Readiness (`ready`, `blocked`, or `contingent`) is orthogonal,
  so a blocked P0 remains scientifically more critical than a ready P2 even
  though only the latter may be immediately executable. Every marker must name
  its affected claim, source, promotion gate, and blocker when blocked. The
  policy deliberately avoids weighted scores whose apparent precision would
  become stale as evidence changes.

  #scientific_core_todo(
    domain: "data",
    priority: "P0",
    readiness: "ready",
    claim: [actor/oracle separation and deployability of the target-conditioned value claim],
    source: [`v1_observed` target protocol and frozen corpus manifest],
    gate: [scene-disjoint corpus, explicit matching failures, source dropout, descriptor identity, and leakage audit],
  )[Freeze and audit the actor-visible target corpus before interpreting any learned target-conditioned result.]

  #scientific_core_todo(
    domain: "architecture",
    priority: "P1",
    readiness: "blocked",
    claim: [whether actor-visible state retains information needed for target-specific bounded return],
    source: [#symb.rl.s_ray candidate realization and selected-observation replay contract],
    gate: [deterministic fusion, no-future-observation test, source masks, and matched held-out comparison against #symb.rl.s_pose],
    blocked-by: [an admitted actor-visible selected-observation data path],
  )[Implement the smallest observation-updated state that preserves surface, free, unknown, support, uncertainty, source, and recency.]

  #scientific_core_todo(
    domain: "data",
    priority: "P1",
    readiness: "blocked",
    claim: [learned lookahead and held-out endpoint recovery],
    source: [exact-$Q_2$ census, oracle-headroom table, and paired endpoint receipt],
    gate: [frozen eligible population, support floor, tolerance, positive oracle headroom, and untouched scene-disjoint evaluation],
    blocked-by: [validated rollout stores under the selected target, state, candidate, and reward protocols],
  )[Produce the immutable evidence chain that separates implementation parity, learned recursion accuracy, and policy recovery.]

  #scientific_core_todo(
    domain: "architecture",
    priority: "P2",
    readiness: "contingent",
    claim: [alternative explanation for residual value error after state and support gates pass],
    source: [A2--A7 interaction ladder, H1, CORAL, residual, and separate-head controls],
    gate: [one measured failure mapped to one factor-matched comparison],
  )[Promote exactly one control that tests the diagnosed limitation; do not bundle state, interaction, and objective changes.]

  #scientific_core_todo(
    domain: "architecture",
    priority: "P3",
    readiness: "contingent",
    claim: [post-core generalization beyond the finite-candidate offline study],
    source: [3DGS memory, SceneScript context, continuous policy, and quantile-value ideas],
    gate: [completed core evidence chain plus a failure that requires the changed state, action, or estimand contract],
  )[Retain these ideas as scoped extensions; do not treat conceptual interest as evidence for inclusion in the core method.]
])
