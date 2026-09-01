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
  feature has demonstrated scientific value. “Planned” names the next frozen
  one-factor comparison. “Possible extension” preserves a conditional test
  whose promotion still depends on a diagnosed failure.

  #figure(
    publication-table(
      text-size: 7.4pt,
      columns: (0.62fr, 1.18fr, 1.42fr, 1.58fr),
      header: ([*Stage and status*], [*Integrated feature*], [*Scientific purpose*], [*Principal risk and promotion gate*]),
      rows: (
        ([F0 — implemented], [candidate-relative geometric query], [Complete candidate pose relative to root and current camera, plus target pose relative to the candidate.], [Already present; retain transform-direction and local-frame tests. It supplies geometry, not selected-observation state.]),
        ([F1 — implemented], [A0/A1 state fusion], [Compare identical-input independent-row fusion with candidate-to-state cross-attention.], [The controls are not parameter matched; report parameters and runtime and require a frozen held-out comparison.]),
        ([F2 — planned], [candidate-relative relation embeddings], [Embed each candidate’s relative transform to the target and pose-bearing causal history or state elements before A1 reads them.], [May duplicate information already contained in F0. Freeze one relation map, causal and padding masks, and a one-factor A1 comparison before promotion.]),
        ([F3 — possible extension], [permutation-invariant candidate-set summary @DeepSets-zaheer2017], [Test whether the sampled admissible set supplies context beyond the physical state and query-local relations.], [Changes conditioning from one physical action to the sampled support; require duplicate-row and absolute-value tests.]),
        ([F4 — possible extension], [masked candidate self-attention @SetTransformer-lee2019], [Test whether pairwise candidate relations explain residual error beyond an invariant set summary.], [Adds quadratic candidate interaction and stronger mask sensitivity; promote only after F3 fails under matched support.]),
        ([F5 — possible extension], [iterative or recurrent state reading], [Test whether one candidate query needs repeated access to an already adequate causal state.], [May hide missing state information behind capacity; promote only after the state, F2 relations, and simpler fusion controls pass.]),
      ),
    ),
    caption: [Development-only architectural feature-integration ladder. Status records implementation maturity, while promotion remains conditional on a named scientific failure and a one-factor comparison.],
  ) <tab:architecture-feature-integration-ladder>

  Candidate-relative relation embeddings are the planned next architectural
  addition because they preserve the current per-candidate value interface while
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
  @GeometricDeepLearning-bronstein2021. F2 is therefore justified by a matched
  failure analysis showing that A1 cannot recover relevant relations from F0,
  not by the existence of relation-embedding architectures in another domain.

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
