#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": *

== Scene-Representation Requirements <sec:thesis-scene-representation>

=== Decision sufficiency rather than representation category

ARIA-NBV does not require one universal reconstruction format. It requires an actor-visible state from which the finite-horizon model can compare a selected target $e$ and a physical candidate pose $q_(t,i)$:

$
  h_(t,e,i) = op("Read")(M_t, z_e, q_(t,i), H_t),
  quad
  Q_(H,theta)(h_(t,e,i)).
$

Here $M_t$ denotes persistent scene evidence, $z_e$ the actor-visible target record, and $H_t$ the selected-view history. A representation is sufficient only if its readout preserves the distinctions that can change target-specific return and if the state can be updated after a selected observation. This criterion is stricter than requiring a feature vector to predict object class or scene layout, yet narrower than requiring a photorealistic or globally dense reconstruction.

The representation problem consequently separates into three interfaces. A *target proposer* must establish which physical entity is being improved, at minimum through a detected or tracked @oriented-bounding-box:short with pose, extents, semantic distribution, confidence, timestamp, and source. A *persistent evidence state* must retain the observed geometry and visibility history relevant to that entity and to feasible candidate paths. A *candidate-conditioned readout* must interrogate the same state in target-local, candidate-local, and ray-relative coordinates. A detector is therefore not automatically a scene representation, and a scene encoder need not predict boxes. This separation is necessary for controlled comparisons: replacing the detector must not silently replace the planning memory, and enlarging the memory must not be reported as improved target recognition.

Prior work supports these interfaces from different directions. VIN-NBV projects an enriched observed point cloud into each candidate camera, demonstrating that candidate utility depends on a view-conditioned readout rather than on a candidate-independent scene summary @VIN-NBV-frahm2025. GenNBV maintains occupied, free, and unknown voxel states together with semantic and action-history embeddings, demonstrating that reconstruction progress and acquisition history are not recoverable from an unqualified surface cloud @GenNBV-chen2024. Hestia associates visibility with voxel faces, motivating directional observation memory instead of a scalar observed/unobserved flag @Hestia-lu2026. EFM3D supplies the Aria-native multi-frame OBB detector and local learned field, whereas SceneScript shows that sparse semidense evidence can also support scene layout and gravity-aligned OBB prediction @EFM3D-straub2024 @SceneScript-avetisyan2024. These representations are complementary precedents, not interchangeable answers to the ARIA-NBV state problem.

=== Symmetries, observable distinctions, and causality

The desired invariances follow from the physical decision problem. Applying a common translation, or a common yaw rotation about gravity, to the current camera, target, scene evidence, history, and candidate set must not change the value assigned to the same physical action. Point and sparse-cell order are irrelevant, and permuting the finite candidate table must permute the output rows without changing their values. Relative frames and permutation-equivariant set processing therefore remove nuisance coordinates without erasing task geometry @GeometricDeepLearning-bronstein2021 @DeepSets-zaheer2017 @SetTransformer-lee2019.

Full $op("SE")(3)$ invariance would be incorrect. Gravity, metric scale, target orientation and extent, candidate viewing direction, path geometry, and the directional history of observations remain physically meaningful. Temporal order is also not a permutation symmetry: the same set of selected poses can induce different feasible successors or state updates when acquisition and motion constraints are history dependent.

The state must preserve actor-visible target identity, metric target--candidate relations, observed surfaces, observed free space, unknown space, occlusion structure, support count, uncertainty, recency, and observation direction. Missing support must be represented by masks and reason codes rather than by ordinary zeros or low predicted RRI. Otherwise the model cannot distinguish an unsupported query from a confidently empty region or from a genuinely uninformative candidate.

Causality imposes an additional asymmetry. Logged snippets may contain calibrated RGB/SLAM streams, poses, semidense points, image-foundation features, EVL fields, and actor-visible detections. A counterfactual successor may add selected geometry, traversed free space, support counts, and directional history. It may not receive fresh RGB, DINO, detector, or EVL features from an unvisited pose unless a separately validated actor-visible modality generator is introduced. Ground-truth meshes, GT target crops, all-candidate renders, and oracle RRI remain supervision or evaluation products.

=== When a latent scene state is sufficient

