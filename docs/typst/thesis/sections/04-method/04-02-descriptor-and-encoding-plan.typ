#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status
#import "../../../shared/tables.typ": publication-table

== Target, Candidate, and History Encoding

#thesis_status(
  implementation: "implemented",
  evidence: "pending",
  citation: [@GeometricDeepLearning-bronstein2021 @UVFA-schaul2015],
  source: "aria_nbv/aria_nbv/data_handling/qh_data/views.py; aria_nbv/aria_nbv/vin/models/target_finite_horizon.py; aria_nbv/aria_nbv/vin/modules/qh_history_encoders.py; aria_nbv/tests/vin/test_target_finite_horizon.py; aria_nbv/tests/vin/test_qh_history_encoders.py",
  gate: [preserve local-frame, mask, source, and strictly causal prefix tests; evaluate held-out ranking],
)[The selected encoder materializes one target-conditioned query per candidate from root evidence, local relative geometry, H0 selected-pose history, remaining budget, and requested horizon. Its tensor contract is tested; scientific usefulness remains pending.]

For target $e$ and candidate #symb.oracle.candidate_qti, the scorer input is the
structured relation

$
  #eqs.model.qh_input_contract
$

rather than a flat replay row. Source and availability masks distinguish absent
evidence from measured zeros; padding is separate from physical invalidity;
supervision and audit lineage never enter the learned query.

=== Logical data roles

The normalized reader may collate actor inputs, supervision, transition
linkage, and audit lineage in one batch, but tensor colocation does not grant
the model access. The Method therefore describes the logical contract rather
than enumerating storage columns:

#figure(
  publication-table(
    text-size: 8pt,
    columns: (0.82fr, 1.38fr, 1.08fr),
    header: ([*Logical role*], [*Scientific content*], [*Model access*]),
    rows: (
      [Scene and target state], [root actor evidence, source-bound target descriptor, #symb.rl.selected_pose_prefix, #symb.rl.budget], [candidate-value input],
      [Candidate table], [stable row identity, local pose relations, materialization, physical validity, reason and proposal provenance], [geometry and materialization only; #symb.rl.action_mask is external],
      [Value query], [scalar #symb.rl.requested_horizon with $1 <= #symb.rl.requested_horizon <= #symb.rl.budget <= #symb.rl.H_max$], [input only when bundle-supported],
      [Candidate supervision], [root-normalized gain, fitted target, #symb.rl.q_label_mask], [loss admission after prediction],
      [Selected transition], [factual selected row, reward, terminal flag, successor identity], [Bellman linkage only],
      [Audit lineage], [scene, target, store, generator, policy, seed, source, and configuration identity], [never a learned feature],
    ),
  ),
  caption: [Logical data roles at the reader--model boundary. Storage readability and batch colocation do not imply actor visibility.],
) <tab:thesis-qh-logical-data-roles>

This separation matters for causal interpretation. Target-source provenance is
experiment identity rather than a shortcut feature; generator family is
proposal-support evidence rather than a semantic action label; and oracle
returns supervise #symb.rl.conditional_q only after that value has been emitted.
The same reader can therefore support privileged controls and actor-visible
experiments without pretending that they estimate the same value function.

=== Target-conditioned query

The selected target protocol supplies a root-relative target pose and metric
OBB extents. The target token is therefore

$
  #eqs.model.qh_target_token
$

The source protocol that produced this geometry is frozen experiment identity,
not another model input. Current oracle tasks use ground-truth-derived target
geometry; this privileged source limits deployability even though gains,
meshes, associations, and audit lineage remain outside the prediction graph.

=== Relative candidate geometry

Canonical world poses remain reproducibility facts, but the selected scorer
encodes each candidate both relative to the rollout root and relative to the
factual current camera. Its physical trunk is

$
  #eqs.model.candidate_pose_context
$

The conditional-value query then adds the target pose expressed from that
candidate:

$
  #eqs.model.candidate_row_features
$

This factorization removes arbitrary world origin while retaining the complete
relative rotations and translations represented by the shared PoseTW encoder.
It does not append handcrafted range, bearing, height, frustum, sampler-family,
or generator-provenance features. The physical token feeds feasibility without
target or horizon information; only the conditional-value query receives the
candidate-from-target transform.

=== Strictly causal pose history

For every realized state, the reader supplies the complete
#symb.rl.selected_pose_prefix for $j<t$, expressed from the factual current
camera. The selected H0 encoder applies
the shared pose map and a padding-aware arithmetic mean:

$
  #eqs.model.qh_history_controls
$

Only the H0 branch of this equation belongs to the selected method. The H1
branch is implemented and replaces the order-invariant mean with a causal
Transformer and relative age; it remains an unselected pose-only control. The root
state uses a learned empty token; padded entries cannot affect the history
summary. Prefix cardinality and chronology are not substitutes for remaining
budget $b_t$ or requested horizon $h$, which remain separate tokens. Because
H0 observes poses rather than selected surfaces or free-space evidence, it
inherits the #symb.rl.s_pose sufficiency limitation identified above.

Pose order and observation content answer different questions. H1 tests
whether chronology within the same pose-only state matters. A signed first
view-direction moment together with #symb.spatial.dir_moment would instead test
whether approach-direction coverage is lost by generic history pooling. Such a
directional descriptor is scientifically meaningful, but it remains a
contingent idea until held-out errors are shown to depend on target-relative
approach direction; neither H1 nor directional moments supply missing surface
or free-space observations.

The current encoder implements the #symb.rl.s_pose actor-state carrier described
above. The implemented `v1_observed` protocol can supply its target token
without adding selected-observation state; target provenance and dynamic state
are separate axes. Reaching the scientific target therefore does not merely
append a larger scene token: the encoder must preserve source and availability
while letting each candidate query both the actor-visible target and the causal
dynamic state in relative geometry. Whether points, voxels, rays, or another
carrier best meets that requirement remains an empirical comparison.

The maximum horizon #symb.rl.H_max binds data, model, and checkpoint. Remaining
budget #symb.rl.budget records the factual state and #symb.rl.requested_horizon
selects one return from
$1 <= #symb.rl.requested_horizon <= #symb.rl.budget <= #symb.rl.H_max$.
Current bundles record trained horizons rather
than budget--horizon pairs, so deployed inference requests the factual diagonal
$#symb.rl.requested_horizon=#symb.rl.budget$. A manifest-bound pair gate is
required before any off-diagonal $#symb.rl.requested_horizon>1$
query is promoted beyond the syntactic scorer interface. The public interface
scores one scalar horizon at a time and preserves candidate order in its
$[B,S,N_q]$ output.
