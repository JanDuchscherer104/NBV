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

The planned value model needs more than a generic 3D feature extractor. A thesis-grade backbone or scene encoder must provide actor-visible target hypotheses, especially @oriented-bounding-box:short detections, and a reusable scene representation for target-, history-, and candidate-conditioned #symb.rl.qh queries. The current default therefore remains @egocentric-foundation-model-3d:short / @egocentric-voxel-lifting:short: it is trained for the Project Aria / @aria-synthetic-environments:short regime, lifts multi-frame image features into a gravity-aligned 3D volume, uses semi-dense support, and exposes OBB/object evidence @EFM3D-straub2024 @EVL-Doc-2025. A replacement backbone is only thesis-relevant if it preserves this target-detection contract while improving the conditioning representation used by #symb.rl.qh.

The central asymmetry is that the historic state is rich and multimodal, while counterfactual states are not. Logged snippets contain calibrated RGB/SLAM streams, poses, semidense points, EVL evidence, and observed or predicted OBBs. Counterfactual successors can reliably add selected geometry, support counts, visibility history, oracle-rendered labels, and actor-visible summaries derived from those sources; they cannot assume fresh RGB, DINO, semantic, or detector outputs at unvisited candidate poses unless a separate renderable or learned modality generator is introduced and validated. This prevents a model from winning by consuming modalities that exist only for the logged trajectory or only inside the oracle.

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

#figure(
  table(
    columns: (0.8fr, 1.05fr, 1.24fr),
    toprule(),
    table.header([*Candidate representation*], [*Useful role*], [*Boundary before thesis-core use*]),
    midrule(),
    [@egocentric-foundation-model-3d:short / @egocentric-voxel-lifting:short],
    [Default Aria-native target/support anchor: OBB evidence, lifted visual features, occupancy/free-space support, and local voxel reasoning.],
    [Do not claim full long-horizon memory; report local-volume extent and final-pose anchoring limits.],
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

The descriptor plan follows from this backbone constraint. #symb.rl.qh should first receive typed, actor-visible query pools rather than a monolithic feature tensor: a target token, selected-history summaries, per-candidate geometry, candidate-target relations, directional visibility memory, and optional feature-bank joins. The storage contract remains canonical: persist IDs, poses, masks, support counts, feature provenance, and oracle labels in replay rows; derive model descriptors in the reader so that new encoders do not rewrite the supervision artifact. This also keeps the historic/counterfactual asymmetry explicit: logged history may contribute lifted visual and semidense evidence, but counterfactual future rows may only use selected successor geometry and validated actor-visible summaries.

#figure(
  text(size: 8.6pt, table(
      columns: (0.78fr, 1.1fr, 1.42fr),
      toprule(),
      table.header([*Status*], [*Representation*], [*Use and gate*]),
      midrule(),
      [Adopt now],
      [EFM3D/EVL target and support evidence],
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
    )
  ),
  caption: [Core descriptor plan for #symb.rl.qh. This is a design contract, not an empirical ranking.],
) <tab:thesis-descriptor-core-plan>

#figure(
  text(size: 8.6pt, table(
      columns: (0.78fr, 1.1fr, 1.42fr),
      toprule(),
      table.header([*Status*], [*Representation*], [*Use and gate*]),
      midrule(),
      [Ablate next],
      [Semidense/fused point bank plus compressed DINO-on-point],
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
    )
  ),
  caption: [Escalation candidates for scene encodings and backbone alternatives. Each candidate needs actor-visible training, storage, runtime, and ablation evidence before thesis-core use.],
) <tab:thesis-encoder-escalation-plan>

