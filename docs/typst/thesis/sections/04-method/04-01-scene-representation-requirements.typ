#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status
#import "@preview/booktabs:0.0.4": *

== Actor State and Representation Boundary <sec:thesis-scene-representation>

=== Implemented carrier and information boundary

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@EFM3D-straub2024],
  source: "aria_nbv/aria_nbv/data_handling/qh_data/views.py; aria_nbv/aria_nbv/rollouts/qh_reader.py; aria_nbv/tests/lightning/test_qh_module.py",
  gate: [retain actor/oracle provenance checks and name the admitted state protocol in every run],
)[The replay carrier, actor/supervision separation, scalar requested-horizon scorer, fitted-Q adapter, and privileged `S1-points` selected-surface control are implemented. The deployable `S0-pose` root-moments state and privileged S1 state are deliberately incomplete; task-sufficient ray memory and frozen scientific validation remain pending.]

The implemented one-step scorer consumes an actor-visible snippet view, a row-aligned candidate table, a reference rig pose, calibrated candidate cameras, and optionally cached @egocentric-voxel-lifting:short output. Oracle @relative-reconstruction-improvement:short labels enter the loss after prediction and are not scorer inputs. The current oracle target descriptor contains semantic identity, pose, positive metric extents, and reference-relative pose in an actor-safe shape, but its values are derived from privileged @ground-truth:short target tasks. A deployable claim therefore still requires observed or predicted target fields with explicit provenance.

The implemented `QhActorTensors` contract carries root semidense evidence, target geometry admitted by the declared target-input protocol, root-relative candidate poses, selected-pose history, and remaining budget to the finite-horizon scorer. The non-deployable `v0_gt_input` protocol derives that geometry from Oracle GT tasks; deployable `v1_observed` instead requires an actor-visible descriptor whose source, construction provenance, and descriptor hash are bound in training and held-out receipts. The current model reduces root evidence to global moments and selected history to a causal pose summary. Candidate regeneration changes pose, history, budget, and the finite action table; richer models must still define how causal selected observations update scene memory without widening this actor/oracle boundary.

Three boundaries are invariant. Invalidity is a hard mask with versioned reason codes, not a small value. GT meshes, target crops, current all-candidate renders, associations, and returns remain oracle or audit fields. Previously selected GT-mesh depth may enter a later state only under an explicitly privileged `CF-GT` protocol; the corresponding sensor-like or observed variants must use distinct provenance. Candidate rows remain tied to stable shell identities and documented coordinate frames.

=== Task-sufficient actor state

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@GeometricDeepLearning-bronstein2021 @DeepSets-zaheer2017],
  source: "aria_nbv/aria_nbv/vin/modules/qh_scene_encoders.py; aria_nbv/aria_nbv/rendering/unproject.py; aria_nbv/tests/vin/test_qh_scene_encoders.py; docs/contents/theory/efm3d_scene_embeddings.qmd; docs/contents/theory/candidate_view_dependence.qmd",
  gate: [selected-observation reader, deterministic fusion, source-dropout tests, and held-out target-RRI ranking],
)[The canonical state separates immutable root context from causal dynamic memory. A bounded, privileged identity-start S1 selected-surface residual is executable behind the scene-carrier seam. Its first five-chain comparison is development evidence because it informed subsequent initialization design and has no immutable run receipt; S1 remains unpromoted and S2 free/unknown memory remains planned.]

ARIA-NBV does not require one universal reconstruction format. It requires an actor-visible state from which a model can compare a target $e$ and candidate $q_(t,i)$ at decision step $t$. The frozen scorer interface includes the scalar requested residual horizon $h$ in addition to the factual remaining budget $b_t$:

$
  #eqs.scene.actor_state_read
$

For architectural and DTO purposes, the resulting scene memory is represented
as the state consumed by the value model,

#eqs.scene.qh_scene_memory

