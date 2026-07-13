#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

== Scene-Representation Requirements <sec:thesis-scene-representation>

=== Start from the decision query

ARIA-NBV does not require one universal reconstruction format. It requires an actor-visible state from which the finite-horizon model can compare a target $e$ and a physical candidate pose $q_(t,i)$:

$
  h_(t,e,i) = op("Read")(M_t, z_e, q_(t,i), H_t),
  quad
  Q_(H,theta)(h_(t,e,i)).
$

Here $M_t$ is persistent scene evidence, $z_e$ is the actor-visible target record, and $H_t$ is selected-view history. The representation is sufficient only if its readout preserves the distinctions that change target-specific return and if it can be updated after a selected observation. This criterion is stricter than asking whether a feature vector predicts object class or scene layout. It is also narrower than requiring a photorealistic or globally dense reconstruction.

The representation contract therefore has three separate interfaces:

- *Target proposal:* produce an actor-visible target identity and geometry, at minimum a detected or tracked @oriented-bounding-box:short with pose, extents, semantic distribution, confidence, timestamp, and source frame.
- *Persistent scene evidence:* retain observed surface, observed free space, unknown space, uncertainty, support, and observation history over the region that can affect the target or a candidate path/frustum.
- *Candidate-conditioned readout:* query the same state in target-local, candidate-local, and ray-relative coordinates and return one typed feature row per candidate.

A detector is therefore not automatically a scene representation, and a good scene encoder need not predict boxes. Keeping these roles separate permits a controlled detector comparison while holding the planning memory fixed.

The current literature set supplies complementary, not interchangeable, precedents. VIN-NBV projects an enriched observed point cloud into each candidate camera and shows the value of candidate-conditioned geometric readouts @VIN-NBV-frahm2025. GenNBV maintains an occupied/free/unknown probabilistic grid together with semantic and action-history embeddings, showing why unknown space and acquisition history cannot be recovered from a surface cloud alone @GenNBV-chen2024. Hestia stores visibility by voxel face, motivating directional observation memory rather than a scalar seen/unseen flag @Hestia-lu2026. EFM3D contributes the Aria-native multi-frame OBB detector and local learned field, while SceneScript demonstrates that sparse point evidence can also support global layout and OBB prediction @EFM3D-straub2024 @SceneScript-avetisyan2024. ARIA-NBV combines these requirements under a target-specific reconstruction objective; it does not adopt any one source representation unchanged.

=== Information that the state must preserve

#figure(
  table(
    columns: (0.77fr, 1.12fr, 1.30fr),
    toprule(),
    table.header([*Requirement*], [*Operational meaning*], [*Acceptance consequence*]),
    midrule(),
    [Actor-visible causality],
    [Every feature is derived from logged observations or from an already selected successor.],
    [Ground-truth meshes, target crops, all-candidate renders, and oracle RRI remain supervision or evaluation products.],
    [Target identity and support],
    [The target record contains OBB geometry, class/confidence, source time, and observed support.],
    [Two nearby objects or an ambiguous detection cannot silently share one target token.],
    [Metric relative geometry],
    [Target, candidate, current camera, and history are expressed in consistent local frames.],
    [Changing the arbitrary world origin or global yaw cannot change the score of the same physical configuration; gravity, scale, target orientation, and camera frusta remain meaningful.],
    [Spatial queryability],
    [Evidence can be cropped by the target OBB and queried by candidate frusta or rays.],
    [A single pooled scene vector is insufficient unless a decoder demonstrably recovers these target--candidate relations.],
    [Known free versus unknown],
    [Ray traversal and support masks distinguish observed empty space from unobserved space.],
    [Missing support cannot be encoded as ordinary zero features or as low RRI.],
    [Updateability],
    [The state admits a deterministic update from selected geometry and history.],
    [Repeated updates, state replay, and rollout recomputation must agree up to stated numerical tolerance.],
    [Set and sampling robustness],
    [Point/cell order is irrelevant; candidate rows are permutation equivariant; density and uncertainty remain explicit.],
    [Shuffling points or candidate rows cannot change the value assigned to the same physical candidate.],
    [Support domain and provenance],
    [Every local feature carries its coordinate frame, spatial support, checkpoint/configuration, and observation lineage.],
    [Out-of-support is an explicit mask and reason code, not evidence that the target or candidate is invalid.],
    bottomrule(),
  ),
  caption: [Task requirements for an actor-visible target-conditioned NBV state. The geometric symmetry requirements follow the local-frame and permutation arguments in @GeometricDeepLearning-bronstein2021 and Section @sec:thesis-geometric-learning-theory.],
) <tab:scene-representation-requirements>

