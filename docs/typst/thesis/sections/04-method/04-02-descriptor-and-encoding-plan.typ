#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status

== Target, Candidate, and History Encoding

#thesis_status(
  implementation: "implemented",
  evidence: "pending",
  citation: [@GeometricDeepLearning-bronstein2021 @UVFA-schaul2015],
  source: "aria_nbv/aria_nbv/data_handling/qh_data/views.py; aria_nbv/aria_nbv/vin/modules/pooling.py; aria_nbv/aria_nbv/vin/modules/qh_history_encoders.py; aria_nbv/tests/vin/test_qh_history_encoders.py",
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

The target descriptor separates identity, geometry, observed support,
confidence, and source:

$
  #eqs.entity.target_descriptor
$

The learned target token combines only fields admitted by the named target
protocol with target-local scene support:

$
  #eqs.model.qh_target_token
$

Current oracle tasks populate ground-truth-derived target geometry and leave
some generic descriptor fields unmeasured. Availability must therefore be
explicit. Replacing an absent measurement by an ordinary zero would make
source provenance indistinguishable from scene evidence.

=== Relative candidate geometry

Canonical world poses remain reproducibility facts, but the model receives a
candidate pose relative to the current decision frame,

$
  #eqs.spatial.candidate_reference_transform
$

with continuous pose features

$
  #eqs.spatial.candidate_pose_features
$

and an explicit candidate--target relation:

$
  #eqs.spatial.candidate_target_relation
$

This factorization removes arbitrary world origin and yaw conventions while
retaining physical variables such as gravity, scale, height, target
orientation, bearing, and camera direction. The candidate row is a geometric
query, not a copy of the scene. Sampler family and generator provenance remain
audit variables unless a named ablation admits them.

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
budget records the factual state; $h$ selects a requested return within
$1 <= h <= b_t <= H_"max"$. A syntactically valid query still fails closed if
its horizon lacks manifest-bound training and evaluation support. The public
interface scores one scalar horizon at a time and preserves candidate order in
its $[B,S,N_q]$ output.
