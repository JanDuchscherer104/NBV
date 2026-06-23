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
The planned value model needs more than a generic 3D feature extractor. A thesis-grade perception stack must provide actor-visible target hypotheses, especially @oriented-bounding-box:short detections, while the scene memory must preserve reusable geometry, uncertainty, free/unknown evidence, and history for target-, history-, and candidate-conditioned #symb.rl.qh queries. These are separate interfaces: a detector can propose the target without being the scene memory, and a scene memory can support candidate scoring without predicting OBBs. The current default therefore remains @egocentric-foundation-model-3d:short / @egocentric-voxel-lifting:short for Aria-native target and local evidence: it is trained for the Project Aria / @aria-synthetic-environments:short regime, lifts multi-frame image features into a gravity-aligned 3D volume, uses semi-dense support, and exposes OBB/object evidence @EFM3D-straub2024 @EVL-Doc-2025. A replacement perception backbone is only thesis-relevant if it preserves this target-detection contract; a replacement memory is relevant if it improves candidate-conditioned evidence without breaking actor-visible provenance.

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

    [Expose typed query pools and ray-aware candidate queries rather than one final-pose voxel tensor: target crop, candidate support, candidate render/query, and directional-history support.],
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

=== Descriptor and Encoding Plan

// source: aria_nbv/aria_nbv/data_handling/_target_selection.py:1-30 defines oracle target-task sampling versus actor-visible target selection.
// source: aria_nbv/aria_nbv/data_handling/_target_selection.py:209-254 lists oracle target-task identity and audit fields.
// source: aria_nbv/aria_nbv/rollouts/trace.py:79-151 carries rollout target lineage into replay.
The descriptor plan follows from this backbone constraint. #symb.rl.qh receives typed query pools rather than a monolithic feature tensor: a target token, selected-history summaries, a ray-aware scene-memory query, per-candidate geometry, candidate-target relations, directional visibility memory, and optional feature-bank joins. Replay rows persist IDs, poses, masks, support counts, feature provenance, selected transitions, and oracle labels; training readers derive descriptor versions. This keeps the logged/counterfactual asymmetry explicit: logged history may contribute lifted visual and semidense evidence, while counterfactual future rows may use only selected successor geometry and validated actor-visible summaries.

The target descriptor must separate identity, support, and evaluation. Identity says which object the rollout is about; support says what actor-visible evidence currently covers it; evaluation associates that target with hidden GT assets for labels. Conflating these channels creates two opposite errors: low-support targets are silently removed before they can expose non-myopic headroom, or oracle GT crops leak into the actor input. The first descriptor version should therefore expose OBB geometry, class/confidence, relative pose, projected area, semidense support, EVL support, EVL coverage/out-of-extent, and selector provenance as actor features, while storing GT match, GT crop, and target-error fields as label/evaluation metadata only.

The first adopted blocks are EFM3D/EVL target evidence, scalar candidate descriptors, canonical replay rows, and derived reader-side descriptor versions. The next representation block is ray-aware occupied/free/unknown memory with selected-view transition updates. Query-centric relations, directional memory, visibility-gated DINO-on-point, EVL internals, point/sparse support encoders, renderable state, recurrence, and Cube R-CNN ROI features enter only as ablations with actor-visible provenance, storage, runtime, and row-order tests.

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
    [Stable point, voxel, or ray-cell id; feature-model id; compression version; observation count; visibility lineage; uncertainty; and out-of-extent status.],

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

The representation-level transition also updates the sparse ray-aware memory:

$
  bold(M)_(t+1)^"ray"
  =
  op("Fuse")(
    bold(M)_t^"ray",
    #symb.obs.points_cand_ti,
    bold(R)_(q_(t,i))^"selected-rays"
  ).
$

This update can add selected surface evidence, ray-carve selected free space, convert unknown cells into observed-free or observed-surface cells, update support counts and uncertainty, and refresh target-local directional memory. It cannot attach a visual descriptor to newly selected counterfactual geometry unless a corresponding actor-visible RGB observation exists; those cells instead carry a selected-depth geometry source and a missing-visual-descriptor mask.

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
The geometric-learning rationale in @sec:thesis-geometric-learning-theory becomes replay-field acceptance tests. Each module must answer a symmetry or provenance requirement: candidate rows need row-level permutation equivariance; invalid and padded rows need mask isolation; candidate, target, and history geometry need local frames; and actor/oracle fields need separate provenance. The task is gravity aligned and egocentric, so exact global $op("SO")(3)$ or $op("SE")(3)$ equivariance is an ablation claim, not the default system claim.

