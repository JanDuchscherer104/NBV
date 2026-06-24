#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

== Scene-Representation Requirements

// source: docs/contents/thesis/roadmap.qmd owns the source-family adoption boundary.
// source: docs/contents/theory/efm3d_scene_embeddings.qmd explains EVL as local evidence and semidense/fused points as broad scene memory.
The planned value model needs more than a generic 3D feature extractor. A thesis-grade perception stack must provide actor-visible target hypotheses, especially @oriented-bounding-box:short detections, while the scene memory must preserve reusable geometry, uncertainty, free/unknown evidence, and history for target-, history-, and candidate-conditioned #symb.rl.qh queries. These are separate interfaces: a detector can propose the target without being the scene memory, and a scene memory can support candidate scoring without predicting OBBs. The current default therefore remains @egocentric-foundation-model-3d:short / @egocentric-voxel-lifting:short for Aria-native target and local evidence: it is trained for the Project Aria / @aria-synthetic-environments:short regime, lifts multi-frame image features into a gravity-aligned 3D volume, uses semi-dense support, and exposes OBB/object evidence @EFM3D-straub2024 @EVL-Doc-2025. A replacement perception backbone is only thesis-relevant if it preserves this target-detection contract; a replacement memory is relevant if it improves candidate-conditioned evidence without breaking actor-visible provenance.

The central asymmetry is that the historic state is rich and multimodal, while counterfactual states are not. Logged snippets contain calibrated RGB/SLAM streams, poses, semidense points, EVL evidence, and observed or predicted OBBs. Counterfactual successors can reliably add selected geometry, support counts, visibility history, oracle-rendered labels, and actor-visible summaries derived from those sources; they cannot assume fresh RGB, DINO, semantic, or detector outputs at unvisited candidate poses unless a separate renderable or learned modality generator is introduced and validated. This prevents a model from winning by consuming modalities that exist only for the logged trajectory or only inside the oracle.

// source: docs/contents/theory/efm3d_scene_embeddings.qmd records implementation pointers for EVL support reads and semidense candidate visibility.
The important failure mode is support mismatch. The EVL voxel field is rooted in the snippet evidence and has finite local support; a target OBB, target-local surface cell, or candidate frustum can be physically relevant while partially or fully outside that field. For #symb.rl.qh, an EVL read therefore contributes both a feature and a coverage diagnostic, not a proof that the target is irrelevant:

$
  #eqs.scene.evl_local_support_read
$

Here $x_(t,i,k)$ are target-crop, frustum, or target-frustum-intersection query points for candidate $i$, $cal(V)_0^"EVL"$ is the root EVL support volume, $omega_(t,i)^"EVL"$ is the actor-visible local-support fraction, and #symb.scene.evl_support_token is a pooled local evidence token. Low $omega_(t,i)^"EVL"$ should usually be a support feature, uncertainty feature, or preflight warning; it becomes hard invalidity only when the row cannot be evaluated or cannot produce a meaningful actor-state transition.

This is why the final @egocentric-voxel-lifting:short head fields are a baseline, not the thesis memory optimum. Fields such as `occ_pr`, `cent_pr`, `bbox_pr`, and `clas_pr` are compact actor-visible predictions, but they are local, task-collapsed, and tied to the root snippet. They do not by themselves preserve broad free/unknown space, target-candidate visibility, directional history, or logged appearance ambiguity. Enlarging the @egocentric-voxel-lifting:short cube is therefore a useful ablation for local-support failure, not the default state design: dense 3D cost grows with volume, and a larger root cube still cannot create counterfactual RGB, DINO, detector, or history evidence. The tractable optimum is local @egocentric-voxel-lifting:short evidence plus sparse ray-aware actor-visible memory, with compressed logged descriptors only after visibility and provenance are enforced.

