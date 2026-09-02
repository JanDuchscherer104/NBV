#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status, development_only
#import "../../../shared/tables.typ": publication-table

== Selected Interaction and Acceptance Conditions <sec:thesis-method-geometry-contract>

#thesis_status(
  implementation: "implemented",
  evidence: "pending",
  citation: [@GeometricDeepLearning-bronstein2021 @DeepSets-zaheer2017],
  source: "aria_nbv/aria_nbv/vin/models/target_finite_horizon.py; aria_nbv/aria_nbv/vin/modules/qh_state_fusion.py; aria_nbv/tests/vin/test_qh_state_fusion.py; aria_nbv/tests/vin/test_target_finite_horizon.py",
  gate: [retain row-equivariance, invalid-row isolation, frame, source, mask-independence, and horizon tests; measure the A0/A1 control],
)[A1 candidate-to-state cross-attention is the selected interaction; A0 is its feature-matched independent-row control. Both pass the same executable acceptance tests. Their scientific comparison remains pending.]

Each materialized candidate is an independent query over shared scene, target,
history, budget, and horizon tokens. A1 uses the candidate as query and those
five state tokens as keys and values; candidates never attend to other
candidates. A0 flattens the same ordered tokens and applies a row-shared MLP.
Both expose the same-width context to the same value-decoder seam.

The A0/A1 choice is orthogonal to the state distinction in
@tab:thesis-counterfactual-state-protocols. A1 is the current interaction
choice, not the scientific target itself: the same row-equivariant interface
can read a richer causal state without introducing candidate-to-candidate
communication. Architecture should escalate only if a frozen comparison shows
that an admitted state is informative but A0/A1 cannot recover its value.

