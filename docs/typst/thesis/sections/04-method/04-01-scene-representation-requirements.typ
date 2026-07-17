#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb

== Scene-Representation Requirements <sec:thesis-scene-representation>

=== Representation as a task-sufficient actor state

ARIA-NBV does not require one universal reconstruction format. It requires an actor-visible state from which the finite-horizon model can compare a selected target $e$ and a physical candidate pose $q_(t,i)$:

$
  h_(t,e,i) = op("Read")(M_t, z_e, q_(t,i), H_t),
  quad
  Q_(H,theta)(h_(t,e,i)).
$

Here $M_t$ denotes persistent scene evidence, $z_e$ the actor-visible target record, and $H_t$ the selected-view history. A representation is sufficient for this decision problem only if its readout preserves distinctions that can change the distribution of target-specific return and if the state admits a well-defined update after a selected observation. This criterion is stricter than requiring a feature vector to predict object class or scene layout, but narrower than demanding a globally dense or photorealistic reconstruction.

Three interfaces follow. First, the target-proposal interface must identify the entity whose reconstruction is optimized. At minimum it provides a detected or tracked @oriented-bounding-box:short, semantic probabilities, confidence, time, source, and observed support. Second, persistent scene evidence must distinguish observed surface, observed free space, unknown space, uncertainty, support, and observation history over regions that can affect the target or a candidate path and frustum. Third, a candidate-conditioned readout must query the same evidence in target-local, candidate-local, and ray-relative coordinates. A detector is therefore not automatically a scene representation, and a scene encoder need not itself predict boxes.

Existing NBV representations support these interfaces in complementary ways. VIN-NBV rasterizes an enriched observed point cloud into each query camera, establishing candidate-conditioned projection as a useful readout rather than scoring one scene vector for every action @VIN-NBV-frahm2025. GenNBV distinguishes occupied, free, and unknown cells in a probabilistic 3D grid and combines that geometry with semantic and action-history embeddings, demonstrating why an observed surface cloud alone does not encode reconstruction progress @GenNBV-chen2024. Hestia stores visibility per voxel face, providing a precedent for directional observation memory rather than a scalar seen/unseen state @Hestia-lu2026. ARIA-NBV adopts these representation principles under target-specific reconstruction return; it does not import their coverage objectives or action policies unchanged.

The state should remove gauge choices without removing physical variables. Applying one common world translation or global-yaw change to target, history, map, and candidates must leave candidate values unchanged. Point and sparse-cell order is irrelevant, while a permutation of candidate rows must induce the same permutation of output values and masked rows must not affect valid rows. These are invariance or equivariance requirements. Gravity, metric scale, target orientation and extent, camera direction, target--candidate relative pose, occlusion, free versus unknown space, support count, uncertainty, and the temporal order of selected observations are not nuisance variables and must remain observable @GeometricDeepLearning-bronstein2021 @DeepSets-zaheer2017 @SetTransformer-lee2019. Full $op("SE")(3)$ invariance would therefore be inappropriate.

Actor-visible causality is equally important. Every input feature must arise from logged observations or from a successor that has already been selected and fused. Ground-truth meshes and target crops, all-candidate renders, and oracle @relative-reconstruction-improvement:short values remain supervision or evaluation products. Out-of-support evidence is represented by masks, support fractions, and reason codes; it is not encoded as an ordinary zero vector or silently converted into low utility. Deterministic replay of the same observations must reproduce the same memory state up to a declared numerical tolerance.

=== Target identity beyond box geometry

An OBB is necessary for target proposal, canonicalization, and geometric cropping, but it is only a coarse spatial support hypothesis. In clutter, a hard inside-box predicate can mix the selected object with occluders, supporting surfaces, or nearby instances. The target representation should consequently permit a soft actor-visible membership field $mu_e(bold(p)) in [0,1]$ in addition to box geometry. Candidate- and target-conditioned pools can then weight each point, cell, or render primitive by its probability of belonging to the target rather than treating every element inside the OBB equally:

$
  g_(t,e,i)^"soft"
  =
  op("Pool")({mu_e(bold(p)_j) bold(x)_j^"pt" :
  bold(p)_j in op("Frustum")(q_(t,i))}).
$