A latent representation is admissible; a non-spatial bottleneck is not automatically sufficient. The decisive question is whether the latent state preserves reward-relevant and transition-relevant distinctions. For ARIA-NBV, the readout must still determine where evidence lies relative to the target and each candidate, which parts are unsupported, what a candidate ray encounters, and how the state changes after the chosen view.

The appropriate latent forms are therefore spatially indexed: point tokens with coordinates, sparse voxel or ray-cell tokens, object tokens with OBB poses, or a small target-canonical feature grid. Each element requires a declared coordinate frame, a spatial support domain, an observed/valid mask, source and time or rollout-step provenance, and an update rule. A learned latent field is acceptable when it exposes target crops and candidate-ray queries directly or when a validated decoder recovers them. A single globally pooled vector may accompany such a state, but should not replace indexed evidence until it matches the spatial representation in oracle-evaluated target-RRI ranking, gauge and permutation tests, and rollout-transition fidelity.

This distinction also constrains uncertainty. Generic uncertainty is not itself task relevance. A useful state must support *target-conditioned uncertainty*: uncertainty associated with the selected object and visible from candidate $q$ should contribute differently from equally uncertain background geometry. The object-centric 3DGS results discussed below provide an explicit instance of this principle.

=== What EVL actually provides

EFM3D's @egocentric-voxel-lifting:short model remains the primary Aria-native target proposer and local feature source @EFM3D-straub2024. The current configuration uses a frozen DINOv2.5 ViT-B image encoder, a DPT-style projection to 32-channel dense feature maps, and a $48^3$ gravity-aligned voxel grid with extent $[-2,2] times [0,4] times [-2,2]$ metres, anchored to the final RGB pose of the snippet. Semi-dense point and free-space masks are concatenated to the lifted image evidence before a 3D encoder--decoder predicts occupancy and gravity-aligned 7-DoF OBB fields.

The image and volume outputs must be distinguished. `rgb/token2d` contains the patch-level, potentially multi-layer DINO token maps. `rgb/feat2d_upsampled` contains the lower-dimensional DPT/CNN-transformed maps used by the lifter, with abstract shape $B times T times C_(2D) times H_f times W_f$ and $C_(2D)=32$ in the pinned configuration. These maps exist for every logged RGB frame and are not clipped by `voxel_extent`. They are learned contextual image descriptors, not semantic labels and not point-local measurements: ViT attention and dense upsampling mix information across an image neighbourhood.

The spatial restriction arises during lifting. EVL constructs voxel centres only inside the configured grid, projects those centres into the logged cameras, samples the image maps, averages valid projections, and appends point/free-space evidence. Consequently, `voxel/feat`, the neck field, and all dense heads are finite-support three-dimensional tensors even though the source image maps cover all logged frames. In the released implementation, `neck/occ_feat` and `neck/obb_feat` currently refer to the same neck tensor; they are semantic access names rather than independently learned branches. Head probabilities are interpretable, but are task-collapsed and should not be mistaken for the only latent evidence inside EVL.

There is no hidden global EVL volume containing every region visible somewhere in the video. The 2D encoder has processed the logged images, but the 3D neck has processed only the lifted local cube. EFM3D obtains persistence through explicit OBB tracking and fusion of overlapping local occupancy predictions, not through an unexposed global token @EFM3D-straub2024.

A useful implementation invariant follows from the detector construction. EVL decodes an OBB centre from a centerness voxel plus a bounded local offset. An OBB generated by the same forward pass must therefore have its centre inside, or only marginally outside, that pass's voxel support. A same-pass centre far outside the grid indicates a frame, timestamp, tracker, or cache-lineage error. The box extents may nevertheless cross the grid boundary, and a tracked box or a prediction produced by another snippet or detector may legitimately lie outside the current root volume. Detecting a box therefore establishes a target hypothesis; it does not imply dense learned support over the entire box volume.

=== Target-canonical reads and scene-scale derivations

For an EVL target prediction with object pose $T^w_e$ and extents $d_e$, a target-aligned representation can be derived without keeping the box axis-aligned in the EVL frame. Let $u_k in [-1,1]^3$ be a fixed lattice in normalized object coordinates. Its sampling locations in the voxel frame are

$
  x^v_(e,k)
  = (T^w_v)^(-1) T^w_e
    op("diag")(d_e / 2) u_k,
  quad k = 1, dots, K,
