#import "../../shared/macros.typ": *
#import "../../shared/symbols.typ": symb
#import "../../shared/equations.typ": eqs
#import "../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

= Method <sec:thesis-method>

ARIA-NBV is a target-conditioned, finite-candidate @next-best-view problem in the Project Aria / @aria-synthetic-environments:short / @egocentric-foundation-model-3d:short observation regime. The thesis is deliberately not a first-order continuous-control claim: it tests whether bounded planning over a finite valid candidate table improves target reconstruction quality beyond myopic view selection.

#include "03-01-formal-state.typ"

#include "03-02-data-generation.typ"

== Backbone and Scene-Encoder Requirements

// source: docs/contents/thesis/roadmap.qmd:115-123 owns the source-family adoption boundary.
// source: docs/contents/theory/efm3d_scene_embeddings.qmd:26-58 explains EVL as local evidence and semidense/fused points as broad scene memory.
// source: aria_nbv/aria_nbv/vin/model_v3.py:1-64 documents the current one-step VIN actor-visible input and leakage boundary.
The planned value model needs more than a generic 3D feature extractor. A thesis-grade backbone or scene encoder must provide actor-visible target hypotheses, especially @oriented-bounding-box:short detections, and a reusable scene representation for target-, history-, and candidate-conditioned #symb.rl.qh queries. The current default therefore remains @egocentric-foundation-model-3d:short / @egocentric-voxel-lifting:short: it is trained for the Project Aria / @aria-synthetic-environments:short regime, lifts multi-frame image features into a gravity-aligned 3D volume, uses semi-dense support, and exposes OBB/object evidence @EFM3D-straub2024 @EVL-Doc-2025. A replacement backbone is only thesis-relevant if it preserves this target-detection contract while improving the conditioning representation used by #symb.rl.qh.

The central asymmetry is that the historic state is rich and multimodal, while counterfactual states are not. Logged snippets contain calibrated RGB/SLAM streams, poses, semidense points, EVL evidence, and observed or predicted OBBs. Counterfactual successors can reliably add selected geometry, support counts, visibility history, oracle-rendered labels, and actor-visible summaries derived from those sources; they cannot assume fresh RGB, DINO, semantic, or detector outputs at unvisited candidate poses unless a separate renderable or learned modality generator is introduced and validated. This prevents a model from winning by consuming modalities that exist only for the logged trajectory or only inside the oracle.

// source: aria_nbv/aria_nbv/vin/experimental/model.py:614-631 and aria_nbv/aria_nbv/vin/experimental/model.py:826-850 show EVL frustum sampling and voxel_valid_frac as local support coverage.
// source: aria_nbv/aria_nbv/vin/model_v3.py:1331-1468 shows current VINv3 separately using voxel-center coverage and semidense candidate visibility.
The important failure mode is support mismatch. The EVL voxel field is rooted in the snippet evidence and has finite local support; a target OBB, target-local surface cell, or candidate frustum can be physically relevant while partially or fully outside that field. For #symb.rl.qh, an EVL read therefore contributes both a feature and a coverage diagnostic, not a proof that the target is irrelevant:

$
  omega_(t,i)^"EVL"
  =
  1 / K sum_(k=1)^K
  bb(1)[x_(t,i,k) in cal(V)_0^"EVL"],
  quad
  bold(s)_(t,i)^"EVL"
  =
  op("Pool")({F_0^"EVL"(x_(t,i,k)) : x_(t,i,k) in cal(V)_0^"EVL"}).
$

Here $x_(t,i,k)$ are target-crop, frustum, or target-frustum-intersection query points for candidate $i$, $cal(V)_0^"EVL"$ is the root EVL support volume, $omega_(t,i)^"EVL"$ is the actor-visible local-support fraction, and $bold(s)_(t,i)^"EVL"$ is a pooled local evidence token. Low $omega_(t,i)^"EVL"$ should usually be a support feature, uncertainty feature, or preflight warning; it becomes hard invalidity only when the row cannot be evaluated or cannot produce a meaningful actor-state transition.