The object-aware 3D Gaussian representation of Jeong et al. provides a direct precedent for this separation @ObjectCentricNBV-jeong2026. Their map attaches object logits to every Gaussian, alpha-composites the resulting class probabilities into image-space masks, and supervises them with instance masks. The same per-Gaussian object probability is then used to define confidence: low opacity and diffuse object probability identify poorly fitted or under-observed primitives, whose Jacobians receive greater weight during information-gain computation. For object-centric planning, the global maximum object probability is replaced by the probability assigned to the selected target, so the utility is concentrated on primitives associated with that object. The reported candidate views consequently shift toward the designated object; the paper reports an additional 25.60% reduction in target depth error relative to whole-scene targeting. This result also shows that compact instance-identity channels can be useful planning state without requiring every primitive to carry a high-dimensional semantic embedding.

Jeong et al. also keep RGB, depth, and mask evidence as distinct rendered outputs. Because their information-gain magnitudes are not directly comparable, each output is normalized by its mean gain over the training views before the terms are combined @ObjectCentricNBV-jeong2026. The corresponding implication for ARIA-NBV is that geometry, appearance, target membership, and uncertainty should remain typed and separately calibrated; concatenating them into one latent vector does not make their scales or reliability commensurate.

For ARIA-NBV, the transferable result is representational rather than objective-level. Target identity should be a spatially distributed weight that can modulate candidate visibility, support, uncertainty, and reconstruction evidence. A scene-wide uncertainty scalar or an OBB alone cannot express that an uncertain primitive is irrelevant to the selected object. Conversely, target membership and observation confidence must remain separate channels: low membership may indicate another object, while low confidence may indicate insufficient observation. ARIA-NBV retains mesh-supervised @target-specific-rri as the utility and treats confidence-weighted Fisher information as a diagnostic or ablation, not as a replacement objective. Object-aware 3DGS also depends on instance masks and per-scene optimization; mask errors can propagate into both reconstruction and view selection, so it is not the default actor state for the ASE/EFM3D pipeline @ObjectCentricNBV-jeong2026.

The membership field is not a native EVL output. A minimal actor-visible approximation is geometric: a smooth function of target-frame distance to the selected OBB, gated by the matched detection track and observed point support. A stronger branch projects predicted instance masks from logged RGB frames onto semi-dense or fused points and fuses only observations that pass visibility or depth-consistency checks. EVL's dense `clas_pr` field encodes semantic class probabilities within the local cube, not persistent instance identity; two objects of the same class still require OBB association or tracking. ASE ground-truth instance masks may supervise or evaluate this branch in a named privileged experiment, but they cannot enter the V1 actor state.

=== What EVL actually provides

EFM3D's @egocentric-voxel-lifting:short model is the primary Aria-native target proposer and local feature source @EFM3D-straub2024. EVL first computes frozen DINOv2.5 features for every logged RGB frame. In the pinned inference configuration, multi-layer 768-dimensional ViT-B patch tokens are decoded by a DPT-style head into `rgb/feat2d_upsampled` with shape $B times T times 32 times H times W$. These maps cover valid pixels in all logged snippet frames and are not clipped by the EVL voxel extent. They remain image-space features, however: they have no persistent world location until sampled at calibrated three-dimensional query points. They are contextual descriptors derived from patch receptive fields; DPT upsampling refines their spatial resolution but does not turn them into calibrated semantic probabilities, independent pixel labels, depth, or three-dimensional points @DINOv2-oquab2023 @EFM3D-straub2024.

The lifter constructs a gravity-aligned $48^3$ grid with extent $[-2,2] times [0,4] times [-2,2]$ metres in the voxel frame, anchored to the final RGB pose of the snippet. EVL projects only those voxel centres into the logged images, samples and averages valid upsampled features, appends semi-dense point and free-space masks, and processes the local field with a 3D encoder--decoder. Consequently `voxel/feat`, the neck tensor, and the dense occupancy, centerness, box, and class heads have finite spatial support even though their source image maps do not. In the released implementation, `neck/occ_feat` and `neck/obb_feat` refer to the same neck tensor and should not be stored as independent evidence unless a different checkpoint or fork establishes distinct branches.

There is no hidden global EVL volume containing every region observed by the input video. The image encoder has processed every logged frame, but three-dimensional lifting occurs only at centres of the configured local grid. EFM3D obtains longer-lived products through explicit OBB tracking and fusion of overlapping local occupancy volumes rather than through an exposed global scene token @EFM3D-straub2024.