$

where $T^w_v$ is the stored voxel-to-world transform. Trilinear sampling of `voxel/feat` or the shared neck tensor yields an orientation-normalized local crop. The crop must retain its in-bounds mask, image-projection counts, semidense and free-space support, and selected head probabilities. It may remain a small 3D token grid or be pooled with mask-aware statistics into $z_e$. Missing crop volume is a feature, not ordinary zero-valued evidence.

When a target is only partly supported by the root cube, the actor-visible evidence can be extended in three ways. First, semidense or fused world points inside an expanded OBB provide direct metric support beyond the crop boundary. Second, logged image descriptors may be attached to those world points. For point $p_j^w$, calibrated projection samples `rgb/feat2d_upsampled` in logged frames and pools only valid, genuinely observed views. Projection validity alone is insufficient: EFM3D's sampling mask establishes that a point is in front of the camera and inside the image domain, but not that it is unoccluded. Native observation lineage, depth consistency, or a conservative z-buffer must therefore gate descriptor attachment. Pixels without a corresponding actor-visible 3D carrier remain ungrounded; not all DINO image features are automatically mapped to the semidense cloud. Third, a target-centred grid can be re-lifted from the already logged feature maps. This produces a new spatial latent outside the root grid, but the released 3D neck and heads were trained on final-pose-centred grids, so target-centred re-lifting is an adaptation experiment rather than extraction of a pre-existing global field.

These extensions preserve the crucial boundary: they can reorganize evidence from logged observations, but they cannot invent appearance or detector evidence at an unvisited candidate pose.

=== Object-conditioned evidence and the 3DGS precedent

Jeong et al. provide a particularly relevant example of a spatial representation whose semantics participate directly in view selection @ObjectCentricNBV-jeong2026. Their object-aware 3D Gaussian Splatting map augments each Gaussian primitive with a one-hot-trained object vector. After softmax and alpha blending, this vector defines per-primitive and per-pixel instance probabilities. The representation is therefore not merely a global target token: object membership is attached to spatial, renderable primitives.

Their NBV criterion also shows why target relevance must modulate uncertainty. Conventional Hessian- or Fisher-style information gain can be dominated by well-observed primitives because those primitives contribute strongly to the rendering Jacobian. Jeong et al. counter this exploitation bias by weighting each Gaussian according to low opacity and low object confidence, thereby emphasizing poorly fitted or occluded regions. For object-centric planning, the maximum instance probability is replaced by the probability assigned to the selected target. Abstractly, the same design principle can be written as

$
  U_e(q) = sum_j w_(j,e) u_j(q),
  quad
  0 <= w_(j,e) <= 1,
$

where $u_j(q)$ is candidate-visible uncertainty or expected improvement for spatial element $j$, and $w_(j,e)$ is its actor-visible membership and support weight for target $e$. In ARIA-NBV, $w_(j,e)$ may initially be a soft OBB-membership weight combined with detection confidence and observed support; a learned instance field is a later ablation. Uncertainty outside the target should not dominate target-specific RRI merely because it is large.

In the authors' cluttered-scene 3DGS setting, confidence-weighted object-aware selection reduced depth error by up to 77.14% on their synthetic data and 34.10% on GraspNet relative to evaluated baselines. Targeting a specified object instead of the whole scene yielded an additional 25.60% reduction in depth error for that object, and shifted selected views toward the object's informative side @ObjectCentricNBV-jeong2026. These numbers are not directly transferable to ASE, semidense reconstruction, or RRI supervision. Their value here is evidential: spatial instance membership and target-conditioned confidence can materially change which views are selected in clutter.

Object-aware 3DGS is not the default ARIA-NBV memory. It requires per-scene optimization and object masks; mask errors propagate into reconstruction and NBV; and it does not supply the Aria-native OBB proposal contract. It is instead a strong explicit-map ablation and a design precedent for attaching target membership to scene elements, rendering candidate-conditioned evidence, and separating uncertainty from task relevance.

=== Selected representation hypothesis

The thesis state is therefore layered rather than a categorical choice between point cloud, voxel field, TSDF, or latent vector:

$
  M_t = (P_t^"semi/fused", R_t^"ray", V_0^"EVL", A_t^"logged"),
$

with target record

