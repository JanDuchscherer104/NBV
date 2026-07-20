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
  source: "aria_nbv/aria_nbv/rollouts/zarr_store.py; aria_nbv/aria_nbv/targets/descriptor.py; aria_nbv/tests/rollouts/test_zarr_store.py",
  gate: [preserve row identity, masks, and provenance in every tensor reader],
)[The factual replay schema and dense `q_h/` view are implemented and unit-tested. Frozen scientific replay evidence remains pending. The schema is a storage contract; readability from the store does not make a field actor-visible.]

The rollout store preserves source, target, rollout, step, candidate, diagnostic, and lineage tables. Its derived `q_h/` arrays provide a padded state--candidate view without changing factual identities or labels. Target pose and extents in the V0 task remain privileged GT-derived instructions. Candidate geometry, selected history, remaining budget, and hard masks are decision inputs; target gains, GT associations, mesh diagnostics, crops, and candidate renders remain label or audit fields.

#figure(
  text(size: 8.3pt, table(
    columns: (0.72fr, 1.45fr, 1.05fr),
    toprule(),
    table.header([*Carrier*], [*Persisted content*], [*Learning role*]),
    midrule(),
    [Target], [identity, class, pose, extents, reference-relative pose, source and validity provenance], [privileged V0 instruction; learned actors need observed or predicted equivalents],
    [Candidate], [stable row identities, world/root-relative pose, masks, reasons, sampler provenance, support fields], [finite action row; privileged diagnostics remain source-gated],
    [Selected chain], [selected row, shell index, step order, policy, seed, successor link, terminal state], [history and temporal-difference linkage],
    [Oracle labels], [target RRI, target root gain, errors, optional crops and selected depth], [loss, evaluation, and audit only],
    bottomrule(),
  )),
  caption: [Implemented replay carriers and admissible learning roles.],
) <tab:thesis-descriptor-schema>

=== Planned model-input contract

#thesis_status(
  implementation: "planned",
  evidence: "pending",
  citation: [@GeometricDeepLearning-bronstein2021 @zhou2023query],
  source: "docs/literature/tex-src/arXiv-QCNet/main.tex, Sec. Query-Centric Scene Encoder, lines 159--161; aria_nbv/aria_nbv/vin/models/target_finite_horizon.py; docs/contents/theory/candidate_view_dependence.qmd",
  gate: [dedicated `q_h/` reader, positive-width target path, and leakage tests],
)[The canonical reader will construct typed target, scene, history, budget, time, horizon, candidate, relation, mask, and provenance tensors. It will not expose oracle labels to the actor graph.]

The intended input for target $e$ at step $t$ is

$
  #eqs.model.qh_input_contract
$

The current candidate shell is shared across targets. Multiple target tokens can therefore be evaluated in parallel by adding a target axis and masking unavailable target--candidate pairs; candidate and scene encodings that are target-independent are computed once. The requested horizon and current step remain explicit because otherwise identical geometry can have different value near termination. A horizon mask prevents a short-horizon query from attending to unavailable future transitions.

The target descriptor separates identity, geometry, observed support, confidence, and source:

$
  #eqs.entity.target_descriptor
$

The learned token combines that descriptor with target-local scene support:

$
  #eqs.model.qh_target_token
$

In the current V0 data, target geometry is GT-derived. The same tensor interface becomes actor-admissible only when populated by an observed or predicted target track. Identity IoU and ambiguity-gap equations are deliberately not part of the present Method because the corresponding actor-visible matcher is not implemented.

=== Relative candidate geometry

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@zhou2019continuity @zhou2023query @LFF-li2021],
  source: "docs/literature/tex-src/arXiv-QCNet/main.tex, Sec. Query-Centric Scene Encoder, lines 159--161; aria_nbv/aria_nbv/data_handling/offline/batch.py; aria_nbv/aria_nbv/vin/modules/pooling.py",
  gate: [frame-transform, row-shuffle, and held-out descriptor ablations],
)[World and root-relative poses are persisted and candidate-query pooling exists. The complete target-relative finite-horizon descriptor is planned.]

Canonical rigid transforms remain in the store. The reader derives a candidate pose relative to the current decision reference rather than learning the arbitrary world origin:

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

This adopts QCNet's query-centric geometric discipline, not its trajectory decoder or streaming claim @zhou2023query.

=== Candidate rows and directional history

#thesis_status(
  implementation: "planned",
  evidence: "pending",
  citation: [@e3nn-SphericalHarmonics-2025 @Hestia-lu2026],
  source: "docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex, Sec. Methods, lines 44--58; docs/contents/theory/candidate_view_dependence.qmd",
  gate: [directional-novelty fixture and matched architecture ablation],
)[The minimal planned directional feature pairs a signed target-local first moment with the second moment. This avoids identifying opposite approach directions. Spherical harmonics remain a richer optional ablation.]

The row token keeps self pose, target relation, support, validity, provenance, selected history, step, horizon, and budget as typed blocks:

$
  #eqs.model.candidate_row_features
$

Viewing history is not reducible to camera distance. For a target-local point or cell, selected camera directions define a signed first moment together with the second-moment memory

$
  #eqs.spatial.direction_memory_moment
$

The signed first moment distinguishes opposite approach directions, whereas the second moment records concentration along viewing axes. Their query-relative projections form directional features without committing to a full spherical-harmonic field. Low-order spherical harmonics are promoted only if these moments improve over pose history and still leave systematic directional errors.

The first reader may omit optional appearance, ray, and directional blocks through explicit missing-modality masks. Missing support is never encoded as an ordinary all-zero observation, and sampler family remains provenance rather than a geometric shortcut.