#figure(
  table(
    columns: (0.78fr, 1.18fr, 1.18fr),
    toprule(),
    table.header([*Requirement*], [*Reason*], [*Thesis consequence*]),
    midrule(),
    [Target-proposal interface],
    [Target-specific @relative-reconstruction-improvement:short and target-conditioned #symb.rl.qh need a selectable entity hypothesis, not only a scene embedding.],

    [Models without observed/predicted @oriented-bounding-box:short support are scene-memory or feature ablations unless another actor-visible target proposer supplies the target record.],
    [Aria / ASE domain fit],
    [Egocentric cameras, gravity alignment, semidense support, synthetic-to-real gaps, and ASE OBB taxonomy are part of the data contract.],

    [Prefer @egocentric-foundation-model-3d:short / @egocentric-voxel-lifting:short unless another model is trained or adapted on ARIA/ASE-style data and reports OBB quality.],
    [Reusable conditioning state],
    [#symb.rl.qh must condition on target, selected history, support, visibility, free/unknown evidence, and candidate geometry across many candidate rows.],

    [Expose typed query pools and ray-aware candidate queries rather than one final-pose voxel tensor: target-support pool, candidate support, candidate render/query, and directional-history support.],
    [Actor-visible provenance],
    [Historic and counterfactual states have different modality availability.],

    [Every token records source role, frame, feature model, support count, uncertainty, and whether it came from logged observation, selected successor depth, or oracle-only evaluation.],
    [Controlled scale],
    [The thesis should not become a large foundation-model replacement project.],

    [A smaller or cheaper encoder is desirable, but only after OBB quality, queryability, storage, runtime, and invariance tests pass.],
    bottomrule(),
  ),
  caption: [Hard requirements for a backbone or scene encoder to enter the thesis-core #symb.rl.qh path.],
) <tab:thesis-backbone-requirements>

This makes @egocentric-voxel-lifting:short an anchor, not a ceiling. The near-term representation question is whether the current final-pose voxel field hides useful evidence. The first ablations should keep the EFM3D/EVL target detector and add better actor-visible conditioning: semidense/fused point support, a sparse ray-aware occupied/free/unknown memory, EVL internal or crop reads around target hypotheses, selected-depth successor summaries, explicit directional visibility memory, and only then compressed DINO-on-point features lifted from logged views. These products can give #symb.rl.qh a broader queryable state without claiming that a new model has solved Aria-native OBB detection.

The logged DINO-on-point ablation uses the same geometric contract as EFM3D lifting, but the carrier is a semidense or fused world point rather than a local voxel center:

$
  #eqs.features.logged_point_projection
$

The descriptor is sampled only from logged feature maps and pooled through visibility-gated, actor-visible support weights:

$
  #eqs.features.logged_feature_sample
$

$
  #eqs.features.logged_visibility_gate
$

$
  #eqs.features.logged_feature_pool
$

$
  #eqs.features.compressed_point_descriptor
$

Here $alpha_(j,tau)$ is only the calibrated projection-valid mask. The visibility gate $m_(j,tau)^"vis"$ must additionally come from native semidense observation lineage, depth consistency, a conservative z-buffer, or a quality filter; projection validity alone is not evidence that the point was visible. This path can cover observed points outside the root EVL voxel cube, but it does not create fresh RGB, DINO, detector, or EVL evidence for unvisited future candidate poses.

The representation ladder is therefore short. EFM3D/EVL is the anchor because it supplies Aria-native OBB and support evidence. Semidense or fused observations and a sparse ray-aware map are the first broad-memory ablation because they can preserve observed surface, observed free space, unknown space, support counts, and directional history outside the root EVL cube while remaining actor-visible. EVL internal or crop reads test whether final heads hide local target evidence. Visibility-gated logged DINO descriptors then test appearance memory. Point, sparse, renderable, and recurrent encoders are later support-memory ablations; Cube R-CNN-style features are detector or ROI diagnostics unless they match the EFM3D target-evidence role on ARIA/ASE data @omni3d-cubercnn-brazil2023 @PointNeXt-qian2022 @PointTransformerV3-wu2024 @KPConv-thomas2019 @GaussianSplatting-kerbl2023 @dejaviewloopingtransformersburzio2026.