#figure(
  align(center, image(
    "../figures/qh_symmetry_contract.pdf",
    width: 100%,
  )),
  caption: [Minimum symmetry and provenance contract for the finite-candidate #symb.rl.qh model. The contract requires row-level equivariance, mask isolation, local-frame geometry, target-local directional memory, and oracle/actor provenance gates; it does not claim exact global $op("SE")(3)$ equivariance.],
) <fig:qh-symmetry-contract>

The first model family should therefore use scalar invariant and local-frame relative features before heavier equivariant tensor machinery. A candidate-local relation such as $bold(T)^r_(c_q)$ or a target-relative bearing is a deliberate gauge choice: it removes irrelevant global-coordinate dependence while preserving the yaw, elevation, distance, and approach-direction signals needed for visibility. Directional history is a separate object. A selected view direction belongs on $bb(S)^2$ and should be stored as a target-local histogram, second-moment matrix, or low-order spherical-harmonic memory rather than being merged into generic pose features. This separation protects the interpretation of an ablation: a QCNet-style relative positional bias tests candidate-candidate geometry, while directional memory tests whether the target has already been observed from similar directions @zhou2023query @e3nn-SphericalHarmonics-2025.

The architecture acceptance tests are as important as validation loss. Row-shuffle tests must satisfy $f_theta (Pi X_t, m_t)=Pi f_theta (X_t, m_t)$ up to numerical tolerance for every per-candidate output used by selection. Mask tests must show that invalid rows cannot alter valid scores except through explicit valid-count or support features. Valid-count and duplicate-row stress tests check whether attention normalization has corrupted absolute target-specific @relative-reconstruction-improvement:short calibration. Only after the independent scorer and candidate-to-state query controls pass these tests should DeepSets context, masked Set Transformer interaction, Fisher/SCONE overlap bias, QCNet-style local relative positional encoding, or EGNN-style candidate graphs be credited as architectural gains @DeepSets-zaheer2017 @SetTransformer-lee2019 @FisherRF-jiang2024 @SCONE-guedon2022 @EGNN-satorras2021.

The token design follows the same separation of concerns. State tokens summarize known actor-visible evidence before the next view; candidate tokens describe one finite action and its mask/reason code; relation tokens describe target/candidate/history geometry; label tokens store GT target crops, target gains, endpoint metrics, and TD targets outside the actor graph. The first model should therefore start with a per-candidate scorer and candidate-to-state cross-attention; pooled set context or masked candidate-candidate attention is an ablation only when interaction is needed.

#research_todo(
  [Treat Fisher/SCONE overlap attention and QCNet-style relative encodings as ablation hypotheses until row-shuffle, mask-isolation, and paired oracle policy evidence show they improve target-specific endpoint gain over simpler controls.],
  source: [autoresearch thesis-lit-review report; docs/contents/theory/candidate_view_dependence.qmd],
  gate: [A2/A3/A4 architecture ablation tables],
)

== Finite-Candidate Value Model

// source: .agents/memory/state/DECISIONS.md:97-99 fixes finite-candidate #symb.rl.qh as a hard thesis deliverable; current wording instantiates it as candidate-to-state queries first.
// source: aria_nbv/aria_nbv/vin/model_v3.py:1-64 fixes VINv3 as the myopic one-step baseline/control, not the final multi-step model.
The value-model hypothesis is that a masked finite-candidate model can recover positive oracle-lookahead headroom from actor-visible state. #symb.rl.qh maps each valid candidate row to a finite-horizon value using actor-visible scene, target, selected-history, budget, candidate, mask, and reason-code features. Its outputs select actions, but thesis evidence comes from oracle re-scoring of the selected trajectories.

The model class follows the structure of the decision problem. The action space is a masked finite set of candidate views, each defined relative to a target, selected history, and partially observed geometry. Geometric deep learning supplies vocabulary for these regularities without committing the thesis to a full equivariant tensor network @GeometricDeepLearning-bronstein2021. Candidate-row permutation requires equivariant per-candidate outputs; local camera and target frames reduce dependence on global coordinates; $bb(S)^2$ visibility memory records where the target has already been observed; and the target record acts as the query that determines which reconstruction errors matter.