The immutable root evidence and causally updated dynamic memory remain separate
conceptually: root semidense geometry and supported local EVL features are not
silently replaced by selected-observation evidence. The target is external task
context in $Q(s_t,e,a)$ and is represented by a separate target state; it is not
duplicated inside target-independent scene memory.

The selected-pose history $bold(H)_t$ remains explicit unless a promoted memory is demonstrated to be a sufficient statistic for it. Raw selected depth is an observation consumed by the memory update; it need not remain a direct scorer input once its surface, free-space, support, source, and recency information have been fused.

#figure(
  text(size: 8.2pt, table(
    columns: (0.72fr, 0.94fr, 1.55fr),
    toprule(),
    table.header([*State protocol*], [*Dynamic evidence*], [*Interpretation*]),
    midrule(),
    [`S0-pose`], [selected poses only], [Implemented feature-matched A0/A1 root-moments controls over replay tensors; not a complete reconstruction state.],
    [`S1-points`], [causally fused selected surface points], [Implemented privileged identity-start, fixed-width residual over current-camera point sets; confirmatory evidence remains pending and observed free is not distinguished from unknown space.],
    [`S2-ray`], [surface, free, unknown, support, recency], [Canonical planned dynamic state for candidate-frustum and target-support queries.],
    [Privileged / sensor-like / actor-visible], [source tag on selected observations], [Orthogonal information protocol: privileged mesh depth, declared sensor-like simulation, or actor-visible observation.],
    bottomrule(),
  )),
  caption: [Counterfactual state and source protocols. Scene carrier, information source, interaction architecture, and learning objective are orthogonal experimental choices.],
) <tab:thesis-counterfactual-state-protocols>

A useful representation must preserve distinctions that can change target-specific return, distinguish missing evidence from predicted free space, and admit a causal update after selection. The implemented S1 control deliberately stops earlier: it backprojects only selected $j<t$ depth, expresses points from the factual current camera, applies one shared point map, and mean/max pools the union into a root-width residual. It is point-order invariant but density weighted—each valid strided pixel contributes one set element—and retains only explicit point, pixel-support, and view-support summaries. Candidate queries do not yet read candidate-relative points. Zeroing only S1's final residual projection makes fresh S1 predictions exactly equal to matched H0, lets that projection move on the first backward pass, and delays task gradients into the point map until the residual path opens. The initial five-chain comparison was inspected during architecture development, so it is not an untouched test and supports neither an identity-start improvement nor a geometry-attribution claim. Candidate-local point relations remain unpromoted; S2 must additionally preserve ray/free/unknown evidence. A common world translation or yaw convention must not change physical candidate values, while gravity, scale, target extent, camera direction, occlusion, and temporal order remain observable task variables. Exact global $op("SE")(3)$ invariance is therefore neither required nor claimed.

=== Local EFM3D evidence and the coverage gap

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@EFM3D-straub2024 @EVL-Doc-2025],
  source: "docs/literature/tex-src/arXiv-EFM3D/method.tex, Sec. Egocentric Voxel Lifting, lines 2--44; docs/contents/literature/efm3d.qmd; docs/contents/theory/efm3d_scene_embeddings.qmd; aria_nbv/aria_nbv/data_handling/vin_store/writer.py",
  gate: [report target and candidate support against the persisted voxel pose and extent],
)[EFM3D fields, their voxel pose, and finite extent are persisted. The current finite-horizon scorer consumes lossy global field moments; their sufficiency as the only long-horizon scene representation remains pending.]

EFM3D encodes logged RGB frames before lifting selected evidence into a finite gravity-aligned voxel field anchored to a snippet pose. The stored voxel transform and extent define the support of lifted features and dense heads. They must not be interpreted as a global volume containing every region observed by the trajectory. A target or candidate outside this support can remain physically valid; it has missing local-EVL evidence rather than an ordinary zero feature or automatically invalid action.

