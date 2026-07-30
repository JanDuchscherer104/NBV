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
  source: "aria_nbv/aria_nbv/rollouts/zarr_store.py; aria_nbv/aria_nbv/rollouts/qh_reader.py; aria_nbv/aria_nbv/data_handling/qh.py; aria_nbv/tests/rollouts/test_qh_reader.py",
  gate: [preserve row identity, masks, provenance, and source roles in every tensor reader],
)[The factual replay schema, lazy reader, framework-neutral dataset seam, and dense `q_h/` view are implemented and unit-tested. Frozen scientific replay evidence remains pending. The schema is a storage contract; readability from the store does not make a field actor-visible.]

The rollout store preserves source, target, rollout, step, candidate, diagnostic, and lineage tables. Its derived `q_h/` arrays provide a padded state--candidate view without changing factual identities or labels. Target pose and extents in the V0 task remain privileged GT-derived instructions. Candidate geometry, selected history, remaining budget, and hard masks are actor-side fields in the implemented DTO seam; target gains, GT associations, mesh diagnostics, crops, and current all-candidate renders remain label or audit fields. No production finite-horizon scorer currently consumes these tensors. Previously selected depth becomes a later actor input only under a named counterfactual-observation protocol.

#figure(
  text(size: 8.3pt, table(
    columns: (0.72fr, 1.45fr, 1.05fr),
    toprule(),
    table.header([*Carrier*], [*Persisted content*], [*Learning role*]),
    midrule(),
    [Target], [identity, class, pose, extents, reference-relative pose, source and validity provenance], [privileged V0 task instruction; learned actors need observed or predicted equivalents],
    [Candidate], [stable row identities, world/root-relative pose, masks, reasons, sampler provenance, support fields], [finite action row; privileged diagnostics remain source-gated],
    [Selected chain], [selected row, shell index, step order, policy, seed, successor link, terminal state], [history and temporal-difference linkage],
    [Selected observation], [selected depth, valid mask, calibration, pose and source], [later dynamic-state input only under `CF-GT`, `CF-sensor`, or V1; never an all-candidate student input],
    [Oracle labels], [target RRI, target root gain, errors, optional crops and candidate renders], [supervision, evaluation, and audit only],
    bottomrule(),
  )),
  caption: [Implemented replay carriers and admissible learning roles.],
) <tab:thesis-descriptor-schema>

=== Planned model-input and DTO contract

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@GeometricDeepLearning-bronstein2021 @zhou2023query @FixedHorizonTD-deAsis2020 @UVFA-schaul2015],
  source: "aria_nbv/aria_nbv/data_handling/qh.py; aria_nbv/aria_nbv/lightning/qh_module.py; docs/contents/theory/candidate_view_dependence.qmd",
  gate: [fixed-H versus requested-horizon source-owner decision, typed selected-observation state, positive-width V1 target path, source masks, and leakage tests],
)[The implemented DTO seam separates actor inputs, selected-transition supervision, and audit lineage for varying stored chain lengths. The production scorer DTO remains planned. Static scene context, dynamic selected-observation state, target state, and candidate rows are common requirements; an explicit requested-horizon value query is an alternative pending the source-owner decision.]

The intended input for target $e$ at step $t$ is

$
  #eqs.model.qh_input_contract
$

This equation is an information contract rather than one flat tensor. The corresponding DTO roles are:

#figure(
  text(size: 8.1pt, table(
    columns: (0.92fr, 1.35fr, 1.05fr),
    toprule(),
    table.header([*DTO role*], [*Candidate content*], [*Visibility*]),
    midrule(),
    [`StaticSceneContext`], [root semidense evidence, supported EVL tokens, root frame and EVL extent], [actor input; immutable within one rollout],
    [`DynamicSceneState`], [selected geometry, free/unknown support, recency, source masks and ordered history], [actor input; causal update only],
    [`TargetState`], [protocol-specific descriptor, target-local support and field-availability masks], [V0 instruction or V1 actor-visible target],
    [`CandidateTable`], [row identity, local pose, target relation, actor validity and padding mask], [actor input; row-aligned],
    [`ValueQuery`], [optional requested residual horizon $h$ and its availability mask], [proposed model-visible query if the explicit-horizon design is selected],
    [`CandidateSupervision`], [one-step root gain, diagnostic target RRI and `q_train_mask`], [supervision only],
    [`SelectedTransition`], [factual action index and row id, reward, discount, terminal and successor identity], [training linkage only],
    [`AuditLineage`], [source/store/config hashes, policy, seed and reason vocabulary], [CPU audit data; not a learned feature],
    bottomrule(),
  )),
  caption: [Production-scorer DTO design space. Model inputs, optional horizon queries, supervision, transition linkage, and provenance remain distinct even when collated in one training batch.],
) <tab:thesis-qh-dto-contract>

