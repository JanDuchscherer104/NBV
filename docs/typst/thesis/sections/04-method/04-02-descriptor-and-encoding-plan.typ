#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status
#import "../../../shared/tables.typ": publication-table

== Descriptor and Encoding Protocol

=== Persisted replay interface

#thesis_status(
  implementation: "implemented",
  evidence: "pending",
  source: "aria_nbv/aria_nbv/rollouts/zarr_store.py; aria_nbv/aria_nbv/rollouts/qh_reader.py; aria_nbv/aria_nbv/data_handling/qh_data/dataset.py; aria_nbv/tests/rollouts/test_qh_reader.py",
  gate: [preserve row identity, masks, provenance, and source roles in every tensor reader],
)[The factual replay schema, lazy reader, framework-neutral dataset seam, and dense `q_h/` view are implemented and unit-tested. Frozen scientific replay evidence remains pending. The schema is a storage contract; readability from the store does not make a field actor-visible.]

The rollout store preserves source, target, rollout, step, candidate, diagnostic, and lineage tables. Its derived `q_h/` arrays provide a padded state--candidate view without changing factual identities or labels. Target pose and extents in the current oracle task remain privileged ground-truth-derived instructions. The implemented finite-horizon scorer consumes actor-side candidate geometry, selected-pose history, remaining budget, root evidence, and materialization support; target gains, ground-truth associations, mesh diagnostics, crops, current all-candidate renders, and Q labels remain supervision or audit fields. Previously selected depth becomes a later actor input only under a named counterfactual-observation protocol.

#figure(
  publication-table(
    text-size: 8.3pt,
    columns: (0.72fr, 1.45fr, 1.05fr),
    header: ([*Carrier*], [*Persisted content*], [*Learning role*]),
    rows: (
      [Target], [identity, class, pose, extents, reference-relative pose, source and validity provenance], [privileged oracle-task instruction; learned actors need observed or predicted equivalents],
      [Candidate], [stable row identities, world/root-relative pose, masks, reasons, sampler provenance, support fields], [finite action row; privileged diagnostics remain source-gated],
      [Selected chain], [selected row, shell index, step order, policy, seed, successor link, terminal state], [history and temporal-difference linkage],
      [Selected observation], [selected depth, valid mask, calibration, pose and source], [later dynamic-state input only under a declared privileged, sensor-like, or actor-visible protocol; never an all-candidate student input],
      [Oracle labels], [target RRI, target root gain, errors, optional crops and candidate renders], [supervision, evaluation, and audit only],
    ),
  ),
  caption: [Implemented replay carriers and admissible learning roles.],
) <tab:thesis-descriptor-schema>

=== Model-input and DTO contract

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@GeometricDeepLearning-bronstein2021 @zhou2023query @FixedHorizonTD-deAsis2020 @UVFA-schaul2015],
  source: "aria_nbv/aria_nbv/data_handling/qh_data/views.py; aria_nbv/aria_nbv/lightning/qh_module.py; docs/contents/theory/candidate_view_dependence.qmd",
  gate: [typed selected-observation state, positive-width actor-visible target path, source masks, leakage tests, and scientific policy evidence],
)[The implemented DTO seam separates actor inputs, selected-transition supervision, and audit lineage for varying stored chain lengths. The scalar requested-horizon scorer returns a typed conditional-Q/feasibility result, with optional objective-specific CORAL training tensors that never participate in masking. Static scene context, target state, candidate rows, and causal history are implemented; privileged selected depth can now form the S1 point-set residual, while ray-aware dynamic state remains richer planned work.]

The intended input for target $e$ at step $t$ is

$
  #eqs.model.qh_input_contract
$

This equation is an information contract rather than one flat tensor. The corresponding DTO roles are:

#figure(
  publication-table(
    text-size: 8.1pt,
    columns: (0.92fr, 1.35fr, 1.05fr),
    header: ([*DTO role*], [*Candidate content*], [*Visibility*]),
    rows: (
      [`StaticSceneContext`], [root semidense evidence, supported EVL tokens, root frame and EVL extent], [actor input; immutable within one rollout],
      [`DynamicSceneState`], [selected geometry, free/unknown support, recency, source masks and ordered history], [actor input; causal update only],
      [`TargetState`], [protocol-specific descriptor, target-local support and field-availability masks], [oracle-task instruction or actor-visible target],
      [`CandidateTable`], [row identity, local pose, target relation, actor validity and padding mask], [actor input; row-aligned],
      [`ValueQuery`], [scalar requested residual horizon $h$ per state; omission means $h=b_t$], [`bounded_scalar_v1`: $1 <= h <= b_t$; bundle support gates deployment],
      [`CandidateSupervision`], [one-step root gain, diagnostic target RRI and `q_train_mask`], [supervision only],
      [`SelectedTransition`], [factual action index and row id, reward, discount, terminal and successor identity], [training linkage only],
      [`AuditLineage`], [source/store/config hashes, policy, seed and reason vocabulary], [CPU audit data; not a learned feature],
    ),
  ),
  caption: [Finite-horizon scorer DTO roles. Model inputs, scalar horizon queries, supervision, transition linkage, and provenance remain distinct even when collated in one training batch.],
) <tab:thesis-qh-dto-contract>

