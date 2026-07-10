#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

== Descriptor and Encoding Protocol

#impl_todo(
  [Separate implemented descriptor inputs from planned branches throughout this section. The final Method must retain only persisted/readable fields used by the trained models; optional DINO-on-point, directional-memory, spherical-harmonic, sparse-ray, and relation-bias branches must move to evaluated ablations or future work.],
  source: [thesis peer review; EFM3D literature review],
  gate: [descriptor reader and model-input freeze],
)

// source: docs/contents/theory/efm3d_scene_embeddings.qmd keeps implementation notes for target lineage, replay fields, and feature-bank joins.
This subsection defines the actor-visible descriptor protocol consumed by #symb.rl.qh. Its job is not to choose the neural architecture and not to restate the replay schema. Chapter 03 owns row identity, lineage, labels, masks, and selected-transition storage; @sec:thesis-method-geometry-contract and the value-model section own the encoder and ablation ladder. The descriptor protocol is the typed interface between them: a training reader derives versioned target, scene, history, candidate, relation, support, validity, and provenance tensors from replay facts without giving the actor oracle-only fields or arbitrary coordinate shortcuts.

The order below is causal. The target descriptor fixes the entity whose reconstruction gain is optimized. Scene memory then defines the evidence that can be queried without leakage. Candidate self-pose and candidate-target relations define geometry in local frames. Support, ray, relation, directional-history, mask, and provenance descriptors are added only after those anchors exist. This order keeps descriptors falsifiable: each block can be ablated, shuffled, masked, or source-dropped without changing the meaning of the remaining blocks.

The derived model input at step $t$ is

$
  (#symb.model.target_token, #symb.scene.scene_memory_t, bold(H)_t, {#symb.model.candidate_row, #symb.spatial.relation_rpe, bold(m)_(t,i), bold(rho)_(t,i)}_(i=1)^(#symb.shape.Nq))
$

Here #symb.model.target_token is the selected-target token, #symb.scene.scene_memory_t is queryable actor-visible scene memory, $bold(H)_t$ is selected-history state, and each candidate row carries typed self, relation, support, validity, and provenance descriptors. Hidden @ground-truth:short target crops, GT matches, target errors, all-candidate oracle renders, and oracle returns are label or evaluation products only; they are never part of the V1 actor input. This organization follows the geometric-learning rule that the descriptor should encode task-relevant invariants and equivariances before model capacity is increased @GeometricDeepLearning-bronstein2021.

The target descriptor is the first descriptor because it fixes which object the value model is allowed to care about. It separates identity, actor-visible support, and provenance from later GT association:

$
  #eqs.entity.target_descriptor
$

In this equation the vector #symb.entity.target_desc denotes the actor-visible target representation, while $op("Enc")_"tgt"$ is the constructor. This avoids the older ambiguity where $phi_"target"$ named both an encoder and a target-like representation. Confidence is written $hat(pi)_e$ rather than $hat(p)_e$ to keep probabilities distinct from points or positions, and source mode is written $ell_e^"src"$ rather than a state-like $s$.

The learned target token then augments the descriptor with support read from scene memory:

$
  #eqs.model.qh_target_token
$

The target fields include observed or predicted @oriented-bounding-box:short geometry, class/confidence, projected area, semidense and @egocentric-voxel-lifting:short support, local @egocentric-voxel-lifting:short coverage, source mode, and root/current-relative target geometry. Low target support is therefore observable evidence and a reporting stratum. It becomes hard invalidity only through the target-task protocol when the target cannot be matched, cropped, or evaluated.

The scene descriptor is a queryable support memory, not one dense final-pose tensor:

$
  #eqs.scene.qh_scene_memory
$

This composite keeps sparse ray-aware occupied/free/unknown memory, semidense or fused point tokens, optional compressed logged DINO descriptors, root-local @egocentric-voxel-lifting:short evidence, predicted target hypotheses, and directional-history summaries as distinct channels. The split matters because logged history may contain calibrated RGB/DINO and semidense evidence, while counterfactual successor rows may add only selected geometry, ray/free-space updates, support counts, and missing-visual-descriptor masks.

Optional logged appearance enters through point-attached tokens only after projection, visibility, compression, and source provenance are explicit:

$
  #eqs.features.point_dino_token
$

This planned DINO-on-point branch can represent observed points outside the root @egocentric-voxel-lifting:short voxel cube, but it does not create fresh RGB, DINO, detector, or @egocentric-voxel-lifting:short evidence at unvisited candidate poses.

Candidate pose is only the candidate self descriptor, not the whole row. Canonical poses remain stored as rigid transforms; model readers derive a relative pose feature from a reference pose #symb.spatial.ref_pose. For logged root states, #symb.spatial.ref_pose is the current/root actor pose defining the decision state. For counterfactual successors, it is the preceding selected pose whose geometry/history has already been fused. It is therefore a gauge choice for descriptor construction, not a new observation and not a future-looking anchor. This follows the query-centric principle that coordinates should be expressed relative to the query or decision frame when that removes nuisance global degrees of freedom without erasing task geometry @GeometricDeepLearning-bronstein2021 @zhou2023query.

The reference transform is

$
  #eqs.spatial.candidate_reference_transform
$

and the candidate self descriptor is

$
  #eqs.spatial.candidate_pose_features
$

This descriptor intentionally excludes the target, support pools, and sampler family. It lets the model see motion feasibility and egocentric geometry without depending on arbitrary world origin or yaw. Continuous 6D rotations remain a stable neural representation for rotations @zhou2019continuity, and learnable Fourier features remain a useful scalar/vector encoding control @LFF-li2021, but they should be applied to relative transforms and physically meaningful scalars rather than raw world pose by default.

The candidate-target relation is a separate descriptor:

$
  #eqs.spatial.candidate_target_relation
$

This relation uses candidate-local target displacement, range, bearing or optical-axis alignment, elevation, and OBB/frustum overlap. It replaces the earlier overloaded pose vector that combined absolute translation, 6D rotation, target distance, angle, overlap, and sampler provenance. Sampler family and source lineage remain useful diagnostics, but they are provenance features, not geometric pose.

Candidate support is then queried from the scene memory in three typed pools. These pools are deliberately simpler than a learned sparse scene encoder: they expose target support, candidate-frustum support, and their intersection as controlled sufficient-statistic candidates before heavier point, sparse-convolution, or attention modules are introduced:

$
  #eqs.scene.candidate_query_pools
$

This spatial separation is the core feature-bank isomorphism: the same actor-visible point/ray/EVL carriers are not a single scene vector, but a queryable memory whose predicates are defined by the target, the candidate frustum, and their overlap (@fig:feature-bank-query-pools).

#prune_todo(
  [Replace “sufficient-statistic candidates” and “feature-bank isomorphism” with descriptive terms such as controlled summary features and query decomposition unless sufficiency and a structure-preserving mapping are formally defined and tested.],
  source: [thesis peer review],
  gate: [final terminology audit],
)