The detector construction gives a useful consistency condition. A same-pass OBB centre is decoded from a centerness voxel plus a bounded local offset and should therefore lie inside, or only marginally outside, that pass's support volume. A same-pass centre far outside the cube indicates a frame, timestamp, tracker, or cache-lineage error. The predicted box may nevertheless extend beyond the cube, and a tracked box or a box produced by another snippet or detector may legitimately lie outside the current root field. Thus an OBB prediction establishes a target hypothesis, not complete feature support over the entire target volume.

=== Target-canonical EVL reads and extensions beyond the root cube

For a target pose $T^w_e$ and extents $d_e$, a normalized object lattice $u_k in [-1,1]^3$ can be mapped into the EVL voxel frame:

$
  x^v_(e,k)
  = (T^w_v)^(-1) T^w_e
    op("diag")(d_e / 2) u_k,
  quad k = 1, dots, K.
$

Here $T^w_v$ is the stored voxel-to-world transform. Trilinear sampling at $x^v_(e,k)$ yields an orientation-normalized crop from `voxel/feat` or the shared neck tensor. The crop must carry its in-bounds mask, projection counts, point/free-space support, and selected head probabilities. It may remain a small spatial token grid or be pooled with mask-aware statistics into $z_e$. Missing crop support is retained as a feature rather than padded with ordinary zeros. Canonical crop indexing removes the common world translation and global yaw from the tensor layout; target orientation relative to gravity and to each candidate is retained explicitly in the accompanying relative-pose descriptors.

The target read should combine learned local evidence with interpretable support. The shared neck or lifted volume provides the learned crop; point, free-space, count, occupancy, centerness, and class fields expose calibration and support; semi-dense or fused points inside an expanded target region extend the read beyond the crop boundary; and visibility-gated image descriptors add appearance only as a controlled ablation.

Two actor-visible constructions extend target evidence outside the root cube. The first attaches logged image descriptors to semi-dense or fused world points. A point is projected into each logged camera, `rgb/feat2d_upsampled` is sampled at valid locations, and the descriptors are pooled only after native observation lineage, depth consistency, or a conservative z-buffer has established visibility. Projection validity alone proves neither visibility nor target membership. The resulting point bank can cover observed points outside the root EVL grid, but it contains no unobserved volume and no descriptors from hypothetical candidate views.

The second construction performs target-centred re-lifting. A new grid is placed around an actor-visible target and the already logged 2D feature maps are projected into it with the recorded cameras. This derives a spatial field at the target even when the target is outside the root grid; it does not reveal a pre-existing global EVL tensor. Moreover, the released 3D neck and heads were trained on final-pose-rooted grids with their characteristic support distribution. Applying them unchanged to a target-centred grid is therefore an explicit adaptation ablation, not a guaranteed feature extraction operation.

Neither extension creates RGB, DINO, detector, or EVL evidence at an unvisited pose. Counterfactual successors may update selected geometry, occupied/free/unknown evidence, support, uncertainty, and directional history, while visual and detector descriptors remain marked as missing unless a separate validated observation generator is introduced.

=== Layered scene memory and admissible latent encoders

The selected representation is layered rather than a forced choice between a point cloud and a latent field:

$
  M_t = (P_t^"semi/fused", R_t^"ray", V_0^"EVL", A_t^"logged"),
$

$
  z_e = (B_e, p_e^"class", c_e, s_e, C_e^"EVL", mu_e).
$

$P_t^"semi/fused"$ provides broad actor-visible surface evidence with uncertainty and observation support. $R_t^"ray"$ stores sparse occupied, free, and unknown evidence together with support, recency, uncertainty, and directional history. $V_0^"EVL"$ is the root-local learned field with its pose and finite extent. $A_t^"logged"$ is an optional visibility-gated appearance bank. The target record contains actor-visible OBB geometry $B_e$, semantic probabilities, confidence, support diagnostics, an optional masked target-canonical EVL crop, and an optional soft target-membership field.

A latent representation is admissible when it preserves this query and transition structure. Suitable forms include coordinate-bearing point tokens, sparse voxel or ray-cell tokens, object tokens with OBB poses, and small target-canonical latent grids. Each latent element needs a metric coordinate or object pose in a declared frame, a support domain and observation mask, provenance and time, and an update rule. A globally pooled vector may accompany the indexed state, but it should not replace it until an ablation shows equal target-RRI ranking, invariance behavior, candidate visibility prediction, and rollout-update fidelity.