The coverage limitation motivates a layered interface rather than repeated inference at hypothetical candidate poses. Local EVL features provide high-quality Aria-native evidence where supported. Broader semidense or fused point carriers can preserve observed surfaces beyond that volume. Sparse ray-aware state can distinguish occupied, free, and unknown regions and can be updated from selected geometry. Logged appearance descriptors can be attached to points only after visibility and source lineage are established. None of these carriers creates RGB, DINO, detector, or EVL evidence at an unvisited counterfactual pose.

=== Ranked representation design space

#thesis_status(
  implementation: "exploratory",
  evidence: "pending",
  citation: [@VIN-NBV-frahm2025 @GenNBV-chen2024 @ObjectCentricNBV-jeong2026 @SceneScript-avetisyan2024],
  source: "docs/literature/tex-src/arXiv-GenNBV/3-Method.tex, Secs. Formulation and Generalizable State Embedding, lines 10--49; docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex, Sec. Methods, lines 14--58; docs/literature/tex-src/arXiv-scene-script/sections/structured_scene_language.tex; docs/contents/literature/efm3d.qmd",
  gate: [promote only after matched support, leakage, runtime, and oracle-policy ablations],
)[This table ranks scene carriers only. The interaction architecture is specified separately in @sec:thesis-method-geometry-contract so a carrier change does not silently redefine candidate or target semantics.]

#figure(
  text(size: 8.2pt, table(
    columns: (0.78fr, 0.72fr, 1.18fr, 1.22fr),
    toprule(),
    table.header([*Carrier*], [*Status*], [*Inductive benefit*], [*Cost and promotion gate*]),
    midrule(),
    [Root semidense moments], [implemented S0 control], [Cheap root-level context for contract and optimization tests.], [No spatial support or causal update; never interpret as task-sufficient state.],
    [Persisted EVL and snippet evidence], [available; lossy moments consumed], [Aria-native local fields, OBB hypotheses, calibrated cameras, and explicit extent.], [The scorer consumes global moments rather than spatial EVL fields; limited support still requires coverage metadata.],
    [Selected-surface point memory], [implemented privileged identity-start control; unpromoted], [Strictly causal surfaces follow selected views; fixed width and a zero-output residual preserve matched H0 initialization.], [Confirmatory comparison requires an immutable receipt and untouched scene-disjoint test manifest.],
    [Sparse ray-aware memory], [planned primary extension], [Separates surface, free, unknown, support, uncertainty, and causal updates.], [Requires deterministic fusion and counterfactual-source masks.],
    [Target-centred EVL re-lifting], [adaptation ablation], [Reuses logged frame features when the target lies outside the root field.], [Domain shift in the 3D neck; compare against simple logged-feature pooling.],
    [DINO-on-point], [appearance ablation], [Extends logged appearance to observed points beyond the EVL grid.], [Needs visibility gating, compression, and missing-descriptor masks.],
    [TSDF/SDF or sparse encoder], [geometry/encoder ablation], [Compact metric geometry or learned coordinate-bearing tokens.], [Must preserve observation weights and unknown-space semantics.],
    [Object-aware 3DGS], [renderable-memory ablation], [Candidate rendering, soft target membership, and primitive uncertainty.], [Per-scene optimization and mask supervision change the state contract.],
    [SceneScript], [global-context control], [Broad ASE-aligned layout and object hypotheses from semidense input.], [Not an ATEK drop-in and does not provide causal free/unknown updates.],
    bottomrule(),
  )),
  caption: [Ranked scene-carrier design space. Status describes the role in the thesis method, not empirical superiority.],
) <tab:thesis-scene-representation-design-space>

Representation comparisons begin with the smallest planned scorer carrier and then add the smallest carrier that tests a diagnosed information loss. Learned point, sparse, equivariant, or renderable encoders are introduced only when a simpler carrier demonstrably limits target-RRI ranking or finite-horizon recovery. This ordering keeps representation capacity separate from target identity, candidate support, replay validity, and the candidate interaction architecture.