#development_only(() => [
  === Architectural feature-integration ladder

  The ladder below is a development plan, not a family of co-equal thesis
  methods. It orders feature integration by the smallest additional dependency
  introduced after the current A0/A1 controls. “Implemented” means that the
  tensor path and acceptance properties exist; it does not mean that the
  feature has demonstrated scientific value. “Eligible” names the first
  one-factor comparison that may be frozen after its activation evidence is
  present. “Possible extension” preserves a conditional test whose promotion
  still depends on a diagnosed failure.

  #figure(
    publication-table(
      text-size: 7.4pt,
      columns: (0.62fr, 1.18fr, 1.42fr, 1.58fr),
      header: ([*Stage and status*], [*Integrated feature*], [*Scientific purpose*], [*Principal risk and promotion gate*]),
      rows: (
        ([F0 — implemented], [candidate-relative geometric query], [Complete candidate pose relative to root and current camera, plus target pose relative to the candidate.], [Already present; retain transform-direction and local-frame tests. It supplies geometry, not selected-observation state.]),
        ([F1 — implemented], [A0/A1 state fusion], [Compare identical-input independent-row fusion with candidate-to-state cross-attention.], [The controls are not parameter matched; report parameters and runtime and require a frozen held-out comparison.]),
        ([F2 — first eligible promotion], [candidate-relative relation embeddings], [Embed each candidate’s relative transform to the target and pose-bearing causal history or state elements before A1 reads them.], [Activate only after state, support, label, and optimization failures are ruled out and held-out residuals retain relation structure.]),
        ([F3 — separate support-conditioned hypothesis], [permutation-invariant candidate-set summary @DeepSets-zaheer2017], [Test whether a versioned context-row set supplies ranking information beyond the physical state and query-local relations.], [Does not inherit A0/A1 mask independence or duplicate-row invariance; freeze context rows, masks, duplicate semantics, and the score estimand.]),
        ([F4 — separate support-conditioned hypothesis], [candidate self-attention @SetTransformer-lee2019], [Test whether pairwise candidate relations explain residual ranking error beyond an invariant set summary.], [Adds quadratic interaction and support sensitivity; promote only after a frozen F3 profile fails under matched support.]),
        ([F5 — possible extension], [iterative or recurrent state reading], [Test whether one candidate query needs repeated access to an already adequate causal state.], [May hide missing state information behind capacity; promote only after the state, F2 relations, and simpler fusion controls pass.]),
      ),
    ),
    caption: [Development-only architectural feature-integration ladder. Status records implementation maturity, while promotion remains conditional on a named scientific failure and a one-factor comparison.],
  ) <tab:architecture-feature-integration-ladder>

  Candidate-relative relation embeddings are the first eligible architectural
  promotion because they can preserve the current per-candidate value interface while
  making query-to-context geometry explicit. Query-centric models use local
  coordinate systems and relative positional embeddings so that the active query
  can read other elements through their relation to it @zhou2023query. In
  ARIA-NBV, the same construction can attach a shared embedding of candidate--
  target and candidate--history transforms to the A1 key/value tokens. Applied
  independently to every candidate, it preserves candidate-row equivariance and
  does not make an action’s value depend on unrelated candidate rows.

  The case against immediate promotion is equally important. F0 already exposes
  complete relative poses, so F2 adds an inductive bias rather than new raw
  information. It can redundantly parameterize the same transform, overfit the
  geometry of one proposal generator, increase cost with candidate--history
  pairs, or encode an inappropriate symmetry if gravity, metric scale, camera
  direction, or target orientation is suppressed. Geometric priors can reduce
  the hypothesis space, but only when the chosen symmetry matches the task
  @GeometricDeepLearning-bronstein2021. F2 therefore activates only when
  held-out residual error varies systematically with candidate--target or
  candidate--history relations, a non-learned relation probe predicts that
  residual structure, and the pattern survives matched seeds, capacity, state,
  support, label, and optimization controls. The existence of relation-embedding
  architectures in another domain is not activation evidence.

  F3 and F4 are not contract-preserving extensions of A0/A1. Their natural
  output is a support-conditioned ranking score

  #eqs.rl.support_conditioned_score

  rather than an action value that depends only on one state--action pair.
  Here $cal(C)_t^"ctx"$ is a separately versioned context-row set. Its profile
  must state whether those rows are materialized, action-valid, or
  label-supported; which mask enters the model; whether duplicate poses are one
  semantic action or distinct proposals; and which A0/A1 invariants are retained
  or intentionally replaced. Until corresponding permutation, invalid-row,
  duplicate, and mask-sensitivity tests exist, F3/F4 remain development
  hypotheses and cannot be reported as ordinary #symb.rl.learned_q models.

  Full SE(3)-Transformer and geometric-algebra Transformer variants are out of
  scope for the core study. The current local frames already remove arbitrary
  origin dependence while retaining gravity-aligned and metric quantities that
  may affect sensing. No measured symmetry failure presently warrants the added
  representation, implementation, and compute commitments of an exact
  equivariant backbone. Candidate-set interaction remains a later and separate
  hypothesis because it changes the conditioning context of each action rather
  than only how its physical relations are encoded.

  // Evidence map:
  // - @zhou2023query -> docs/literature/tex-src/arXiv-QCNet/main.tex:159-161 (query-centric local frames and query-relative spatial-temporal positional embeddings)
  // - @GeometricDeepLearning-bronstein2021 -> docs/literature/tex-src/arXiv-Geometric-Deep-Learning/geometricpriors.tex:339-345,950-969 (symmetry priors restrict the hypothesis class; locality and receptive-field tradeoffs)
  // - @DeepSets-zaheer2017 -> docs/literature/tex-src/arXiv-Deep-Sets/nips_2017.tex:803-865,907-996 (permutation-invariant summaries and permutation-equivariant set layers)
  // - @SetTransformer-lee2019 -> docs/literature/tex-src/arXiv-Set-Transformer/01_introduction.tex:54-57; docs/literature/tex-src/arXiv-Set-Transformer/set_transformer.tex:82-86 (self-attention for pairwise or higher-order set interactions and permutation-invariant set modeling)
])

Candidate order has no semantic meaning. Jointly permuting aligned rows by $Pi$
must permute predictions identically:

$
  #eqs.rl.candidate_row_equivariance
$

Changing only hard-invalid row contents must not alter valid-row predictions:

$
  #eqs.rl.candidate_mask_isolation
$

The scorer reads #symb.rl.candidate_row_mask only to sanitize padding. It never
reads #symb.rl.action_mask; training owns label and bootstrap admission, and
online inference owns the final selectable set. Thus changing the hard mask
cannot change raw conditional values or feasibility logits. Duplicate-row and
valid-count tests further prevent accidental set normalization from redefining
the value of an unchanged physical candidate.

Local-frame encoding removes arbitrary global origin conventions without
claiming exact $op("SE")(3)$ equivariance. Complete root/current-relative
candidate poses and the candidate-from-target pose retain translation and
rotation relationships represented by the shared PoseTW encoder
@GeometricDeepLearning-bronstein2021. Provenance tests additionally
exclude target gains, meshes, associations, and current candidate renders from
the actor graph. Previously selected privileged depth belongs only to an
explicit non-deployable state protocol.

Finally, $#symb.rl.requested_horizon=1$ has no bootstrap,
$#symb.rl.requested_horizon>#symb.rl.budget$ is rejected rather than clamped,
and an $#symb.rl.requested_horizon>1$ target may depend only on a factual
successor queried at $#symb.rl.requested_horizon - 1$. No
monotonicity across horizons is assumed because admissible actions may have
negative immediate gain.
