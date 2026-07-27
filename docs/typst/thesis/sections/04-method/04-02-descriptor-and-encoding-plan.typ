#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status
#import "@preview/booktabs:0.0.4": *

== Descriptor and Encoding Protocol

=== Persisted replay interface

#thesis_status(
  implementation: "implemented",
  evidence: "pending",
  source: [#gh("aria_nbv/aria_nbv/rollouts/zarr_store.py"); #gh("aria_nbv/aria_nbv/rollouts/qh_reader.py"); #gh("aria_nbv/aria_nbv/data_handling/qh.py"); #gh("aria_nbv/tests/rollouts/test_qh_reader.py")],
  gate: [preserve row identity, masks, provenance, and source roles in every tensor reader],
)[The factual replay schema, lazy reader, framework-neutral dataset seam, and dense `q_h/` view are implemented and unit-tested. Frozen scientific replay evidence remains pending. The schema is a storage contract; readability from the store does not make a field actor-visible.]

The rollout store preserves source, target, rollout, step, candidate, diagnostic, and lineage tables. Its derived `q_h/` arrays provide a padded state--candidate view without changing factual identities or labels. Target pose and extents in the V0 task remain privileged GT-derived instructions. Candidate geometry, selected history, remaining budget, and hard masks are decision inputs in the implemented tracer; target gains, GT associations, mesh diagnostics, crops, and current all-candidate renders remain label or audit fields. Previously selected depth becomes a later actor input only under a named counterfactual-observation protocol.

#figure(
  text(size: 8.3pt, table(
    columns: (0.72fr, 1.45fr, 1.05fr),
    toprule(),
    table.header([*Carrier*], [*Persisted content*], [*Learning role*]),
    midrule(), [Target], [identity, class, pose, extents, reference-relative pose, source and validity provenance],
    [privileged V0 task instruction; learned actors need observed or predicted equivalents],
    [Candidate],
    [stable row identities, world/root-relative pose, masks, reasons, sampler provenance, support fields],

    [finite action row; privileged diagnostics remain source-gated],
    [Selected chain],
    [selected row, shell index, step order, policy, seed, successor link, terminal state],

    [history and temporal-difference linkage],
    [Selected observation],
    [selected depth, valid mask, calibration, pose and source],

    [later dynamic-state input only under `CF-GT`, `CF-sensor`, or V1; never an all-candidate student input],
    [Oracle labels],
    [target RRI, target root gain, errors, optional crops and candidate renders],

    [supervision, evaluation, and audit only], bottomrule(),
  )),
  caption: [Implemented replay carriers and admissible learning roles.],
) <tab:thesis-descriptor-schema>

=== Planned model-input and DTO contract

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@GeometricDeepLearning-bronstein2021 @zhou2023query @FixedHorizonTD-deAsis2020 @UVFA-schaul2015],
  source: [#gh("aria_nbv/aria_nbv/data_handling/qh.py"); #gh("aria_nbv/aria_nbv/vin/models/target_finite_horizon.py"); #gh("docs/contents/theory/candidate_view_dependence.qmd")],
  gate: [typed selected-observation state, explicit residual-horizon query, positive-width V1 target path, source masks, and leakage tests],
)[The implemented DTO seam separates actor inputs, selected-transition supervision, and audit lineage for an H=2 V0 tracer. The canonical DTO contract additionally separates static scene context, dynamic selected-observation state, target state, candidate rows, and the requested residual horizon.]

The intended input for target $e$ at step $t$ is

$
  #eqs.model.qh_input_contract
$

This equation is an information contract rather than one flat tensor. The corresponding DTO roles are:

The role names below are conceptual interfaces, not claims that same-named Python classes already exist. The implemented persistence boundary is anchored by #gh-wip("aria_nbv/aria_nbv/rollouts/zarr_store.py", body: [`RolloutZarrStoreReader.q_h_view`], line: 517), while the currently blocked model boundary is #gh-wip("aria_nbv/aria_nbv/vin/models/target_finite_horizon.py", body: [`MultiStepCandidateScorer`], line: 51). These draft links disappear as links in the submission profile.