$
  z_e = (B_e, p_e^"class", c_e, s_e, C_e^"EVL").
$

Here $P_t^"semi/fused"$ provides broad actor-visible surface evidence; $R_t^"ray"$ is a sparse occupied/free/unknown memory with support, uncertainty, recency, and directional history; $V_0^"EVL"$ is the root local EVL field with its pose and finite support; and $A_t^"logged"$ is an optional visibility-gated appearance bank. The target record contains the actor-visible OBB $B_e$, semantic probabilities, confidence, support diagnostics, and the masked target-canonical EVL crop $C_e^"EVL"$ when available.

This decomposition is a hypothesis to evaluate, not a claim that sparse ray memory is universally optimal. Its rationale is that each carrier preserves a different planning variable. The OBB and target crop establish entity identity and local learned evidence. Semidense or fused points retain broad measured geometry and support a simple target crop. The ray map supplies distinctions absent from a surface cloud: observed free space, unknown space, occlusion order, and directional observation history. Candidate rows query target-relative pose, target--frustum intersection, ray evidence, local EVL support, and selected history rather than consuming one monolithic scene vector. Logged descriptors add appearance only after geometry, visibility, and provenance are stable.

A dense occupancy grid or TSDF is a valid baseline when its observation weights and unknown mask are retained, but memory and update cost grow with world extent. A neural implicit SDF is spatially queryable and compact, but commonly introduces per-scene optimization or learned completion and weakens the distinction between measured and inferred geometry. A Gaussian map is explicit and renderable and can carry object probabilities, but currently incurs a separate reconstruction/optimization stack. Point and sparse-convolution networks can encode $P_t^"semi/fused"$ or $R_t^"ray"$, but remain memory encoders rather than target proposers @PointNeXt-qian2022 @PointTransformerV3-wu2024 @KPConv-thomas2019 @MinkowskiEngine-choy2019. No carrier removes the need for provenance, target-conditioned reads, and rollout-safe updates.

Within the documented ATEK path, EVL and Cube R-CNN are the directly supported static 3D detection models. EVL remains the primary multi-frame Aria-native detector and local evidence source. Cube R-CNN, for which ATEK supplies the single-frame adaptor and ASE-oriented training assets, is the simplest detector-only comparison @omni3d-cubercnn-brazil2023 @ATEK-Repo. SceneScript provides an additional ASE-trained sparse-point model that predicts scene layout and gravity-aligned OBBs, but it is not an ATEK drop-in detector and does not itself provide ray-aware counterfactual memory @SceneScript-avetisyan2024. These detector alternatives should be compared while holding the scene-memory and target-matching protocols fixed.

=== Controlled ablations and acceptance tests

The representation study should proceed cumulatively so that gains remain attributable. *R0* contains target OBB geometry, class/confidence, support, history, budget, and candidate-relative pose. *R1* adds the masked target-canonical EVL crop and local head channels. *R2* adds target, candidate-frustum, and target--frustum pools over semidense or fused points. *R3* adds sparse ray-aware occupied/free/unknown and directional-history queries. *R4* adds compressed, visibility-gated DINO-on-point descriptors. An optional *R5* attaches soft target-membership or instance probabilities to scene elements and tests target-conditioned uncertainty weighting, following the object-aware 3DGS precedent without changing the target-RRI objective.

Detector ablations replace EVL OBBs with Cube R-CNN or SceneScript predictions while holding the best available memory level fixed. Memory-encoder ablations replace only the encoder over $P_t^"semi/fused"$ or $R_t^"ray"$. A 3DGS experiment changes the explicit map and update mechanism and must therefore be reported as a representation-system ablation rather than as a small feature toggle.

Before entering the main #symb.rl.qh comparison, a representation must pass same-pass OBB-support checks, world-frame translation and yaw stress tests, target-crop transform tests, point and candidate permutation tests, free-versus-unknown tests, out-of-extent mask tests, deterministic update/replay tests, and actor/oracle provenance audits. Scientific comparison then uses held-out target-RRI ranking and oracle regret, calibration across acquisition stages and support strata, oracle evaluation of selected actions, finite-horizon return prediction, storage, and runtime. Feature dimensionality, visual reconstruction quality, or OBB detection quality alone does not establish that a state is better for target-conditioned NBV.