A semi-dense point bank is the minimum broad-memory baseline because its world extent follows observed points and OBB/frustum pooling is simple. It does not represent free or unknown rays by itself, and its density reflects texture and tracking support. A sparse occupancy or ray map is the default planning-memory hypothesis because it explicitly preserves observed surface, free space, unknown space, and incremental ray updates while allocating storage only where evidence or queries exist. A TSDF or neural SDF remains a valid geometry baseline when accompanied by observation weights and unknown-space masks; signed distance alone does not identify whether a value was measured or inferred. Coordinate-bearing point or sparse encoders can compress these explicit carriers after the simpler pooling controls are established.

A renderable field such as object-aware 3DGS is attractive because candidate views can be evaluated through rendering, primitive-level uncertainty, and soft instance membership. Jeong et al. further show that the same explicit primitives can support iterative reconstruction refinement and target-conditioned view utility @ObjectCentricNBV-jeong2026. The cost is a substantially different state-construction contract: per-scene optimization, instance-mask supervision, representation-specific uncertainty, and a more difficult distinction between measured and optimized or completed geometry. Such a field is therefore a valuable renderable-memory ablation, not evidence that explicit sparse geometry is unnecessary.

=== Backbone alternatives and controlled evaluation

Within the documented ATEK path, EVL and Cube R-CNN are the directly supported static 3D detection models. EVL remains the lowest-integration default because it jointly supplies multi-frame Aria-native OBBs, local lifted features, semi-dense support, and surface predictions. Cube R-CNN supplies single-frame RGB OBBs and ROI features and is the cleanest detector-only control through ATEK @omni3d-cubercnn-brazil2023 @ATEK-Repo. Detector comparison must hold scene memory and target matching fixed so that OBB quality is not conflated with memory quality.

SceneScript is an additional ASE-trained alternative. Its released model consumes Project Aria semi-dense point clouds, applies sparse 3D convolutions, and decodes scene layout together with gravity-aligned OBBs @SceneScript-avetisyan2024. It can therefore test whether broad sparse context improves target proposal or high-level layout reasoning without EVL's final-pose cube. It is not an ATEK drop-in replacement and does not by itself supply observed-free/unknown ray memory, uncertainty calibration, or counterfactual state updates.

PointNeXt, Point Transformer variants, KPConv, and sparse-convolution backbones can encode $P_t^"semi/fused"$ or $R_t^"ray"$ @PointNeXt-qian2022 @PointTransformerV3-wu2024 @KPConv-thomas2019 @MinkowskiEngine-choy2019. They are memory encoders, not target proposers, unless paired with EVL, Cube R-CNN, SceneScript, or another validated detector. NeRF, Gaussian splats, and other renderable fields are likewise scene-memory alternatives whose construction cost, provenance, and update semantics must be compared against the sparse state rather than judged by visual fidelity alone @NeRF-mildenhall2020 @GaussianSplatting-kerbl2023.

The representation ablation proceeds cumulatively. The control state contains target OBB geometry, class/confidence, support counts, selected history, budget, and candidate-relative pose. Local learned evidence adds the masked target-canonical EVL crop and interpretable head channels. Broad observed support then adds target, candidate-frustum, and target--frustum pools over semi-dense or fused points. The next stage adds sparse ray-aware occupied/free/unknown and directional-history queries. Logged appearance is introduced only after these geometric and provenance controls through compressed, visibility-gated DINO-on-point descriptors. Learned point, sparse, target-centred re-lifting, SceneScript, and object-aware renderable fields are evaluated only after the explicit carriers establish whether the limiting variable is target support, visibility, appearance, or encoder capacity.

Before entering the main #symb.rl.qh comparison, a representation must pass same-pass OBB-support checks, world-frame translation and yaw stress tests, target-crop transform tests, point and candidate permutation tests, free-versus-unknown tests, out-of-extent mask tests, deterministic update/replay tests, and actor/oracle provenance audits. Representation quality is then measured by held-out one-step target-RRI ranking and calibration, oracle-evaluated selected actions, finite-horizon return prediction, storage, and candidate-query latency. Feature dimensionality, rendering quality, or reconstruction appearance alone does not establish suitability for target-conditioned NBV.