These requirements rule out full $op("SE")(3)$ invariance as a blanket objective. The task should be invariant to arbitrary gauge choices, but not to gravity, metric scale, target orientation, or camera direction. Likewise, temporal order in selected history is not a permutation symmetry, although point samples, sparse cells, and candidate-table rows have set structure.

=== When a latent representation is sufficient

A latent representation is admissible; a non-spatial bottleneck is not automatically admissible. The decisive question is whether the latent state preserves reward-relevant and transition-relevant distinctions. For ARIA-NBV this requires more than a compact vector that summarizes the logged snippet: the model must still know where evidence lies relative to the target and each candidate, which cells are unsupported, and how the state changes after a selected view.

The preferred latent form is therefore *spatially indexed*: point tokens with world or target-local coordinates, sparse voxel/cell tokens, object tokens with OBB poses, or a small target-canonical feature grid. A dense global extent is not required. Each latent element instead needs:

- a metric coordinate or object pose in a declared frame;
- a support domain and valid/observed mask;
- a source and timestamp or rollout step;
- an update rule; and
- a read function for target crops, candidate rays, and target--candidate intersections.

A pooled global token may accompany this state, but it should not replace the indexed evidence until an ablation shows equal oracle-evaluated target-RRI ranking, equal frame-invariance behavior, and equal rollout-update fidelity. Per-candidate queries over indexed tokens are preferable to conditioning every candidate on the same unqualified scene vector.

=== What EVL actually provides

EFM3D's @egocentric-voxel-lifting:short model is the primary Aria-native target proposer and local feature source @EFM3D-straub2024. EVL projects frozen multi-frame image features into a gravity-aligned voxel grid whose frame is constructed from the final RGB pose of the snippet. The released inference configuration uses a $4 "m" times 4 "m" times 4 "m"$ grid with extent $[-2,2] times [0,4] times [-2,2]$ metres in the voxel frame. Semi-dense point and free-space masks are concatenated before a 3D encoder--decoder predicts occupancy and gravity-aligned 7-DoF OBB fields.

The reusable outputs are not limited to the final heads. The released implementation exposes:

- logged 2D tokens and upsampled feature maps, such as `rgb/token2d` and `rgb/feat2d_upsampled`;
- the lifted pre-neck volume `voxel/feat`, observation counts, point/free-space inputs, voxel-centre world coordinates, voxel pose, and extent;
- one 3D U-Net neck feature volume; and
- occupancy, centerness, box, class, and post-processed OBB predictions.

In the released EVL code, `neck/occ_feat` and `neck/obb_feat` refer to the same neck tensor. ARIA-NBV should therefore store one copy unless a different checkpoint or fork proves that the branches diverge. Head probabilities remain useful interpretable channels, but they are task-collapsed and should not be mistaken for the only latent state inside EVL.

There is also no hidden global EVL volume containing every place seen by the input video. The 2D backbone has processed all logged images, but the lifter samples those features only at voxel centres inside the configured local grid. EFM3D obtains persistence explicitly by tracking OBB predictions and by fusing overlapping local occupancy predictions; persistence is not recovered from an unexposed global token @EFM3D-straub2024.

A useful implementation invariant follows from the detector construction. EVL decodes an OBB centre from a centerness voxel plus a bounded local offset. An OBB produced by the *same forward pass* must therefore have its centre inside, or only marginally beyond, that pass's voxel support. A same-pass prediction whose centre lies far outside the support indicates a coordinate-frame, timestamp, tracker, or cache-lineage error. An OBB may still extend beyond the cube, and a tracked box or a box produced by another snippet or detector may legitimately lie outside the current root volume.

