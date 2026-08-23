#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": development_only
#import "@preview/booktabs:0.0.4": *

== Descriptor and Encoding Protocol

=== Implemented replay and DTO projection

// evidence:
// - aria_nbv/aria_nbv/rollouts/zarr_store.py:108-136,218-289 -> persisted return/reward semantics and candidate/Q_H fields.
// - aria_nbv/aria_nbv/rollouts/qh_reader.py:932-935 -> reader projection of action mask, q_train mask, and one-step root-gain labels.
// - aria_nbv/tests/rollouts/test_qh_reader.py:548-558,586-619 -> admitted v1 mask identity and bounded q_h evidence projection.

The replay/read-model projection preserves source, target, rollout, step, candidate, diagnostic, and lineage identities. Its padded `q_h/` view is a storage/read contract; padding does not create factual transitions or actor observations. The actor projection and supervision projection remain separate even when they are collated in one batch.

No production scorer consumes this projection. The current DTO/read-model boundary keeps root context, candidate rows, target context, factual history, remaining budget, and support masks subject to their admitted protocol; `q_train_mask`, target-root-gain labels, target-RRI diagnostics, selected transitions, and lineage remain supervision or audit rather than scorer features.

The actor-facing target descriptor is `#symb.entity.target_desc`; its source and availability must be explicit. The current oracle task uses GT-derived target geometry, so a deployable target-conditioned scorer requires an observed or predicted target protocol before policy evidence can be claimed.

=== Frame and encoding contract

// evidence:
// - aria_nbv/aria_nbv/data_handling/qh_data/views.py:192-218 -> root/candidate relative pose, factual history support, and remaining-budget tensor contracts.
// - aria_nbv/tests/data_handling/test_qh.py:930-1000 -> tensor summaries, transfer, and named-profile artifact checks.

The implemented frame discipline is at the DTO/adapter boundary: root and candidate poses have declared frames and the history mask is true only for factual selected poses preceding the query state. World-frame values remain audit facts. This contract does not establish scorer invariance or prove that any encoder is task-sufficient.

The current boundary does not include a production candidate encoder. It preserves declared frames, separates padding from modality absence, and keeps candidate-family and sampler provenance audit-only.

#development_only(() => [
  === Development alternatives

  The planned scorer input follows the shared contract:

  $
    #eqs.model.qh_input_contract
  $

  The planned candidate representation uses shared equations for pose and target relations:

  $
    #eqs.spatial.candidate_reference_transform
  $

  $
    #eqs.spatial.candidate_pose_features
  $

  Missing EVL, appearance, ray, and target fields require availability/source masks. Padding is separate from modality absence. Candidate-family and sampler provenance remain audit-only unless a named ablation promotes them.

  Requested-horizon embeddings, separate $Q_1,dots,Q_H$ heads, learned point or ray encoders, spherical-harmonic features, target-centred re-lifting, DINO-on-point, and other carrier choices are alternatives. They may be compared only after the fixed-H scorer boundary and source protocol are frozen; none is an implemented primary encoding.
])
