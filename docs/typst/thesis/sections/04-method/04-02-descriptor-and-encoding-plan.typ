#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status

== Target, Candidate, and History Encoding

#thesis_status(
  implementation: "implemented",
  evidence: "pending",
  citation: [@GeometricDeepLearning-bronstein2021 @UVFA-schaul2015],
  source: "aria_nbv/aria_nbv/data_handling/qh_data/views.py; aria_nbv/aria_nbv/vin/models/target_finite_horizon.py; aria_nbv/aria_nbv/vin/modules/qh_history_encoders.py; aria_nbv/tests/vin/test_target_finite_horizon.py; aria_nbv/tests/vin/test_qh_history_encoders.py",
  gate: [preserve local-frame, mask, source, and strictly causal prefix tests; evaluate held-out ranking],
)[The selected encoder materializes one target-conditioned query per candidate from root evidence, local relative geometry, H0 selected-pose history, remaining budget, and requested horizon. Its tensor contract is tested; scientific usefulness remains pending.]

For target $e$ and candidate $q_(t,i)$, the scorer input is the structured
relation

$
  #eqs.model.qh_input_contract
$

rather than a flat replay row. Source and availability masks distinguish absent
evidence from measured zeros; padding is separate from physical invalidity;
supervision and audit lineage never enter the learned query.

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

For every realized state, the reader supplies the complete selected-pose prefix
$j<t$ expressed from the factual current camera. The selected H0 encoder applies
the shared pose map and a padding-aware arithmetic mean:

$
  #eqs.model.qh_history_controls
$

Only the H0 branch of this equation belongs to the selected method. The root
state uses a learned empty token; padded entries cannot affect the history
summary. Prefix cardinality and chronology are not substitutes for remaining
budget $b_t$ or requested horizon $h$, which remain separate tokens. Because
H0 observes poses rather than selected surfaces or free-space evidence, it
inherits the `S0-pose` sufficiency limitation identified above.

The maximum horizon $H_"max"$ binds data, model, and checkpoint. Remaining
budget records the factual state; $h$ selects a requested return within the
joint support domain $1 <= h <= b_t <= H_"max"$. Omitting $h$ selects the
factual diagonal $h=b_t$. Dense $Q_1$ supervision realizes $(b_t,1)$ across
observed budgets, while recursive $h>1$ supervision follows the diagonal and
exact $Q_2$ is executable at $(2,2)$ with its held-out receipt still pending.
The current bundle records trained horizons, not pair-level support. Deployed
online inference requests only $h=b_t$ and rejects horizons absent from that
bundle. The scorer can execute shorter off-diagonal queries syntactically, but
a manifest-bound pair gate is required before promoted off-diagonal $h>1$
inference. The public interface scores one scalar horizon at a time and
preserves candidate order in its $[B,S,N_q]$ output.