=== Target-canonical reads from EVL

For an EVL target prediction with object pose $T^w_e$ and extents $d_e$, ARIA-NBV can derive a target representation without keeping the box axis-aligned in the EVL frame. A fixed lattice $u_k in [-1,1]^3$ is defined in normalized object coordinates and mapped into the EVL voxel frame:

$
  x^v_(e,k)
  = (T^w_v)^(-1) T^w_e
    op("diag")(d_e / 2) u_k,
  quad k = 1, dots, K.
$

Here $T^w_v$ is the stored voxel-to-world transform. Trilinear sampling at $x^v_(e,k)$ yields a small orientation-normalized crop from `voxel/feat` or the shared neck tensor. The crop is accompanied by its in-bounds mask, projection/observation counts, point and free-space evidence, and selected head probabilities. The crop can be retained as a small 3D token grid or pooled with mask-aware statistics into the target descriptor $z_e$. The crop removes arbitrary world translation and global yaw from its tensor indexing; the OBB-relative pose carried alongside it preserves target orientation relative to gravity and the candidate.

The target read should use the following source order:

1. the shared EVL neck or lifted volume for learned local evidence;
2. point, free-space, count, occupancy, centerness, and class channels for interpretable support and calibration;
3. semi-dense or fused world points inside an expanded OBB for evidence beyond the crop boundary; and
4. visibility-gated logged image descriptors only as an appearance ablation.

For a partially clipped crop, the missing fraction is retained as a feature. The crop is not padded with ordinary zeros and then treated as fully observed. If a tracked or externally proposed target lies outside the root EVL support, two actor-visible extensions are possible:

- *Point-carried features:* attach logged image descriptors to observed semi-dense or fused world points after native observation or depth-consistency checks, then crop and pool those points in target coordinates. This is the first extension because it preserves observation lineage and does not assume unvisited imagery @DINOv2-oquab2023 @EFM3D-straub2024.
- *Target-centered re-lifting:* instantiate a new grid around the target and project the already logged 2D EVL feature maps into it using the recorded cameras. This can recover a spatial latent outside the root grid, but the released 3D neck and heads were trained on the final-pose grid distribution. Re-lifting is therefore an explicit ablation that may require adaptation; it is not a free extraction of a pre-existing global feature volume.

Neither path creates RGB, DINO, detector, or EVL evidence at an unvisited candidate pose.

=== Selected representation for ARIA-NBV

The thesis state is a layered representation rather than a choice between “point cloud” and “latent field”:

$
  M_t = (P_t^"semi/fused", R_t^"ray", V_0^"EVL", A_t^"logged"),
$

where $P_t^"semi/fused"$ is broad actor-visible surface evidence, $R_t^"ray"$ is sparse occupied/free/unknown evidence with support and directional history, $V_0^"EVL"$ is the root local EVL field with its pose and finite extent, and $A_t^"logged"$ is an optional visibility-gated appearance bank. The target record is

$
  z_e = (B_e, p_e^"class", c_e, s_e, C_e^"EVL"),
$

with actor-visible OBB $B_e$, semantic probabilities, confidence, support diagnostics, and the masked target-canonical EVL crop $C_e^"EVL"$ when available.

This decomposition assigns each carrier a role:

- The OBB and canonical crop identify the target and preserve local learned evidence.
- Semi-dense/fused points provide broad, directly observed metric support and a simple target crop.
- The sparse ray map supplies information that a surface point cloud lacks: known free space, unknown space, occlusion support, recency, and observation direction.
- Candidate rows read target-relative pose, ray evidence, target--frustum intersection, local EVL support, and history; they do not ingest a monolithic global vector.
- Logged descriptors add appearance only after geometric and visibility contracts are stable.

A dense global occupancy or TSDF field is a valid baseline if its observed-weight mask is retained, but its memory grows with the selected world extent. A neural implicit SDF is spatially queryable and compact, but it introduces per-scene optimization, learned completion, and a weaker distinction between measured and inferred geometry. Neither alternative removes the need for an independent target proposer, provenance, or candidate-conditioned reads. The sparse ray-aware map is the default because it preserves the planning distinctions while allocating storage only where observations or queried rays exist.

