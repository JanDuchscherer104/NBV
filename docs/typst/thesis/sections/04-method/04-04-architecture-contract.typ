#import "../../../shared/macros.typ": *
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status
#import "../../../shared/tables.typ": publication-table

== Selected Interaction and Acceptance Conditions <sec:thesis-method-geometry-contract>

#thesis_status(
  implementation: "implemented",
  evidence: "pending",
  citation: [@GeometricDeepLearning-bronstein2021],
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
    text-size: 8.2pt,
    columns: (0.52fr, 1.1fr, 1.55fr),
    header: ([*Control*], [*Interaction*], [*Interpretive role*]),
    rows: (
      [A0], [independent-row MLP], [Tests whether the frozen descriptors and objective are learnable without attention.],
      [A1], [candidate-to-state cross-attention], [Selected model; tests whether query-dependent reading of shared state improves the same value task.],
    ),
  ),
  caption: [Admitted interaction pair. Inputs, state protocol, decoder, objective, and hard-mask owner remain fixed; parameter count and runtime must still be reported.],
) <tab:geometric-learning-ladder>

Candidate order has no semantic meaning. Jointly permuting aligned rows by $Pi$
must permute predictions identically:

$
  #eqs.rl.candidate_row_equivariance
$

Changing only hard-invalid row contents must not alter valid-row predictions:

$
  #eqs.rl.candidate_mask_isolation
$

The scorer reads the materialization mask only to sanitize padding. It never
reads the hard action mask; training owns label and bootstrap admission, and
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

Finally, $h=1$ has no bootstrap, $h>b_t$ is rejected rather than clamped, and
an $h>1$ target may depend only on a factual successor queried at $h-1$. No
monotonicity across horizons is assumed because admissible actions may have
negative immediate gain.