#figure(
  text(size: 8.1pt, table(
    columns: (0.92fr, 1.35fr, 1.05fr),
    toprule(),
    table.header([*DTO role*], [*Canonical content*], [*Visibility*]),
    midrule(), [Static scene context], [root semidense evidence, supported EVL tokens, root frame and EVL extent],
    [actor input; immutable within one rollout],
    [Dynamic scene state],
    [selected geometry, free/unknown support, recency, source masks and ordered history],

    [actor input; causal update only],
    [Target state],
    [protocol-specific descriptor, target-local support and field-availability masks],

    [V0 instruction or V1 actor-visible target],
    [Candidate table],
    [row identity, local pose, target relation, actor validity and padding mask],

    [actor input; row-aligned], [Value query], [requested residual horizon $h$ and its availability mask],
    [model-visible query; not scene evidence],
    [Candidate supervision],
    [one-step root gain, diagnostic target RRI and `q_train_mask`],

    [supervision only],
    [Selected transition],
    [factual action index and row id, reward, discount, terminal and successor identity],

    [training linkage only], [Audit lineage], [source/store/config hashes, policy, seed and reason vocabulary],
    [CPU audit data; not a learned feature], bottomrule(),
  )),
  caption: [Canonical DTO ownership. Model inputs, horizon queries, supervision, transition linkage, and provenance are distinct types even when collated in one training batch.],
) <tab:thesis-qh-dto-contract>

The maximum supported horizon $H$ is an experiment and checkpoint contract. The remaining budget $b_t$ belongs to the rollout state and limits admissible queries. The requested residual horizon $h$ is the value query and must satisfy $1 <= h <= b_t <= H$. A fixed-H=2 tracer may set $h=b_t$, but the thesis-core variable-horizon scorer must receive $h$ explicitly. Separate $Q_1, dots, Q_H$ heads remain a structural control rather than the canonical interface. The step index $t$ remains lineage by default; it becomes a learned feature only in a named non-stationarity ablation because $h$, the dynamic state, and the budget already encode the minimal time-to-go semantics.

The canonical model call is therefore conceptually `score(static_context, dynamic_state, target_state, candidate_table, requested_horizon)`. One state can be evaluated for several residual horizons by adding a horizon axis and returning values of shape $[B, L, N_q]$, or by flattening the same horizon--candidate queries into the batch. Static scene, target, and candidate encodings are reused. The horizon mask excludes $h>b_t$; it does not invent future observations, and no causal attention between horizon queries is required.

Padding masks, modality-presence masks, source-role masks, action masks, training masks, and horizon-availability masks remain distinct. A missing modality must not be encoded as an ordinary zero observation, padding must not be mistaken for missing evidence, and an unsupported horizon must not be silently clamped to the available budget.

The target descriptor separates identity, geometry, observed support, confidence, and source:

$
  #eqs.entity.target_descriptor
$

The learned token combines that descriptor with target-local scene support:

$
  #eqs.model.qh_target_token
$

In the current V0 data, target geometry is GT-derived and several generic descriptor fields are unmeasured placeholders. The model contract should therefore use protocol-specific variants such as `V0GtTargetState` and `V1ObservedTargetState`, or carry an explicit availability mask per optional field. The same numerical zero cannot simultaneously mean absent support and measured zero support.

Target-independent static scene encodings may be reused across several target tasks. The candidate table, however, is not generally shared: target-bearing, lateral-bypass, and target-looking candidates depend on the selected target. Multi-target evaluation must therefore either carry one candidate table per target or construct a union table with a target--candidate availability mask; only physically identical rows may share candidate encodings.

=== Relative candidate geometry

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@zhou2019continuity @zhou2023query @LFF-li2021],
  source: [#gh("aria_nbv/aria_nbv/data_handling/qh.py"); #gh("aria_nbv/aria_nbv/vin/models/target_finite_horizon.py"); #gh("aria_nbv/aria_nbv/vin/modules/pooling.py")],
  gate: [frame-transform, row-shuffle, and held-out descriptor ablations],
)[Root-relative candidate geometry and a minimal candidate-local target relation are implemented. The complete candidate-frustum and dynamic-memory relation descriptor remains planned.]