#figure(
  table(
    columns: (0.78fr, 1.22fr, 1.18fr),
    toprule(),
    table.header([*Descriptor block*], [*Fields*], [*Failure prevented*]),
    midrule(),
    [Target token],
    [Observed or predicted OBB center, extents, orientation, class probabilities, detector confidence, selector rank, projected visibility, semidense/EVL support, and source mode.],
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

== Candidate and Replay Contract

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

Candidate order has no semantics, so shuffled-candidate evaluation is required. Candidate orientation uses a continuous 6D rotation code @zhou2019continuity, but accumulated visibility is a directional memory over $bb(S)^2$, not a sum of R6D vectors. For a target point or voxel center $bold(v)$ and a previously selected camera center $bold(c)_k$, the observed direction is

$
  #eqs.features.direction_unit
$

The planned actor-visible feature branch stores history either as low-order spherical-harmonic coefficients @e3nn-SphericalHarmonics-2025

$
  #eqs.features.direction_memory_sh
$

or as a second-moment summary,

$
  #eqs.features.direction_memory_moment
$

from which the candidate can read a directional novelty score:

$
  #eqs.features.direction_novelty
$

The minimum replay row contains scene/snippet/target/step identifiers, counterfactual state, target descriptor, candidate table, masks, invalid reasons, selected action, target reward, successor state, successor candidates, successor masks, and policy/seed/sampler metadata. This row reproduces the mask, selected transition, value target, and oracle re-evaluation.

== Architecture Contract and Geometric Acceptance Tests <sec:thesis-method-geometry-contract>

Section @sec:thesis-geometric-learning-theory owns the scientific rationale for the architecture ladder. This method section turns that rationale into acceptance tests over the replay fields. The planned architecture is not justified by adding geometric modules until the model looks sophisticated. Each module must answer a specific symmetry or provenance requirement of the finite-candidate problem. Candidate rows form an unordered set, so the learned value map must be permutation equivariant at the row level: reordering #symb.rl.candidate_table may reorder #symb.rl.qh outputs, but it must not change the value attached to a physical candidate. Invalid and padded rows are constraints, so mask isolation is part of the architecture contract rather than a post-processing detail. Candidate, target, and current-history geometry must be encoded in local frames so that arbitrary world-frame origin or yaw conventions do not become shortcuts. At the same time, the task is gravity aligned and egocentric; the thesis should not claim full $op("SO")(3)$ or $op("SE")(3)$ equivariance for the whole system.

#figure(
  align(center, image(
    "../figures/qh_symmetry_contract.png",
    width: 100%,
  )),
  caption: [Minimum symmetry and provenance contract for the finite-candidate #symb.rl.qh model. The contract requires row-level equivariance, mask isolation, local-frame geometry, target-local directional memory, and oracle/actor provenance gates; it does not claim exact global $op("SE")(3)$ equivariance.],
) <fig:qh-symmetry-contract>

The first model family should therefore use scalar invariant and local-frame relative features before heavier equivariant tensor machinery. A candidate-local relation such as $bold(T)^r_(c_q)$ or a target-relative bearing is a deliberate gauge choice: it removes irrelevant global-coordinate dependence while preserving the yaw, elevation, distance, and approach-direction signals needed for visibility. Directional history is a separate object. A selected view direction belongs on $bb(S)^2$ and should be stored as a target-local histogram, second-moment matrix, or low-order spherical-harmonic memory rather than being merged into generic pose features. This separation protects the interpretation of an ablation: a QCNet-style relative positional bias tests candidate-candidate geometry, while directional memory tests whether the target has already been observed from similar directions @zhou2023query @e3nn-SphericalHarmonics-2025.

The architecture acceptance tests are as important as validation loss. Row-shuffle tests must satisfy $f_theta(Pi X_t, m_t)=Pi f_theta(X_t, m_t)$ up to numerical tolerance for every per-candidate output used by selection. Mask tests must show that invalid rows cannot alter valid scores except through explicit valid-count or support features. Valid-count and duplicate-row stress tests check whether attention normalization has corrupted absolute target-specific @relative-reconstruction-improvement:short calibration. Only after the independent scorer and DeepSets controls pass these tests should masked Set Transformer interaction, Fisher/SCONE overlap bias, QCNet-style local relative positional encoding, or EGNN-style candidate graphs be credited as architectural gains @DeepSets-zaheer2017 @SetTransformer-lee2019 @FisherRF-jiang2024 @SCONE-guedon2022 @EGNN-satorras2021.

#research_todo(
  [Treat Fisher/SCONE overlap attention and QCNet-style relative encodings as ablation hypotheses until row-shuffle, mask-isolation, and paired oracle policy evidence show they improve target-specific endpoint gain over simpler controls.],
  source: [autoresearch thesis-lit-review report; docs/contents/theory/candidate_view_dependence.qmd],
  gate: [A2/A3/A4 architecture ablation tables],
)

== Finite-Candidate Value Model

The value-model hypothesis is that a masked finite-candidate model can recover positive oracle-lookahead headroom from actor-visible state. #symb.rl.qh maps each valid candidate row to a finite-horizon value using actor-visible scene, target, selected-history, budget, candidate, mask, and reason-code features. Its outputs select actions, but thesis evidence comes from oracle re-scoring of the selected trajectories.

The model class follows the structure of the decision problem. The action space is a masked finite set of candidate views, each defined relative to a target, selected history, and partially observed geometry. Geometric deep learning supplies vocabulary for these regularities without committing the thesis to a full equivariant tensor network @GeometricDeepLearning-bronstein2021. Candidate-row permutation requires equivariant per-candidate outputs; local camera and target frames reduce dependence on global coordinates; $bb(S)^2$ visibility memory records where the target has already been observed; and the target record acts as the query that determines which reconstruction errors matter.

#figure(
  table(
    columns: (0.78fr, 0.72fr, 1.0fr, 1.08fr),
    toprule(),
    table.header([*Object*], [*Structure*], [*Bias*], [*Implementation role*]),
    midrule(), [candidate table $cal(Q)_t$], [finite set], [permuting rows permutes per-candidate #symb.rl.qh outputs],
    [independent candidate MLP and pooled DeepSets controls; masked Set Transformer default @DeepSets-zaheer2017 @SetTransformer-lee2019],
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

Training is staged to preserve the residual interpretation: train and calibrate $hat(r)_psi^e$, then freeze or slow-finetune it while fitting residual #symb.rl.qh, and finally ablate whether end-to-end fine-tuning improves oracle-evaluated policy performance.

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
    [adapted target-conditioned myopic scorer, masked Set Transformer candidate interaction, residual dueling #symb.rl.qh, hard masks/reasons, matched-budget oracle re-scoring],
    [Required controls],

    [independent candidate MLP and pooled DeepSets context over valid candidate rows], [Ablations],
    [QCNet-style candidate-local RPE, Fisher/SCONE support-overlap attention bias, $bb(S)^2$ memory variants, EGNN-style candidate graph, privileged-teacher distillation, distributional #symb.rl.qh heads],
    [Architecture ladder],

    [A0 independent scorer; A1 pooled DeepSets context; A2 masked Set Transformer; A3 Set Transformer with $op("SE")(3)$ relative bias; A4 Fisher/SCONE overlap bias; A5 residual dueling #symb.rl.qh],
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