#figure(
  align(center, image(
    "../../figures/feature_bank_query_pools.pdf",
    width: 100%,
  )),
  caption: [Actor-visible feature-bank query pools for #symb.rl.qh. Panel A separates point carriers, optional logged DINO descriptors, ray-memory evidence, root-local @egocentric-voxel-lifting:short support, and missing-modality masks. Panel B shows that the target pool, candidate-frustum pool, target-frustum-intersection pool, and ray query are different spatial predicates over the same actor-visible memory, not fresh counterfactual visual observations.],
) <fig:feature-bank-query-pools>

The pools summarize selected-target support, candidate-frustum support, and the target-frustum intersection. They are cheap support descriptors, not visibility truth by themselves. The candidate observation branch also needs a ray-aware query over occupied, free, unknown, hit, target, support, uncertainty, and directional-novelty channels:

$
  #eqs.scene.candidate_ray_query
$

Query-centric relation encodings are introduced only after the self and support descriptors exist. The transferable part of QCNet is the local coordinate-system and relative positional-embedding discipline: key/value elements are described relative to the query element, giving useful invariances without relying on global scene coordinates @zhou2023query. In ARIA-NBV, each candidate can query target, history, support, and other candidate tokens through features expressed in the query candidate's local frame:

$
  #eqs.spatial.candidate_query_local_frame
$

$
  #eqs.spatial.candidate_query_rpe
$

This imports the geometrically useful idea, not QCNet's trajectory decoder, anchor losses, road-agent metrics, or streaming prediction claim. The default first scorer can ignore these relation embeddings; Deep Sets and Set Transformer controls should establish row-order and mask behavior before relation-biased candidate attention is promoted @DeepSets-zaheer2017 @SetTransformer-lee2019.

Selected-history visibility is a different descriptor family from pose. Candidate orientation uses continuous 6D rotation features @zhou2019continuity, but accumulated observation history lives on $bb(S)^2$. For a target-local point or voxel center $bold(v)$ and a previously selected camera center $bold(c)_k$, the observed direction is

$
  #eqs.spatial.direction_unit
$

The planned actor-visible branch stores this history either as low-order spherical-harmonic coefficients @e3nn-SphericalHarmonics-2025

$
  #eqs.spatial.direction_memory_sh
$