#figure(
  table(
    columns: (0.78fr, 1.18fr, 1.18fr),
    toprule(),
    table.header([*Requirement*], [*Reason*], [*Thesis consequence*]),
    midrule(),
    [OBB-capable target evidence],
    [Target-specific @relative-reconstruction-improvement:short and target-conditioned #symb.rl.qh need a selectable entity hypothesis, not only a scene embedding.],

    [Backbones without observed/predicted @oriented-bounding-box:short support are scene-feature ablations, not replacements for @egocentric-voxel-lifting:short target evidence.],
    [Aria / ASE domain fit],
    [Egocentric cameras, gravity alignment, semidense support, synthetic-to-real gaps, and ASE OBB taxonomy are part of the data contract.],

    [Prefer @egocentric-foundation-model-3d:short / @egocentric-voxel-lifting:short unless another model is trained or adapted on ARIA/ASE-style data and reports OBB quality.],
    [Reusable conditioning state],
    [#symb.rl.qh must condition on target, selected history, support, visibility, and candidate geometry across many candidate rows.],

    [Expose typed query pools rather than one final-pose voxel tensor: target crop, candidate frustum, target-frustum intersection, and directional-history support.],
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

This makes @egocentric-voxel-lifting:short an anchor, not a ceiling. The near-term representation question is whether the current final-pose voxel field hides useful evidence. The first ablations should keep the EFM3D/EVL target detector and add better actor-visible conditioning: semidense/fused point support, compressed DINO-on-point features lifted from logged views, EVL internal or crop reads around target hypotheses, selected-depth successor summaries, and explicit directional visibility memory. These products can give #symb.rl.qh a broader queryable state without claiming that a new model has solved Aria-native OBB detection.

The following table is a design-contract surface: it classifies representation candidates and their entry gates, rather than reporting final experimental rankings.

#figure(
  table(
    columns: (0.8fr, 1.05fr, 1.24fr),
    toprule(),
    table.header([*Candidate representation*], [*Useful role*], [*Boundary before thesis-core use*]),
    midrule(),
    [@egocentric-foundation-model-3d:short / @egocentric-voxel-lifting:short],
    [Default Aria-native target/support anchor: OBB evidence, lifted visual features, occupancy/free-space support, and local voxel reasoning.],

    [Do not claim full long-horizon memory; report local-volume extent, final-pose anchoring, and target/candidate out-of-extent support separately from oracle invalidity.],
    [Cube R-CNN-style detector @omni3d-cubercnn-brazil2023],
    [Useful detector baseline or historical comparison for single-frame 3D OBB prediction.],

    [Not sufficient as scene encoder; must show ARIA/ASE adaptation and OBB quality before replacing EVL target evidence.],
    [Semidense/fused point bank plus compressed DINO-on-point],
    [First serious scene-conditioning ablation: point support, uncertainty, observation lineage, and local visual evidence are queryable by target and candidate geometry.],

    [Requires feature-cache provenance, compression policy, point-order tests, and joins by stable sample ids; no raw unbounded feature dumps.],
    [EVL internal/crop reads],
    [Tests whether pre-head voxel, neck, or crop evidence around predicted OBBs carries target support lost in final heads.],

    [Must stay actor-visible and store EVL extent, crop frame, grid pose, feature id, and out-of-extent status.],
    [Point/sparse encoders @PointNeXt-qian2022 @PointTransformerV3-wu2024 @KPConv-thomas2019],
    [Late support-encoder ablations when simple target/frustum/intersection pools fail.],

    [Need neighborhood, density, serialization, frame-canonicalization, storage, and runtime audits; they do not by themselves provide OBB detections.],
    [Explicit/radiance-field state such as @three-dimensional-gaussian-splatting:short @GaussianSplatting-kerbl2023],
    [Possible bridge for renderable memory, uncertainty, or missing counterfactual modalities.],

    [Not thesis-core unless trained, stored, and evaluated as actor-visible state rather than oracle target leakage.],
    [Deja View-style looped refinement],
    [Useful recurrence, compute-depth, and failure-diagnostic template for bounded iterative updates.],

    [Not a backbone replacement here; adopt the weight-tied refinement idea only after the fixed-depth candidate-set path is stable.],
    bottomrule(),
  ),
  caption: [Backbone and scene-representation ladder. Candidate representations may improve conditioning without replacing the OBB-capable EFM3D/EVL anchor.],
) <tab:thesis-backbone-ladder>

=== Descriptor and Encoding Plan

// source: aria_nbv/aria_nbv/data_handling/_target_selection.py:1-30 defines oracle target-task sampling versus actor-visible target selection.
// source: aria_nbv/aria_nbv/data_handling/_target_selection.py:209-254 lists oracle target-task identity and audit fields.
// source: aria_nbv/aria_nbv/rollouts/trace.py:79-151 carries rollout target lineage into replay.
The descriptor plan follows from this backbone constraint. #symb.rl.qh should first receive typed, actor-visible query pools rather than a monolithic feature tensor: a target token, selected-history summaries, per-candidate geometry, candidate-target relations, directional visibility memory, and optional feature-bank joins. The storage contract remains canonical: persist IDs, poses, masks, support counts, feature provenance, and oracle labels in replay rows; derive model descriptors in the reader so that new encoders do not rewrite the supervision artifact. This also keeps the historic/counterfactual asymmetry explicit: logged history may contribute lifted visual and semidense evidence, but counterfactual future rows may only use selected successor geometry and validated actor-visible summaries.

This core descriptor plan is intentionally marked as a design contract: every adopted block must stay actor-visible and every escalation needs validation evidence before it becomes a thesis-core claim.

The target descriptor must separate identity, support, and evaluation. Identity says which object the rollout is about; support says what actor-visible evidence currently covers it; evaluation associates that target with hidden GT assets for labels. Conflating these channels creates two opposite errors: low-support targets are silently removed before they can expose non-myopic headroom, or oracle GT crops leak into the actor input. The first descriptor version should therefore expose OBB geometry, class/confidence, relative pose, projected area, semidense support, EVL support, EVL coverage/out-of-extent, and selector provenance as actor features, while storing GT match, GT crop, and target-error fields as label/evaluation metadata only.

#figure(
  text(size: 8.6pt, table(
    columns: (0.78fr, 1.1fr, 1.42fr),
    toprule(),
    table.header([*Status*], [*Representation*], [*Use and gate*]),
    midrule(), [Adopt now], [EFM3D/EVL target and support evidence],
    [Aria/ASE-native OBB and surface-regression substrate with posed egocentric streams, semidense points, and target hypotheses @EFM3D-straub2024 @EVL-Doc-2025. Report extent/confidence/support/failures; never promote V0 GT targets or oracle labels to actor-visible state.],
    [Adopt now],
    [Explicit scalar descriptors],

    [Candidate pose, target-relative translation, bearing, range, elevation, R6D orientation, validity reason, strategy id, support counts, projected visibility, and remaining budget @zhou2019continuity. Row-shuffle, mask-isolation, duplicate-row, and valid-count tests are required.],
    [Adopt now],
    [Canonical replay rows with derived descriptors],

    [Store stable ids, poses, masks, selected transition, reward, successor ids, and provenance; derive descriptor versions in the reader and record source role, frame, feature id, compression, support, and uncertainty.],
    [Ablate next],
    [Query-centric relations and directional memory],

    [Use QCNet-style relative positional encodings for candidate-candidate/history relations and keep target visibility as $bb(S)^2$ memory @zhou2023query @FisherRF-jiang2024 @SCONE-guedon2022 @e3nn-SphericalHarmonics-2025. Credit only after simpler controls are calibrated.],
    bottomrule(),
  )),
  caption: [Core descriptor plan for #symb.rl.qh. This is a design contract, not an empirical ranking.],
) <tab:thesis-descriptor-core-plan>

The escalation table is likewise a controlled backlog surface inside the method chapter. It names plausible representation families while keeping their gates explicit.

#figure(
  text(size: 8.6pt, table(
    columns: (0.78fr, 1.1fr, 1.42fr),
    toprule(),
    table.header([*Status*], [*Representation*], [*Use and gate*]),
    midrule(), [Ablate next], [Semidense/fused point bank plus compressed DINO-on-point],
    [Tests broader scene memory than the final EVL volume; EFM3D suggests semidense points and frozen DINO cues matter @EFM3D-straub2024. Require stable point/voxel ids, compression policy, feature hash, density tests, and storage/runtime accounting.],
    [Ablate next],
    [EVL internals and target/candidate crop reads],

    [Reads pre-head voxel, neck, or OBB-crop evidence when final heads hide support. Store crop frame, grid pose, EVL extent, feature id, and out-of-extent flag; never extract features from oracle target meshes.],
    [Ablate later],
    [Point and sparse support encoders],

    [PointNeXt, Point Transformer/PTv3, KPConv, and sparse convolutions are plausible support encoders, not OBB target detectors @PointNeXt-qian2022 @point-transformer-zhao2021 @PointTransformerV3-wu2024 @KPConv-thomas2019 @MinkowskiEngine-choy2019. Escalate only after compact query pools bottleneck.],
    [Defer / bridge],
    [Renderable explicit state and recurrence],

    [3DGS-like state may later supply renderable memory, and Deja View-style looped refinement is a compute-depth diagnostic template @GaussianSplatting-kerbl2023 @dejaviewloopingtransformersburzio2026. Deja View is not the #symb.rl.qh planner.],
    [Diagnostic only],
    [Cube R-CNN-style OBB detector],

    [Useful as a single-frame detector reference, but EFM3D reports off-the-shelf Cube R-CNN generalizes poorly to egocentric Aria data @omni3d-cubercnn-brazil2023 @EFM3D-straub2024. It is not reusable scene-conditioning state.],
    bottomrule(),
  )),
  caption: [Escalation candidates for scene encodings and backbone alternatives. Each candidate needs actor-visible training, storage, runtime, and ablation evidence before thesis-core use.],
) <tab:thesis-encoder-escalation-plan>

The minimal descriptor schema can be summarized as a typed row vector before the table expands the field roles:

$
  bold(x)_(t,i)
  =
  op("concat")(
    bold(z)_e,
    bold(p)_(t,i),
    bold(g)_(t,i),
    phi_"valid"(m_(t,i), rho_(t,i)),
    bold(H)_t
  ),
$

with target descriptor $bold(z)_e$, candidate-pose token $bold(p)_(t,i)$, candidate-geometry token $bold(g)_(t,i)$, hard-mask/reason encoding $phi_"valid"$, and selected-history summary $bold(H)_t$. This symbolic view keeps the table below as a provenance checklist rather than the model definition.

#figure(
  table(
    columns: (0.78fr, 1.22fr, 1.18fr),
    toprule(),
    table.header([*Descriptor block*], [*Fields*], [*Failure prevented*]),
    midrule(),
    [Target token],
    [Observed or predicted OBB center, extents, orientation, class probabilities, detector confidence, selector rank, projected visibility, semidense/EVL support, EVL coverage/out-of-extent, and source mode.],

    [Separates V1 actor-visible target input from GT-EVAL matching and prevents GT OBB leakage into deployable policy inputs.],
    [Candidate self token],
    [Candidate pose in root, target, and current-camera frames; distance, bearing, elevation, optical-axis alignment, remaining horizon, sampler strategy, validity mask, and reason code.],

    [Makes the finite action row interpretable and keeps invalidity a hard mask rather than a low-reward training example.],
    [Candidate-target relation],
    [Frustum-target overlap, projected target area, expected support change, target-local approach direction, visibility novelty, and optional EVL/crop support read.],

    [Forces the model to condition on the chosen target instead of learning scene-level coverage shortcuts.],
    [Candidate-candidate and history relations],
    [Relative poses, angular separation, duplicate/near-duplicate indicators, selected-view directional memory, and valid-count features.],

    [Supports permutation-equivariant interaction while exposing attention-normalization shortcuts and duplicate-row artifacts.],
    [Feature-bank joins],
    [Stable point or voxel id, feature-model id, compression version, observation count, frame lineage, uncertainty, and out-of-extent status.],

    [Prevents silent mixing of logged RGB/DINO features with counterfactual rows that only have selected successor geometry.],
    bottomrule(),
  ),
  caption: [Minimum descriptor schema before heavier scene encoders are evaluated. Every field is either actor-visible or explicitly stored as oracle-only label/evaluation metadata outside the policy input.],
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

== Candidate and Replay Contract

// source: aria_nbv/aria_nbv/pose_generation/candidate_mixture.py:16-24 and aria_nbv/aria_nbv/pose_generation/candidate_mixture.py:150-177 define the three-family default and per-row provenance.
// source: aria_nbv/aria_nbv/rollouts/zarr_store.py:224-263 persists candidate masks, sampler provenance, rewards, and support metrics.
Each decision state carries a finite candidate table #symb.rl.candidate_table, hard mask $bold(m)_t$, invalid-reason vector $bold(rho)_t$, and the target descriptor #symb.entity.target_desc. It also stores selected-view history and remaining budget. The admissible action is a valid candidate row index:

$
  #eqs.rl.finite_action_set
$

Selecting a candidate means choosing a valid index $a_t=i in cal(A)_t$ for the transition. Oracle rendering follows the repository's PyTorch3D depth-rendering path, so camera-frame and rasterizer conventions are part of the label contract rather than model input @PyTorch3D-Cameras-2025. All valid candidates may be rendered at the oracle layer to score one-step labels, while the rollout writer separately persists selected/parent depth at a canonical configured resolution as actor-history state for successor #symb.rl.qh encoders.

After selection, acquired geometry is added to the current geometry:

$
  #symb.obs.points_next
  =
  #symb.obs.points_t
  union
  #symb.obs.points_cand_ti.
$

The next candidate table $cal(Q)_(t+1)$ is regenerated from updated geometry, selected-view history, and remaining horizon metadata with the same logged mixture families, while root local @egocentric-voxel-lifting:short evidence remains fixed unless a later ablation explicitly recomputes it. The current target-conditioned mixture vocabulary contains forward/local candidates, target-bearing candidates, lateral target-bypass candidates, bounded orientation jitter, and per-row strategy provenance. The older radial free-shell sampler from the seminar paper is retained as a historical upper-bound or stress ablation, not as the default target-conditioned candidate distribution.

Candidate provenance is a model input only through typed scalar or embedding channels. The row stores `strategy_id`, `position_id`, `mixture_id`, `sampler_probability`, target-distance/bearing diagnostics, motion-realism diagnostics, and invalid-reason bits. The training reader may embed these as candidate-family tokens, but the model must still pass row-shuffle and duplicate-row tests: the family label explains how the row was sampled, not an ordering prior.

Candidate order has no semantics, so shuffled-candidate evaluation is required. Candidate orientation uses a continuous 6D rotation code @zhou2019continuity, but accumulated visibility is a directional memory over $bb(S)^2$, not a sum of R6D vectors. For a target point or voxel center $bold(v)$ and a previously selected camera center $bold(c)_k$, the observed direction is

$
  #eqs.features.direction_unit
$

Here $bold(v) in RR^3$ is a target-local point or voxel center, $bold(c)_k in RR^3$ is the center of a selected camera, and $bold(d)_k(bold(v)) in bb(S)^2$ is the unit ray from the target-local support location toward that selected view. The scalar weight $w_k(bold(v))$ can encode whether view $k$ observed, supported, or improved that target-local region. The planned actor-visible feature branch stores history either as low-order spherical-harmonic coefficients @e3nn-SphericalHarmonics-2025

$
  #eqs.features.direction_memory_sh
$

or as a second-moment summary over unit directions,

$
  #eqs.features.direction_memory_moment
$

from which the candidate can read a directional novelty score. The numerator projects the candidate direction through the accumulated second-moment matrix; the trace-normalized complement is high when the candidate approaches the target from an underrepresented direction:

$
  #eqs.features.direction_novelty
$

The directional-memory diagram in @fig:qh-directional-memory keeps this branch separate from generic pose tokens: selected views first accumulate target-local directional evidence, and each candidate then queries whether it sees the target from a genuinely new direction.

#figure(
  align(center, image(
    "../figures/qh_directional_memory.pdf",
    width: 72%,
  )),
  caption: [Actor-visible directional memory for target-local view novelty. The figure shows a planned descriptor branch, not an implemented performance result: selected view directions over observed points or voxels are summarized as low-order directional coefficients, and each valid candidate reads the memory to produce a candidate token feature for #symb.rl.qh.],
) <fig:qh-directional-memory>

The minimum replay row contains scene/snippet/target/step identifiers, counterfactual state, target descriptor, candidate table, masks, invalid reasons, selected action, target reward, successor state, successor candidates, successor masks, and policy/seed/sampler metadata. This row reproduces the mask, selected transition, value target, and oracle re-evaluation.

== Architecture Contract and Geometric Acceptance Tests <sec:thesis-method-geometry-contract>

// source: docs/contents/theory/candidate_view_dependence.qmd:83-89 and docs/contents/theory/candidate_view_dependence.qmd:384-421 define the candidate-set architecture ladder.
// source: aria_nbv/aria_nbv/rollouts/zarr_store.py:2502-2603 defines the derived q_h training view, masks, rewards, and TD links.
The geometric-learning rationale in @sec:thesis-geometric-learning-theory becomes acceptance tests over the replay fields here. The planned architecture is not justified by adding geometric modules until the model looks sophisticated. Each module must answer a specific symmetry or provenance requirement of the finite-candidate problem. Candidate rows form an unordered set, so the learned value map must be permutation equivariant at the row level: reordering #symb.rl.candidate_table may reorder #symb.rl.qh outputs, but it must not change the value attached to a physical candidate. Invalid and padded rows are constraints, so mask isolation is part of the architecture contract rather than a post-processing detail. Candidate, target, and current-history geometry must be encoded in local frames so that arbitrary world-frame origin or yaw conventions do not become shortcuts. At the same time, the task is gravity aligned and egocentric; the thesis should not claim full $op("SO")(3)$ or $op("SE")(3)$ equivariance for the whole system.

#figure(
  align(center, image(
    "../figures/qh_symmetry_contract.pdf",
    width: 100%,
  )),
  caption: [Minimum symmetry and provenance contract for the finite-candidate #symb.rl.qh model. The contract requires row-level equivariance, mask isolation, local-frame geometry, target-local directional memory, and oracle/actor provenance gates; it does not claim exact global $op("SE")(3)$ equivariance.],
) <fig:qh-symmetry-contract>

The first model family should therefore use scalar invariant and local-frame relative features before heavier equivariant tensor machinery. A candidate-local relation such as $bold(T)^r_(c_q)$ or a target-relative bearing is a deliberate gauge choice: it removes irrelevant global-coordinate dependence while preserving the yaw, elevation, distance, and approach-direction signals needed for visibility. Directional history is a separate object. A selected view direction belongs on $bb(S)^2$ and should be stored as a target-local histogram, second-moment matrix, or low-order spherical-harmonic memory rather than being merged into generic pose features. This separation protects the interpretation of an ablation: a QCNet-style relative positional bias tests candidate-candidate geometry, while directional memory tests whether the target has already been observed from similar directions @zhou2023query @e3nn-SphericalHarmonics-2025.

The architecture acceptance tests are as important as validation loss. Row-shuffle tests must satisfy $f_theta (Pi X_t, m_t)=Pi f_theta (X_t, m_t)$ up to numerical tolerance for every per-candidate output used by selection. Mask tests must show that invalid rows cannot alter valid scores except through explicit valid-count or support features. Valid-count and duplicate-row stress tests check whether attention normalization has corrupted absolute target-specific @relative-reconstruction-improvement:short calibration. Only after the independent scorer and DeepSets controls pass these tests should masked Set Transformer interaction, Fisher/SCONE overlap bias, QCNet-style local relative positional encoding, or EGNN-style candidate graphs be credited as architectural gains @DeepSets-zaheer2017 @SetTransformer-lee2019 @FisherRF-jiang2024 @SCONE-guedon2022 @EGNN-satorras2021.

The token design follows the same separation of concerns. State tokens summarize what is known before choosing the next view; candidate tokens describe one admissible or invalid finite action; relation tokens describe target/candidate/history geometry; label tokens do not enter the actor graph. This keeps the first model educationally simple: start with a per-candidate scorer, add pooled set context, then add masked attention only when interaction is needed.

// source: aria_nbv/aria_nbv/vin/model_v3.py:1209-1508 describes the implemented one-step candidate feature path.
// source: docs/contents/theory/efm3d_scene_embeddings.qmd:91-137 defines target/frustum/intersection query pools.
#figure(
  text(size: 8.6pt, table(
    columns: (0.72fr, 1.2fr, 1.25fr),
    toprule(),
    table.header([*Token role*], [*Content*], [*Invariant / gate*]),
    midrule(),
    [Target token],
    [Actor-visible OBB geometry, class/confidence, projected area, semidense/EVL support, relative target pose, and support coverage.],

    [No GT crop, GT identity, or oracle target error in actor input.],
    [Candidate-row token],
    [Pose in root/current/target frames, R6D orientation, strategy/position ids, motion diagnostics, mask/reason bits, and candidate-local support reads.],

    [Row permutation equivariance and hard-mask isolation.],
    [Scene/support token],
    [Root EVL local evidence, semidense/fused point support, selected-depth successor summaries, optional compressed DINO-on-point features.],

    [Actor-visible provenance, feature hash/compression version, support count, and EVL extent status.],
    [History token],
    [Selected-view poses, remaining budget, accumulated target-local directional memory, and selected successor depth metadata.],

    [No all-candidate oracle renders; only selected successor geometry updates history.],
    [Relation token],
    [Candidate-target frustum overlap, target-frustum intersection support, candidate-candidate relative pose, and QCNet-style local RPE.],

    [Ablation-gated after independent and DeepSets controls.],
    [Label/evaluation token],
    [GT target crop, target RRI, root-normalized target gain, oracle endpoint metric, and TD target.],

    [Stored in replay/q_h views only; never fed into the actor graph.], bottomrule(),
  )),
  caption: [Token ownership for the first finite-candidate #symb.rl.qh architecture. The table defines what may enter the actor model, what remains an ablation, and what is label/evaluation only.],
) <tab:thesis-qh-token-ownership>

#research_todo(
  [Treat Fisher/SCONE overlap attention and QCNet-style relative encodings as ablation hypotheses until row-shuffle, mask-isolation, and paired oracle policy evidence show they improve target-specific endpoint gain over simpler controls.],
  source: [autoresearch thesis-lit-review report; docs/contents/theory/candidate_view_dependence.qmd],
  gate: [A2/A3/A4 architecture ablation tables],
)

== Finite-Candidate Value Model

// source: .agents/memory/state/DECISIONS.md:97-99 fixes candidate-query Transformer #symb.rl.qh as a hard thesis deliverable.
// source: aria_nbv/aria_nbv/vin/model_v3.py:1-64 fixes VINv3 as the myopic one-step baseline/control, not the final multi-step model.
The value-model hypothesis is that a masked finite-candidate model can recover positive oracle-lookahead headroom from actor-visible state. #symb.rl.qh maps each valid candidate row to a finite-horizon value using actor-visible scene, target, selected-history, budget, candidate, mask, and reason-code features. Its outputs select actions, but thesis evidence comes from oracle re-scoring of the selected trajectories.

The model class follows the structure of the decision problem. The action space is a masked finite set of candidate views, each defined relative to a target, selected history, and partially observed geometry. Geometric deep learning supplies vocabulary for these regularities without committing the thesis to a full equivariant tensor network @GeometricDeepLearning-bronstein2021. Candidate-row permutation requires equivariant per-candidate outputs; local camera and target frames reduce dependence on global coordinates; $bb(S)^2$ visibility memory records where the target has already been observed; and the target record acts as the query that determines which reconstruction errors matter.

// source: docs/contents/theory/candidate_view_dependence.qmd:405-421 critiques absolute-label contamination and generator overfitting.
// source: aria_nbv/aria_nbv/rollouts/zarr_store.py:224-260 and aria_nbv/aria_nbv/rollouts/zarr_store.py:2534-2603 show that replay already exposes masks, provenance, target gains, and selected-transition TD fields.
The architecture critique is therefore simple: the first serious model should not be a monolithic transformer over every available tensor. The clean object is a calibrated one-step target utility field plus a masked residual correction over the valid candidate set. The one-step field owns absolute target-gain calibration; the set module owns only context-dependent advantage, redundancy, and finite-horizon effects. This prevents unrelated sampled rows from changing the physical one-step label attached to a candidate, while still allowing non-myopic effects from candidate regeneration, selected-history geometry, occlusion, and support overlap.

$
  b_(psi,i)
  =
  f_psi^"1-step" (s_t^"cf0", z_e, q_(t,i)),
  quad
  A_(theta,i)
  =
  g_theta (bold(x)_(t,i), {bold(x)_(t,j)}_(j in cal(A)_t), h_t),
$

$
  Q_(H,theta,i)
  =
  b_(psi,i)
  +
  A_(theta,i)
  -
  1 / abs(cal(A)_t)
  sum_(j in cal(A)_t) A_(theta,j).
$

The zero-mean residual form is not required forever, but it is the most defensible first architecture: if set interaction helps, it improves ranking through relative candidate context; if it does not, the model collapses to the calibrated myopic scorer rather than corrupting the target-RRI scale. Recent object-centric view-planning work reinforces this separation: target-centric visibility and feasibility should be explicit scoring factors, while difficulty, reachability, budget, and object saturation must be reported separately because they can change planner rankings and failure modes @OANBV-hu2026 @ObjViewBench-pan2026.

#figure(
  text(size: 8.6pt, table(
    columns: (0.68fr, 1.22fr, 1.28fr),
    toprule(),
    table.header([*Design principle*], [*Adopt in #symb.rl.qh*], [*Reject or defer*]),
    midrule(),
    [Calibrated absolute field],
    [Keep a one-step target-gain head that can be evaluated candidate-by-candidate under fixed masks.],

    [Letting attention over unrelated rows redefine the absolute immediate-RRI label.],
    [Residual set context],
    [Use DeepSets or masked Set Transformer context as a zero-mean advantage correction over valid rows.],

    [A pooled scene embedding with no per-row path, or unmasked invalid-row attention.],
    [Typed relative geometry],
    [Encode target-current-candidate-history relations in local frames; use QCNet-style RPE as an ablation.],

    [Claiming full global $op("SE")(3)$ equivariance for an egocentric, gravity-aligned, frustum-limited task.],
    [Directional visibility],
    [Represent selected history on $bb(S)^2$ and keep it distinct from generic pose tokens.],

    [Collapsing target-local observability into a scalar distance or sampler family prior.],
    [Support and difficulty reporting],
    [Report EVL extent, semidense support, reachability, validity, budget, and target saturation bins.],

    [Using support, Fisher/coverage proxies, or target area as the thesis reward instead of oracle target-RRI.],
    [Late geometric transformers],
    [Treat EGNN, SE(3)-Transformer, and GATr-style equivariant modules as support-encoder or candidate-graph ablations.],

    [Making exact equivariance the first thesis claim before the replay/mask/target-RRI contract is stable @EGNN-satorras2021 @SE3Transformer-fuchs2020 @GATr-brehmer2023.],
    bottomrule(),
  )),
  caption: [Architecture critique distilled into a conservative design order. The clean first model preserves a calibrated candidate-local field and allows set/geometric context to explain only residual advantage under explicit masks and evaluation gates.],
) <tab:thesis-qh-clean-architecture>

#figure(
  table(
    columns: (0.78fr, 0.72fr, 1.0fr, 1.08fr),
    toprule(),
    table.header([*Object*], [*Structure*], [*Bias*], [*Implementation role*]),
    midrule(), [candidate table $cal(Q)_t$], [finite set], [permuting rows permutes per-candidate #symb.rl.qh outputs],
    [independent candidate MLP, pooled DeepSets residual context, and masked Set Transformer residual context @DeepSets-zaheer2017 @SetTransformer-lee2019],
    [camera, target, and history poses],
    [$op("SE")(3)$ / gravity-aligned local frames],
    [relative geometry reduces dependence on arbitrary global frame choice],

    [relative target/history pose features, R6D rotations, QCNet-style candidate-local RPE; EGNN-style graph as ablation @zhou2019continuity @zhou2023query @EGNN-satorras2021],
    [directional visibility],
    [$bb(S)^2$],
    [encode which directions have already observed target-local cells],

    [second-moment memory by default; histogram or low-order spherical harmonics as ablations @e3nn-SphericalHarmonics-2025],
    [target identity],
    [selected entity / OBB query],
    [target defines the query frame for value estimation],

    [target-task descriptor and predicted-OBB crop; @ground-truth:short crops remain labels/evaluation], bottomrule(),
  ),
  caption: [Symmetry contract for the value model. Added structure is evaluated by oracle-scored endpoint target quality under the paired headroom protocol.],
) <tab:thesis-geometric-bias>

The one-step target scorer is adapted to counterfactual rollout rows rather than reusing the seminar @view-introspection-network:short checkpoint unchanged. It remains myopic and predicts immediate target-specific @relative-reconstruction-improvement:short evidence for each candidate; the seminar VINv3 scorer is therefore a control architecture and implementation substrate, not already a target-conditioned finite-horizon #symb.rl.qh result. #symb.rl.qh is residual around this calibrated base, with the dueling residual head as the canonical value definition. The myopic scorer uses the CORAL ordinal-regression interface of Cao et al. and the `coral-pytorch` layer/loss implementation, adapted to ARIA-NBV's skewed oracle @relative-reconstruction-improvement:short labels @CORAL-cao2019 @coral-pytorch-2025:

$
  #eqs.rl.qh_coral_interface
$

ARIA-NBV's adaptation is in the binning and decoding around that interface. Continuous oracle target gains are fitted to empirical quantile edges $tau_1 <= dots <= tau_(K-1)$, and each sample receives the ordinal label $y = sum_(j=1)^(K-1) bb(1)[r^e > tau_j]$, matching the repository's `RriOrdinalBinner`. CORAL levels are threshold indicators $ell_k = bb(1)[y > k]$ for $k=0,dots,K-2$, matching `ordinal_labels_to_levels`. The code then decodes logits both as cumulative probabilities $P(y>k)=sigma(o_k)$ and as a ranking proxy $E[y]=sum_k sigma(o_k)$; when calibrated bin representatives are available, the expectation over $u_k$ maps the ordinal distribution back to target-gain units. This preserves the VIN-NBV ordinal-ranking precedent while making calibration, bin drift, and residual #symb.rl.qh recovery explicit ARIA-NBV diagnostics.

Training is staged to preserve the residual interpretation: train and calibrate $hat(r)_psi^e$, then freeze or slow-finetune it while fitting residual #symb.rl.qh, and finally ablate whether end-to-end fine-tuning improves oracle-evaluated policy performance. This also keeps the educational story clean: VINv3 answers "which single candidate looks good now?", while #symb.rl.qh answers "which first action has the best bounded downstream target gain under the same finite candidate and mask contract?".

The first #symb.rl.qh implementation should start from implemented @view-introspection-network:short/@egocentric-voxel-lifting:short heads plus semi-dense or fused geometry. A richer queryable feature bank is a planned representation ablation, not a current persisted cache schema:

$
  #eqs.features.qh_scene_memory
$

Candidate rows query the target crop, candidate frustum, and their intersection:

$
  #eqs.features.candidate_query_pools
$

The candidate encoder is permutation-equivariant:

$
  #eqs.features.qh_set_encoder
$

The candidate-query architecture in @fig:qh-vin-gnn-architecture expands the same contract into the architecture used for the thesis hypothesis and ablation ladder.

#figure(
  image(
    "../figures/qh_vin_gnn_architecture.pdf",
    width: 100%,
  ),
  caption: [Candidate-query #symb.rl.qh architecture sketch. Actor-visible @egocentric-voxel-lifting:short evidence, accumulated geometry, target descriptors, selected-history summaries, candidate geometry, masks, and directional memory feed a permutation-equivariant set reasoner; residual finite-horizon values, one-step auxiliary scores, and diagnostics are then decoded only over valid candidate rows. Oracle labels supervise training and evaluation outside this actor-input graph.],
) <fig:qh-vin-gnn-architecture>

No-interaction candidate MLP scoring and pooled DeepSets aggregation are required baselines before attributing gains to masked Set Transformer interaction or QCNet-style RPE. For immediate target-specific @relative-reconstruction-improvement:short, the physical oracle label of candidate $q_i$ does not change when unrelated rows are added to $cal(Q)_t$. Candidate interaction can therefore corrupt absolute calibration if it replaces the independent scorer. The safer myopic ablation uses candidate context only as a zero-mean relative advantage correction.

The value head is a dueling residual decomposition over valid actions @DuelingDQN-wang2016:

$
  #eqs.rl.qh_dueling_residual
$

#figure(
  table(
    columns: (0.62fr, 1.76fr),
    toprule(),
    table.header([*Model role*], [*Content*]),
    midrule(), [Hypothesis model],
    [adapted target-conditioned myopic scorer, zero-mean residual set context, residual dueling #symb.rl.qh, hard masks/reasons, matched-budget oracle re-scoring],
    [Required controls],

    [independent candidate MLP, calibrated myopic scorer, and pooled DeepSets residual context over valid candidate rows],
    [Ablations],

    [QCNet-style candidate-local RPE, Fisher/SCONE support-overlap attention bias, $bb(S)^2$ memory variants, EGNN-style candidate graph, privileged-teacher distillation, distributional #symb.rl.qh heads],
    [Architecture ladder],

    [A0 independent scorer; A1 pooled DeepSets residual context; A2 masked Set Transformer residual context; A3 query-local relative bias; A4 Fisher/SCONE overlap bias; A5 residual dueling #symb.rl.qh],
    [Bridges],

    [Hestia-style target-then-pose policies, online discrete interaction, external mesh/oracle-compatible simulators, sparse/point backbones],
    bottomrule(),
  ),
  caption: [Value-model hypothesis, controls, and ablations. Dense @ground-truth:short candidate renders may supervise later ablations, while learned policy inputs use the configured state and target-task descriptors.],
) <tab:thesis-value-ladder>

#impl_todo(
  [Confirm which architecture ladder levels are implemented, planned, or deferred once the final code state is frozen.],
  source: [advisor handout; proposal method],
  gate: [method implementation audit],
)
