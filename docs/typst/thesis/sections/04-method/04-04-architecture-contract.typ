#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status
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

#figure(
  publication-table(
    text-size: 7.8pt,
    columns: (0.48fr, 0.95fr, 0.83fr, 1.45fr),
    header: ([*Level*], [*Interaction*], [*Scientific role*], [*Question isolated before promotion*]),
    rows: (
      [A0], [independent-row MLP], [implemented matched control], [Are the frozen descriptors and objective learnable without query-dependent state reading?],
      [A1], [candidate-to-state cross-attention], [implemented selected interaction], [Does each candidate benefit from querying the shared state under the same inputs and decoder?],
      [A2], [DeepSets summary @DeepSets-zaheer2017], [contingent alternative], [Do errors depend on a permutation-invariant summary of the admitted candidate set?],
      [A3], [masked candidate self-attention @SetTransformer-lee2019], [contingent alternative], [Do pairwise candidate relations add value beyond a global set summary?],
      [A4], [query-local relation bias], [contingent alternative], [Are remaining errors explained by explicit target--history--candidate geometry?],
      [A5], [recurrent state reading], [contingent alternative], [Does iterative refinement help after the causal state itself is adequate?],
      [A6], [one-step base + residual], [objective/architecture hypothesis], [Can calibrated immediate gain simplify learning the continuation term?],
      [A7+], [graph or exact-equivariant layers @GeometricDeepLearning-bronstein2021], [exploratory idea], [Is a measured symmetry or relational failure still unresolved by lower levels?],
    ),
  ),
  caption: [Interaction ladder. Only A0 and A1 are currently admitted; higher levels remain conceptually specified so a diagnosed failure maps to one test rather than an unconstrained architecture search.],
) <tab:geometric-learning-ladder>

The ladder is not a presumed performance ordering. A2 or A3 changes the
conditional context of a row from the physical state alone to the sampled
candidate set, so the value being approximated must still remain the absolute
conditional value of that row. In particular, adding or duplicating an
irrelevant row must not redefine an unchanged candidate through batch-relative
centering. A4 targets geometric aliasing; A5 targets insufficient iterative
computation; A6 changes the value decomposition; and A7+ is justified only by
a measured symmetry or relational failure. These are different hypotheses and
must not be bundled into one larger model.

// Evidence map:
// - @DeepSets-zaheer2017 -> docs/literature/tex-src/arXiv-Deep-Sets/nips_2017.tex:803-865,907-996 (permutation-invariant summaries and permutation-equivariant set layers)
// - @SetTransformer-lee2019 -> docs/literature/tex-src/arXiv-Set-Transformer/01_introduction.tex:54-57; docs/literature/tex-src/arXiv-Set-Transformer/set_transformer.tex:82-86 (self-attention for pairwise or higher-order set interactions and permutation-invariant set modeling)
// - @GeometricDeepLearning-bronstein2021 -> docs/literature/tex-src/arXiv-Geometric-Deep-Learning/geometricdomains.tex:190-207,290-331 (permutation equivariance and graph-local aggregation)

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