// source: docs/contents/theory/candidate_view_dependence.qmd:405-421 critiques absolute-label contamination and generator overfitting.
// source: aria_nbv/aria_nbv/rollouts/zarr_store.py:224-260 and aria_nbv/aria_nbv/rollouts/zarr_store.py:2534-2603 show that replay already exposes masks, provenance, target gains, and selected-transition TD fields.
The architecture critique is therefore simple: the first serious model should not be a monolithic transformer over every available tensor or over arbitrary candidate rows. The clean object is a calibrated one-step target utility field plus an uncentred finite-horizon residual from candidate-to-state evidence. The one-step field owns immediate target-gain calibration; the residual owns downstream effects from candidate regeneration, selected-history geometry, occlusion, free/unknown evidence, and support overlap. Unrelated sampled rows should not change the physical value of candidate $q_i$ except through explicitly modeled support or policy-context ablations.

$
  b_(psi,i)
  =
  f_psi^"1-step" (s_t^"cf0", z_e, q_(t,i)),
  quad
  delta_(theta,i)^H
  =
  g_theta (bold(x)_(t,i), {bold(T)_e, bold(M)_t^"ray", bold(H)_t, bold(E)_0^"EVL-local"}, h_t),
$

$
  Q_(H,theta,i)
  =
  b_(psi,i)
  +
  delta_(theta,i)^H.
$

The residual can be kept small with a norm penalty or dataset-level regularization, but it should not be exactly mean-centred within each sampled candidate table. Per-set centering changes absolute Q values when duplicate or unrelated valid rows are added, which is unsafe for TD targets. Candidate-candidate interaction remains useful for policy logits, diversity, or top-$k$ selection ablations, but the default finite-horizon value head stays in continuous target-gain units. Recent object-centric view-planning work reinforces this separation: target-centric visibility and feasibility should be explicit scoring factors, while difficulty, reachability, budget, and object saturation must be reported separately because they can change planner rankings and failure modes @OANBV-hu2026 @ObjViewBench-pan2026.