The maximum supported horizon $H_"max"$ is a scorer, data, and checkpoint contract. Remaining budget $b_t$ is a factual rollout-state field, whereas requested horizon $h$ selects one member of the scalar family $1 <= h <= b_t <= H_"max"$. Implemented `bounded_scalar_v1` validates this full syntactic domain: `None` means $h=b_t$, realized off-diagonal calls may request a shorter supported return, and padding alone uses $h=0$. This admission is not an empirical capability claim. Lightning records the horizons that actually receive targets, and a verified inference bundle rejects any syntactically valid horizon absent from its manifest-bound promoted support. The public output remains $[B,S,N_q]$; multiple horizons use separate scalar calls, while a public vectorized horizon axis remains evidence-gated. The step index $t$ remains lineage by default and becomes a learned feature only in a named non-stationarity ablation.

The executable boundary is `score(actor, requested_horizon=None)`. It hides scene, target, candidate, history, and time encoding behind one deep module and returns conditional Q plus feasibility logits in stored candidate order. The continuous `conditional_q` field retains one meaning for regression and CORAL: it alone enters Bellman backup and online ranking. CORAL additionally carries cumulative logits and its fixed support as training metadata. Static encodings may be reused privately, but the interface exposes no cache lifecycle, encoder handles, candidate sorting, or public horizon axis.

Padding masks, modality-presence masks, source-role masks, action masks, and training masks remain distinct. Out-of-range requests and bundle-unsupported in-range horizons fail closed and are never clamped to the available budget. This does not break recursion from $h$ to $h-1$: the target scorer receives the explicit supported scalar query $h-1$ at the factual successor, whose remaining budget is $b_t-1$. A missing modality must never be encoded as an ordinary zero observation or confused with padding.

The target descriptor separates identity, geometry, observed support, confidence, and source:

$
  #eqs.entity.target_descriptor
$

The learned token combines that descriptor with target-local scene support:

$
  #eqs.model.qh_target_token
$

In the current oracle-task data, target geometry is ground-truth-derived and several generic descriptor fields are unmeasured placeholders. The model contract should therefore use protocol-specific target-state variants, or carry an explicit availability mask per optional field. The same numerical zero cannot simultaneously mean absent support and measured zero support.

Target-independent static scene encodings may be reused across several target tasks. The candidate table, however, is not generally shared: target-bearing, lateral-bypass, and target-looking candidates depend on the selected target. Multi-target evaluation must therefore either carry one candidate table per target or construct a union table with a target--candidate availability mask; only physically identical rows may share candidate encodings.

=== Relative candidate geometry

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@zhou2019continuity @zhou2023query @LFF-li2021],
  source: "aria_nbv/aria_nbv/data_handling/qh_data/views.py; aria_nbv/aria_nbv/lightning/qh_module.py; aria_nbv/aria_nbv/vin/modules/pooling.py",
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
  source: "aria_nbv/aria_nbv/data_handling/qh_data/views.py; aria_nbv/aria_nbv/vin/modules/qh_history_encoders.py; aria_nbv/tests/vin/test_qh_history_encoders.py; docs/contents/theory/candidate_view_dependence.qmd",
  gate: [matched repeated-seed H0/H1 measurement, directional-novelty fixture, and held-out policy evidence],
)[The scorer exposes a versioned selected-pose history seam. H0 is the checkpoint-compatible masked mean; H1 is an implemented exploratory causal Transformer over current-camera-relative pose tokens and relative age. Directional scene memory and scientific longer-horizon evidence remain pending.]

The candidate row is a local query, not a duplicate of the full state. The implemented trunk encodes root-relative and current-relative candidate pose plus global root-scene moments, predicts feasibility before target or horizon conditioning, and then adds a candidate-local target transform for conditional value prediction. Shared target, scene, causal-history, remaining-budget, and requested-horizon context are supplied as state tokens. Hard action validity is not a scorer feature; candidate family or sampler provenance is audit-only by default and may enter the model only as a named ablation.

For each realized state, materialization must provide the complete strictly causal selected-pose prefix. Each selected pose is expressed from the current camera before the shared R6D--LFF pose encoder. H0 reproduces the original masked arithmetic mean exactly. H1 attaches relative age—zero for the immediate predecessor, increasing backward through the prefix—then uses causal self-attention and last-valid-token readout:

$
  #eqs.model.qh_history_controls
$

The learned empty token represents the realized root state with no selected predecessor; padded states remain zero and cannot enter a candidate output. Relative age makes chronology observable without adding absolute step index as a separate feature. Prefix cardinality is also factual causal state, but neither chronology nor cardinality substitutes for the separately encoded remaining budget $b_t$ or requested value horizon $h$. H1 still observes poses only: it carries no selected depth, appearance, free/unknown update, target-local evidence, or new counterfactual render. It is therefore an `S0-pose` ablation rather than a sufficient dynamic reconstruction state.

Viewing history is not reducible to camera distance. For a target-local point or cell, selected camera directions define a signed first moment together with the second-moment memory

$
  #eqs.spatial.direction_memory_moment
$

The signed first moment distinguishes opposite approach directions, whereas the second moment records concentration along viewing axes. Their query-relative projections form directional features without committing to a full spherical-harmonic field. Low-order spherical harmonics are promoted only if these moments improve over ordered pose history and still leave systematic directional errors.

Optional appearance, ray, and directional blocks require three independent indicators where applicable: modality presence, batch padding, and evidence source. Removing one optional source must alter only its masked branch, and counterfactual-only geometry must not receive fabricated RGB, DINO, detector, or EVL descriptors.