Canonical rigid transforms remain in the store. The reader or tensor adapter derives a candidate pose relative to the current decision reference rather than learning the arbitrary world origin:

$
  #eqs.spatial.candidate_reference_transform
$

The world poses $bold(T)_(w,r_t)$ and $bold(T)_(w,c_(t,i))$ locate the current reference and candidate camera. Their product $bold(T)_(w,r_t)^(-1) bold(T)_(w,c_(t,i))$ expresses candidate $i$ in the current reference frame; $bold(delta)_(r_t,i)^p$ and $bold(R)_(r_t,i)$ are its relative translation and rotation.

$
  #eqs.spatial.candidate_pose_features
$

The pose vector is a menu of candidate descriptors rather than a fixed mandatory encoding. It collects relative translation, one continuous rotation encoding, metric range, planar bearing, height change, and camera-up or frustum orientation. The six-dimensional rotation representation is the baseline candidate because it is continuous for neural regression; axis--angle, quaternion, Fourier, or equivariant alternatives remain matched ablations and must not be concatenated silently with the baseline.

The target relation is encoded separately so candidate self-motion cannot be confused with target conditioning:

$
  #eqs.spatial.candidate_target_relation
$

Here $bold(delta)_(e|i)^p$ is the target displacement in the candidate frame, its norm is candidate--target range, $cos theta_(t,e,i)^"opt"$ measures optical-axis alignment, $beta_(t,e,i)^"elev"$ is relative elevation, and $lambda_(t,e,i)^"obb"$ denotes the declared target-box/frustum relation vector for the experiment. These channels are also descriptor candidates: each must be enabled, removed, or replaced in a named ablation. Vector or 3D visualizations of the displacement, optical axis, frustum, and target box are diagnostic explanations of those channels, not additional model inputs.

Continuous rotation features, metric range, bearing, elevation, height, and frustum variables preserve physical task structure. Query-local relative positional encoding is a later ablation for candidate--target, candidate--history, or candidate--candidate interactions:

$
  #eqs.spatial.candidate_query_local_frame
$

$
  #eqs.spatial.candidate_query_rpe
$

This adopts QCNet's query-centric geometric discipline, not its trajectory decoder or streaming claim @zhou2023query. World-frame copies remain audit facts; the learned interface should expose one authoritative local transform rather than recomputing the same relation through multiple fields.

=== Candidate rows and directional history

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@e3nn-SphericalHarmonics-2025 @Hestia-lu2026],
  source: [#gh("aria_nbv/aria_nbv/vin/models/target_finite_horizon.py"); #gh("docs/contents/theory/candidate_view_dependence.qmd")],
  gate: [directional-novelty fixture and matched architecture ablation],
)[The H=2 tracer consumes set-valued pose history, for which at most one prior selected action is observable. Ordered temporal encoding and directional memory remain required for H>=3.]

The canonical candidate row is a local query, not a duplicate of the full state. It contains candidate self pose, candidate--target relation, and candidate-local scene/support reads. Shared target, scene, ordered history, requested horizon, and any admitted budget context are supplied once as state/query tokens. Hard action validity and padding remain masks; candidate family or sampler provenance is audit-only by default and may enter the model only as a named ablation.

Viewing history is not reducible to camera distance. For a target-local point or cell, selected camera directions define a signed first moment together with the second-moment memory

$
  #eqs.spatial.direction_memory_moment
$

The signed first moment distinguishes opposite approach directions, whereas the second moment records concentration along viewing axes. Their query-relative projections form directional features without committing to a full spherical-harmonic field. Low-order spherical harmonics are promoted only if these moments improve over ordered pose history and still leave systematic directional errors.

Optional appearance, ray, and directional blocks require three independent indicators where applicable: modality presence, batch padding, and evidence source. Removing one optional source must alter only its masked branch, and counterfactual-only geometry must not receive fabricated RGB, DINO, detector, or EVL descriptors.