=== Backbone alternatives and controlled comparisons

#figure(
  table(
    columns: (0.72fr, 1.02fr, 1.38fr),
    toprule(),
    table.header([*Model or carrier*], [*What it contributes*], [*Role in this thesis*]),
    midrule(),
    [EFM3D / EVL],
    [Multi-frame Aria-native OBBs, local lifted image features, surface/free-space evidence, and released checkpoints.],
    [Primary target proposer and local target-evidence source; not the sole persistent scene memory.],
    [Cube R-CNN through ATEK],
    [Single-frame RGB 3D OBBs and ROI features. ATEK provides ASE preprocessing/training support and released ASE-trained example weights @omni3d-cubercnn-brazil2023 @ATEK-Repo.],
    [Easiest detector-only ablation. Hold the scene memory and target-matching protocol fixed so detector quality is not conflated with memory quality.],
    [SceneScript],
    [Sparse semi-dense point encoder with scene-layout commands and gravity-aligned OBB predictions; an ASE-trained checkpoint is released @SceneScript-avetisyan2024.],
    [Global structured-layout and target-proposal ablation. It is heavier and does not by itself provide free/unknown ray memory or counterfactual updates.],
    [Point or sparse 3D encoder],
    [Learned features over semidense/fused points or sparse map cells @PointNeXt-qian2022 @PointTransformerV3-wu2024 @KPConv-thomas2019 @MinkowskiEngine-choy2019.],
    [Memory-encoder ablation only; it still requires EVL, Cube R-CNN, SceneScript, or another actor-visible target proposer.],
    [Dense voxel / TSDF / implicit field],
    [Continuous spatial queries, surface and clearance information, and potentially coherent fusion.],
    [Geometry-memory baseline; compare storage, update cost, observed/unknown calibration, and target-RRI performance, not visual fidelity alone.],
    bottomrule(),
  ),
  caption: [Backbone and carrier roles. Detector substitutions and scene-memory substitutions are evaluated on separate axes.],
) <tab:scene-representation-alternatives>

Within the documented ATEK path, EVL and Cube R-CNN are the directly supported static 3D detection models. SceneScript is an additional ASE-trained alternative available in the repository stack, but it is not an ATEK drop-in detector. Generic point, sparse, radiance-field, or recurrent reconstruction networks are not substitutes for the OBB interface unless they are paired with and evaluated against an actor-visible target proposer.

=== Representation ablations and gates

The representation study is ordered to isolate the source of any gain:

1. *R0 -- target geometry:* OBB, class/confidence, support counts, history, budget, and candidate-relative pose.
2. *R1 -- local learned evidence:* R0 plus the masked target-canonical EVL crop and local head channels.
3. *R2 -- observed spatial support:* R1 plus target and candidate pools over semi-dense/fused points.
4. *R3 -- visibility state:* R2 plus sparse ray-aware occupied/free/unknown and directional-history queries.
5. *R4 -- logged appearance:* R3 plus compressed, visibility-gated DINO-on-point descriptors.

Detector ablations replace EVL OBBs with Cube R-CNN or SceneScript predictions while holding the best available memory level fixed. Memory-encoder ablations replace only the encoder over $P_t^"semi/fused"$ or $R_t^"ray"$. This factorial separation is necessary: otherwise a better target detector can be misreported as a better scene representation, or a larger scene memory can be misreported as better target recognition.

Before a representation enters the main #symb.rl.qh comparison, it must pass: same-pass OBB-support checks; world-frame translation/yaw stress tests; OBB-crop transform tests; point and candidate permutation tests; free-versus-unknown tests; out-of-extent mask tests; deterministic update/replay tests; and actor/oracle provenance audits. Representation quality is then judged by held-out one-step target-RRI ranking, calibration across acquisition stages, oracle-evaluated selected actions, finite-horizon return prediction, storage, and runtime. Feature dimensionality or reconstruction appearance alone is not evidence that the state is better for target-conditioned NBV.