or, as the thesis-safe default, as a second-moment summary over unit directions,

$
  #eqs.spatial.direction_memory_moment
$

from which the candidate can read a directional novelty score:

$
  #eqs.spatial.direction_novelty
$

The directional-memory diagram in @fig:qh-directional-memory keeps this branch separate from generic pose tokens: selected views first accumulate target-local directional evidence, and each valid candidate then queries whether it sees the target from a genuinely new direction.

#figure(
  align(center, image(
    "../../figures/directional_memory_view_novelty.pdf",
    width: 100%,
  )),
  caption: [Actor-visible directional memory for target-local view novelty. The figure shows a planned descriptor branch, not an implemented performance result: selected view directions over observed points or voxels are summarized as low-order directional coefficients or second moments, and each valid candidate reads the memory to produce a candidate token feature for #symb.rl.qh.],
) <fig:qh-directional-memory>

The row-level descriptor assembled for candidate scoring is therefore a contract, not a single mandatory tensor layout:

$
  #eqs.model.candidate_row_features
$

with relative pose/relation features, candidate-geometry token #symb.model.candidate_geometry_token, hard-mask/reason embedding #symb.model.candidate_validity_token, provenance embedding #symb.model.candidate_provenance_token, and selected-history summary $bold(H)_t$. The selected target enters through #symb.model.target_token and candidate-target query pools. This symbolic view keeps the table below as a provenance checklist rather than the model definition.

#figure(
  text(size: 8.2pt, table(
    columns: (0.78fr, 1.22fr, 1.18fr),
    toprule(),
    table.header([*Descriptor block*], [*Fields*], [*Failure prevented*]),
    midrule(),
    [Target descriptor and token],
    [OBB geometry, class/confidence, selector rank, projection, semidense/EVL support, EVL coverage, source mode.],

    [Keeps V1 target input separate from GT-EVAL matching and GT OBB crops.],
    [Candidate self pose],
    [Reference-pose-relative translation, range, azimuth, continuous 6D relative rotation, height/up/frustum scalars, optional LFF controls.],

    [Keeps each finite action row interpretable and invalidity hard-masked.],
    [Candidate-target relation],
    [Candidate-local target displacement, range, bearing, elevation, target-frustum overlap, support change, optional EVL/crop read.],

    [Forces conditioning on the selected target instead of scene-coverage shortcuts.],
    [Candidate-candidate and history relations],
    [Query-local relative poses, angular separation, duplicate indicators, selected-view memory, valid-count features.],

    [Supports row-equivariant interaction and duplicate-row diagnostics.],
    [Feature-bank joins],
    [Point/voxel/ray-cell id, feature-model id, compression version, observation count, lineage, uncertainty, extent status.],

    [Prevents mixing logged RGB/DINO with counterfactual selected-depth geometry.],
    [Relation encodings],
    [Query-local target/candidate/history/support relations, source tags, optional attention-bias embeddings.],

    [Transfers QCNet-style geometry without motion-forecasting objectives.],
    [Directional memory],
    [Target-local $bb(S)^2$ moments, optional SH coefficients, directional novelty, selected-view support weights.],

    [Keeps accumulated visibility separate from pose and sampler features.],
    [Provenance],
    [Sampler family, source role, descriptor version, feature-source id, compression id, and missing-modality masks.],

    [Lets ablations test shortcut risk instead of hiding provenance inside pose geometry.],
    bottomrule(),
  )),
  caption: [Actor-visible descriptor blocks and the leakage boundary before heavier scene encoders are evaluated.],
) <tab:thesis-descriptor-schema>

#validation_todo(
  [Before promoting any feature-bank, point/sparse, radiance-field, or recurrent scene encoder to thesis-core status, run EVL-extent, source-dropout, density, row-shuffle, mask-isolation, storage, and runtime ablations against the simpler descriptor controls.],
  source: [autoresearch thesis-lit-review Iterations 16, 24, 25, and 26; local EFM3D and Deja View literature refresh],
  gate: [representation ablation evidence],
)

#validation_todo(
  [Resolve the current wording/code tension around outside-EVL extent: some rollout contracts list outside-EVL support as a hard reason, while current VIN evidence treats low EVL coverage as a diagnostic/support feature. The thesis-core rule should be: infeasible pose, missing oracle/evaluation sample, or empty target crop is hard invalidity; low local EVL support alone is a model feature unless it blocks evaluation.],
  source: [docs/contents/thesis/questions.qmd:21; aria_nbv/aria_nbv/vin/experimental/model.py:848; aria_nbv/aria_nbv/vin/model_v3.py:1465],
  gate: [rollout invalidity audit before first #symb.rl.qh training run],
)