The maximum supported horizon $H$ is an experiment contract and becomes a checkpoint contract once a scorer exists. In the current fixed-horizon direction, remaining budget $b_t$ belongs to the rollout state and supplies time-to-go context without a separate requested-horizon input. The alternative explicit-horizon design would add $h$ with $1 <= h <= b_t <= H$ so one scorer can answer several residual-horizon queries. That alternative, separate $Q_1, dots, Q_H$ heads, and fixed-H models must be compared before the public scorer interface is frozen. The step index $t$ remains lineage by default and becomes a learned feature only in a named non-stationarity ablation.

The common model boundary is conceptually `score(static_context, dynamic_state, target_state, candidate_table, time_context)`, where `time_context` is remaining budget for fixed-H and may additionally contain requested horizon if that design is selected. The explicit-horizon candidate could evaluate one state for several residual horizons and return $[B,L,N_q]$, but this is proposed rather than implemented. Either interface must keep static encodings reusable and must not expose future observations.

Padding masks, modality-presence masks, source-role masks, action masks, and training masks remain distinct. If the explicit-horizon design is selected, its horizon-availability mask is also distinct and an unsupported horizon must not be silently clamped to the available budget. A missing modality must never be encoded as an ordinary zero observation or confused with padding.

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
  source: "aria_nbv/aria_nbv/data_handling/qh.py; aria_nbv/aria_nbv/lightning/qh_module.py; aria_nbv/aria_nbv/vin/modules/pooling.py",
  gate: [frame-transform, row-shuffle, and held-out descriptor ablations],
)[Root-relative candidate geometry and a minimal candidate-local target relation are implemented. The complete candidate-frustum and dynamic-memory relation descriptor remains planned.]

Canonical rigid transforms remain in the store. The reader or tensor adapter derives a candidate pose relative to the current decision reference rather than learning the arbitrary world origin:

$
  #eqs.spatial.candidate_reference_transform
$

$
  #eqs.spatial.candidate_pose_features
$

The target relation is encoded separately so candidate self-motion cannot be confused with target conditioning:

$
  #eqs.spatial.candidate_target_relation
$

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
  source: "aria_nbv/aria_nbv/data_handling/qh.py; docs/contents/theory/candidate_view_dependence.qmd",
  gate: [directional-novelty fixture and matched architecture ablation],
)[The implemented DTO carries set-valued selected-pose history, but no production scorer consumes it yet. Ordered temporal encoding and directional memory remain candidate requirements for longer-horizon models.]

The proposed candidate row is a local query, not a duplicate of the full state. It contains candidate self pose, candidate--target relation, and candidate-local scene/support reads. Shared target, scene, ordered history, and remaining-budget context are supplied once as state tokens; a requested-horizon token is added only if that design is selected. Hard action validity and padding remain masks; candidate family or sampler provenance is audit-only by default and may enter the model only as a named ablation.

Viewing history is not reducible to camera distance. For a target-local point or cell, selected camera directions define a signed first moment together with the second-moment memory

$
  #eqs.spatial.direction_memory_moment
$

The signed first moment distinguishes opposite approach directions, whereas the second moment records concentration along viewing axes. Their query-relative projections form directional features without committing to a full spherical-harmonic field. Low-order spherical harmonics are promoted only if these moments improve over ordered pose history and still leave systematic directional errors.

Optional appearance, ray, and directional blocks require three independent indicators where applicable: modality presence, batch padding, and evidence source. Removing one optional source must alter only its masked branch, and counterfactual-only geometry must not receive fabricated RGB, DINO, detector, or EVL descriptors.