#figure(
  text(size: 8.6pt, table(
    columns: (0.68fr, 1.22fr, 1.28fr),
    toprule(),
    table.header([*Design principle*], [*Adopt in #symb.rl.qh*], [*Reject or defer*]),
    midrule(),
    [Calibrated absolute field],
    [Keep a one-step target-gain head that can be evaluated candidate-by-candidate under fixed masks.],

    [Letting attention over unrelated rows redefine the absolute immediate-RRI label.],
    [Finite-horizon residual context],
    [Use candidate-to-state cross-attention for the default residual; regularize residual magnitude without exact per-set centering.],

    [A pooled scene embedding with no per-row path, exact candidate-table mean centering for TD values, or unmasked invalid-row attention.],
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
  caption: [Architecture critique distilled into a conservative design order. The clean first model preserves a calibrated candidate-local field and allows actor-visible state, history, and geometry context to explain finite-horizon residual value under explicit masks and evaluation gates.],
) <tab:thesis-qh-clean-architecture>

The one-step target scorer is adapted to counterfactual rollout rows rather than reusing the seminar @view-introspection-network:short checkpoint unchanged. It remains myopic and predicts immediate target-specific @relative-reconstruction-improvement:short evidence for each candidate; the seminar VINv3 scorer is therefore a control architecture and implementation substrate, not already a target-conditioned finite-horizon #symb.rl.qh result. #symb.rl.qh is residual around this calibrated base, with an uncentred continuous residual head as the canonical finite-horizon value definition. The myopic scorer uses the CORAL ordinal-regression interface of Cao et al. and the `coral-pytorch` layer/loss implementation, adapted to ARIA-NBV's skewed oracle @relative-reconstruction-improvement:short labels @CORAL-cao2019 @coral-pytorch-2025:

$
  #eqs.rl.qh_coral_interface
$

ARIA-NBV's adaptation is in the binning and decoding around that interface. Continuous oracle target gains are fitted to empirical quantile edges $tau_1 <= dots <= tau_(K-1)$, and each sample receives the ordinal label $y = sum_(j=1)^(K-1) bb(1)[r^e > tau_j]$, matching the repository's `RriOrdinalBinner`. CORAL levels are threshold indicators $ell_k = bb(1)[y > k]$ for $k=0,dots,K-2$, matching `ordinal_labels_to_levels`. The code then decodes logits both as cumulative probabilities $P(y>k)=sigma(o_k)$ and as a ranking proxy $E[y]=sum_k sigma(o_k)$; when calibrated bin representatives are available, the expectation over $u_k$ maps the ordinal distribution back to target-gain units. This preserves the VIN-NBV ordinal-ranking precedent while making calibration, bin drift, and residual #symb.rl.qh recovery explicit ARIA-NBV diagnostics.

Training is staged to preserve the residual interpretation: train and calibrate $hat(r)_psi^e$, then freeze or slow-finetune it while fitting residual #symb.rl.qh in continuous return units with Huber or distributional/quantile losses, and finally ablate whether end-to-end fine-tuning improves oracle-evaluated policy performance. CORAL remains the one-step ranking/calibration interface; finite-horizon #symb.rl.qh must preserve the metric structure of additive returns. This also keeps the educational story clean: VINv3 answers "which single candidate looks good now?", while #symb.rl.qh answers "which first action has the best bounded downstream target gain under the same finite candidate and mask contract?".

The first #symb.rl.qh implementation should start from implemented @view-introspection-network:short/@egocentric-voxel-lifting:short heads plus semi-dense or fused geometry. A reader-side logged-feature sampling helper exists, but a richer queryable feature bank is still a planned persisted-cache and training-reader ablation. It keeps root @egocentric-voxel-lifting:short local evidence separate from broad ray-aware memory, optional logged DINO-on-point descriptors, and actor-visible target hypotheses:

$
  #eqs.features.qh_scene_memory
$

Candidate rows first use target/support pools as cheap summaries:

$
  #eqs.features.candidate_query_pools
$

These pools are not visibility by themselves. The candidate observation branch should also query the ray-aware memory in the candidate camera:

$
  #eqs.features.candidate_ray_query
$

The default candidate-query encoder is candidate-to-state cross-attention, so each physical candidate reads the same fixed target, map, history, budget, and local-EVL tokens without unrelated candidate rows redefining its absolute value:

$
  #eqs.features.qh_candidate_state_cross_attention
$

The candidate-query architecture in @fig:qh-vin-gnn-architecture expands the same contract into the architecture used for the thesis hypothesis and ablation ladder.

#figure(
  image(
    "../figures/qh_vin_gnn_architecture.pdf",
    width: 100%,
  ),
  caption: [Candidate-query #symb.rl.qh architecture sketch. Actor-visible @egocentric-voxel-lifting:short evidence, accumulated geometry, ray-aware memory, target descriptors, selected-history summaries, candidate geometry, masks, and directional memory feed candidate-to-state value queries; residual finite-horizon values, one-step auxiliary scores, and diagnostics are then decoded only over valid candidate rows. Oracle labels supervise training and evaluation outside this actor-input graph.],
) <fig:qh-vin-gnn-architecture>

No-interaction candidate MLP scoring and candidate-to-state cross-attention are required baselines before attributing gains to masked Set Transformer interaction or QCNet-style RPE. For immediate target-specific @relative-reconstruction-improvement:short, the physical oracle label of candidate $q_i$ does not change when unrelated rows are added to $cal(Q)_t$. Candidate interaction can therefore corrupt absolute calibration if it replaces the independent scorer. The safer finite-horizon ablation lets candidate context influence policy logits, diversity, or a separately regularized residual, but not an exact per-set mean-centred TD value.

The value head is an uncentred residual decomposition over valid actions, with residual regularization rather than exact candidate-table centering:

$
  #eqs.rl.qh_uncentered_residual
$

#figure(
  table(
    columns: (0.62fr, 1.76fr),
    toprule(),
    table.header([*Model role*], [*Content*]),
    midrule(), [Hypothesis model],
    [adapted target-conditioned myopic scorer, candidate-to-state residual #symb.rl.qh in continuous return units, hard masks/reasons, matched-budget oracle re-scoring],
    [Required controls],

    [independent candidate MLP, calibrated myopic scorer, and candidate-to-state cross-attention without candidate-candidate self-attention],
    [Ablations],

    [pooled DeepSets context, masked Set Transformer policy context, QCNet-style candidate-local RPE, Fisher/SCONE support-overlap attention bias, $bb(S)^2$ memory variants, EGNN-style candidate graph, privileged-teacher distillation, distributional #symb.rl.qh heads],
    [Architecture ladder],

    [A0 independent scorer; A1 candidate-to-state cross-attention; A2 pooled DeepSets context; A3 masked Set Transformer policy/context ablation; A4 query-local relative bias; A5 Fisher/SCONE overlap bias; A6 distributional or quantile #symb.rl.qh],
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
