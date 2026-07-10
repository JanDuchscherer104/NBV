# Thesis Literature Review And Implementation Aim Autoresearch

Date: 2026-06-17

## Executive Result

The thesis seed is directionally coherent, but three claims needed tightening:
EVL must be described as local actor-visible target/support evidence rather than
a full scene memory; queryable point-attached feature banks are planned
representation ablations rather than a current persisted cache schema; and
`gamma=1` telescoping only justifies equal-horizon/equal-budget reporting while
discount/clipping policy remains open. These are now patched in the thesis
background and method sections.

The literature manifest now carries thesis-specific metadata for all 38 source
entries:

- `relevance_rank`: 1 to 5.
- `relevance_category`: descriptive thesis role.
- `adoptable_ideas`: concrete ideas to adopt or explicitly defer.

litkg now preserves those fields through manifest loading, registry snapshots,
materialized Markdown, tabular exports, `kg-show-paper`/search structs, CLI text
rendering, and Neo4j export. During integration, two litkg correctness bugs were
found and fixed: multiple manifest rows with empty `arxiv_id` were collapsing
into one key, and empty `tex_dir` rows were parsed as the entire TeX root.

## Wrong Or Weak Claims In `main.typ`

| Finding | Evidence | Resolution |
| --- | --- | --- |
| EVL was too broad as an actor-visible basis. | `docs/contents/theory/efm3d_scene_embeddings.qmd` says EVL is local finite support and risky as sole long-horizon memory; the thesis background previously leaned on EVL without that caveat. | `docs/typst/thesis/sections/02-background.typ` now says EVL is local target/support evidence; broader context comes from semi-dense/fused geometry; point-attached feature banks are planned ablations. |
| Queryable feature bank was stated as if current implementation. | `docs/contents/theory/efm3d_scene_embeddings.qmd` marks point-feature banks as planned until writer/cache/training reader exist. | `docs/typst/thesis/sections/03-method.typ` now frames richer queryable feature banks as planned representation ablations. |
| `gamma=1` telescoping needed scope. | `docs/contents/theory/rl_planning.qmd` and `docs/contents/theory/rri_theory.qmd` keep gamma symbolic/open and report fixed-budget root-normalized gain first. | `docs/typst/thesis/sections/03-method.typ` now limits telescoping to equal-horizon/equal-budget comparisons and states final discount/clipping policy remains open. |
| Draft schedule/open-work content remains archival. | `docs/typst/thesis/sections/06-draft-open-work.typ` carries archive/conflict markers. | No patch needed in this pass; keep as TODO-marked draft/open-work material until thesis schedule is frozen. |

## Thesis Content Placement Map

| Chapter / Section | Include | Source Basis |
| --- | --- | --- |
| Introduction | Narrow thesis position: target-conditioned finite-candidate NBV over ASE mesh/oracle replay; not a generic continuous-control or online-RL claim. | `docs/contents/thesis/questions.qmd`, `docs/contents/thesis/roadmap.qmd`, `.agents/memory/state/PROJECT_STATE.md`. |
| Background: egocentric substrate | Project Aria, ASE, EFM3D, EVL, semi-dense/fused geometry, and actor-visible/privileged-state split. | EFM3D, Project Aria, `docs/contents/theory/efm3d_scene_embeddings.qmd`. |
| Background: NBV objective families | VIN-NBV as closest RRI precedent; PB-NBV/SCONE/FisherRF/Hestia/Instance-NBV as contrastive families. | Literature manifest categories and local theory pages. |
| Background: finite candidate value learning | DQN lineage, Double DQN overestimation control, offline RL bridges, sequence-model bridges. | DQN, Double DQN, IQL, CQL, BCQ, Decision Transformer, Trajectory Transformer. |
| Method: state contract | `s_hist`, `s_cf0`, `s_oracle`, actor-visible target descriptors, GT-only labels/evaluation. | Current `sections/03-method.typ`, target-selection work audits, roadmap/questions. |
| Method: target selection and matching | OBS-SEL/PRED-Q/GT-EVAL, target-interest sampling, deterministic GT matching, invalid target handling. | `.agents/work/target-selection-methodology/*`, `docs/contents/theory/candidate_sampling_target_selection.qmd`. |
| Method: candidate/replay contract | Selected candidate transition only, successor candidate regeneration, hard masks/reasons, root local EVL fixed unless ablated. | Current method section, rollout-scale readiness notes. |
| Method: geometric symmetry contract | Candidate-row permutation equivariance, target/local-frame pose relations, gravity-aware orientation signals, hard validity masks, and `S^2` directional visibility memory. | `docs/contents/theory/candidate_view_dependence.qmd`, GDL, Deep Sets, Set Transformer, QCNet, SE(3)-Transformer, EGNN. |
| Method: architecture ladder | Independent scorer, DeepSets, masked Set Transformer, QCNet-style relative encodings, directional memory, residual dueling `Q_H`; Deja View-style recurrence and point/geometric backbones stay ablations until simple set models fail. | Set Transformer, Deep Sets, QCNet, GDL, Double DQN, e3nn SH, Deja View, EGNN, SE(3)-Transformer, Point Transformer/KPConv/PTv3. |
| Evaluation | M1 evidence gates, target matching counts, valid support, headroom/recovery, paired policy comparison, replay integrity, scale/storage reporting, failure interpretation. | `.agents/work`, roadmap, theory docs, generated code docs for target-RRI scorer. |
| Discussion / Future | Hestia target-then-pose, GenNBV continuous policy, radiance-field/3DGS bridges, external simulators only if target-RRI supervision is preserved. | Hestia, GenNBV, FisherRF, Next Best Sense, Habitat, ProcTHOR, Isaac Sim Sensors. |

## Implementation Aims Sharpened

1. Stabilize M1 data/oracle evidence before scaling: offline store integrity,
   target-RRI labels, frame/CW90 contracts, candidate-label ordering,
   depth/backprojection, and Rerun evidence.
2. Treat V0 GT-OBB target input as a diagnostic/upper-bound path only; V1 uses
   actor-visible observed/predicted target descriptors matched to GT for labels.
3. Build a calibrated one-step target scorer as the myopic baseline.
4. Generate standalone `rollouts.zarr` traces with selected-action transitions,
   successor candidate regeneration, masks, invalid reasons, and lineage.
5. Train/evaluate finite-candidate `Q_H` only after replay rows and target
   returns are trustworthy; use matched-budget oracle rescoring for claims.
6. Keep continuous policies, generic Gymnasium/SB3, and external simulator work
   as bridge/future scope unless mesh/oracle target-RRI supervision is preserved.

## Literature Review Spine

| Rank | Category | Core sources | Thesis adoption |
| --- | --- | --- | --- |
| 5 | Core substrate/objective/model | EFM3D, Project Aria, VIN-NBV, Set Transformer | Actor-visible egocentric substrate; oracle target-RRI; finite-candidate set attention. |
| 4 | Strong thesis controls/ablations | Hestia, Instance-NBV, Double DQN, Gumbel-Top-k, FisherRF, QCNet, GDL, Deep Sets, SCONE, point-transformer backbones | Hierarchy bridge, object-centric utility pressure, overestimation control, branch sampling, geometry/set inductive biases. |
| 3 | Useful bridges | GenNBV, PB-NBV, Dynamic 3DGS NBV, Trajectory Transformer, IQL/CQL, Decision Transformer, e3nn SH, MACARONS, MinkowskiEngine, KPConv, Déjà View | Future continuous policy, shortlist/proxy baselines, radiance-field diagnostics, offline/sequence bridges, representation ablations. |
| 2 | Background/future only | SceneScript, DQN, BCQ, Deep Energy-Based Policies, ProcTHOR, Habitat, Isaac Sim Sensors | Lineage and future simulator/semantic/modality scope; not core evidence. |
| 1 | Peripheral downstream utility | FOV-HPE | Mention only as downstream-task viewpoint background. |

## Geometric Invariance And Architecture Critique

### Design Target

The planned `Q_H` model should be framed as a value model over an unordered,
masked, finite sample of candidate poses and target/support descriptors, not as
a sequence model over whatever row order the data loader emits. Locally, each
sample approximates a target-conditioned utility field over `SE(3)`:

```text
F_{s,e}(q) = RRI_e(s, q)
```

where the candidate table is a sampled finite set from that field. The model
therefore needs set equivariance for per-candidate scores and should use
relative geometric coordinates for interactions. Absolute scene/world pose can
remain available only when it carries a physical signal, such as gravity,
floor/up direction, calibrated rig orientation, or dataset-specific support
priors.

### Symmetry Contract

| Requirement | Desired behavior | Practical consequence |
| --- | --- | --- |
| Candidate-row permutation equivariance | Per-candidate scores must satisfy `f(P X)=P f(X)` for any row permutation `P`. | All candidate encoders, masks, losses, and argmax/value reductions need row-shuffle tests. |
| Set-level invariance | Scene/candidate-set summaries must be invariant to row order. | DeepSets pooling is the minimum control; attention pooling must be mask-safe. |
| Local-frame / gauge discipline | A global coordinate frame change should not change scalar scores if the same physical scene/action relation is represented. | Encode target-to-candidate, current-to-candidate, and candidate-to-candidate transforms in target/current/query-local frames; avoid raw absolute pose as the main feature. |
| Gravity-aware partial symmetry | Full `SO(3)` invariance is not always correct because Project Aria/ASE scenes have gravity, floor/up structure, and camera/frustum conventions. | Preserve explicit up/gravity, camera optical-axis, and frustum features as actor-visible physical signals; do not erase them with an overstrong invariant model. |
| Directional visibility on `S^2` | Accumulated observation directions should transform consistently with target/camera frames. | Start with second-moment or low-order spherical summaries; use e3nn spherical harmonics only as an ablation if simple summaries bottleneck. |
| Validity-mask equivariance | Invalid/padded rows transform with candidate rows and cannot influence valid outputs except through explicit valid-count features. | Hard-mask attention, losses, bootstrap targets, argmax, and reductions before any model comparison. |
| Actor/oracle separation | Privileged target meshes/GT boxes are not a symmetry; they are a causal/evidence boundary. | Keep GT only for labels, matching, evaluation, and privileged-critic experiments, never as V1 actor-visible input. |

This means "respect geometric isomorphisms" should be interpreted as
representation discipline, not a blanket commitment to exact `SE(3)`
equivariance. The thesis needs to state which transformations preserve the
task semantics and which transformations change real observables.

### Architecture Ladder Revision

1. **A0 calibrated independent scorer.** Keep the one-step target-RRI scorer as
   the calibration anchor. It proves the labels, target matching, and candidate
   features work before interaction effects are introduced.
2. **A1 DeepSets context.** Add a pooled valid-candidate context
   `g=rho(sum phi(x_j))` and score `hat r_i=f(x_i,g)`. This tests whether
   global candidate-population context helps while preserving set symmetry.
3. **A2 masked Set Transformer.** Add candidate-candidate self-attention only
   after A1. Use hard masks and row-shuffle tests; consider induced attention
   only if valid candidate count makes quadratic attention a real bottleneck.
4. **A3 QCNet-style query-centric RPE.** For candidate `i`, encode candidate
   `j`, target `e`, and history/support descriptors in `i`'s or the target's
   local frame. Use relative spatial/pose/budget embeddings as attention bias
   or key/value augmentation. Do not import QCNet's trajectory decoder,
   motion-forecasting losses, or streaming claims into the thesis core.
5. **A4 directional/support bias.** Add Fisher/SCONE-style overlap, target
   support, frustum overlap, and directional novelty as separate logged
   channels. Treat these as attention biases or diagnostics, not replacements
   for target-RRI supervision.
6. **A5 residual dueling `Q_H`.** Predict finite-horizon value only after
   rollout lineage, successor candidate regeneration, masks, and endpoint gains
   are trustworthy. Keep the dueling/residual head tied to the calibrated
   one-step signal so set context cannot silently corrupt absolute RRI
   calibration.
7. **A6 recurrent set refinement inspired by Deja View.** A tied candidate-token
   block with variable iteration count is a plausible later ablation for
   compute/quality tradeoff. It should not be the first `Q_H` architecture:
   Deja View's evidence is multi-view reconstruction with trained step-range
   limits, final-step supervision, and no guarantee of extrapolation outside the
   trained loop count.
8. **A7 exact equivariance / point backbones.** EGNN, SE(3)-Transformer,
   Point Transformer, PTv3, KPConv, MinkowskiEngine, or feature-bank point
   backbones should be ablations after simpler relative encodings fail. They
   are useful for diagnosing geometry bottlenecks, but they raise cost and can
   obscure whether target matching/support/headroom is the real blocker.

### Critique Of Current Encoding Plan

- **R6D + LFF absolute pose features are too easy to misuse.** They should be
  primary only for relative rotations/transforms, optical-axis/up features, and
  target/current local-frame descriptors. Raw world pose should be a controlled
  ablation or an explicitly justified physical prior.
- **Candidate-set interaction must not destroy one-step calibration.** For
  myopic target-RRI, use an independent absolute head plus a zero-mean set
  residual:

  ```text
  r_abs_i = f_abs(x_i)
  delta_i = f_set(X, mask)_i
  hat r_i = r_abs_i + lambda * (delta_i - mean_valid(delta))
  ```

  `Q_H` can allow stronger interaction because the value of one action depends
  on successor candidates, but it still needs mask and row-shuffle invariance.
- **Pairwise geometric smoothness is local and conditional.** The Lie-algebra
  displacement `xi_ij = log(q_i^{-1} q_j)` is useful only inside stable
  visibility/support regimes. Do not smooth across occlusion, invalidity,
  frustum, target-support, or target-match boundaries.
- **Directional memory is not a bag of rotations.** Observation history should
  be represented as target-local directions on `S^2` with support/novelty
  weights. A second-moment tensor is the minimum thesis-safe representation;
  spherical harmonics are an ablation when angular detail matters.
- **Deja View is a refinement analogy, not direct supervision.** Its useful
  adoption is the idea of a weight-tied iterative refinement block and
  inference-time compute knob. The thesis should not claim Deja View-style
  recurrence will extrapolate, converge to a fixed point, or solve NBV planning
  without a fixed-depth set-attention baseline.
- **Point/geometric backbones need a bottleneck test.** Before importing
  Point Transformer/PTv3/KPConv/Minkowski-style geometry modules, show that
  simpler target-local geometry, support vectors, and directional memory are
  insufficient. Otherwise architecture complexity may hide data/label issues.

### Proposed Thesis Section

Dedicate a method/background bridge section titled
**Geometric Symmetries And Candidate-Set Architecture**. Suggested structure:

1. Candidate views as an unordered finite sample of a target-conditioned utility
   field over `SE(3)`.
2. Permutation equivariance/invariance for candidate rows and set summaries.
3. Local-frame/gauge discipline: why target/current/query-relative transforms
   are preferable to absolute world pose.
4. Partial physical symmetries: gravity, camera/frustum conventions, and
   target support are real signals, so full `SO(3)` invariance is not always
   correct.
5. Directional visibility memory on `S^2` and its relation to support overlap,
   Fisher/SCONE-style redundancy, and target novelty.
6. Architecture ladder and ablation plan from independent scorer to DeepSets,
   masked Set Transformer, QCNet-style RPE, residual dueling `Q_H`, and optional
   recurrent/equivariant/point-backbone ablations.
7. Required robustness tests: row shuffle, duplicate row, mask isolation,
   valid-count calibration, candidate-family shift, and local-frame ablation.

### Evidence Anchors

| Source | Evidence used | Adoption for ARIA-NBV |
| --- | --- | --- |
| `docs/contents/theory/candidate_view_dependence.qmd` | Defines candidate views as a finite candidate set, requires `f(P X)=P f(X)`, recommends staged A0-A5 set-interaction ladder and row-shuffle/mask tests. | Treat this as the repo-local architecture contract for candidate-set models. |
| Deep Sets | Characterizes set functions via pooled element embeddings and gives permutation-equivariant layer conditions. | Use DeepSets as the minimum candidate-context control and as a row-order sanity baseline. |
| Set Transformer | Uses self-attention for pairwise/high-order interactions over sets; ISAB trades quadratic attention for inducing-point attention. | Use masked self-attention for candidate interactions; reserve ISAB for large candidate counts. |
| QCNet/QCNeXt | Query-centric local coordinate systems yield permutation equivariance over elements and roto-translation/time invariance through relative positional embeddings. | Adopt query-centric relative pose embeddings; reject trajectory decoder/loss/streaming claims as out of thesis core. |
| Geometric Deep Learning | Symmetry and gauge framing clarifies which coordinate choices are representational artifacts versus physical signals. | Justify local-frame encodings and explicit symmetry tests instead of raw world-pose shortcuts. |
| SE(3)-Transformer | SE(3)-equivariant attention gives robustness/weight sharing, but gravity-aligned data may benefit from symmetry-breaking up-direction features. | Use exact equivariant attention as an ablation, not the minimum path. Preserve gravity/up when physically meaningful. |
| EGNN | Uses relative squared distances and radial coordinate updates for E(n)-equivariant message passing without spherical harmonics. | Good lightweight exact-equivariance ablation if relative scalar/vector features appear insufficient. |
| Point Transformer / PTv3 / KPConv | Point models exploit local neighborhoods, relative position encodings, serialization/scalable attention, or continuous kernels for irregular 3D data. | Useful for feature-bank/backbone ablations after proving simple target-local descriptors bottleneck. |
| Deja View | Weight-tied recurrent transformer block gives a variable compute knob for iterative multi-view reconstruction but is limited to trained step ranges. | Future recurrent candidate-token refinement ablation; not first architecture and no extrapolation/convergence claim. |
| e3nn spherical harmonics | Provides spherical harmonic basis functions for rotation-aware angular features. | Optional `S^2` directional-memory ablation against second-moment summaries. |

## Iteration 2: Candidate-Query Architecture Refinement

The next architecture decision should be framed as a set/value-model design
question, not as a search for the strongest geometric neural network. The
literature supports a conservative split:

- QCNet/QCNeXt justify query-centric relative encodings and attention over
  unordered local elements. They do not justify importing trajectory-proposal
  decoders, multi-agent motion forecasting losses, social-future consistency
  objectives, or streaming claims into the thesis core.
- Deep Sets and Set Transformer justify the candidate table as a set. Per-row
  `Q_H` scores are transductive/equivariant outputs, so invariant pooling is
  context only; it cannot replace the row-preserving score head.
- Deja View justifies weight-tied iterative refinement as a later compute/quality
  ablation, but its evidence is multi-view reconstruction at very large scale,
  with bounded trained step counts and explicit failure beyond that range.
- Point Transformer, PTv3, and KPConv are geometry-feature-backbone options for
  semidense or point-attached support fields. They are not the right default
  model for the finite candidate table unless simple target-local descriptors
  are proven to be the bottleneck.

### Refined Design Gates

| Gate | Adopt | Reject for thesis core | Evidence basis |
| --- | --- | --- | --- |
| QCNet-style RPE | Encode target-to-candidate, current-to-candidate, candidate-to-candidate, horizon, remaining budget, and validity relations in query/target/current local frames. Use relative embeddings as attention bias or key/value augmentation. | Joint trajectory decoder, scene-level likelihood, DETR-style proposal matching, social-future consistency losses, and road-agent streaming claims. | QCNet uses local spacetime systems, query-relative key/value embeddings, and set permutation equivariance; its decoder and benchmark target are motion forecasting, not NBV value estimation. |
| DeepSets floor | Keep an independent candidate scorer plus invariant pooled valid-candidate context. Add row-shuffle tests and valid-count calibration. | Treating a pooled set embedding as the only scorer for per-candidate `Q_H`. | Deep Sets separates invariant set summaries from equivariant per-instance outputs. |
| Set Transformer default | Use 1-2 masked SAB blocks once the independent scorer and DeepSets context are calibrated. Use ISAB only when valid candidate count or latency makes quadratic attention a measured bottleneck. | Unmasked attention over padded/invalid rows; PMA as the primary per-candidate score path. | Set Transformer SAB/ISAB are permutation equivariant; PMA is an invariant/pooled decoder useful for summaries, clusters, or critics. |
| Deja View recurrence | Later tied-block candidate-token refinement with `K` sampled inside a trained range; log state-norm drift, logit drift, and monotone value calibration by step. | Any claim of fixed-point convergence, arbitrary extrapolation to larger `K`, or direct transfer from 3D reconstruction quality to NBV value learning. | Deja View reports directional refinement inside the trained range and collapse beyond excessive iteration counts. |
| Point backbones | Use Point Transformer/PTv3/KPConv only for semidense geometry/support feature banks when feature extraction, not candidate interaction, is the bottleneck. | Replacing the candidate-set value model with a point-cloud backbone before target matching, masks, and rollout headroom are proven. | Point Transformer relies on local relative position/vector attention; PTv3 trades exact permutation handling for scalable serialized point processing; KPConv uses radius neighborhoods and continuous kernels for irregular point clouds. |

### Updated Ablation Ladder

| Stage | Model | Purpose | Stop / escalation criterion |
| --- | --- | --- | --- |
| B0 | Calibrated independent one-step target scorer | Prove labels, masks, target descriptors, and candidate features. | Do not train `Q_H` if B0 is unstable or target-invalid rows leak as low-RRI rows. |
| B1 | Independent scorer plus DeepSets context | Measure whether candidate-population context helps without attention complexity. | Escalate only if context improves paired validation under row-shuffle checks. |
| B2 | Masked SAB Set Transformer | Test pairwise/higher-order candidate interactions. | Escalate only with mask-isolation, duplicate-row, and valid-count tests passing. |
| B3 | SAB plus QCNet-style local RPE | Test whether query-relative geometry improves candidate interaction. | Keep raw world pose as an ablation, not the default, unless it captures an explicit physical prior. |
| B4 | Residual/dueling `Q_H` with Double-Q backup | Learn finite-horizon value while anchoring one-step calibration and reducing overestimation. | Do not interpret if rollout lineage, selected transitions, successor candidates, and masks are not trustworthy. |
| B5 | Weight-tied recurrent candidate refinement | Test a compute/quality knob after fixed-depth models are stable. | Keep `K` inside the trained range and report drift/failure beyond it. |
| B6 | Point/geometry feature backbone | Test whether semidense or point-attached support features are the bottleneck. | Use only after simple target-local descriptors and directional summaries fail. |
| B7 | Exact EGNN/SE(3)-Transformer/e3nn ablation | Test whether exact equivariance improves data efficiency or robustness. | Preserve gravity/up/frustum signals; full equivariance is not automatically semantically correct. |

### Critique Of The Current Encoding Plan

- **Candidate rows are not points in a point cloud.** They are sampled actions
  with validity reasons, target descriptors, rollout lineage, and future
  successor distributions. A Point Transformer/KPConv-style backbone can
  extract geometry/support features, but the action scorer still needs a
  row-equivariant candidate-set head.
- **RPE should be local and typed.** Encode different relations separately:
  candidate-current, candidate-target, candidate-candidate, candidate-support,
  horizon-step, remaining-budget, and validity/mask relation. A single
  concatenated absolute pose vector hides which symmetry is being claimed.
- **PMA belongs in diagnostics or privileged critics first.** Pooling by
  attention is useful for set-level summaries, replay health, support coverage,
  or a privileged critic, but per-action `Q_H` needs row-preserving outputs.
- **Recurrence needs a value-specific failure monitor.** If adopting a Deja
  View-style tied block, decode scores at every iteration and track rank
  stability, calibration, state norm, and logit drift. The thesis should
  explicitly reject any "more iterations always help" assumption.
- **Architecture cannot repair missing headroom.** If oracle rollouts show
  near-zero non-myopic headroom, escalating from DeepSets to Set Transformer,
  QCNet-style RPE, recurrence, or point backbones is the wrong interpretation.
  The correct result is a negative planning/headroom finding or a narrower
  validated subset.

### Thesis Section Additions

The planned geometric-invariance section should include one compact table that
separates representation level from model level:

| Level | Object | Required symmetry | Candidate implementation |
| --- | --- | --- | --- |
| Candidate table | Finite sampled action set | Row permutation equivariance | Independent scorer, DeepSets context, masked SAB |
| Geometry relation | Pose/target/support relation | Target/current/query-local gauge discipline | Typed relative transforms and QCNet-style RPE |
| Directional history | Target-local observation directions | Rotation-aware but gravity/frustum-aware | Second moments first; e3nn SH ablation |
| Semidense support | Local 3D support field | Local spatial locality, density robustness | Point Transformer/PTv3/KPConv feature-bank ablations |
| Rollout value | Selected-action finite-horizon return | Mask/lineage correctness before model complexity | Residual dueling `Q_H`, Double-Q backup, matched-budget evaluation |

### Immediate Follow-Up Reading

Useful referenced-paper leads that are not yet first-class local archive entries:

- From QCNet/QCNeXt: HiVT for hierarchical symmetric scene encoding, Perceiver
  for latent bottleneck attention, Scene Transformer and Wayformer for simple
  attention baselines and scene-level forecasting interfaces. These should be
  mined only for encoder/bottleneck ideas, not for motion-forecasting claims.
- From Deja View: Universal Transformer and ALBERT for parameter sharing,
  RAFT for task-space iterative refinement, RAPTOR for looped ViT block
  distillation, and DUSt3R/VGGT/MASt3R for multi-view geometry refinement.
  These should be mined for recurrence diagnostics and compute/quality tradeoff
  language, not for direct NBV value supervision.

## Iteration 3: Referenced-Paper Design Transfers

The referenced papers sharpen the same conclusion: use them as architecture
controls and diagnostic vocabulary, not as thesis-core objective changes.

| Referenced source | Transfer worth adopting | Boundary / rejection |
| --- | --- | --- |
| HiVT | Decompose modeling into local context extraction and global interaction. For ARIA-NBV, this maps to local target/candidate/support descriptors followed by a global candidate-set interaction block. | Do not import road-agent trajectory assumptions, lane graph semantics, or motion-forecasting metrics. |
| Perceiver | Use asymmetric cross-attention into a small latent bottleneck when semidense support, point-attached EVL features, or multimodal context becomes too large for candidate-candidate attention. Candidate queries can then attend to this support memory. | Do not let a latent bottleneck erase per-candidate row equivariance; the final `Q_H` output path remains row-preserving. |
| Wayformer | Treat simple homogeneous attention/fusion baselines as controls: early fusion of typed candidate/support descriptors, late fusion of modality-specific summaries, and hierarchical fusion of local/global context. | Do not overfit the architecture to autonomous-driving modality schemas or scene-agent forecasting outputs. |
| Universal Transformer | If recurrence is tested, compare fixed-depth blocks against a tied recurrent block and optionally a halting/ponder-cost diagnostic. | Do not assume algorithmic extrapolation from recurrence alone; ARIA-NBV needs value-calibration and rollout-headroom evidence. |
| RAFT | The useful pattern is fixed evidence plus iterative updates: a candidate/query state can repeatedly consult a stable support/correlation memory. | RAFT's output-space flow refinement and all-pairs pixel correlation do not directly transfer to finite-candidate NBV unless there is a concrete support-memory tensor. |
| Raptor / block-recurrent ViT evidence | Use recurrence as parameter sharing or model compression after a strong fixed-depth baseline exists. | Do not start with recurrence before knowing what fixed-depth candidate-set model it should approximate or improve. |
| DUSt3R / VGGT / MASt3R family | These provide vocabulary for multi-view geometry features, pointmaps, camera/depth heads, and representation transfer. They can seed future actor-visible feature-bank ablations or external representation baselines. | They should not replace ASE mesh/oracle target-RRI labels or turn the thesis into general feed-forward 3D reconstruction. |

### Latent Bottleneck Design Option

Perceiver and Wayformer make one concrete addition to the ARIA architecture
ladder: a latent support-memory path can sit beside the candidate-set path.

```text
semidense_support_tokens -> cross-attend -> L support latents
candidate_tokens + typed RPE -> masked candidate SAB
candidate_tokens -> cross-attend(L) -> support-conditioned candidate tokens
row-preserving head -> Q_H(candidate_i)
```

This is preferable to feeding all semidense points directly into candidate SABs.
It keeps candidate-candidate attention small, makes the support-context budget
explicit, and leaves row-shuffle tests meaningful. The required tests are:

- shuffle candidate rows while holding support tokens fixed;
- shuffle support tokens while holding candidate rows fixed;
- vary the number of support latents `L`;
- ablate support latents against the simpler DeepSets/SAB candidate-only model;
- verify that invalid candidates remain hard-masked after cross-attention.

### Fusion Ablation Plan

Wayformer suggests a clean fusion vocabulary for ARIA-NBV:

| Fusion | ARIA version | Why it matters |
| --- | --- | --- |
| Early fusion | Concatenate typed candidate pose, target descriptors, support summaries, validity features, and directional memory before the first row MLP. | Simple baseline; exposes whether model complexity is premature. |
| Late fusion | Encode geometry, target descriptors, support, and rollout context separately, then combine before the score head. | Tests whether modality-specific preprocessing improves calibration. |
| Hierarchical fusion | Local candidate/target/support encoder first; global candidate-set interaction second; optional support-latent cross-attention third. | Matches the local/global split from HiVT/QCNet without importing motion-forecasting objectives. |

The thesis should require early fusion and hierarchical fusion as the main
comparison. Late fusion is useful only if the modality-specific encoders are
small and interpretable.

### Recurrence Decision Rule

Universal Transformer, RAFT, Raptor, and Deja View jointly support a narrow
recurrence rule:

1. Start with a fixed-depth model whose failures are measured.
2. Add a tied recurrent block only if the fixed-depth model benefits from depth
   or repeated candidate/support reasoning.
3. Train and evaluate only inside a declared iteration range.
4. Decode `Q_H` at each iteration and report value calibration, action-rank
   stability, state-norm drift, logit drift, and wall-clock cost.
5. Reject the recurrence if more steps improve training metrics while degrading
   row-shuffle robustness, mask isolation, calibration, or matched-budget policy
   comparison.

This gives the thesis a defensible recurrence ablation without letting "iterative
reasoning" become an unbounded architecture story.

### Representation Transfer Boundary

DUSt3R/VGGT/MASt3R-style geometry models are attractive because they expose
camera, depth, pointmap, and correspondence-like outputs. In ARIA-NBV, however,
ASE already supplies a privileged mesh/oracle loop for label generation. The
right thesis boundary is:

- use these papers to motivate actor-visible geometry representation baselines;
- use their output types as possible support-feature channels;
- keep GT meshes, OBBs, and target-RRI labels as evaluation/oracle surfaces;
- do not claim feed-forward reconstruction replaces counterfactual rollout
  supervision;
- do not compare learned geometry-backbone quality to `Q_H` planning quality
  without a paired policy evaluation under equal target/candidate budget.

## Iteration 4: Offline Value-Learning And Branching Critique

The value-learning literature reinforces that `Q_H` is a finite-action offline
value estimator over logged/generated candidate sets. It should not be framed as
a generic online RL agent or as a continuous-action offline RL benchmark.

### Value-Target Design Rules

| Source family | Useful idea | ARIA-NBV implication |
| --- | --- | --- |
| DQN | Experience replay breaks temporal correlations, reuses data efficiently, and computes all discrete action values in one forward pass. Held-out predicted `Q` on fixed states is a useful stability diagnostic but not the policy metric. | `rollouts.zarr` should expose replay rows, fixed validation roots, all-candidate score vectors, TD errors, and policy rollouts under equal budget. |
| Double DQN | Max over noisy action estimates causes overoptimism; decoupling action selection from action evaluation reduces overestimation and improves stability. | `Q_H` backups should use a Double-Q or target-network split for next-candidate argmax/evaluation. Report overestimation by comparing predicted best-candidate value to oracle-rescored rollout return. |
| CQL | Offline value learning needs pessimism/conservatism when policy actions drift outside data support; lower-bound diagnostics and support counts matter. | Penalize or mask unsupported candidate/target/scene regions rather than trusting extrapolated high `Q_H`. Report coverage by scene, target, candidate family, horizon, and invalid reason. |
| IQL | In-sample learning avoids querying values for unseen actions by learning from dataset actions and extracting policies via advantage-weighted behavior cloning. | Keep the first `Q_H` training target in-sample over generated finite candidate sets. Online discrete `Q_H` can be a later bridge once offline evidence is stable. |
| Decision Transformer | Return-conditioned sequence modeling can handle delayed/sparse rewards and exploit trajectory context. | Useful as a future sequence baseline for rollout traces, but not the first thesis model because target-conditioned finite-candidate values already give a more direct oracle-supervised target. |
| Trajectory Transformer | Sequence models plus beam search can combine generative trajectory modeling and Q-guided planning, but planning can be slow and resource-heavy. | Treat beam/sequence planning as a bridge only after fixed-horizon candidate rollouts are trustworthy; do not replace oracle rollout traces with a learned dynamics sequence model. |
| Gumbel-Top-k | Samples unique branches without replacement and connects stochastic sampling with beam search. | Use for stochastic rollout branch diversity only after deterministic selected-transition traces, masks, and headroom checks pass. |

### `Q_H` Training Contract

The minimal training row for finite-candidate `Q_H` should contain:

- root state id, target id, target-valid/match status, and actor-visible target
  descriptor id;
- candidate row id, `position_id`, candidate-family id, validity mask, invalid
  reason, and actor-visible candidate features;
- selected-action transition lineage: selected candidate id, successor root id,
  successor candidate-set id, terminal/timeout flag, and horizon index;
- root-normalized immediate reward and cumulative endpoint gain;
- bootstrap mask and support/coverage counters for candidate family, target
  family, scene, and horizon;
- oracle-rescored return for validation rows, separate from model bootstrap
  targets.

This contract should precede any architecture comparison. Without it, model
choice cannot distinguish actual value-learning improvement from invalid-row
leakage, target mismatch, candidate-family shortcuts, or unsupported
extrapolation.

### Backup And Evaluation Recommendations

| Risk | Recommended control | Thesis reporting |
| --- | --- | --- |
| Max-backup overestimation | Double-Q or target-network argmax/evaluation split. | Plot predicted best-candidate value vs oracle-rescored realized return. |
| Offline support extrapolation | Hard masks for invalid rows; conservative penalty or abstention for low-support candidate/target regions. | Report coverage tables before value metrics. |
| Headroom absence | Oracle greedy vs oracle rollout headroom before training learned `Q_H`. | If headroom is near zero, report a negative planning result. |
| Candidate-family shortcut | Train/evaluate splits across candidate mixture family, `position_id`, scene, and target. | Report paired policy comparison under matched candidate budgets. |
| Sequence-model overreach | Keep DT/Trajectory Transformer as future baselines only after row-wise `Q_H` is stable. | Do not claim sequence planning superiority without compute-normalized policy evaluation. |
| Stochastic branch variance | Gumbel-Top-k/no-replacement branch sampling with fixed seeds and logged branch probabilities. | Report diversity, duplicate rate, and oracle-return variance by branch budget. |

### Architecture Consequences

- The output head should produce all valid candidate values in one forward pass,
  DQN-style, but with set-equivariant row outputs rather than a fixed action
  index head.
- A residual/dueling head remains a good fit: preserve a calibrated immediate
  target-RRI scorer and learn finite-horizon residual value only where rollout
  evidence supports it.
- Conservative penalties should be feature/support aware. Penalizing every
  high value uniformly can hide real headroom; unsupported scene/target/candidate
  regions should be flagged separately from valid but low-return actions.
- Sequence models are a discussion/future bridge unless there is a clear failure
  of finite-action value estimation despite adequate rollout support.
- Gumbel-Top-k belongs in rollout data generation and branch evaluation, not in
  the first supervised value head.

## Iteration 5: NBV Objective, Support, And Hierarchy Critique

The NBV-specific literature sharpens the objective boundary. ARIA-NBV should
optimize target-conditioned reconstruction improvement under a fixed
candidate/rollout protocol. Scene coverage, uncertainty, object masks, and
hierarchical navigation are valuable support signals and ablations, but they
should not silently replace target-RRI as the thesis objective.

### Objective Boundary

| Source family | Keep | Do not import |
| --- | --- | --- |
| VIN-NBV | Predicted reconstruction-quality criteria and the lineage for replacing pure coverage with learned view utility. | Scene coverage as the primary target objective. |
| Instance-NBV | Object-centric target selection, instance-level view utility, and mask-quality failure reporting. | Unverified pseudo-semantic masks as actor-visible thesis truth. |
| SCONE / MACARONS | Coverage/support/history features, occlusion-aware memory, local neighborhoods, and gain distributions as diagnostics or auxiliary channels. | Coverage gain as the scalar `Q_H` reward when target-RRI is the thesis objective. |
| FisherRF / Next Best Sense | Fisher/depth uncertainty as support, candidate-prior, and failure-explanation channels. | Radiance-field uncertainty as a replacement for target-RRI supervision. |
| Hestia | Target-then-pose hierarchy, directional/face coverage, and warnings about spurious future-reward credit assignment. | Continuous 5-DoF RL or drone/object-centric coverage reward as the core thesis model. |
| PB-NBV | The representation/candidate-generation/view-selection triad and compute-aware reporting. | Ellipsoid projection as the core substrate when ARIA already has ASE mesh/oracle rollouts. |

### Support Vs Invalidity

Low immediate target visibility should not automatically become invalidity. It
can be a setup action that enables later target gain, especially in non-myopic
rollouts. The protocol should separate hard invalidity from weak support:

- hard invalid: collision, no depth, out-of-bounds pose, no oracle render, no
  valid target match, or a target-invalid/matching-invalid state;
- soft diagnostic support: low projected target area, low immediate target
  visibility, weak overlap/support density, high ambiguity, high uncertainty, or
  poor coverage history;
- reporting: invalid fraction, invalid-reason distribution, target-visible
  fraction, support quantiles, ambiguity rates, and setup-action recovery.

This distinction protects the learned value target from treating every
occluded-yet-recoverable state as a negative label.

### Representation Additions

| Addition | Literature support | ARIA-NBV use |
| --- | --- | --- |
| Target-local `S^2` history | SCONE, MACARONS, and Hestia directional/face coverage. | Low-order moments, spherical-harmonic bins, or coarse directional histograms around the target. |
| Occlusion-aware selected-view history | MACARONS memory and NBV coverage history. | Mark only selected views where the target or local support could plausibly be visible. |
| Fisher/depth uncertainty channel | FisherRF and Next Best Sense. | Auxiliary support/uncertainty input and failure explanation, not the target reward. |
| Object/semantic mask quality audit | Instance-NBV. | Report OBS-SEL ambiguity, unmatched targets, unsupported targets, and descriptor quality. |
| Distance/angle density correction | SCONE/MACARONS view scoring and local-neighborhood methods. | Candidate features should expose frustum, incidence angle, target distance, overlap, and support-density scalars. |

These channels fit the current candidate-query ladder: they can be row features,
target descriptors, support-latent inputs, or diagnostics without changing the
reward owner.

### Hierarchy And RQ6

Hestia is useful mainly as a hierarchy warning and bridge. Its target-then-pose
factorization supports a later RQ6 question: first select the target/look-at or
support region, then select the concrete candidate pose. That bridge should be
tested only after offline finite-candidate `Q_H` shows either planning headroom
or a candidate-sampling bottleneck.

RQ5 should remain the online discrete `Q_H` bridge over the existing ASE
finite-candidate loop. Continuous actor-critic, external simulators, drone
control, or semantic-global object navigation should stay out of the thesis core
unless they preserve target-RRI supervision and are introduced as explicit
future-work or RQ6 material.

### Evaluation Consequences

The evaluation should keep separate columns for target endpoint gain, cumulative
target-RRI, diagnostic scene coverage, support/uncertainty metrics, and
candidate-set headroom. Coverage/uncertainty baselines can be compared as
candidate priors or diagnostic policies, but they should not be scalarized with
target-RRI unless an ablation explicitly studies that tradeoff.

If headroom is near zero, the result may indicate a candidate distribution,
target-selection, support, or evaluation problem rather than a model failure.
The thesis should then report a validated subset or negative planning result
before adding architecture complexity.

## Iteration 6: Symmetry Contract And Equivariance Escalation

The geometric-learning sources and current theory pages point to a sharper
architecture rule: exact equivariance is not a virtue by itself. The model
should preserve the symmetries that the ARIA task actually has, quotient out
irrelevant coordinate choices with local frames, and keep physically meaningful
symmetry-breaking signals such as gravity, camera frustum, support density, and
target ambiguity.

### Symmetry Contract

| Structure | Required behavior | Recommended implementation |
| --- | --- | --- |
| Candidate-row order | Per-candidate output must be permutation equivariant: shuffling rows shuffles scores and masks in the same way. | Independent row scorer, DeepSets context, masked SAB/Set Transformer, row-shuffle tests for scores, losses, masks, and argmax. |
| Global translation | Absolute world origin should not affect `Q_H`. | Express candidate, target, current pose, and support positions in root-, current-, target-, or query-local frames. |
| Global yaw / rotation | The model should not depend on arbitrary map yaw, but it may depend on gravity/up and camera orientation. | Use relative `SE(3)`/Lie features and local-frame RPE; keep explicit up, pitch, frustum, distance, and incidence-angle scalars. |
| Full `SO(3)` / `SE(3)` | Only valid if the task truly treats all rotations as equivalent or produces geometric vectors/tensors that should rotate. | Treat SE(3)-Transformer, EGNN, e3nn, and tensor features as controlled ablations, not prerequisites. |
| Target-local `S^2` visibility | Observation history around a target should rotate with the target/camera frame, but the first output remains scalar. | Start with second-moment, directional-bin, or low-order spherical summaries; test spherical harmonics only after simple memory fails. |
| Support/scene geometry | Local support fields have density, occlusion, frustum, and resolution effects. | Use scalar support/overlap/uncertainty channels first; use Point Transformer, PTv3, KPConv, or sparse convolution only if feature extraction is the bottleneck. |
| Surface/mesh gauge | Tangent-frame features on meshes have gauge ambiguity. | Avoid mesh-gauge networks unless thesis scope shifts to mesh surface processing; rollout labels already use oracle mesh evaluation. |
| Selected-view history | Temporal order and selected-action lineage matter; it is not just an unordered set. | Store ordered selected-view history plus symmetric accumulated support summaries. Do not force sequence history through candidate-row set symmetry. |
| Actor/oracle split | No symmetry model fixes supervision leakage. | Keep actor-visible features, oracle-only labels, target matching, and `rollouts.zarr` lineage separate before architecture comparisons. |

### Escalation Rule

The default `Q_H` model should use scalar invariant features and local-frame
relative geometry before exact tensor equivariance:

1. encode target/root/query-local relative positions, distances, bearings,
   frustum overlap, incidence angle, support density, validity, and provenance;
2. run the candidate table through row-equivariant set layers;
3. add local RPE or attention bias for candidate-candidate/current/target
   relations;
4. only then test exact equivariant graph or tensor modules.

This rule is consistent with the Geometric Deep Learning distinction between
node features and spatial coordinates, the EGNN result that distance-based
relative geometry can give efficient E(n) equivariance without spherical
harmonics, and the SE(3)-Transformer warning that gravity-aligned data can lose
useful information when forced into full rotation invariance.

### Exact-Equivariance Ablation Boundaries

| Candidate module | Use when | Reject or defer when |
| --- | --- | --- |
| EGNN candidate graph | Candidate/target/history nodes form a meaningful geometric graph and relative scalar/vector features are insufficient. | The output is still scalar `Q_H` and local-frame scalar features already recover headroom. |
| SE(3)-Transformer | There is a demonstrated need for vector/tensor feature transport or better rotation robustness under controlled augmentation. | Gravity/up, camera pitch, frustum, and target-facing directions are semantically meaningful. |
| e3nn spherical harmonics | Directional visibility memory needs angular frequency detail beyond bins or second moments. | `S^2` memory is only a compact support diagnostic, or data scale cannot justify higher-order bases. |
| Point Transformer / PTv3 | Semidense actor-visible support features bottleneck target-RRI ranking or transfer. | Candidate-set interaction, target matching, masks, and rollout headroom are still unresolved. |
| KPConv | Local point neighborhoods and varying density are the bottleneck. | Radius/neighborhood engineering would distract from the finite-candidate value contract. |
| MinkowskiEngine | Sparse 3D/4D feature volumes become necessary for accumulated support memory. | The current compact EVL/semidense summaries suffice or storage/compute are the limiting factor. |
| Gauge-equivariant mesh CNNs | Thesis scope shifts to learned mesh-surface feature transport. | Meshes remain oracle-only evaluation surfaces and not actor-visible model inputs. |

### Readiness Risk Register

The local theory and work notes add four practical risks that should be stated
beside the architecture ladder:

- target-local frame consistency: every candidate feature, support feature,
  RPE, and visualization must state its frame and transform path;
- support-field leakage: eligibility gates, ranking features, GT-only matching,
  and oracle labels must remain separable;
- invalidity-mask semantics: invalid rows, target-invalid cases, and weak
  support must not collapse into one low-value class;
- rollout preflight: `rollouts.zarr` scale-up should wait for lineage,
  selected-transition, invalid-reason, support-coverage, and actor/oracle field
  checks.

### Thesis Wording Recommendation

The architecture claim should read approximately:

> The first value model is not a generic Transformer over arbitrary features. It
> is a geometry-aware row-equivariant finite-candidate scorer. It tests whether
> target-local relative pose, directional support memory, validity masks, and
> candidate-set interactions recover oracle-measured target-RRI headroom before
> heavier equivariant graph, point-backbone, or recurrent modules are introduced.

## Iteration 7: Paper-To-Experiment Matrix And Rollout Readiness

The architecture ladder should be written as a sequence of falsifiable
experiments, not a menu of models. Each paper family enters only when the
rollout store contains the fields needed to make the comparison valid.

### Ablation Matrix

| Stage | Literature support | Required rollout/data fields | Pass/fail evidence | Blocker interpretation |
| --- | --- | --- | --- | --- |
| A0 independent target scorer | VIN-NBV, CORAL/ordinal scorer controls | Actor-visible target descriptor, candidate features, validity mask, target labels, split/checkpoint lineage. | Spearman/Kendall, top-k oracle hit, selected-candidate oracle target-RRI, calibration by bin/stage. | If weak, fix target labels, feature contract, and calibration before set models. |
| A1 DeepSets context | Deep Sets | Full valid candidate table, valid-count features, row masks, candidate provenance. | Row-shuffle equivariance, valid-count sensitivity, duplicate-row robustness, calibration. | If valid-count or duplicate rows corrupt scores, set context is leaking through normalization. |
| A2 masked Set Transformer | Set Transformer | Candidate table with masks, candidate ids, row order, support features, family/provenance fields. | Mask isolation, candidate-family robustness, top-k/rank lift over A1. | If gains vanish by family, the model learned sampler shortcuts rather than utility. |
| A3 local-frame RPE | QCNet, GDL, HiVT local/global split | Current/root/target/query-local transforms, typed relation features, frame/schema hashes, pose convention checks. | Local-vs-world ablation, frame-consistency tests, row-shuffle preserved after RPE. | If world-frame features win, either there is a real physical prior or a split/frame leak. |
| A4 support/overlap bias | SCONE, MACARONS, FisherRF, Next Best Sense | Target support, overlap, frustum, uncertainty, directional history, candidate-family fields. | Support quantiles, support-vs-RRI correlations, flat-reward checks, diagnostic coverage. | If support predicts all gains, report a support/prior result before claiming planning. |
| A5 residual/dueling `Q_H` | DQN, Double DQN, CQL/IQL controls | Selected action, successor state, successor candidate table, horizon, root-normalized reward, return/bootstrapping masks, oracle-rescored validation returns. | Oracle-lookahead headroom, recovered headroom fraction, learned-action oracle re-evaluation, overestimation plot. | If no headroom, report a negative planning result for the evaluated target/candidate distribution. |
| A6 stochastic branch support | Gumbel-Top-k, offline support constraints | Branch seed, branch probability, sampled selected chain, duplicate rate, stochastic replay provenance. | Unique-chain diversity, effective sample size, return variance by branch budget. | If diversity is low, data generation is the bottleneck, not the value head. |
| A7 exact equivariance / point / recurrence | EGNN, SE(3)-Transformer, e3nn, Point Transformer, KPConv, MinkowskiEngine, Deja View | Geometry graph/support tokens, directional memory order, recurrence logs, runtime/latency, matched training budget. | Robustness under controlled transforms, matched-budget policy gain, runtime/storage cost. | If A0-A5 are unresolved, this stage is architecture noise. |

### `rollouts.zarr` Minimum Contract For Learning

Before any learned `Q_H` result is interpreted, the store should expose:

- identity and split: scene, snippet, target, step, horizon, rollout policy,
  scene-level split hash, store schema, command/config hash, and seed lineage;
- actor input references: `s_cf0`, actor-visible target descriptor, selected
  history, budget, candidate features, feature-schema version, and no
  GT-only actor fields;
- candidate table: stable row id, candidate id, `position_id`, `strategy_id`,
  `mixture_id`, sampler probability, pose/action, validity mask,
  invalid-reason bitset, primary invalid reason, support/visibility diagnostics,
  and row-order provenance;
- selected transition: selected candidate id, parent state id, successor state
  id, successor candidate-table id, selected/parent depth references, terminal
  flag, and timeout flag;
- labels: root-normalized target gain, cumulative return or bootstrap target,
  state-relative target-RRI diagnostic, scene-RRI diagnostic, GT-match metadata,
  oracle provenance, and oracle-rescored validation return.

The recurring local audit warning about `position_id` is important: if the
candidate generator emits a provenance axis that is not persisted, later
candidate-family or position-family claims become unverifiable.

### Production Preflight Gate

Architecture work should wait for a machine-readable preflight report that
fails broad generation on:

- unsupported or stale schema;
- missing selected-transition lineage or successor candidate tables;
- missing `position_id` / strategy / mixture / probability provenance;
- hard diagnostic invalidity not reflected in invalidity bits;
- too many low-valid roots or candidate-family collapse;
- flat reward or near-zero headroom without target/support explanation;
- missing stochastic replay provenance for stochastic traces;
- scene split leakage or missing split manifest hash;
- excessive file/chunk counts for factual candidate arrays.

This turns the rollout store into an experimental substrate rather than a
post-hoc artifact dump. It also prevents the common failure mode where a larger
model is used to explain a result that is actually caused by stale schema,
invalid-row leakage, family collapse, or absent successor support.

### Thesis Integration

The thesis method should describe the architecture ladder and the rollout-data
contract in the same section. The evaluation chapter should report the store
preflight before any model metric table. A compact ordering is:

1. store/preflight validity;
2. target and candidate support coverage;
3. one-step target scorer calibration;
4. oracle lookahead headroom;
5. learned `Q_H` recovery under oracle re-evaluation;
6. optional architecture ablations under matched data and compute.

## Iteration 8: Candidate Sampler Realism And Target-Selection Sensitivity

The value architecture can only answer the right question when the candidate
distribution is named, stratified, and reported. `Q_H` headroom is conditional
on the candidate profile: a free-shell policy, a local egocentric walking prior,
and a target-bearing local prior are different experimental regimes, not
interchangeable samples from one abstract action space.

### Candidate Distribution Claim Boundary

| Source family | Adopt for ARIA-NBV | Do not import as thesis-core truth |
| --- | --- | --- |
| Hestia | Target-then-pose factorization, directional observability, and the warning that large future returns can make bad current views look useful. | Drone-style 5-DoF continuous action search, coverage reward, or close-greedy discount as the fixed ARIA objective. |
| GenNBV | Diverse training conditions, free/unknown/occupied support signals, and action-history conditioning as optional state features. | Free-space PPO/controller framing, semantic-global planning, or coverage ratio as the target-RRI objective. |
| PB-NBV | Cheap projection/frontier prefilters, region partitioning, and compute-aware candidate-shortlist ideas. | Ellipsoid/frontier quality as a replacement for target-specific RRI and GT-evaluated endpoint gain. |
| Instance-NBV | Object-centric target focus, object-mask quality checks, and confidence/support diagnostics. | Unverified segmentation masks or 3DGS-specific information gain as actor-visible target truth. |
| ARIA theory/work notes | Local, forward-biased, target-aware candidate mixtures with explicit `position_id`, `strategy_id`, `mixture_id`, and sampler probability. | Silently mixing free-shell upper bounds into the same claims as realistic V1 local-motion candidates. |

This boundary keeps the thesis claim concrete: the primary V1 generator is a
local egocentric motion prior over finite candidates; free shells remain upper
bounds or diagnostics.

### Required Profile Comparison

Every headroom or `Q_H` result should state the candidate profile it used:

| Profile | Role | Minimum interpretation |
| --- | --- | --- |
| `D0` current/smoke | Development and regression smoke. | Useful for plumbing only; do not publish as the main V1 performance claim unless it matches the locked profile. |
| `D1` `v1_realistic_3family` | Main thesis candidate distribution. | Local egocentric motion limits, target-bearing actions, and lateral bypass actions define the realistic ARIA setting. |
| `D2` `v1_relaxed_3family` | Sensitivity check. | Tests whether modestly wider step, yaw, height, or backward bounds unlock headroom without becoming free-space planning. |
| `D3` `upper_bound_free_shell` | Upper-bound diagnostic. | Shows whether target-RRI headroom exists when motion realism is relaxed; it does not prove deployable ARIA-NBV planning. |
| `D4` `v1_rich_5family` | Optional support ablation. | Adds local refinement and revisit/backtrack families only if the three-family profile is valid but behaviorally too narrow. |

The minimum report for each profile should include:

- valid candidates per step and per `position_id`;
- valid non-forward target-aware candidates per step;
- invalid-reason distribution by `position_id`;
- selected `position_id` and `strategy_id` histograms;
- target-current support and target-candidate support;
- target-RRI or root-normalized target-gain distributions;
- oracle-greedy versus oracle-lookahead endpoint gain;
- path length, yaw, height, backward displacement, and distance from the
  logged trajectory;
- scene, target, and support-bin stratification.

Interpretation rules:

- If `D3` has headroom but `D1`/`D2` do not, the result is free-space upper-bound
  headroom, not realistic ARIA planning headroom.
- If `D1`/`D2` have too few non-forward target-aware valid rows, the bottleneck
  is candidate feasibility before it is architecture.
- If `D1`/`D2` have oracle headroom but learned `Q_H` fails, the next suspect is
  data support, labels, calibration, leakage, or model capacity.
- If pure target-point controls beat the mixed profile under matched validity,
  the thesis should report that the simpler target-point control is sufficient
  for the evaluated split instead of defending mixture complexity.

### Target-Selection Sensitivity

Target selection should not collapse reliability, interestingness, support, and
GT matching into one opaque score. The thesis protocol should keep these axes
auditable:

- OBS-SEL samples or reweights actor-visible target hypotheses that are
  supported enough to evaluate and under-observed enough to matter;
- PRED-Q conditions the scorer on actor-visible target descriptors and support
  features only;
- GT-EVAL uses GT OBBs, target meshes, and deterministic matching only for
  labels, matching, and evaluation;
- unmatched, unsupported, or ambiguous targets are target-invalid cases, not
  low-RRI valid samples.

This makes sparse target matching interpretable. A low-valid target subset is a
protocol limitation or reporting stratum, not a reason to train on corrupted
negative examples.

### Sampler Architecture Implications

Candidate-family provenance is an input and split axis, not decorative
metadata. `Q_H` may condition on `position_id` and related family descriptors,
but evaluation must check whether it learned family shortcuts rather than
viewpoint utility. Useful tests are row shuffling, held-family evaluation,
family-frequency perturbation, and calibration by `position_id`.

Target-bearing and lateral-bypass families should be treated as setup-action
providers. They may have low immediate target visibility while still enabling
positive horizon value. This is exactly where one-step scorers, greedy oracle
policies, and multi-step `Q_H` should be compared.

### Preflight Gates Before Retuning

Before broad rollout generation or value-head training, run a small audit over
25 to 50 roots across at least five scenes. Fail or quarantine roots when:

- `num_valid_candidates < max(12, ceil(0.25 * N_q))`;
- there are no valid non-forward target-aware actions for a state, unless this
  is an explicit forward-only ablation;
- production profiles have fewer than three valid non-forward target-aware
  actions per state;
- invalidity is dominated by one `position_id` without an explanatory geometry
  or support stratum;
- `position_id`, strategy, mixture, sampler probability, or invalid-reason
  fields are absent from the generated artifact.

Retune in this order: target-bearing and lateral-bypass direction construction,
radius/height/yaw bounds, clearance/path-collision filters, root skipping, then
only finally upper-bound free-shell comparisons.

### Thesis Wording Recommendation

The method should state:

> All `Q_H` and oracle-headroom claims are indexed by candidate distribution.
> The main V1 claim uses a local egocentric ARIA motion prior with target-aware
> finite candidates; free-shell candidates are retained only as explicit upper
> bounds for diagnosing whether headroom exists outside realistic motion
> support.

## Iteration 9: Target-Descriptor Reliability And Matching Protocol

Target selection is not merely a preprocessor for `Q_H`. It is a separate
measurement protocol whose reliability determines whether target-conditioned
scores and returns are interpretable. The current repo contract correctly
separates actor-visible selection from GT labels, but the next thesis pass
should make descriptor quality, target eligibility, and GT association failure
rates first-class evidence.

### OBS-SEL / PRED-Q / GT-EVAL As Three Data Products

| Stage | Actor-visible fields | Oracle-only fields | Required audit |
| --- | --- | --- | --- |
| OBS-SEL | detected or predicted OBB, class, confidence, projected area, semidense support, EVL support, relative pose, source mode, score components | none before selection | selected/rejected counts, reason codes, score-component histograms, source-mode distribution |
| PRED-Q | target descriptor `z_e`, candidate table, selected history, masks, support diagnostics | no GT OBB, GT crop, GT mesh, or all-candidate oracle render | feature-schema version, leakage check, stratification by target source and support bin |
| GT-EVAL | none as actor input | matched GT OBB id, target crop, target mesh, target-RRI labels, match IoU/score, ambiguity gap, label-valid mask | unmatched/ambiguous/unsupported counts, per-class IoU, target crop support, endpoint target gain |

This table should appear near the method definition of `z_e`. It prevents a
common category error: using target-match metadata to explain model input
quality after it has already leaked into the model-facing tensor.

### Current Methodology Risks To Preserve

The current implementation audit found that V1 does not grossly leak GT OBBs
into actor-visible selection, but three scale risks remain:

- zero-projection targets can be selected and label-valid when 3D support is
  sufficient under `require_projected_visibility=false`;
- saturated-support targets can have target interest score `0.0` because the
  support-deficit factor reaches zero, yet still be selected by greedy top-K
  when they are the available eligible rows;
- public thesis wording and current implementation differ on GT matching score
  semantics: docs sometimes describe support/projection as part of matching,
  while code uses support/projection for eligibility/audit and class-compatible
  3D IoU for GT association.

The last point is a documentation and methodology decision, not necessarily a
code bug. The cleaner protocol is to keep:

1. eligibility: actor-visible support, projection, confidence, finite OBB, and
   source validity;
2. association: compatible semantic class, 3D IoU, threshold, and ambiguity
   margin;
3. reliability audit: support/projection/class/source bins that explain when
   association is likely to fail.

If a broader compact match score is used, it should be named as such and
reported separately from pure 3D IoU.

### Literature Transfers For Target Descriptors

| Source family | Useful transfer | ARIA-NBV boundary |
| --- | --- | --- |
| EFM3D / EVL | Gravity-aligned local voxel evidence, OBB predictions, point and freespace masks, per-class and sim-to-real failure analysis, visibility-threshold thinking. | EVL OBBs are actor-visible hypotheses with known failure modes, not guaranteed target truth. |
| Project Aria | Egocentric object understanding depends on natural motion, trajectory, point clouds, and wearable constraints. | Do not assume clean scanning trajectories or externally curated object-centric views. |
| Instance-NBV | Target-object confidence and object-vector conditioning motivate target-centric support features and mask/descriptor quality audits. | Do not import 3DGS masks, object vectors, or confidence scores as available actor truth unless built and validated. |
| SceneScript | Structured object commands and OBB predictions suggest future semantic memory and target-retrieval abstractions. | Scene-language outputs, open-vocabulary boxes, and AP-style confidence ranking are future bridges, not current V1 target selection. |

The EFM3D evidence is especially relevant: small or unusual object classes, real
AEO transfer, objects on top of other objects, mirrors, and finite local voxel
extent all create target-descriptor reliability strata. Those strata should be
visible in the ARIA-NBV selector report before `Q_H` results are interpreted.

### Descriptor Ladder

The first target descriptor should stay compact and auditable:

| Descriptor tier | Contents | Use |
| --- | --- | --- |
| T0 scalar geometry/support | predicted center, orientation, extents, class, confidence, clipped projected area, semidense support, EVL support, relative pose. | Main V1 baseline because every field has a clear actor-visible provenance. |
| T1 reliability-expanded | T0 plus source mode, source rank, score components, zero-projection flag, saturation flag, class frequency, support bin, ambiguity diagnostics. | Calibration and failure interpretation; not necessarily all model input. |
| T2 pooled local evidence | compact pooled EVL/voxel, semidense point, or image-projection features around the actor-visible target. | Ablation only after T0/T1 support and matching are stable. |
| T3 object/semantic features | object-mask confidence, instance embedding, target object vector, grounded entity token. | Later semantic ablation; requires a validated actor-visible producer and leakage audit. |
| T4 structured scene memory | SceneScript-style object commands, global entity graph, VLM/VLA retrieval. | Future semantic-global bridge after target-RRI, candidate support, and `Q_H` are stable. |

This ladder keeps the current architecture honest. If T0 fails because target
matching is sparse or ambiguous, adding T3/T4 semantics is not a principled
fix unless the new producer is evaluated as part of the target protocol.

### Required Target-Selector Coverage Report

Before thesis-scale rollout generation, produce a small trusted-subset report
with:

- target source distribution: detected OBB, EVL/backbone predicted OBB, V0 GT
  sanity input;
- selected and rejected counts by class, source, support bin, projected-area
  bin, distance, and scene;
- score-component histograms: confidence, projected visibility, support,
  support deficit, product score;
- zero-projection and zero-score selected-target counts;
- GT association: match valid, unmatched, semantic mismatch, geometric
  mismatch, ambiguous top-1/top-2 gap, IoU distribution, and match score if a
  broader score is used;
- target crop support: mesh-face count, current eval points, candidate eval
  points, empty-crop rate, and near-solved-target rate;
- policy impact: one-step oracle rank and learned scorer calibration stratified
  by target source and support bin.

### `Q_H` Implications

`Q_H` should be evaluated under target-descriptor strata, not only aggregate
scene metrics. Report whether learned actions recover oracle headroom for:

- V0 GT-input sanity targets versus V1 observed/predicted targets;
- detected OBBs versus EVL/backbone predicted OBBs;
- high-support versus low-support targets;
- projected-visible versus zero-projection support-only targets;
- unambiguous versus near-ambiguous GT matches;
- frequent large classes versus rare/small/problematic classes.

If `Q_H` works only for V0 or only for high-support targets, the result is still
valuable, but it should be reported as a descriptor/support finding rather than
as a general target-conditioned planning result.

## Iteration 10: Actor-Visible State, Support Memory, And Recurrence

The representation problem should be framed as a state-contract problem first
and a backbone-selection problem second. `Q_H` consumes
`s_t^{cf0}`, not arbitrary scene features. The first architecture should prove
that target-local support, candidate frusta, selected-view history, and compact
actor-visible evidence recover headroom before expensive point, sparse, or
recurrent reconstruction backbones are promoted to thesis core.

### State Contract For Representation Choices

| State surface | Thesis role | Representation consequence |
| --- | --- | --- |
| `s_hist` | raw logged Project Aria / ASE evidence | Useful for building actor-visible descriptors, but not the direct learned `Q_H` table unless materialized consistently. |
| `s_off` | immutable VIN/offline sample store | Baseline and diagnostic substrate; not the full multi-step rollout state. |
| `s_cf0` | first thesis-core counterfactual actor state | Frozen root EVL context, fused point proxy, selected-view history, target descriptor, budget, candidate table, validity masks, and current candidate-query features. |
| `s_cf+` | richer ablation state | Adds selected-action synthetic observations, backprojected points, normals, and local support summaries after the action has been selected. |
| `s_oracle` | privileged label/evaluation state | GT mesh, GT target crops, all-candidate renders, oracle RRI, and GT OBBs; never model input for V1 actor claims. |

This split rules out all-candidate dense GT render features as V1 actor input.
It also rules out recomputing EVL with synthetic future observations in the
first thesis-core state unless that recomputation is explicitly promoted into
`s_cf+` and evaluated as an ablation.

### Representation Ladder

| Rung | Representation | Adopt when | Reject or defer when |
| --- | --- | --- | --- |
| R0 current compact state | EVL heads, semidense projection statistics, target descriptor, candidate pose/support/mask features. | First `Q_H` and one-step scorer baseline. | Never enough to claim geometry-rich modeling, but enough to test the planning contract. |
| R1 actor-visible support tokens | Point position, inverse distance std, observation count, support history, free/occupied/unknown indicators, target/frustum/intersection pools. | Support bins or candidate frusta explain score error. | Point identity, support, or storage is unstable. |
| R2 compressed image-feature point cache | DINO/EVL features attached to semidense or fused points after compression. | R0/R1 fail from feature collapse or target ambiguity. | Raw 768D features would dominate storage or lack a manifest/training reader. |
| R3 EVL internals | lifted voxel features, neck features, voxel counts, point/free-space masks, local grid reads. | Final EVL heads are too lossy and local voxel extent is enough for the target/candidate regime. | Long-horizon support lies outside EVL extent or requires broad scene memory. |
| R4 selected-view recurrent memory | recurrent update over selected-view history or support tokens, inspired by Deja View / RAFT-style refinement. | The same selected evidence needs iterative refinement under a fixed compute budget. | The first failure is target matching, candidate support, or label headroom. |
| R5 point/sparse/scene backbones | KPConv, Point Transformer/PTv3, MinkowskiEngine, or sparse 3D/4D encoders over actor-visible support. | Compact support tokens bottleneck generalization and scale evidence justifies heavy geometry encoders. | Candidate-set reasoning, masks, rollout lineage, or target descriptors are still unresolved. |

The default thesis path should stop at the first rung that recovers headroom
under oracle re-evaluation. A heavier rung is a controlled ablation, not a
replacement for the finite-candidate planning claim.

### Query Pools Before Backbones

The highest-leverage representation improvement is not a new global backbone.
It is to make every candidate token ask the same actor-visible questions:

- target pool: actor-visible evidence inside the observed/predicted target OBB;
- candidate-frustum pool: actor-visible evidence projected into the candidate
  frustum;
- target-frustum intersection pool: evidence that is both target-related and
  candidate-visible;
- support novelty: directional or support-count summary for target-local points
  or voxels;
- out-of-support flags: outside EVL extent, outside semidense support, no
  target projection, low support, or invalid reason.

These pools can start as masked mean/max/count statistics. A learned point,
sparse, or cross-attention encoder should be justified by showing that simple
pools fail in a specific stratum.

### Literature Transfers For Support Memory

| Source family | Useful transfer | Boundary |
| --- | --- | --- |
| EFM3D / EVL | Frozen image features lifted to a gravity-aligned voxel grid, point and freespace masks, 3D U-Net processing, and evidence that point/free-space channels matter. | EVL is local actor-visible evidence, not a full long-horizon memory or oracle. |
| Deja View | Weight-tied recurrent refinement over DINO-initialized multi-view tokens and an inference-time step-count knob. | It is a reconstruction model, not a value model; recurrence should stay within trained step budgets and selected-view actor evidence. |
| Point Transformer / KPConv | Local point neighborhoods, spatial kernels, density robustness, and point-order handling. | Heavy point backbones are support encoders after compact pools fail, not the first candidate-set scorer. |
| PTv3 | Serialization and shifted orders make large point attention efficient. | Serialization intentionally relaxes strict permutation invariance; use for point-feature banks, not candidate-row semantics. |
| MinkowskiEngine | Sparse 3D/4D convolutions for spatiotemporal point/depth streams. | Useful only if support memory becomes large and voxelizable enough to justify sparse-conv infrastructure. |

### Directional Memory Scope

Directional observation memory should start as low-order, target-local support
features rather than a large per-point history tensor:

- coarse view-direction bins or second moments around the target;
- optional low-order spherical-harmonic summaries for selected support points;
- per-candidate novelty summaries computed from target and frustum pools;
- stratified reports showing whether directional support predicts target gain.

Do not promote e3nn, spherical CNNs, or high-order SH channels until the
low-order summaries prove useful and stable.

### Recurrent And Teacher/Student Boundaries

Deja View and RAFT-style evidence supports explicit iterative refinement, but
the safe ARIA transfer is narrow:

1. recurrently refine the internal representation of selected-view history or
   support tokens under a fixed trained step range;
2. expose inference-time compute only inside that trained range;
3. decode intermediate support/score diagnostics to ensure recurrence improves
   the target-specific task, not only representation norm or visual quality;
4. keep all-candidate GT renders and GT crops in the oracle path.

A privileged teacher may use dense oracle renders as an upper-bound diagnostic
or distillation source only if the reported V1 student receives actor-visible
state. Any teacher/student result must include an ablation showing the student
without privileged render inputs.

### Architecture Recommendation

The next implementable `Q_H` architecture should be:

1. independent target-conditioned scorer over R0 compact features;
2. residual/dueling set head over candidate tokens and masks;
3. query-pool support features for target, frustum, and intersection evidence;
4. selected-view history summaries and low-order directional support;
5. only then R2/R3 feature-cache or EVL-internal ablations;
6. only after that, R4/R5 recurrence or point/sparse backbones.

This is the minimum path that respects actor visibility, finite-candidate set
symmetry, target-specific utility, and the real likelihood that the first
failures will be target selection, candidate support, rollout lineage, or label
headroom rather than insufficient neural capacity.

## Iteration 11: Offline Support, Branch Diversity, And `Q_H` Backups

The `Q_H` architecture is only meaningful under the replay distribution that
generated its selected-action transitions. Offline value learning can fail
because the model optimizes unsupported actions even when the network class is
reasonable. The thesis should therefore treat behavior-policy support and
stochastic provenance as architecture prerequisites, not implementation
details.

### Behavior Policy Mixture Before Model Complexity

The first usable rollout mix should include:

| Trace family | Purpose | Required report |
| --- | --- | --- |
| random-valid | coverage floor and sanity baseline | valid-action distribution, family/source coverage, return quantiles |
| one-step oracle greedy | strong myopic upper-bound behavior | selected family/source, target gain, failure cases where greedy saturates |
| bounded oracle lookahead | non-myopic headroom upper bound | recovered headroom over greedy, horizon and branch-factor sensitivity |
| oracle-scored temperature-softmax | diversified high-score support | entropy, duplicate rate, selected-family spread, score-source lineage |
| Gumbel-Top-k / stochastic beam | later branch diversity without replacement | Gumbel keys/seeds, ordered samples, effective unique chains, late-branch coverage |

If these traces collapse onto the same first action or same candidate family,
the right response is to fix the rollout policy and candidate sampler before
changing the value model.

### Replay Support Diagnostics

Every training store should report support diagnostics before `Q_H` metrics:

- behavior-policy composition by root, step, target, candidate profile, and
  scene split;
- selected-action counts by `position_id`, `strategy_id`, target source, support
  bin, and invalidity neighborhood;
- successor candidate-table availability for every nonterminal transition;
- duplicate selected-chain rate and effective number of unique chains;
- per-step entropy and log-probability for stochastic selectors;
- coverage of low, medium, and high target-gain bins;
- bootstrap mask coverage and terminal/timeout rates;
- predicted max-Q versus oracle-rescored return on fixed held-out roots.

The DQN lesson is replay and held-out predicted-Q diagnostics; the Double DQN
lesson is selector/evaluator decoupling; the offline-RL lesson is not to trust
greedy values on unsupported candidate regions.

### Backup Ladder

| Backup | Use first when | Evidence needed | Defer when |
| --- | --- | --- | --- |
| Monte-Carlo or finite-horizon return regression | Rollout traces contain complete bounded returns. | Held-out rank/top-k, calibration, oracle-evaluated selected actions. | Returns are too sparse or horizon coverage is inconsistent. |
| Masked fitted Double-Q | Successor candidate tables and masks are complete. | Overestimation plot, target-network lag, bootstrap mask coverage, oracle-rescored policy rollouts. | Successor tables or selected-transition lineage are missing. |
| CQL-style conservative penalty | Fitted Double-Q overselects unsupported high-Q candidates. | Candidate-table logsumexp or sampled-action penalty, behavior-action value comparison, support-stratified policy evaluation. | Behavior support is too narrow to define meaningful action density or candidate tables are unstable. |
| IQL-style in-sample value fitting | Avoiding out-of-sample max queries is more important than explicit greedy `Q_H`. | Dataset-action value fit, expectile sensitivity, advantage-weighted extraction diagnostics. | The mandatory finite-candidate `Q_H` comparison has not been attempted. |
| Decision / Trajectory Transformer | State-action-reward sequences are long, typed, and plentiful. | Sequence split, return-conditioning ablation, beam-search oracle comparison. | Typed rollout traces, target labels, and behavior coverage are still immature. |

This ladder keeps CQL/IQL honest. They are useful diagnostics for offline
support, not shortcuts around the mandatory finite-candidate `Q_H` result.

### Stochastic Provenance Contract

Stochastic traces should be replayable without guessing:

- rollout/job seed, shard order, source row, and scene split hash;
- selector family, policy parameters hash, temperature, score source, and branch
  schedule;
- candidate logits or oracle scores before normalization;
- robust-normalization statistics, probabilities, log-probabilities, entropy,
  sampled outcome, and RNG-state hash or derivable per-step seed;
- for Gumbel-Top-k: Gumbel keys, ordered sample, without-replacement rank, and
  duplicate/sibling-diversity guard status;
- parent chain id, selected chain id, selected action, successor state id, and
  successor candidate-table id.

Without these fields, stochastic traces are visual/debug evidence only. They
should not become training or thesis evidence.

### Offline Support Failure Interpretation

Interpret learned-policy failures in this order:

1. no oracle headroom under the named candidate distribution;
2. candidate or target support too sparse for training;
3. behavior-policy mixture collapsed onto one family or first-step action;
4. successor candidate tables or lineage missing;
5. max backup overestimation or unsupported-action selection;
6. model capacity or architecture.

This ordering prevents a common false repair: adding a larger set Transformer,
point backbone, or recurrence when the training data never supports the chosen
actions.

### Required `Q_H` Evidence

The first thesis-grade `Q_H` result should report:

- random-valid, one-step oracle greedy, one-step model scorer, bounded oracle
  lookahead, temperature-softmax, and learned `Q_H` under equal acquisition and
  candidate budgets;
- all learned-selected actions re-evaluated by the oracle;
- cumulative root-normalized target gain and endpoint target gain;
- calibration and rank metrics for held-out rows;
- overestimation diagnostics comparing predicted max-Q to oracle-rescored
  return;
- support-stratified results by candidate profile, `position_id`, target source,
  and scene split;
- exact coverage gaps for scenes, snippets, targets, transitions, policies, and
  blockers.

If the learned policy does not beat the one-step scorer but the oracle
lookahead does, the result is a value-learning/data-support failure. If the
oracle lookahead itself does not beat greedy, the result is a negative planning
headroom finding for the evaluated distribution.

## Iteration 12: Online Bridge And Simulator Escalation Gate

The simulator and online-learning question should be framed as a typed bridge
ladder, not as a menu of attractive RL frameworks. The current source order is
clear: ASE mesh/oracle counterfactual rollouts are the thesis-core substrate;
online discrete `Q_H` over the same finite candidate contract is RQ5 after
offline `Q_H`; continuous target-then-pose control and external simulators are
RQ6 or future-work escalation.

### Bridge Ladder

| Stage | Role | Allowed evidence | Gate to next stage |
| --- | --- | --- | --- |
| B0 offline finite-candidate `Q_H` | hard M5 thesis result | `rollouts.zarr`, selected-transition lineage, target-root gain, oracle re-evaluation | positive oracle headroom and a trusted offline `Q_H` failure/success report |
| B1 online discrete `Q_H` in ASE | RQ5 bridge | same finite candidates, same masks/reasons, same target-RRI oracle, interactive selected-state updates | online loop reproduces offline candidate/action contract without changing reward semantics |
| B2 learned-transition finite candidates | optional bridge | learned or cached successor features with oracle audit rows | selected-state prediction error is bounded and does not corrupt target-gain ordering |
| B3 target-then-pose local continuous actor | RQ6 headroom test | Hestia-style look-at/pose factorization, collision-free projection, target-RRI labels | finite-candidate evidence shows headroom that is limited by candidate discretization |
| B4 external simulator or semantic/global planning | future extension | Habitat/ProcTHOR/Isaac/3DGS only if target-RRI supervision or a validated proxy is preserved | advisor-approved scope change and no replacement of thesis utility by coverage/navigation metrics |

This ordering prevents a scope inversion. If offline `Q_H` fails because the
candidate distribution or rollout support is poor, a Gymnasium/SB3 wrapper
would mostly make the same support problem harder to observe. If offline `Q_H`
succeeds and free-shell or target-aware candidates expose missed headroom, a
continuous bridge becomes scientifically meaningful.

### External Paper Transfers

| Source | Adopt | Reject as core |
| --- | --- | --- |
| GenNBV | continuous 5-DoF notation, explicit MDP, action-history embedding, simulator-throughput warning, collision/path-cost reporting | coverage-gain reward, PPO/SB3 as first path, Isaac-Gym performance numbers as evidence for ASE target-RRI |
| Hestia | target/look-at then feasible-pose factorization, directional face/visibility features, collision-free projection, close-greedy failure warning | face coverage as the thesis reward, fixed `gamma=0.1`, mandatory continuous actor-critic |
| Habitat | modular simulator/task/agent/sensor abstraction, fast rendered interaction, train/val/test episode discipline, sensor/action ablation mindset | PointGoal/SPL/navigation success as NBV evidence, GPS-like task state, simulator performance as proof of target reconstruction quality |
| ProcTHOR / AI2-THOR | procedural diversity, object visibility eligibility, target-category sampling balance, zero-shot/fine-tune distinction | synthetic interactive object navigation as a substitute for ASE/EFM target-RRI supervision |
| Active 3DGS / FisherRF / object-centric NBV | utility-channel separation, uncertainty/object-focus/proposal signals, downstream simulator bridge | 3DGS uncertainty or task reward as the thesis utility before calibration against target RRI |

The key architectural implication is that ARIA-NBV should define an
environment boundary only after the data contract is stable. A useful future
environment exposes `reset`, `step`, masks, observations, oracle audit labels,
and selected-state updates, but the policy interface must still preserve the
same actor-visible state split and hard invalidity contract.

### RQ5 Online Discrete Scope

The first online bridge should be deliberately narrow:

- input: trusted root state, actor-visible target descriptor, candidate table,
  masks/reasons, budget, and selected-view history;
- action: one valid candidate index from the current table;
- transition: render/fuse the selected view, regenerate successor candidates,
  and update only actor-visible counterfactual state;
- reward/evaluation: root-normalized target gain and endpoint target gain from
  the same oracle audit stream used offline;
- comparison: online `Q_H` versus one-step scorer, online oracle greedy,
  bounded oracle lookahead, and random-valid under equal acquisition budget;
- non-goal: no continuous action, no generic PPO/SAC/SB3 benchmark, no Habitat
  or Isaac replacement of the ASE mesh/oracle loop.

The online result can be a smoke/bridge if time is tight. It should not be
allowed to replace the M5 offline `Q_H` evidence.

### Continuous And Simulator Escalation Criteria

Continuous or external-simulator work should require all of the following:

1. offline `Q_H` and oracle lookahead show positive headroom or a clearly
   diagnosed candidate-discretization bottleneck;
2. target-RRI labels, GT target matching, and invalidity reasons remain
   available, or the proxy reward is explicitly calibrated against target RRI;
3. action-space change is isolated from reward change, so continuous control is
   not confounded with coverage or navigation objectives;
4. simulator substrate reports scene/target split, visibility eligibility,
   collision model, sensor model, and reward throughput;
5. failure cases distinguish no headroom, invalid transition support, target
   mismatch, and simulator/reward mismatch before blaming actor architecture.

Hestia's hierarchy is the best local form of this bridge: choose a target or
look-at hypothesis first, then choose a feasible pose. GenNBV mainly warns that
continuous PPO-style control needs a fast online reward loop and large-scale
parallel simulation. Habitat and ProcTHOR mainly inform environment contracts
and diversity gates, not the ARIA-NBV thesis reward.

### Architecture Consequences

The architecture plan should therefore keep two model families separate:

- finite-candidate `Q_H`: permutation-equivariant candidate set model with
  actor-visible target/candidate/history tokens and oracle-audited discrete
  selections;
- optional continuous bridge: target-then-pose actor with directional
  observability features, feasibility projection, and a critic that is audited
  against the finite-candidate oracle before any performance claim.

Do not let continuous-control literature erase the discrete evidence contract.
It should answer a later question: after the finite-candidate system is known,
what headroom is left because the candidate table cannot express the right
viewpoint?

## Iteration 13: Frame-Aware Invariance Contract

The planned architecture should not chase "SE(3) equivariance" as a slogan.
ARIA-NBV contains three different symmetry regimes:

1. candidate rows are an unordered set and require permutation equivariance;
2. candidate, target, and history geometry should be expressed in local frames
   so global world pose does not become an accidental shortcut;
3. gravity, egocentric heading, observed support, and target bearing are
   physically meaningful, so full rotation invariance would erase useful
   information.

The right contract is frame-aware invariance: canonicalize what is arbitrary,
preserve what is semantic, and test both explicitly.

### Descriptor Ownership

| Descriptor family | Frame / symmetry | Use in `Q_H` | Failure to watch |
| --- | --- | --- | --- |
| candidate row id, masks, provenance | set row, not semantic order | mask, grouping, diagnostics only | leaking row order or sampler id into claims without ablation |
| candidate pose relative to root | root rig or gravity-aligned root frame | first pose descriptor: translation, yaw/pitch, range, R6D or sin/cos angles | raw world pose shortcut and scene-id memorization |
| candidate relative to target | target-centered local frame | target bearing, distance, look angle, frustum/target overlap, support rays | GT target-center leakage in V1 if descriptor uses oracle OBB before actor selection |
| candidate-candidate pair | query-centric relative transform | attention bias / QCNet-style relative embedding | attention score changes under row shuffle or duplicate rows |
| history and selected views | root frame plus selected-step deltas | selected-view memory, overlap, target-observation history | treating unselected all-candidate oracle renders as actor-visible |
| sparse/point state | world or root frame with explicit transform metadata | optional feature-cache or point-backbone ablation | mixing PyTorch3D z-depth, ray-depth, CW90 display, and PoseTW direction |

QCNet/QCNeXt transfer is mainly the query-centric encoding principle. Each
query element builds a local coordinate system, and attention uses features
relative to that query. For ARIA-NBV, the candidate token is the natural query:
other candidates, selected history, target support, and local point/feature
evidence should be encoded relative to the scored candidate or target-root
frame, not as raw global coordinates.

### Equivariance Boundary

| Model level | Default | Escalate only if |
| --- | --- | --- |
| finite candidate table | permutation-equivariant Set/Transformer model | row-shuffle, mask isolation, duplicate-row, and valid-count tests pass |
| pose descriptors | handcrafted relative pose in root/target frames | residual errors correlate with geometry not captured by descriptors |
| point/support cache | Point Transformer/KPConv/sparse conv ablation | compact support/query pools are insufficient and data volume justifies it |
| exact SE(3)/E(n) backbone | not first path | target-root point geometry is central, enough point data exists, and orientation semantics are separated from nuisance rotations |
| continuous actor bridge | target-then-pose local policy | finite candidates show candidate-discretization headroom |

SE(3)-Transformer and EGNN are useful warnings: exact equivariance helps when
the task truly transforms predictably under rotations/translations, but Scan
ObjectNN-style evidence also shows that gravity/up can be informative. ARIA-NBV
is closer to the latter: the device is egocentric, gravity-aligned sampling is
intentional, and target-bearing/height cues are not nuisance variables.

### Tests Before Architecture Escalation

The thesis method/evaluation should define these model-level checks:

| Test | Transformation | Required signal |
| --- | --- | --- |
| row-shuffle equivariance | permute candidate rows and masks | outputs permute identically; selected index maps through the permutation |
| duplicate stability | insert duplicate valid/invalid candidate rows | original candidate score changes only within tolerance; masks remain isolated |
| global translation | add a constant offset to all world-frame geometry before feature extraction | relative descriptors and predictions are unchanged after canonicalization |
| yaw-frame consistency | rotate root/candidate/target geometry together around gravity | predictions are invariant when yaw is a nuisance, or intentionally equivariant when heading is a feature |
| CW90/display isolation | apply display-only CW90 paths only to visualization | model features, depth backprojection, and candidate poses are unchanged |
| depth convention audit | compare PyTorch3D z-depth and ASE ray-distance contracts | training features record source/convention and never mix them silently |
| target-frame ablation | remove target-relative descriptors or replace with root-only descriptors | performance loss or failure mode quantifies target-geometry value |
| sampler-provenance ablation | remove strategy/position ids from model input | verifies the model is not only learning sampler priors |

These checks are cheaper and more informative than adding a heavier backbone.
If they fail, the fix is a contract or feature bug, not a new architecture.

### Point And Sparse Backbone Critique

Point Transformer, KPConv, PTv3, and MinkowskiEngine are relevant only after the
lean descriptor path is exhausted. Their transferable ideas are:

- point-transformer relative position encoding: local pair geometry matters in
  attention;
- KPConv: local continuous kernels adapt to irregular point support but require
  density and receptive-field control;
- PTv3/MinkowskiEngine: sparse or serialized point processing is efficient but
  introduces quantization/order design choices that need audit metadata;
- SE(3)/EGNN families: exact equivariance is a diagnostic ablation, not a
  default for a task with gravity-aligned egocentric semantics.

For the first thesis path, encode compact target/frustum/intersection support
statistics and relative candidate descriptors. Add point/sparse backbones only
if the failure analysis says the compact descriptors cannot distinguish
geometrically different but descriptor-identical cases.

### Recommendation

The default architecture should be:

1. actor-visible root/target/candidate descriptors in explicitly named frames;
2. pairwise query-centric relative encodings between candidate tokens;
3. masked permutation-equivariant candidate-set encoder;
4. residual absolute head preserving calibrated one-step semantics;
5. invariance/frame tests as acceptance gates;
6. point/sparse/equivariant backbones only as documented ablations.

This respects geometric isomorphisms without pretending every orientation is a
nuisance. It also gives the thesis a clean invariance/equivariance subsection:
ARIA-NBV enforces permutation symmetry exactly, uses local-frame invariance for
global pose, preserves gravity and egocentric target semantics, and escalates to
equivariant geometry only when measured failures demand it.

## Iteration 14: Selected-View Memory And Recurrence Gate

Temporal memory should be treated as an actor-visible state contract before it
is treated as a recurrent architecture problem. The current narrow environment
already exposes pose history and masks through `history_positions`,
`history_mask`, `current_position`, `candidate_positions`,
`candidate_valid_mask`, and `step_fraction`. The rollout contract separately
defines `selected_depth/` as durable selected-view observation history for the
first `Q_H`/history-encoder path, while all-candidate RRI scoring remains an
oracle label path. That split is exactly the boundary a recurrence design must
respect.

### Memory Ladder

| Tier | State signal | First use | Escalation test |
| --- | --- | --- | --- |
| M0 pose chain | selected camera positions, step fraction, valid mask | current RL smoke surface and finite-horizon sanity checks | proves horizon, masking, and action indexing work |
| M1 directional memory | target/support-centered view directions or second moments on `S^2` | compact history feature for target and frustum support | improves over pose-only without new oracle data |
| M2 selected-depth summary | fused selected-depth points, valid-mask ratios, selected-view support deltas | first learned history encoder | uses only materialized selected actions and records depth convention |
| M3 feature/cache summary | root EVL/DINO point summaries plus selected-view support updates | ablation after M1/M2 are stable | no hidden recomputation from synthetic future RGB or GT labels |
| M4 bounded recurrence | shared-update history refiner over selected-history tokens | Deja View / RAFT-style ablation | trained and evaluated for explicit `K`/horizon range |
| M5 sequence model | Decision/Trajectory-Transformer-style long traces | later bridge after many typed rollouts exist | behavior-policy support and horizon generalization are measured |

M1 is the best next addition. SCONE's camera-history idea translates cleanly:
history should be represented around target-local or support-local points, not
only as a raw sequence of global poses. The existing shared feature equations
already contain `direction_memory_moment` and `direction_novelty`, so the thesis
can introduce this without inventing a new notation family.

### Actor-Visible History Boundary

Selected synthetic depth is legitimate successor-state history only after a
candidate has been selected and rendered. Unselected all-candidate depth, all
candidate target-RRI scores, GT mesh labels, and candidate oracle crops remain
oracle-only. The storage role should therefore stay explicit:
`selected_depth/` is `selected_successor_state_history`, not a generic
candidate-depth table.

This gives a simple leakage rule:

1. `Q_H(s_t, q_{t,i})` may see previous selected poses and previous selected
   observations;
2. it may see the current actor-visible candidate table and masks;
3. it may not see future candidate renderings or oracle target labels for
   candidates that have not been chosen.

Any recurrent model that violates this rule is solving a privileged critic
problem, not actor-visible NBV.

### Deja View / RAFT Transfer

Deja View is useful as an architectural warning and an ablation template. Its
core lesson is not "add recurrence everywhere"; it is that explicit,
shared-weight iterative refinement can replace some parameter depth when the
task already contains repeated geometric correspondence work. The paper also
shows the failure mode: iterations outside the trained range eventually degrade
or collapse because feature channels drift. RAFT and Universal Transformer give
the same general caution from different directions: recurrent updates need a
clear state, fixed or trained stopping budget, and task-specific supervision.

For ARIA-NBV this implies:

- first prove finite-horizon value learning with M0/M1/M2 history;
- if recurrence is used, share a small update block over selected-history
  tokens or candidate-context tokens, not over hidden oracle artifacts;
- train and report the exact update count or horizon range;
- evaluate beyond the trained horizon only as a generalization diagnostic, not
  as evidence that the model is an unbounded planner;
- log per-iteration score deltas, norm/update statistics, and candidate-rank
  stability if a recurrent refiner is introduced.

The positive transfer is strongest for iterative correspondence and support
aggregation: a recurrent block may help align target support, selected-depth
updates, and candidate-query tokens. The negative transfer is equally important:
if M1/M2 history does not improve headroom recovery, a recurrent hidden state is
more likely to hide a data/support problem than to fix it.

### Required Tests

| Test | Mutation | Required result |
| --- | --- | --- |
| selected-only leakage | remove all unselected candidate render payloads from model inputs | predictions and training code still run |
| oracle-depth firewall | replace unselected candidate depths with noise or zeros | actor model output is unchanged because it never consumes them |
| history ablation | compare M0 pose-only, M1 directional memory, M2 selected-depth summaries, and M4 recurrence | each added tier must justify its extra complexity |
| time/order sanity | reverse, duplicate, or mask selected-history entries | model behavior changes only where the encoded history should matter |
| horizon split | train on one horizon range and evaluate on held horizon lengths | report degradation instead of extrapolating claims |
| provenance audit | check selected-depth role, pose, intrinsics, renderer, units, clip planes, and depth convention | every selected observation can be traced to a selected action |
| no-support-change control | select actions that do not change target/support evidence | memory encoder should not invent target gain |

### Recommendation

Keep temporal memory in the core plan, but keep recurrence behind a gate. The
first thesis architecture should use selected pose history plus directional
support memory and optional selected-depth summaries. A Deja View-style looped
block is a good M4 ablation only after the selected-history contract, Zarr
provenance, and no-leakage tests pass. This preserves the useful idea of
iterative geometric refinement without turning `Q_H` into a hidden
oracle-consumer or an unbounded recurrent planner.

## Iteration 15: Fusion And Value-Head Contract

The architecture should make feature fusion auditable before it makes it
powerful. Candidate-query `Q_H` needs target descriptors, selected history,
candidate geometry, support evidence, invalidity masks, and candidate-set
context, but these signals do not have the same semantics. Fusing them too early
can create a model that ranks well while nobody can tell whether it learned
target utility, sampler priors, invalidity shortcuts, or oracle leakage.

### What To Adopt From Set And Motion-Forecasting Papers

| Source | Adopt | Do not import |
| --- | --- | --- |
| Deep Sets | shared row encoder plus commutative pooling as the mandatory candidate-context control | treating pooled context as enough evidence that pairwise geometry was modeled |
| Set Transformer | masked candidate self-attention for candidate-candidate and candidate-context interaction | unmasked padding/invalid rows or global pooling when per-candidate outputs are required |
| QCNet / QCNeXt | query-centric relative coordinate systems and relative positional embeddings between candidate, target, history, and support tokens | autonomous-driving lane/agent semantics, social-motion losses, or scene-trajectory mixtures |
| Wayformer | explicitly compare early, late, and hierarchical fusion rather than inventing modality-specific stacks first | modality-agnostic early fusion without token-type/provenance checks |
| Perceiver | latent bottleneck for very large point/support/candidate contexts if direct set attention becomes too expensive | opaque latent compression before leakage, mask, and calibration tests pass |
| Scene Transformer | typed attention across agents/elements/time and masking as a query interface | future-interaction prediction as if ARIA's unselected candidate futures were actor-visible |
| VectorNet / HiVT family | vectorized local components, hierarchy, and query-centric locality | road-map priors or ordered polyline assumptions as candidate-order semantics |

The common transferable principle is not "use the biggest Transformer." It is
typed, masked, query-centric interaction over a set whose symmetry and
provenance are known.

### Fusion Ladder

| Tier | Fusion pattern | Use | Failure gate |
| --- | --- | --- | --- |
| F0 independent candidate | per-row MLP over actor-visible candidate/target/support fields | calibrated one-step baseline | cannot rank obvious target-support differences |
| F1 DeepSets context | pooled valid-candidate context appended to each row | detects global low-support or degenerate candidate sets | row-order or valid-count tests fail |
| F2 masked Set Transformer | valid candidate rows attend to each other and typed context tokens | first interaction model for `Q_H` | invalid rows affect valid scores |
| F3 query-centric RPE | add candidate-relative target/history/support/candidate biases | tests whether geometry interaction matters | no gain over F2 or frame tests fail |
| F4 cross-attention to support tokens | candidates query target/frustum/intersection support pools | tests richer actor-visible support | support source/provenance unclear |
| F5 latent bottleneck | Perceiver-style latent compression for large support/point contexts | scale ablation after F2-F4 pass | bottleneck hides which source produced a decision |
| F6 recurrent/joint decoder | bounded iterative or scene-level proposal refinement | late ablation for horizon/planning ambiguity | recurrence leaks unselected futures or extrapolates beyond trained horizon |

This ladder keeps Wayformer-style fusion comparisons and Perceiver-style
scalability as experiments, not unexamined defaults.

### Value-Head Decomposition

The immediate one-step target gain remains a physical label for a candidate in a
state: changing unrelated candidate rows does not change the oracle one-step
gain of `q_i`. Therefore the model should keep an independent calibrated
one-step head and put set interaction into a zero-mean residual or dueling
horizon head:

| Head | Inputs | Purpose | Constraint |
| --- | --- | --- | --- |
| `r_abs(s,e,q_i)` | candidate-local actor-visible features | calibrated H=1 root-normalized target gain | stable when unrelated rows are added or permuted |
| `V_H(s,e,h_t)` | state, target, selected history, support summary | shared finite-horizon state value | no candidate-row identity or padding leakage |
| `A_H(s,e,q_i,Q_t,m_t)` | candidate token plus masked set/context interaction | per-candidate finite-horizon advantage | mean-subtract over valid rows only |
| invalidity head / mask | validity reason features and hard masks | feasibility, not utility | invalid rows are masked from argmax, losses, and bootstrap |

The thesis-safe `Q_H` output is then:

```text
Q_H(i) = r_abs(i) + V_H + A_H(i) - mean_valid(A_H)
```

This structure lets the one-step scorer stay interpretable while `Q_H` captures
branch support, candidate-set degeneracy, and non-myopic opportunity. If the
set model improves immediate ranking only by changing `r_abs` when unrelated
rows appear, that is absolute-label contamination, not evidence for candidate
interaction.

### Fusion Tests

| Test | Mutation | Required signal |
| --- | --- | --- |
| absolute-head contamination | add unrelated valid rows while keeping candidate `i` unchanged | `r_abs(i)` stays stable; only residual/advantage may change |
| valid-mean correctness | change number of valid rows and padding rows | mean subtraction uses valid rows only |
| invalid firewall | make invalid rows carry extreme feature values | valid scores and bootstrap targets are unchanged |
| token-type ablation | remove target, history, support, strategy, or RPE channels one at a time | report which source actually drives gains |
| early-vs-late fusion | compare F1/F2 early concat against typed cross-attention | gains must survive provenance and leakage checks |
| latent bottleneck audit | compress support tokens through a Perceiver-style latent | preserve source dropout sensitivity and calibration |
| branch-support split | evaluate low/high headroom and low/high behavior support separately | no aggregate win without support-stratified evidence |

### Recommendation

Make residual-dueling `Q_H` the first horizon model, not a monolithic
Transformer regressor. The baseline stack should be F0 independent scorer,
F1 DeepSets context, F2 masked Set Transformer, then F3 query-centric relative
encoding. F4-F6 are ablations after masks, frame tests, target protocol, and
rollout support pass. This gives the thesis a clear architecture claim:
candidate-set modeling is used to improve finite-horizon advantage and ranking
under a hard actor-visible contract, while one-step utility, invalidity, and
source provenance remain separately testable.

## Iteration 16: Scene And Support Encoding Contract

The scene representation should be designed around candidate queries, not around
choosing one global backbone. EFM3D/EVL is valuable because it is Aria-native,
actor-visible, gravity-aligned, and produces OBB/target evidence. It is not a
complete long-horizon scene memory: the local voxel field is anchored to the
snippet/root window, final heads collapse much of the DINO evidence, and
candidate frusta can extend outside the EVL volume while still being valid.

The thesis should therefore say:

```text
EVL = local actor-visible target/support evidence
semidense/fused points = broader queryable scene memory
```

### Representation Ladder

| Tier | Representation | Adopt for | Do not claim |
| --- | --- | --- | --- |
| S0 current VIN/EVL features | EVL heads/evidence plus semidense projection statistics | implemented one-step baseline and smoke comparator | whole-scene memory or oracle target truth |
| S1 semidense/fused point state | point position, uncertainty, support count, observation lineage, selected-history support | broad actor-visible geometry substrate | dense oracle reconstruction quality |
| S2 compressed DINO@point | lifted 2D foundation features attached to observed/fused points | first serious scene-embedding ablation | raw uncompressed feature dump as default storage |
| S3 local EVL internals/crops | `voxel/feat`, neck features, local target/OBB crop reads | test whether pre-head EVL evidence helps target support | replacing scene-scale semidense/fused memory |
| S4 selected-depth history summaries | selected successor depth/point support after actions | finite-horizon history and `Q_H` successor state | pre-selection all-candidate render input |
| S5 point/sparse learned encoders | Point Transformer, KPConv, PTv3, Minkowski-style sparse encoders | ablation after query pools fail | first-path architecture or free invariance |
| S6 external scene models | DUSt3R/VGGT/MASt3R, OpenScene, 3DGS/GS-SLAM, ConceptGraphs | future bridge or semantic/renderable memory | thesis-core dependency before RRI/support gates pass |

This ladder converts the EVL criticism into a controlled experiment rather than
a backbone search project.

### Candidate-Query Pooling First

Before a point backbone, compute transparent query pools from actor-visible
points and features:

- target crop pool: points/features inside the observed or predicted target
  OBB;
- candidate frustum pool: points/features visible or geometrically relevant to
  `q_i`;
- target-frustum intersection pool: target-local support that candidate `q_i`
  can plausibly inspect;
- directional history pool: selected-view novelty/support around target-local
  or support-local points;
- EVL local read: optional local crop from EVL voxel/neck/head evidence with
  voxel pose and extent metadata.

These pools should start as mean/max/count/statistic summaries. Cross-attention,
Point Transformer, KPConv, sparse convolution, or Perceiver-style latents are
only justified if the simple pools cannot distinguish measured failure cases.

### Point / Sparse Backbone Critique

Point and sparse backbones contribute useful inductive biases but also introduce
new contracts:

| Family | Useful idea | Required contract |
| --- | --- | --- |
| Point Transformer | local point-pair attention with relative position encodings | neighbor radius/kNN choice, density bins, frame canonicalization |
| KPConv | continuous local kernels over irregular point support; radius neighborhoods are density-robust | radius, subsampling, density normalization, kernel scale |
| PTv3 / serialized point models | efficient large point-cloud processing | serialization/order provenance and shuffle tests |
| Minkowski sparse conv | efficient sparse 3D/4D convolutions over quantized coordinates | voxel size, quantization origin, hash/grid convention, temporal kernel policy |
| exact equivariant GNNs | controlled rotation/translation behavior | only after gravity/egocentric semantics are separated from nuisance transforms |

The first question is not which backbone is strongest on segmentation. It is
whether any learned point scene memory improves target-RRI ranking or `Q_H`
headroom after target/frustum/intersection pools, support counts, and
directional memory are already present.

### Provenance And Invariance Rules

Every scene/support token must record enough metadata to avoid mixing
incomparable evidence:

- source role: semidense actor point, selected-depth successor point,
  predicted-dense-depth point, EVL voxel/head/crop, or oracle/eval-only point;
- frame: world, root, target-local, candidate-local, and any gravity alignment;
- camera/pose/intrinsics/timestamp lineage for lifted image features;
- feature model id, checkpoint hash, compression method, feature dimension, and
  source RGB stream;
- point uncertainty, observation count, support count, and validity mask;
- depth convention for selected or predicted dense support;
- EVL voxel extent, voxel pose, grid resolution, and out-of-extent status.

Point-order invariance is mandatory for pooled point features. Frame
canonicalization should make global translations and arbitrary world origins
irrelevant, while preserving gravity, egocentric heading, target bearing, and
device/camera semantics when they are physically meaningful.

### Scene-Encoding Tests

| Test | Mutation / stratum | Required interpretation |
| --- | --- | --- |
| EVL extent split | candidates/targets inside vs outside local EVL volume | tells whether EVL limits scene memory |
| source dropout | remove EVL, semidense, DINO@point, selected-depth, or support channels | attributes gains to sources, not model capacity |
| point-order shuffle | permute point rows before pooling/encoding | pooled/candidate output invariant or equivariant as specified |
| density stress | subsample/densify semidense support and vary point uncertainty bins | model should expose sensitivity, not hide it |
| frame transform | translate/rotate canonicalized point/candidate/target geometry consistently | predictions unchanged except for intentionally preserved gravity/heading features |
| predicted-depth split | keep predicted dense support separate from semidense and selected-depth support | hallucination/confidence effects are reportable |
| quantization audit | vary sparse voxel size or point subsampling radius | learned backbone gains survive reasonable representation choices |
| storage/runtime audit | report feature-cache size, point count, compression, load time, and training memory | heavier scene encoders justify their cost |

### Recommendation

The next thesis method should define scene state as a typed actor-visible point
and support bank, queried by target and candidate geometry. Use S0/S1/S2/S3 as
the near-term representation ablation ladder. Treat S5/S6 as future or late
ablation gates. This respects geometric isomorphisms by making points unordered,
features source-typed, transforms explicit, and candidate queries local, while
avoiding the false choice between "EVL as everything" and "replace the project
with a new 3D foundation model."

## Iteration 17: Query-Centric Encoder Transfer

The QCNet/QCNeXt archive is the strongest local source for adapting
trajectory-forecasting encoders without importing the wrong task. Its useful
idea is not the multi-agent trajectory decoder. It is the local-frame,
query-centric scene encoder: each scene element is represented in a local
spacetime frame, and attention receives relative spatial-temporal embeddings
from key/value elements to the query element. That maps cleanly to `Q_H`
candidate rows if the thesis treats target, candidate, history, and support as
typed queryable tokens.

The transfer should be:

```text
trajectory scene element -> typed ARIA support/history/target/candidate token
local spacetime frame -> target-local or candidate-local ARIA frame
relative temporal embedding -> selected-history step or rollout-depth embedding
social/map attention -> masked candidate/support/history interaction
trajectory mode score -> not transferred to Q_H
```

### What To Adopt

| Source idea | Adopt in ARIA-NBV | Required guard |
| --- | --- | --- |
| QCNet query-centric local frames | candidate-local and target-local relative pose channels for `Q_H` rows | frame-transform tests and gravity/egocentric feature separation |
| QCNet relative spatial-temporal embeddings | RPE over candidate-target, candidate-history, candidate-support, and candidate-candidate edges | type tags and valid masks must gate all attention edges |
| HiVT local/global split | optional two-stage support memory: local candidate pools before global support compression | local pools must beat independent/DeepSets controls before global memory is claimed |
| Wayformer fusion taxonomy | explicit early, late, and hierarchical fusion ablations for scene/support/history streams | fusion cannot change calibrated one-step utility for an unchanged candidate |
| Perceiver latent bottleneck | support-memory compression only when candidate/support tokens are too many | source-dropout and calibration tests must survive the bottleneck |
| VectorNet polyline lineage | structured local-to-global aggregation as a conceptual precedent for frustum/support paths | use for support paths, not as a replacement for finite candidate scoring |
| Scene Transformer pooling/scoring | attentive pooling as a possible support-summary ablation | do not collapse candidate-row `Q_H` into one scene score |

### What To Reject

- QCNet/QCNeXt trajectory proposal, anchor refinement, and scene-level
  trajectory confidence are task-specific to forecasting. They should not become
  the ARIA value head.
- Scene-level pooling is useful for summarizing support tokens, but it is
  wrong as the main `Q_H` output because the thesis needs one masked finite
  value per candidate row.
- Interaction-first self-attention is still not the baseline. The thesis must
  keep independent candidate scoring and pooled DeepSets controls before
  attributing gains to masked Set Transformer or QCNet-style RPE.
- Local-frame invariance is not free. ARIA keeps meaningful gravity, egocentric
  heading, camera/device, and target-bearing signals; the model should only
  ignore arbitrary world-origin and row-order choices.

### Candidate-Query Encoder Contract

The clean architecture contract is:

1. Build typed actor-visible tokens: target descriptor, candidate row,
   selected-history summary, support pool, EVL local read, and optional point
   feature pool.
2. Canonicalize geometry in target-local or candidate-local frames while
   preserving physical gravity/egocentric channels.
3. Attach relative encodings by edge type:
   candidate-target, candidate-support, candidate-history, candidate-candidate,
   and history-history.
4. Apply hard validity masks before attention and backup construction.
5. Produce per-candidate outputs with a residual-dueling head, not a pooled
   scene score.
6. Test row permutation, duplicate candidates, invalid-row firewall,
   target-frame transforms, history-step shuffles, and fusion-source dropout.

This contract converts the forecasting-paper transfer into a thesis-specific
encoder design instead of a broad "use QCNet" claim.

### Literature Manifest Gap

Several referenced-paper sources are now important enough to index explicitly
instead of leaving them hidden in the QCNet bibliography:

| Missing source | Why it matters | Suggested status |
| --- | --- | --- |
| VectorNet | vectorized local-to-global scene aggregation precedent | add as low/medium-rank support-memory source |
| Perceiver | latent support-memory compression precedent | add as medium-rank scaling ablation source |
| Wayformer | early/late/hierarchical fusion taxonomy | add as medium-rank fusion-ablation source |
| HiVT | local/global temporal scene hierarchy | add as medium-rank temporal/support hierarchy source |
| Scene Transformer | scene-level multi-agent pooling and scoring cautionary source | add as low/medium-rank anti-pattern/support-summary source |

Do not promote these papers into the core method until they are either imported
into `docs/literature/sources.jsonl` with relevance metadata and litkg
propagation, or cited through the QCNet bibliography as referenced-paper leads.

## Iteration 18: Referenced-Paper Manifest Integration

The Iteration 17 manifest gap is now closed at metadata level. VectorNet,
Perceiver, Wayformer, HiVT, and Scene Transformer were added to
`docs/literature/sources.jsonl` with `relevance_rank`, `relevance_category`,
and `adoptable_ideas`, then propagated through `make kg-sync`,
`make kg-materialize`, and `make kg-export-neo4j`.

These are intentionally metadata-only records for now. They are queryable
through the litkg registry and `kg-show-paper`, but they do not yet have local
TeX/PDF parse bodies. Treat them as indexed literature leads and primary-source
anchors, not as locally parsed archive evidence.

### Primary-Source Checks

| Paper | Primary source checked | ARIA-NBV interpretation |
| --- | --- | --- |
| VectorNet | arXiv `2005.04259` | vectorized local-to-global aggregation can inspire frustum/support paths; road-polyline order must not become candidate-row order |
| Perceiver | arXiv `2103.03206` | asymmetric latent attention is a scaling ablation for large support/point token banks; provenance and calibration must survive compression |
| Wayformer | arXiv `2207.05844` | early, late, and hierarchical fusion become explicit ablation names for target/support/history/candidate streams |
| HiVT | CVF Open Access CVPR 2022 page | local context extraction before global interaction is a useful hierarchy; road-agent priors stay out of the thesis core |
| Scene Transformer | OpenReview ICLR 2022 page / arXiv `2106.08417` | masked sequence queries and typed attention are useful support-summary ideas; scene-level trajectory scoring is an anti-pattern for candidate-row `Q_H` |

### New Manifest Records

| Paper id | Status | Relevance category |
| --- | --- | --- |
| `arxiv-2005-04259` | metadata-only, `kg-show-paper` verified | vectorized local-to-global scene aggregation precedent |
| `arxiv-2103-03206` | metadata-only, registry verified | latent bottleneck support-memory compression ablation |
| `arxiv-2207-05844` | metadata-only, `kg-show-paper` verified | early late and hierarchical fusion ablation taxonomy |
| `hivt-hierarchical-vector-transformer-for-multi-agent-motion-prediction` | metadata-only, `kg-show-paper` verified | local global temporal scene hierarchy precedent |
| `arxiv-2106-08417` | metadata-only, registry verified | scene-centric masked attention and pooling cautionary source |

The generated records currently report `download_mode = MetadataOnly` and
`parse_status = PendingDownload`. For thesis writing this means the entries are
usable as indexed metadata and relevance hints, while deeper claims still need
the primary paper page, a local TeX/PDF download, or an explicit citation to the
QCNet bibliography context that led to them.

## Iteration 19: Calibration, Uncertainty, And Support-Aware Value Heads

The architecture should not treat uncertainty or support as replacement rewards.
The current thesis contract is sharper: target-RRI is the supervised utility,
invalidity is a hard mask/reason contract, and `Q_H` must beat calibrated
one-step controls under equal acquisition budget. Calibration and uncertainty
therefore belong around the value model as evidence gates, diagnostics, and
optional support-aware ablations.

### Literature Transfer

| Source | Useful idea | ARIA-NBV boundary |
| --- | --- | --- |
| VIN-NBV | RRI directly targets reconstruction-quality improvement and is stronger than coverage-only utility in its setting. | Keep target-root-normalized RRI as the label/evaluation target; do not demote to coverage, entropy, or information gain. |
| CORAL | Ordinal prediction can preserve ordered RRI-bin structure for the myopic scorer. | Calibrate predicted bins/probabilities; do not pretend ordinal confidence is oracle certainty. |
| Double DQN | Max backups over noisy estimates overestimate values; decoupling action selection and action evaluation reduces this bias. | Use masked Double-Q backups for finite candidates and report predicted `Q_H` versus oracle-rescored returns. |
| CQL | Offline conservatism can lower unsupported action values and guard against out-of-distribution actions. | It is an ablation for weak support; hard validity masks and behavior/support diagnostics stay primary. |
| IQL | Expectile value learning avoids querying arbitrary out-of-sample actions and can stitch in-support trajectory parts. | Use only after finite-candidate supervised/Double-Q evidence exists; do not replace the simpler `Q_H` baseline first. |
| SCONE | Occupancy-weighted visibility and camera-history directions are useful support/coverage features. | Use as actor-visible support diagnostics, not target-RRI reward replacement. |
| FisherRF | Fisher information gives an uncertainty/information-gain view of active selection. | Use as an uncertainty/support channel or radiance-field bridge, not the thesis objective. |

### Value-Head Contract

The value stack should be decomposed into separately testable outputs:

```text
valid_mask(i)         hard mask from candidate/target protocol
r_abs(i)             calibrated one-step target-RRI estimate
support(i)           actor-visible support / behavior-policy diagnostics
u_diag(i)            uncertainty, Fisher, coverage, or disagreement diagnostics
A_H(i)               finite-horizon residual advantage over valid rows
Q_H(i)               r_abs(i) + V_H + A_H(i) - mean_valid(A_H)
```

This prevents a common failure mode: a larger model improves aggregate action
choice by learning invalidity, support, or uncertainty shortcuts, while the
target-RRI value estimate itself remains uncalibrated.

### Calibration And Support Tests

| Test | What to compute | Failure interpretation |
| --- | --- | --- |
| one-step reliability | predicted RRI bin/probability versus oracle target-RRI bins, ECE/Brier/top-k hit/rank correlation | myopic scorer is not safe as the `Q_H` residual base |
| ordinal monotonicity | bin thresholds and expected RRI are ordered and stable across splits | CORAL-style head is being used as opaque classification |
| Double-Q overestimation | predicted `max_i Q_H(i)` versus oracle-rescored return for the selected action | bootstrapped values are optimistic or unstable |
| support-stratified value | report metrics by behavior support, candidate family, target support, EVL extent, and valid-count strata | aggregate gains hide out-of-support failures |
| invalid firewall | invalid rows get masks/reasons and cannot affect valid backups or valid-row means | learned penalties are leaking into the reward target |
| uncertainty disagreement | compare uncertainty/Fisher/coverage channels against target-RRI residual errors | uncertainty is diagnostic only if it predicts failure, not if it substitutes for reward |
| offline bridge ablation | compare supervised `Q_H`, masked Double-Q, CQL-style conservative penalty, and IQL-style expectile value only after data support is reported | offline RL method choice is otherwise architecture theater |

### Recommendation

The first thesis-grade architecture should be:

1. calibrated one-step target-RRI scorer with ordinal/reliability plots;
2. residual-dueling finite-candidate `Q_H` with hard masks;
3. masked Double-Q target construction for bootstrapped rows;
4. support and uncertainty channels logged as diagnostics and optional features;
5. CQL/IQL as controlled ablations only if the supervised/Double-Q baseline is
   support-limited or overoptimistic.

Do not use uncertainty as an exploration bonus in the offline result. Do not use
coverage or Fisher information as the reward. Do not replace invalid masks with
scalar penalties. The thesis claim should be that the architecture estimates
target-RRI value under explicit validity/support contracts, and then reports
where uncertainty/support explain successes or failures.

## Iteration 20: Semantic Target-Descriptor Boundary

The next architectural risk is semantic leakage. ARIA-NBV needs target descriptors
rich enough to condition `Q_H`, but not so rich that GT object annotations,
oracle crops, or future semantic world models become hidden actor inputs. The
current owner surfaces already define the split: V0 may use GT OBBs only as a
sanity/upper-bound path; V1 uses observed or predicted target descriptors under
OBS-SEL / PRED-Q / GT-EVAL, with GT OBBs and target meshes restricted to matching,
labels, and evaluation.

### Source Transfer

| Source | Useful idea | ARIA-NBV boundary |
| --- | --- | --- |
| Project Aria | Egocentric sensor records, MPS trajectories, calibration, and semi-dense point clouds are actor-visible substrate. | Treat Aria modality provenance as the visibility boundary; do not invent dense RGB-D or semantic state that is unavailable in the logged/counterfactual actor state. |
| EFM3D / EVL | Lifted image features, voxel evidence, OBB predictions, class probabilities, confidence, and support are natural V1 target descriptors. | Predicted OBBs are noisy actor-visible hypotheses, not GT objects; report false positives, missed objects, sim-to-real failures, and local-volume limits. |
| Instance-NBV / Object-centric NBV | Instance/object masks and object confidence can focus NBV on task-relevant regions and expose exploration/exploitation imbalance. | Use object confidence and mask quality as target-support diagnostics or ablations; do not replace target-RRI with semantic-aware information gain. |
| SceneScript | Structured commands show how grounded scene/entity tokens can represent layouts, object boxes, and coarse object primitives. | Keep semantic-global memory as RQ6/future bridge unless generated tokens are actor-visible, validated, and matched under OBS-SEL/PRED-Q/GT-EVAL. |
| `.agents/work` target-selection reviews | Target selection and GT matching are different operations; unmatched, unsupported, or ambiguous targets are invalid rows. | Do not train low-RRI labels on target-invalid rows; record selector/source/match reason codes in rollout and evaluation tables. |

### Descriptor Ladder

| Rung | Actor-visible descriptor | Use first when | Required tests |
| --- | --- | --- | --- |
| T0 | observed/predicted OBB geometry, class distribution, confidence, projected area, relative pose, semidense support, EVL support | first V1 scorer and `Q_H` baseline | target coverage, match rate, ambiguity gap, support bins, class/source stratification |
| T1 | compact crop descriptor from actor-visible predicted/observed crop only: pooled EVL/voxel features, semidense point stats, or compressed DINO point tokens | T0 ranking is weak but target matches are valid | no GT-crop read, no GT-mesh read, crop-source provenance, ablation against OBB-only |
| T2 | object-confidence/support channel inspired by Instance-NBV | target support is sparse or semantics explain residual errors | object-confidence versus target-RRI residual, mask-quality failure report, no reward substitution |
| T3 | grounded entity/region/portal token inspired by SceneScript or semantic-global planners | offline `Q_H` evidence is stable and RQ6/future bridge is active | generated-token provenance, verifier/replanner loop, GT-token exclusion, fallback to geometric controller |

This ladder prevents the model from hiding a target-selector problem inside a
larger semantic encoder. T0 proves the basic target protocol. T1 tests whether
actor-visible crop evidence adds useful local appearance/geometry. T2 asks
whether semantic confidence explains failures. T3 is not a thesis-core
architecture unless the project explicitly escalates to semantic-global planning.

### Failure Modes To Report

| Failure | What it means | Correct response |
| --- | --- | --- |
| low V1 target coverage | observed/predicted targets rarely clear eligibility | report validated subsets or improve selector/support gates before `Q_H` claims |
| ambiguous GT match | one actor-visible target maps to multiple GT objects, or vice versa | mark target-invalid or apply a named advisor-approved tie rule; do not create a low-RRI sample |
| class/source drift | EVL class probabilities or tracked OBBs fail by class, source, or scene split | stratify results and keep GT labels out of actor input |
| semantic shortcut | semantic class/source predicts gains while geometry/candidate evidence is ignored | add class/source holdout and OBB-only/crop-only ablations |
| crop leakage | crop descriptor reads GT OBB, GT mesh, or oracle render outputs | invalidate the V1 run; it is V0/privileged evidence only |

### Architecture Recommendation

The first thesis-grade target descriptor should stay boring: predicted/observed
OBB geometry, class probabilities, confidence, projected visibility, semidense
support, EVL support, and relative pose. Add a compact actor-visible crop
descriptor only after the OBB-only path has a clean coverage and matching report.
Treat Instance-NBV-style object confidence as a diagnostic/support channel, not
as a reward. Treat SceneScript-style structured semantics as a future grounded
memory interface, not as current `Q_H` input.

The thesis should explicitly claim:

> `Q_H` conditions on actor-visible target hypotheses. GT target annotations
> assign labels and evaluate outcomes; they do not define the main actor input.

That sentence should be tested in code and documentation by field provenance:
every target feature used by the scorer or `Q_H` needs a source mode, selector
rank, support fields, and GT-match status kept outside the actor feature tensor.

## Iteration 21: Acquisition Curves And Greedy Headroom Baselines

The next evaluation risk is overclaiming a single endpoint table. The local
roadmap already says that bounded oracle lookahead must be compared against
one-step greedy under equal acquisition and candidate budgets. The NBV coverage
literature adds a useful reporting pattern: plot the full acquisition curve,
not only the final view. The transfer is the reporting discipline, not the
objective. ARIA-NBV should report target-RRI acquisition curves while keeping
endpoint target gain primary and treating coverage/Fisher curves as diagnostics
or proxy baselines.

### Source Transfer

| Source | Useful idea | ARIA-NBV boundary |
| --- | --- | --- |
| SCONE | Report surface-coverage evolution and AUC across sequential NBV choices; compare convergence speed as well as final coverage. | Use the curve/AUC reporting pattern for target endpoint gain and root-normalized target return; do not replace target-RRI with surface coverage. |
| MACARONS | Average coverage curves over matched starting poses and report AUC after a fixed number of iterations. | Pair ARIA policies by root snippet, target, seed, horizon, candidate count, candidate profile, and validity constraints. |
| Hestia | Close-greedy/coverage results warn that future-return labels can create misleading current-action associations. | Keep one-step greedy as a serious control and diagnose whether multi-step labels add real target headroom before adding model complexity. |
| VIN-NBV | Reconstruction-quality scoring can beat coverage-max policies when the quality metric is the target. | The thesis objective remains target point-mesh improvement, with coverage and uncertainty as support/proxy diagnostics. |
| Submodular / adaptive submodular NBV lineage | Greedy baselines are theoretically important for coverage-like monotone objectives. | Do not claim submodular approximation guarantees for target-RRI: invalid masks, target matching, candidate regeneration, occlusion, and state-dependent root-normalized errors break the simple set-function story unless separately proven. |

### Target Acquisition Curve

For each policy `pi` and paired root/target, record the target endpoint-gain
curve over the selected-view budget:

```text
G_e^pi(k) = (Delta_e(P_0) - Delta_e(P_k)) / (Delta_e(P_0) + eps),
            k = 0..H.
```

The endpoint value `G_e^pi(H)` stays the primary thesis quality metric because
it matches the fixed-budget target outcome. A curve-AUC companion reports
convergence speed:

```text
AUC_e^H(pi) = (1 / H) * sum_{k=1..H} G_e^pi(k).
```

The oracle lookahead gap should be reported for both endpoint and AUC:

```text
Delta_look_end = G_e^{oracle-look}(H) - G_e^{oracle-1}(H)
Delta_look_auc = AUC_e^H(oracle-look) - AUC_e^H(oracle-1).
```

The learned recovery fraction is useful only when the denominator is positive:

```text
eta_Q_auc =
  (AUC_e^H(pi_Q) - AUC_e^H(pi_learned-1))
  / (AUC_e^H(oracle-look) - AUC_e^H(pi_learned-1) + eps).
```

This makes myopic adequacy visible. If the curves for one-step oracle greedy
and bounded oracle lookahead are nearly identical, the correct result is a
negative planning-headroom finding for that target set, candidate profile, and
horizon.

### Policy Curve Table

| Policy | Curve role | Interpretation |
| --- | --- | --- |
| random-valid | support floor | Shows whether valid candidate support alone improves targets and exposes invalidity/candidate-collapse regimes. |
| learned one-step scorer | deployable myopic control | Tests whether actor-visible features can recover immediate target utility without GT at decision time. |
| one-step oracle greedy | supervised myopic upper reference | Measures how much the candidate distribution and immediate oracle labels can do before non-myopic planning. |
| bounded oracle lookahead | non-myopic headroom upper bound | Estimates whether the target/candidate distribution has multi-step value before training `Q_H`. |
| `pi_Q` | learned finite-horizon recovery | Must be oracle-rescored; predicted values alone are not evidence. |
| coverage/Fisher/SCONE/MACARONS-style proxy | diagnostic/proxy comparator | Useful only to show proxy alignment or mismatch against target-RRI; not a replacement objective. |

Every row should expose endpoint gain, AUC, scene RRI, target support, valid
counts, invalidity reason rates, candidate-family selections, path/runtime, and
oracle evaluation count. Policy curves should be stratified by target support,
target-selector confidence, candidate profile, valid-count bin, scene, and
class/source where those fields exist.

### Submodularity Critique

The thesis should avoid the easy but wrong sentence "greedy is near-optimal by
submodularity" unless the evaluated ARIA target-RRI objective is actually shown
to be monotone submodular under the candidate-generation process. The current
objective is not a static coverage set function. It includes target matching,
invalid masks, actor-visible support, oracle-only labels, selected-view state
updates, candidate regeneration, occlusion, finite-horizon transitions, and
root-normalized target errors. These mechanisms can produce non-monotone or
non-diminishing returns.

Use submodular NBV papers as a control lineage and as motivation for greedy
baselines, then run empirical greedy-adequacy checks:

- plot marginal target gains by step for one-step greedy and lookahead;
- report whether lookahead improves early actions, endpoint gain, or only AUC;
- compare coverage/Fisher marginal gains against target-RRI residuals;
- flag target/candidate regimes where greedy and lookahead tie;
- do not promote `Q_H` architecture complexity when oracle lookahead itself has
  no measurable gap.

### Architecture And Data Implications

The model contract becomes simpler, not more complex:

1. train and calibrate the one-step target scorer;
2. measure oracle-greedy and oracle-lookahead curves under matched roots;
3. train `Q_H` only when a positive gap exists for a named candidate profile;
4. oracle-rescore the selected `Q_H` actions to obtain actual curves;
5. explain failures through support, invalidity, target matching, and proxy
   mismatch before escalating model capacity.

The rollout/evaluation store should include per-step target error, endpoint
gain, root-normalized immediate gain, cumulative root-normalized return,
state-relative target-RRI diagnostic, scene-RRI diagnostic, valid-row count,
invalidity reasons, selected candidate id, policy id, candidate profile, seed,
horizon, and candidate-table lineage.

### Thesis Wording Recommendation

The evaluation chapter should say:

> We compare policies as target-RRI acquisition curves under identical roots,
> targets, candidate budgets, horizons, and validity masks. Endpoint gain is the
> primary fixed-budget result; AUC is a convergence-speed companion. Greedy and
> bounded oracle lookahead are empirical headroom controls, not formal
> submodularity claims for the ARIA target-RRI objective.

That wording keeps the literature benefit from SCONE/MACARONS-style curves while
preserving the current ARIA source order: target endpoint gain and cumulative
root-normalized target return own the thesis metric; coverage and uncertainty
remain diagnostics or ablations.

## Iteration 22: Rollout Store And Feature-Cache Contract

The next architecture risk is treating all data products as one blob. The live
implementation now owns more of the replay contract than older work notes imply:
`rollouts.zarr` is a standalone replay store with source, target, rollout,
lineage, step, candidate, diagnostic, selected-depth, target-eval-crop, and
derived `q_h/` groups. The critique should therefore shift from "build the
store" to "separate fact tables, derived training views, audit-heavy payloads,
and future feature banks."

### Source Reconciliation

| Source | Current evidence | Architecture implication |
| --- | --- | --- |
| `aria_nbv/aria_nbv/rollouts/zarr_store.py` | Defines schema metadata, candidate/step/target/source tables, invalidity masks, selected-depth and target-eval-crop groups, a validated `q_h/` view, and checks that `q_train_mask` is a subset of valid actions. | Treat `rollouts.zarr` as the canonical replay data product for selected-action transitions and finite-candidate `Q_H` rows. |
| `aria_nbv/aria_nbv/rollouts/dataset_writer.py` | Writes standalone rollout stores from VIN/offline roots, actor-visible targets, mixed candidate tables, target scoring, selected depth, lineage, and recipe policies such as random-valid, oracle-greedy, oracle-lookahead, and temperature-softmax. | Planning evidence should be generated by replayable rollout recipes, not by ad hoc notebook traces. |
| `aria_nbv/aria_nbv/data_handling/README.md` | Documents two-store separation: immutable VIN offline samples stay in the VIN store, while counterfactual rollouts live in standalone `rollouts.zarr`. | Do not embed multi-step counterfactual traces into immutable VIN offline stores. |
| `.agents/work/target-selection-sampling/02-review-gpt55pro.md` | Recommends `training_core` versus `audit_heavy` retention profiles and warns against persisting target-eval crops by default at thesis scale. | Model training should consume compact replay fields first; expensive crops and rendered artifacts belong to audit profiles. |
| `.agents/work/rollout-scale-readiness/03-rollout-generation-preflight-plan.md` | Specifies a desired production preflight JSON with schema, validation, lineage, coverage, validity, rewards, retention, storage, and go/no-go sections. | The current CLI has `--validate`, `--stats`, and `--random-index`; the production `--preflight --profile production --json` gate remains planned work. |
| `.agents/work/scene-encoding-efm-backbone/01-evl-critique-directions-gpt55pro.md` | Proposes `feature_lift_v1.zarr` with point positions, observation counts, uncertainty, DINO/CLIP/depth features, frame ids, and target/candidate/frustum query pools. | Keep point-attached feature caches as a separate representation artifact until ownership, schema, joins, and consumer tests exist. |
| `.agents/references/rollout_zarr_q_invalidity_contract.md` | Labels itself as a draft contract and warns that it is not evidence of writer behavior. | Reconcile this draft against live code and README before citing it as current truth. |

### Data-Product Boundary

| Product | Owns | Does not own |
| --- | --- | --- |
| `sources/`, `targets/`, `rollouts/`, `lineage/` | VIN source identity, target protocol, rollout recipe identity, config/source hashes, GT-match metadata for labels/evaluation, and scene/split provenance. | Actor-visible model tensors that silently include GT match fields. |
| `steps/` and `candidates/` | Candidate poses, masks, invalid reasons, strategy/profile provenance, selected candidate ids, target/scene RRI diagnostics, root gains, support metrics, and cumulative returns. | Unselected future observations as actor input. |
| `selected_depth/` | Selected-action successor evidence and visual/audit history for the action actually taken. | All-candidate oracle render banks. |
| `target_eval_crops/` | Audit-heavy label/evaluation crops when explicitly retained. | Default thesis-scale training payload. |
| `q_h/` | A dense derived training/cache view over candidate facts, valid masks, train masks, selected transitions, TD rewards, next-step ids, terminal masks, and discounts. | Source-of-truth facts; it should be reproducible from the replay tables and validation rules. |
| `feature_lift_v1.zarr` or successor | Future actor-visible support/feature bank for DINO@point, uncertainty, frame ids, target/candidate/frustum pools, and directional novelty. | Rollout replay ownership or privileged target labels. |

This boundary suggests three retention profiles:

- `training_core`: source/target ids, candidate pose and local-frame features,
  masks, invalid reasons, strategy/profile ids, support counts, target-root
  gain, selected action, TD arrays, and lineage hashes.
- `audit_heavy`: `training_core` plus selected-depth artifacts,
  `target_eval_crops/`, Rerun-friendly diagnostics, and policy comparison
  traces.
- `feature_bank`: point/voxel feature caches with their own manifest, source
  ids, frame ids, compression version, and consumer tests.

The first `Q_H` architecture should consume `training_core` plus explicitly
approved actor-visible feature-bank joins. It should not depend on
`target_eval_crops/`, GT-match fields, or unselected candidate renders. If
selected-depth history is used, it must be named as selected successor history
and tested for leakage.

### Store Gaps Before Thesis-Scale Claims

The store is no longer a blank slate, but four gaps still matter:

1. **Production preflight.** `nbv-rollouts-info` currently supports manifest,
   validation, stats, and random-index inspection. The richer production
   preflight profile with go/no-go thresholds, stale-schema detection, storage
   budgeting, scene-split purity, reward flatness, and retention enforcement is
   still a planned gate.
2. **Collection-level scale layer.** Individual stores validate, but thesis
   reporting still needs a collection-level manifest that aggregates shards,
   scene splits, profile names, source-row coverage, target counts, candidate
   profiles, and storage/chunk budgets.
3. **Feature-cache ownership.** `feature_lift_v1.zarr` is a good next artifact
   for compressed point-attached descriptors, but it must stay separate from
   rollout replay until its schema, join keys, compression, and reader tests are
   explicit.
4. **Invalidity parity.** Candidate hard masks, target-invalid rows,
   selected-depth failures, and target-eval-crop failures need one consistent
   reason-code story across writer, validator, inspector, preflight, and model
   training masks.

### Architecture Consequences

The replay store should constrain the model design:

- The independent one-step scorer and early `Q_H` heads should be trainable
  from fact tables and `q_h/` without audit-heavy payloads.
- The `q_h/` group is a regenerated cache. If it disagrees with `steps/` and
  `candidates/`, validation should fail rather than letting training choose a
  convenient version.
- Candidate/profile fields should be reported as experimental variables, not
  hidden inside config hashes only.
- Feature-bank joins should be explicit inputs with ablation names such as
  geometry-only, geometry plus compressed DINO, target-crop pool, candidate
  frustum pool, target-frustum intersection pool, and directional novelty pool.
- If the model needs all-candidate oracle render features to work, that is a
  privileged-teacher or audit result, not the V1 actor-visible thesis claim.

### Thesis Wording Recommendation

The method chapter should say:

> We separate replay facts, derived training caches, audit payloads, and future
> feature banks. `rollouts.zarr` owns selected-transition and candidate-table
> facts; `q_h/` is a validated derived view for finite-candidate value learning.
> Actor-visible feature caches may be joined only through explicit, tested
> provenance. Privileged crops, GT matches, and all-candidate oracle renders are
> label or audit surfaces, not V1 actor inputs.

That wording aligns the thesis with the current code while preserving the
remaining scale work: production preflight, collection manifests, feature-cache
ownership, and invalidity parity.

## Iteration 23: Geometric Invariance Test Matrix

The geometric-ML section should not merely list DeepSets, Set Transformer,
QCNet-style RPE, EGNN, SE(3)-Transformer, and spherical harmonics. It should
state the transformation contract for ARIA-NBV and make every claimed symmetry
testable. The relevant literature agrees on the principle but not on the
specific group: DeepSets/Set Transformer supply permutation structure; QCNet
motivates query-local relative encodings; EGNN and SE(3)-Transformer show exact
equivariance mechanisms; the SE(3)-Transformer ScanObjectNN result warns that
full rotation invariance can hurt when gravity/up is informative; and the local
ARIA frame/CW90 gotchas show that display conventions and physical camera
frames must not be conflated.

### Symmetry Claims To Test

| Object | Transformation | Expected behavior | Not a required symmetry |
| --- | --- | --- | --- |
| Candidate rows | Permute rows of `X`, mask, reasons, candidate ids, and labels together. | Per-candidate scores and `Q_H` values permute in the same way; unpermuted outputs match within tolerance. | Any dependence on file/Zarr row order. |
| Padded or invalid rows | Insert invalid/padded rows with hard masks and reason codes. | Valid-row scores, argmax, losses, bootstrap targets, and calibration are unchanged except for explicitly modeled valid-count features. | Treating invalidity as low RRI. |
| Duplicate candidate row | Duplicate a valid candidate while keeping the original candidate row identifiable. | The original row's immediate score stays stable; rank/top-k changes are reported as attention-normalization diagnostics. | Exact duplicate invariance as a hard physical law for finite-horizon `Q_H`, because future branch support can depend on sampled candidates. |
| Global translation | Translate camera, target, support points, and candidate poses consistently. | Scalar target utility and candidate ranking are unchanged when only coordinate origin changes. | Translation of only candidate poses or only target metadata. |
| Global yaw about gravity | Rotate the whole scene, candidate table, selected history, target descriptor, and support features around the gravity axis. | Local-frame features and scalar values should match when the same physical problem is represented in a different horizontal frame. | Erasing gravity/up or pitch/elevation signals. |
| Full `SO(3)` rotation | Rotate the whole problem by arbitrary 3D rotation. | Use only as a diagnostic for exact-equivariant ablations; the default actor should not be forced to ignore up, floor, gravity, camera pitch, or rig conventions. | Claiming full rotation invariance for ARIA scenes. |
| CW90/display convention | Apply display-frame corrections only in visualization/rendering paths while physical camera/pose tensors stay in the documented frame. | Model-facing features, labels, and backprojection results are unchanged by display-only rotations. | Rotating candidate poses, cameras, or render references independently. |
| Target-local gauge | Re-express candidate, history, and support relations in the target or query candidate frame. | Relative encodings should be stable to global frame choice while preserving target orientation and support semantics. | Treating target identity, GT match status, or crop labels as actor-visible geometry. |
| Directional visibility on `S^2` | Rotate target-local observed directions and candidate direction together. | Second-moment memory transforms as `M -> R M R^T`, and novelty scalars remain stable after consistent rotation. | Assuming a bag of rotations or history frames is permutation-invariant in time. |
| Candidate-family mixture | Change candidate generator mixture proportions or candidate profile. | Robustness is reported by profile and valid-count strata. | A symmetry; this is a distribution-shift stress test. |
| Selected history | Keep selected-view history in temporal/causal order. | Recurrent/history encoders may be order-sensitive; only per-step support-point pools can be set-invariant. | Shuffling selected actions as if they were candidate rows. |

This matrix clarifies "respect geometric isomorphisms": the scalar decision
should be invariant to coordinate gauge changes, equivariant to candidate row
permutations, and sensitive to physical signals such as gravity, camera
frustum, target support, validity, and selected history.

### Architecture Stage Acceptance

| Stage | Required geometric tests before claim | Failure interpretation |
| --- | --- | --- |
| Independent scorer | local-frame translation/yaw consistency, CW90 isolation, invalidity firewall, support/target provenance audit. | Feature construction is wrong; do not add set attention yet. |
| DeepSets context | row-shuffle equivariance, valid-count calibration, duplicate-row stress, mask isolation. | The pooled context is leaking row order or candidate-count artifacts. |
| Masked Set Transformer | all DeepSets tests plus padded-row isolation and attention-mask audit. | Attention implementation is not safe for variable-width candidate tables. |
| QCNet-style RPE | target/query-local transform consistency, candidate-to-candidate relation symmetry, relative-pose ablation against raw world pose. | The model is learning frame shortcuts rather than geometric relations. |
| Directional memory | second-moment rotation consistency, selected-history-only provenance, SH-vs-moment ablation. | Directional features are either frame-broken or not adding target-specific observability. |
| EGNN / SE(3) ablation | exact synthetic equivariance checks under translation/rotation/reflection for the ablation's declared group. | The ablation does not deserve an "equivariant" claim; fall back to scalar local-frame features. |
| Point/sparse backbone | point-order stress, local-neighborhood radius sensitivity, source/frame lineage, feature-cache join tests. | Representation cost is hiding storage or frame bugs. |

The thesis should report an "architecture cannot be interpreted" blocker if a
candidate-set model improves validation loss but fails row-shuffle or mask
isolation. Likewise, an equivariant ablation that fails its synthetic transform
check should be described as a geometry-informed model, not an equivariant one.

### Test Metrics And Fixtures

For a fixed batch, define transform diagnostics:

```text
delta_perm = max_i |unpermute(f(P X))_i - f(X)_i|
delta_mask = max_i_valid |f(X plus invalid rows)_i - f(X)_i|
delta_frame = max_i |f(T_gauge X)_i - f(X)_i|
top1_stable = argmax_valid(f(T X)) == transformed_argmax_valid(f(X))
rank_tau = KendallTau(f(T X), transformed(f(X)))
```

Use strict numerical tolerances for deterministic feature transforms and looser
ranking/calibration tolerances for learned stochastic models. Every test should
log the transformation, affected fields, mask width, valid count, candidate
profile, target source, scene id, and model stage.

The fixture ladder should start synthetic and then use real rollout rows:

1. synthetic tiny candidate tables with known masks, duplicates, and row
   permutations;
2. synthetic pose/target/support triples under translation and yaw transforms;
3. real `rollouts.zarr` batches with row-shuffle, padded invalid rows, and
   candidate-family perturbations;
4. selected-history rows with second-moment directional memory checks;
5. optional exact-equivariance fixtures for EGNN/SE(3)-style ablations.

### Literature Transfer

| Source | Transfer | Boundary |
| --- | --- | --- |
| Geometric Deep Learning | Define the domain, transformation group, signal, and desired invariant/equivariant output before choosing the architecture. | The group is task-specific; do not import `SE(3)` invariance wholesale. |
| Deep Sets | Permutation invariance/equivariance is the minimum structure for candidate sets. | Pooled invariant summaries cannot replace per-candidate `Q_H` outputs. |
| Set Transformer | Attention can model set interactions while preserving permutation structure when masks are correct. | Unmasked attention over padded/invalid rows invalidates the claim. |
| QCNet/QCNeXt | Query-centric local frames and relative positional encodings avoid global-coordinate shortcuts. | Motion-forecasting decoder, lane/agent priors, and trajectory losses stay outside the thesis core. |
| EGNN | Relative distances and relative coordinate updates provide a lightweight exact equivariance ablation. | Exact `E(n)` equivariance may erase useful gravity/up or camera-frame signals if used as the default. |
| SE(3)-Transformer | Equivariant attention can be checked by equivariance error; ScanObjectNN shows that supplying up/gravity can help when the data are gravity-aligned. | Full `SO(3)` invariance is not a free improvement for ARIA. |
| e3nn spherical harmonics | Low-order SH is a principled ablation for richer `S^2` directional memory. | The second-moment memory is the thesis-safe baseline until angular detail is proven useful. |

### Thesis Wording Recommendation

The method chapter should say:

> We do not assume that stronger equivariance is always better. We first define
> which transformations are coordinate gauges and which are physical signals.
> Candidate rows require permutation equivariance; target/candidate geometry is
> encoded in local frames; gravity, frustum, validity, and selected history are
> preserved as task signals. Exact equivariant modules are ablations that must
> pass synthetic transform checks and improve oracle-evaluated target outcomes
> over simpler local-frame models.

This makes the planned geometric-invariance section a falsifiable method
contract. If the tests fail, the fix is not a larger model; it is to repair
feature construction, masks, frame transforms, or candidate support first.

## Iteration 24: Query-Centric Descriptor Schema

The phrase "QCNet-style descriptor" is too vague unless it is reduced to a
field contract. The transferable idea is query-centric relative encoding:
represent each relation from the perspective of the query candidate and use
that relation as an attention edge or bias. The non-transferable parts are
motion-forecasting trajectory decoders, lane/agent priors, scene likelihood
scores, DETR-style proposal matching, and streaming claims.

The current VIN pose encoder provides a useful control: it encodes a pose in a
chosen reference frame as translation plus continuous 6D rotation through
learnable Fourier features. The planned `Q_H` descriptor should keep that
simple control and add query-centric relations as a staged ablation, not replace
all pose features at once.

### Descriptor Blocks

| Block | Fields to include first | Fields to exclude from V1 actor input |
| --- | --- | --- |
| Candidate self token | candidate pose in a documented reference frame, target-relative translation, optical-axis/target-bearing features, gravity/up and pitch/elevation scalars, path increment, strategy/mixture/profile ids, valid mask, invalid reason. | row index as semantics, hidden config hash as a feature, raw world pose without frame tag, unselected oracle depth/render features. |
| Actor-visible target token | observed/predicted OBB center, extents, orientation, class probabilities, confidence, source mode, selector rank, projected visibility, semidense support, EVL support, target-interest score components. | GT OBB, GT mesh, GT crop, GT-match id/status as input, label-valid mask as input. |
| Candidate-target relation | candidate-frame target center, target-frame candidate center, target bearing/elevation, incidence proxy, distance, expected crop/frustum intersection, target support deficit. | GT target crop geometry or target-RRI label fields. |
| Candidate-candidate RPE | `delta_p[j,i] = R_i^T(p_j - c_i)`, distance, bearing/elevation, relative rotation/log or R6D, overlap/support relation, same-family/profile relation, both-valid relation. | order-based positional encoding or sequence index. |
| Candidate-history RPE | relative pose from candidate to selected views, last selected action, selected-view support summaries, remaining budget/time-to-go, selected-depth provenance. | unselected candidate render history. |
| Directional memory | target-local second-moment or coarse directional histogram, candidate directional novelty, support weights, optional low-order SH coefficients. | treating RPE as a persistent visibility memory or summing R6D rotations as observation history. |
| Feature-bank joins | target/frustum/intersection pooled actor-visible features keyed by source row, target id, candidate id, frame ids, cache schema, and compression version. | implicit joins to feature caches without provenance and leakage tests. |

This split is important because RPE and directional memory answer different
questions. RPE asks "where is token `j` relative to candidate `i`?" Directional
memory asks "from which directions has this target-local support already been
observed?" They should be logged and ablated separately.

### Candidate-Local RPE Contract

For a query candidate `i` with camera center `c_i` and rotation `R_i`, encode a
context item `j` in the query frame:

```text
delta_p[j,i] = R_i^T (p_j - c_i)
delta_R[j,i] = R_i^T R_j
edge_ij = phi_rel(delta_p[j,i], delta_R[j,i], distance_ij,
                  bearing_ij, elevation_ij, overlap_ij, mask_pair_ij)
```

`edge_ij` may be concatenated to key/value features or added as an attention
bias. It should be computed for candidate-candidate, candidate-target,
candidate-history, and candidate-support relations only when the corresponding
source is actor-visible. For continuous features, the first implementation can
use MLP or learned Fourier encodings; exact Lie-log maps and EGNN-style updates
are ablations after the local-frame baseline is correct.

The descriptor should keep three frame choices explicit:

1. **root/current frame:** useful for comparison with implemented VIN controls;
2. **target frame:** useful for target-local support and directional memory;
3. **query candidate frame:** useful for candidate-local attention relations.

Raw world-frame pose should be a controlled ablation or a physical prior with a
named reason. It must not silently be the strongest feature.

### Ablation Ladder

| Stage | Descriptor | Purpose |
| --- | --- | --- |
| D0 current pose control | `R6dLffPoseEncoder` on pose expressed in a documented reference frame. | Keep the implemented VIN-style geometry baseline and verify the label path. |
| D1 scalar local descriptor | target-relative translation, distance, bearing/elevation, optical-axis alignment, gravity/up, pitch, path cost, support counts, masks/reasons. | Test whether explicit geometry scalars beat raw pose embeddings. |
| D2 RPE-enhanced Set Transformer | D1 plus candidate-candidate, candidate-target, and candidate-history edge encodings in the query candidate frame. | Test QCNet-style relation transfer without importing trajectory decoding. |
| D3 support-overlap bias | D2 plus Fisher/SCONE-style target/frustum/intersection overlap channels. | Test whether attention needs information-overlap priors. |
| D4 directional-memory add-on | D2 or D3 plus `S^2` second-moment novelty, then optional histogram/SH. | Test whether selected-view angular history improves endpoint target gain. |
| D5 exact geometry ablation | EGNN or SE(3)-style candidate/target/history graph. | Test whether exact equivariance improves over local-frame scalar/RPE descriptors. |
| D6 feature-bank descriptor | compressed point/voxel feature pools joined through an explicit feature-cache schema. | Test whether richer actor-visible scene evidence, not just pose relations, is the bottleneck. |

Do not proceed from D0 to D5 as a single "bigger architecture" jump. Each stage
should keep the same rollout rows, masks, target protocol, and oracle rescoring
budget so the gain can be attributed.

### Anti-Shortcut Tests

| Shortcut risk | Test |
| --- | --- |
| Raw world-pose shortcut | Compare raw-world pose, root-local pose, target-local pose, and query-local RPE under matched splits and gauge transforms. |
| Strategy/provenance shortcut | Train with and without strategy/mixture/profile ids; report per-family performance and selected-action distribution. |
| Row-order leakage | Shuffle rows, insert padded invalid rows, duplicate rows, and verify unpermuted predictions. |
| GT target leakage | Drop all GT-match, GT-label-valid, target crop, and oracle fields from the actor tensor; assert feature schemas exclude them. |
| RPE/memory conflation | Ablate RPE without directional memory and directional memory without RPE. |
| Frame-convention drift | Use `PoseTW`/`CameraTW` paths and explicit frame tags; reject derived caches that cannot be regenerated from stored world/root poses. |
| Scene-id memorization | Stratify by scene/source split and remove opaque scene ids from model input unless explicitly testing domain priors. |

### Implementation Rule

Store canonical poses and identifiers first, derive descriptors later:

```text
canonical rows:
  source_row_id, target_row_id, candidate_row_id
  pose_world_cam or documented PoseTW
  target actor-visible pose/OBB/source/support fields
  candidate mask/reason/provenance

derived descriptor cache, optional:
  frame_tag
  target_local_features
  candidate_query_rpe
  directional_memory_features
  feature_schema_hash
```

If training speed requires cached RPE arrays, the cache must record the frame
definition and source row hashes so it can be invalidated. Otherwise, derive
relative features in the reader to avoid stale descriptor schemas.

### Thesis Wording Recommendation

The method chapter should say:

> Our "QCNet-style" component is limited to query-centric relative positional
> encoding: candidate attention receives pairwise local-frame relations between
> candidates, target descriptors, selected history, and support pools. It is not
> a trajectory decoder, scene scorer, or streaming motion-forecasting model.
> We compare this descriptor against an implemented R6D/LFF pose control,
> explicit scalar local geometry, support-overlap bias, and directional-memory
> ablations under the same masked rollout rows.

This phrasing gives the thesis a concrete descriptor story and prevents the
architecture section from drifting back into a list of fashionable modules.

## Iteration 25: Deja View Recurrence Budget

Deja View should be used as a compute-depth and diagnostic template, not as a
new default planner. Its useful claim is narrow: a shared block can refine an
internal multi-view representation for a bounded number of trained steps, and
the number of refinement steps can become an inference-time compute knob within
that trained range. ARIA-NBV should not convert that into "more recurrence means
more NBV planning" or "loop until convergence."

### Separate The Four Depth Axes

| Axis | Meaning in ARIA-NBV | Must not be confused with |
| --- | --- | --- |
| `H` | acquisition horizon: number of selected candidate views in a rollout. | internal neural refinement steps. |
| `K` | recurrence/refinement steps inside a model for a fixed state and candidate table. | extra environment interaction or oracle render calls. |
| `N_q` | candidate-table width for a single decision state. | rollout branch count or selected history length. |
| `B` | branch/beam/lookahead width for oracle or behavior-policy rollouts. | Transformer attention heads or recurrent steps. |

The Deja View transfer is about `K`, not `H`, `N_q`, or `B`. A recurrent block
may refine candidate/support/history tokens before producing `Q_H(s_t,q_i)`,
but it does not acquire new views, regenerate candidates, or extend the
planning horizon unless the rollout data product explicitly contains those
transitions.

### What May Recur

| Recurrent state | Allowed evidence | First question |
| --- | --- | --- |
| selected-history support tokens | selected poses, selected-depth summaries, target-local support updates, directional memory. | Does iterative support aggregation improve endpoint target gain over M1/M2 history? |
| candidate-context tokens | candidate self tokens, masks, RPE edges, support-overlap channels, target descriptor. | Does extra compute refine ranking beyond fixed-depth Set Transformer/RPE under the same rollout rows? |
| feature-bank support tokens | compressed actor-visible point/voxel features, target/frustum/intersection pools, frame ids. | Does recurrence help align target support after simple pooling and fixed-depth attention fail? |

It must not recur over unselected candidate renders, GT target crops, all-action
oracle labels, future successor candidate tables, or hidden simulator state.

### Recurrence Gate

Run recurrence only after these gates are positive:

1. the one-step scorer is calibrated and the fixed-depth candidate-set model
   passes row-shuffle, mask, and frame tests;
2. oracle lookahead has positive headroom for the named candidate distribution;
3. selected-history features M1/M2 improve or at least diagnose target-support
   regimes;
4. the rollout store exposes selected-depth and history provenance without
   leaking all-candidate oracle observations;
5. fixed-depth depth-vs-parameter baselines show that model depth or iterative
   support aggregation is plausibly the bottleneck.

If these gates fail, recurrence is likely to hide a data, support, target, or
mask problem.

### Training And Diagnostics

If recurrence is tested, train it as a bounded `K`-elastic ablation:

```text
K_train ~ sampler([K_min, K_max])
K_eval in {K_min, ..., K_max}
K_beyond > K_max only as a failure/generalization diagnostic
```

Report recurrence diagnostics alongside policy metrics:

| Diagnostic | Why it matters |
| --- | --- |
| state norm by step | Deja View shows norm drift can collapse beyond the trained range. |
| relative update norm | Confirms whether steps actually slow/refine or merely rescale. |
| cosine-to-final-state | Detects directional refinement without claiming fixed-point convergence. |
| logit/value delta by step | Shows whether `Q_H` stabilizes or oscillates. |
| top-1/top-3 rank stability | Reveals whether extra `K` changes selected actions. |
| calibration by `K` | Prevents more steps from only inflating predicted values. |
| oracle-rescored endpoint gain by `K` | The only policy-quality evidence that matters. |
| runtime/memory by `K` | Ensures compute knob is worth its cost. |

Compare at least three baselines under matched rollout rows:

- fixed-depth untied blocks with similar compute;
- shared/tied recurrent block;
- smaller fixed-depth model with similar parameter count.

Deja View's own evidence matters here: variable-`K` training covers a trained
range, but pushing inference far beyond that range eventually degrades or
collapses. ARIA should copy the diagnostic honesty, not the scale.

### Failure Interpretation

| Symptom | Interpretation |
| --- | --- |
| validation loss improves, oracle-rescored endpoint gain does not | recurrence is fitting labels or calibration artifacts, not improving decisions. |
| predicted max-Q grows with `K` but selected actions do not improve | value inflation or unsupported-action overestimation. |
| rank oscillates with `K` | recurrent state is unstable for action selection. |
| norm grows monotonically and beyond-range `K` collapses | expected Deja-style drift; do not claim convergence. |
| recurrence helps only with all-candidate render features | privileged-teacher result, not V1 actor-visible evidence. |
| recurrence helps only for one candidate profile | report profile-specific result; do not generalize. |

### Thesis Wording Recommendation

The method/discussion should say:

> Deja View motivates a bounded, weight-tied refinement ablation for
> selected-history and candidate-context tokens. Its refinement count `K` is a
> neural compute budget for a fixed decision state, not an acquisition horizon.
> We evaluate `K` only within the trained range for thesis claims, log
> state/value/rank stability by step, and treat beyond-range behavior as a
> failure diagnostic. The first thesis path remains fixed-depth masked
> candidate-set value learning.

This wording keeps recurrence available as a principled later ablation while
protecting the core thesis from becoming an unbounded recurrent planner.

## Iteration 26: Feature Bank And Point-Backbone Escalation

The next architecture risk is representation over-escalation: replacing a
clear target/candidate query model with a heavy point-cloud backbone before the
feature bank, query pools, and rollout labels are trustworthy. The correct
question is not "which point backbone is best?" It is:

```text
Do compact actor-visible target/frustum/intersection pools leave a measurable
representation bottleneck for target-RRI ranking or finite-candidate Q_H?
```

If the answer is no, Point Transformer, PTv3, KPConv, and Minkowski-style
sparse convolution are architecture noise for the thesis core. If the answer is
yes, they become controlled support-encoder ablations with explicit systems and
symmetry contracts.

### Representation Products

| Product | Owner / storage | Use first for | Escalation risk |
| --- | --- | --- | --- |
| compact query pools | derived from `rollouts.zarr` rows and actor-visible point/support sources | target crop, candidate frustum, target-frustum intersection, direction/history statistics | underfitting local texture/semantic ambiguity |
| `feature_lift_v1.zarr` | proposed separate actor-visible feature bank, not replay truth | compressed DINO@point, support counts, uncertainty, frame/source lineage | stale schema or leakage if mixed into replay ownership |
| Point Transformer | learned local point attention over support pools | point-feature interaction after mean/max/stat pools fail | kNN/radius, density, and frame-canonicalization sensitivity |
| Point Transformer V3 | serialized point/patch attention | large point sets where kNN/RPE cost dominates | intentionally breaks strict permutation handling through order/serialization |
| KPConv | local continuous kernels over irregular point support | density-robust local geometry encoding | radius/subsampling/kernel scale and deformable-kernel regularization burden |
| Minkowski sparse conv | sparse voxel convolution over quantized support | large stable sparse volumes with persistent voxel coordinates | voxel size, quantization origin, hash/grid convention, and build complexity |

This preserves the Iteration 16 ownership split: `rollouts.zarr` owns replay
facts, `q_h/` owns derived value targets, and `feature_lift_v1.zarr` is a
separate actor-visible representation artifact if it is built. A model reader
may join them by stable sample ids and feature schema hashes; the replay store
should not absorb a fast-changing learned feature cache.

### Escalation Gate

Do not add a point/sparse backbone until all five gates are satisfied:

1. S0-S3 baselines are measured: current EVL/VIN features, semidense support,
   compressed DINO@point query pools, and optional EVL-internal/local crops.
2. Failures are localized to representation bottlenecks, not target matching,
   invalidity masks, candidate profile headroom, value calibration, or selected
   transition lineage.
3. Source-dropout and support-stratified metrics show that point features add
   signal beyond pose, support count, directional memory, and target/frustum
   overlap scalars.
4. Feature provenance is stable: feature model id, checkpoint hash,
   compression method, frame ids, projection validity, support counts,
   uncertainty, and source schema hash are stored or derivable.
5. Runtime/storage cost is acceptable for the planned thesis scale, including
   feature-cache size, point count, load time, training memory, and inference
   latency per candidate table.

If any gate fails, the correct response is to fix the data/label/protocol
surface, not to hide the failure behind a bigger backbone.

### Backbone Ladder

| Rung | Model | Hypothesis | Required tests |
| --- | --- | --- | --- |
| P0 | scalar/stat query pools | support and overlap statistics explain most target-RRI ranking signal | row shuffle, source dropout, support-stratified calibration |
| P1 | compressed DINO@point pooled features | local visual/semantic evidence resolves target ambiguity beyond geometry | feature-model/source-hash audit, target-source stratification |
| P2 | small target/frustum/intersection cross-attention | candidate-specific point subsets need learned interaction but not full scene encoding | point-order shuffle, invalid-row firewall, fixed point-budget sweep |
| P3 | Point Transformer / PTv3 support encoder | local point-feature relations bottleneck ranking at larger support sizes | kNN/radius or serialization sweeps, frame tests, runtime report |
| P4 | KPConv local support encoder | varying density and radius-local structure are the dominant bottleneck | radius/subsampling/density bins, kernel-scale sensitivity |
| P5 | Minkowski sparse-volume encoder | sparse voxel memory is needed for broad accumulated support | voxel-size/origin/hash audit, sparse-coordinate stability, build/runtime report |

Point Transformer's useful thesis idea is local vector attention with learned
relative position encoding. PTv3's useful idea is the scalability tradeoff:
serialization and patch attention can reduce kNN/RPE cost, but they turn order
and serialization into provenance. KPConv's useful idea is a radius-neighborhood
local kernel that is robust to varying densities, while its deformable variant
adds regularization debt. MinkowskiEngine's useful idea is an efficient sparse
tensor contract, but only after voxel quantization and coordinate ownership are
already stable.

### Failure Interpretation

| Symptom | Interpretation |
| --- | --- |
| point backbone helps only on training scenes | feature cache or backbone overfits support density / scene identity. |
| gains vanish under point-order or serialization shuffle | claimed set/geometric behavior is order leakage. |
| gains appear only when GT crops or all-candidate render features are joined | privileged evidence leakage, not V1 actor-visible improvement. |
| gains appear only outside EVL extent | EVL local support was limiting; report as representation boundary evidence. |
| gains improve labels but not oracle-rescored acquisition curves | representation improves regression fit, not policy quality. |
| sparse conv result changes with voxel origin/size | quantization contract is not stable enough for thesis claims. |

### Thesis Wording Recommendation

The method chapter should say:

> The first scene encoder is a typed actor-visible feature bank queried by target
> and candidate geometry. We start with compact target, frustum, and
> target-frustum-intersection pools over semidense/fused support and compressed
> DINO@point features. Point Transformer, PTv3, KPConv, and sparse-convolution
> encoders are late ablations, introduced only when pool-level features fail a
> localized representation-bottleneck test and when their neighborhood,
> serialization, density, frame, and storage contracts pass.

This gives the thesis a sharper geometric-learning stance: respect permutation,
frame, and density structure where it matters, but do not mistake stronger point
cloud segmentation backbones for proof of better target-conditioned NBV policy.

## Iteration 27: Symmetry Output Contract

The next geometric-learning correction is to stop asking whether "the model" is
invariant or equivariant. ARIA-NBV has several typed objects, and each one has a
different symmetry contract. The thesis should define the contract by output
type:

```text
symmetry is a property of a specific input/output map, not of the whole system
```

This follows the geometric deep learning distinction between invariant outputs
and equivariant outputs, the Deep Sets requirement that set functions ignore row
order, and the candidate-set requirement from the local theory notes:
candidate-row scores must permute with candidate rows while pooled state
summaries remain invariant to candidate order.

### Output-Type Contract

| Object / output | Domain | Required behavior | Default implementation | Escalation |
| --- | --- | --- | --- | --- |
| `r_abs(s,e,q_i)` | scalar one-step target gain | invariant to global coordinate gauge for the same physical state/action; stable when unrelated rows are added | candidate-local target/frustum/support descriptors in root/target/candidate frames | exact geometry encoders only if frame tests fail for useful reasons |
| `Q_H(i)` / advantage | scalar row output over candidate set | row-permutation equivariant: `Q_H(P Q)_i = P Q_H(Q)_i`; invariant to padded/invalid rows | masked DeepSets/Set Transformer/QCNet-style relative encoding | EGNN/SE(3)-style ablations after row, mask, and support tests pass |
| `V_H(s,e,h_t)` | state scalar | invariant to candidate row order and padding | pooled actor-visible support, selected history, target state | latent bottleneck only after source-dropout evidence |
| candidate table | finite action set | row order is arbitrary; masks and losses must follow row permutation exactly | explicit valid mask, row ids, position ids, and mean-over-valid operations | serialization models only with shuffle/serialization tests |
| target/candidate relative geometry | local descriptors | preserve physically meaningful gravity, heading, camera, frustum, and target-bearing signals | root-local, target-local, and candidate-local relative pose/RPE; R6D/LFF controls | exact rotation handling only if local descriptors fail |
| point/support bank | unordered observed support | invariant to point row order for pooled summaries; equivariant only for point-wise outputs | typed point pools, support counts, uncertainty, source lineage | Point Transformer/KPConv/PTv3/Minkowski after feature-bank gates |
| directional visibility memory | target- or support-local sphere | paired rotation of memory directions and candidate direction should preserve scalar novelty/support | low-order bins or spherical statistics over selected views | spherical harmonics/e3nn-style channels after simple S2 baselines |
| pose/vector field ablation | vector or pose output, if introduced | equivariant to the chosen transform group | explicit frame and transform tests | SE(3)/EGNN-style exact equivariance with reported equivariance error |
| mesh/tangent gauge model | local tangent/gauge features | gauge changes are coordinate choices; physical scalar decisions should be gauge-invariant after consistent transport | avoid in thesis core | only if a true connection/parallel-transport contract is specified |
| selected history | ordered action/evidence sequence | temporal order is meaningful; history shuffling is illegal unless explicitly pooled | append selected action/evidence records with timestamps | recurrence only under selected-history provenance tests |
| actor/oracle evidence split | information boundary | not a symmetry: actor-visible inputs exclude oracle labels; oracle data labels, matches, and evaluates | V1 target protocol plus GT-EVAL owner split | privileged critic only as explicit advisor decision |

The common trap is to impose a larger symmetry than the task has. A value score
for a physical candidate should not depend on the arbitrary world origin, but it
may legitimately depend on gravity, camera heading, target bearing, frustum
shape, support density, and selected-history direction. A full SO(3)-invariant
model can erase useful "up" and egocentric cues; exact equivariance belongs in
controlled ablations, not as a default architecture slogan.

### Gauge Discipline

Root frame, current camera frame, target frame, candidate frame, and display
CW90 frame are coordinate choices. The scalar decision should be stable under a
consistent change of arbitrary gauge, but the implementation does not get that
property for free. It must state which frame each descriptor uses and which
transforms are treated as nuisance versus signal.

The gauge literature also warns against a naive "gauge-equivariant mesh CNN"
escalation. If every tangent gauge is independently free, overly strong
constraints can force useful filters toward trivial behavior; useful
gauge-equivariant convolution needs local support plus a connection/parallel
transport rule. ARIA-NBV should therefore not adopt a mesh/tangent gauge model
unless the thesis changes to explicitly own transport, local chart, and filter
contracts. For the current thesis, local-frame descriptors and scalar invariance
tests are the right level.

### Transformation Tests

| Test | Mutation | Required signal |
| --- | --- | --- |
| candidate row permutation | permute valid candidate rows and associated masks/ids | row-wise scores, losses, argmax, and selected `position_id` permute exactly |
| invalid-row firewall | append invalid/padded rows with extreme features | valid scalar scores and bootstrap targets are unchanged |
| global translation / world-origin shift | shift all world-frame positions consistently | scalar `r_abs` and `Q_H` are unchanged within tolerance |
| yaw / gravity-preserving frame change | rotate world frame about gravity while transforming poses consistently | scalar decisions remain stable if descriptors are correctly local-frame |
| full SO(3) synthetic ablation | rotate gravity too | report separately; do not require invariance for normal Aria scenes |
| paired S2 directional rotation | rotate directional memory and query direction together in the target frame | scalar novelty/support stays stable; channel representation transforms as specified |
| point-order shuffle | permute support/point rows before pooling/encoding | pooled candidate outputs are unchanged or point-wise outputs permute as declared |
| history-order audit | shuffle selected-view history | either fail by construction or show the model explicitly treats history as a set |
| exact-equivariance ablation | apply known SE(3)/E(n) transforms to vector/pose outputs | report equivariance error, not just task loss |
| CW90 isolation | toggle display-only CW90 conventions | model descriptors and scalar scores do not change |

These tests should be reported alongside model comparisons. Otherwise a
Transformer improvement can be an artifact of row order, padding, display-frame
leakage, or candidate serialization rather than a geometric NBV result.

### Architecture Recommendation

The first thesis model should be described as a geometry-aware scalar value
model:

> The model predicts scalar target-gain and finite-horizon candidate values from
> actor-visible target, support, history, and candidate descriptors. Candidate
> scores are row-permutation equivariant, pooled state summaries are
> row-invariant, local-frame descriptors remove arbitrary world-origin choices,
> and gravity/camera/frustum/target-bearing signals are preserved when they are
> physically meaningful. Exact EGNN, SE(3)-Transformer, e3nn/spherical-harmonic,
> or gauge-equivariant variants are ablations that must report transformation
> tests and storage/runtime cost.

This gives the planned geometric-invariance thesis section a sharper claim:
respect the isomorphisms the data product actually has, preserve asymmetries
that carry task information, and escalate to exact equivariance only when the
output type and evaluation prove it is the missing inductive bias.

## Iteration 28: Directional Visibility Memory Ladder

The next architecture choice is how to represent "already seen from this
direction" without changing the thesis objective. SCONE, MACARONS, Hestia, and
FisherRF all point at the same useful auxiliary signal: view history is not only
a list of poses. It is directional support around a target, point, voxel face,
or local support cell. The mistake would be to promote that auxiliary support
signal into the reward.

The thesis rule should be:

```text
target-RRI remains the label and evaluation target;
directional memory is an actor-visible support / novelty / diversity channel.
```

SCONE predicts visibility gain from proxy points, occupancy, occlusion context,
and camera history projected on a sphere. MACARONS tightens this by projecting
only previous cameras for which the point was plausibly visible, so history
reflects occlusion rather than raw pose count. Hestia tracks visibility of voxel
faces and uses immediate face-coverage increments, but the ARIA transfer is only
the face/direction bookkeeping. FisherRF says the branch-diversity version of
the same idea should be diminishing returns: a candidate is less useful when it
constrains target-local variables that are already well constrained.

### Memory Objects

The architecture should keep these objects separate:

| Object | Meaning | First representation | Do not confuse with |
| --- | --- | --- | --- |
| selected-view history `h_t` | ordered selected actions and observed/synthetic successor evidence | append-only sequence with pose, time, source, support hashes | unordered candidate set |
| target-local support cells `v in Omega_e` | actor-visible points/voxels/features in observed or predicted target region | semidense/EVL/fused point support with counts and uncertainty | GT target mesh samples |
| directional memory `M_dir(v)` | accumulated directions from which support cell `v` was plausibly observed | weighted second moment `sum w d d^T` in target/support frame | pose encoding for the candidate row |
| scalar directional novelty `u_dir(q,e)` | how much candidate `q` sees target support from under-covered directions | SCONE/Fisher-style support-weighted novelty sum | reward or oracle RRI |
| branch overlap `Delta u(q | B,e)` | whether rollout siblings repeat the same target-local support/directions | Fisher-style diminishing-return feature | stochastic branch reward |
| face/incidence bins | coarse normal/face-side observation evidence | six-face or normal-aligned bins from Hestia-style bookkeeping | full continuous actor policy |
| SH/e3nn channels | compact angular basis for richer `S^2` memory | low-order spherical harmonics ablation | default pose encoder or target-RRI label |

The current code already encodes this separation: candidate direction sampling
happens on `S^2`, while orientation encodings such as R6D describe pose rows and
accumulated target visibility is called out as a separate actor-visible
directional-memory feature. VIN v3 repeats the same warning: target visibility
should be represented as directional memory over view directions, not folded
into pose encoding.

### Directional-Memory Ladder

| Rung | Feature | Purpose | Required proof |
| --- | --- | --- | --- |
| D0 current diagnostics | semidense projection coverage, voxel valid fraction, depth moments, target support counts | establish that support/frustum diagnostics correlate with target-RRI | per-family support histograms and Spearman/top-k oracle hit |
| D1 second-moment memory | `M_dir(v)=sum_k w_k(v)d_k(v)d_k(v)^T` over actor-visible target/support cells | minimal target-local `S^2` history without learned angular basis | paired-rotation consistency and support-source audit |
| D2 scalar novelty | `u_dir(q,e)=sum_v p_surf p_frustum (1 - d^T M_dir d / (tr M_dir + eps))` | test whether under-observed directions predict target-RRI beyond support count | ablate support only vs support+direction |
| D3 Fisher-style branch diversity | greedy marginal `Delta u(q | B,e)` for rollout sibling selection | avoid stochastic branches that inspect the same support from the same directions | branch-overlap report and oracle-lookahead recovery |
| D4 face/incidence histograms | six-face, normal-aligned, or incidence-angle bins | Hestia-style coarse directional observability for voxels/points | compare against D1/D2 under target-support bins |
| D5 low-order SH/e3nn memory | compact spherical harmonic channels for `M_dir` or candidate direction features | test whether angular frequency detail matters | match D1/D2 inputs; report lmax, normalization, roll assumptions |
| D6 learned visibility module | SCONE/MACARONS-style learned occupancy/visibility over proxy points | late ablation if transparent support/novelty channels bottleneck policy | no oracle leakage, storage/runtime report, and task gain beyond target-RRI scorer |

D1-D3 are the thesis-safe path. They are transparent, actor-visible, and easy
to inspect in rollout artifacts. D4-D6 are ablations after the target-RRI store,
support coverage diagnostics, and `Q_H` value target are already trustworthy.

### SH And Pose-Encoding Caveat

The experimental SH encoder is useful, but it is currently a shell pose
descriptor: it consumes candidate center direction, forward direction, radius,
and alignment. It explicitly does not encode roll about the forward axis. That
is fine for a pose-encoder ablation when roll is not meaningful, but it is not a
substitute for accumulated directional visibility. A thesis claim about
directional memory should therefore distinguish:

```text
SH pose descriptor: angular encoding of one candidate row.
SH memory descriptor: angular encoding of selected observation history around
target/support cells.
```

Only the second one tests the SCONE/MACARONS/Hestia idea. If SH helps merely by
encoding shell pose better than R6D/LFF under a fixed candidate profile, that is
a pose-encoding result, not evidence for view-history memory.

### Failure Interpretation

| Symptom | Interpretation |
| --- | --- |
| `u_dir` correlates with RRI only for free-shell candidates | realistic candidate families lack target support; fix candidate generation before `Q_H`. |
| `u_vis` helps but `u_dir` does not | support overlap matters, but directional history is not yet informative at the chosen target/support resolution. |
| SH beats D1/D2 without paired-rotation stability | angular basis may be exploiting frame or sampling artifacts. |
| branch diversity improves support but not endpoint target gain | diversity is exploring non-target or low-quality support; keep as diagnostic, not policy objective. |
| face/incidence bins disagree with Chamfer/RRI gains | Hestia-style face coverage is a proxy; report disagreement rather than replacing the label. |
| directional memory uses GT mesh-visible cells | oracle leakage; restrict cells to actor-visible target/support sources and use GT only for labels/evaluation. |

### Tests And Artifact Requirements

Any directional-memory claim should log:

- support-cell source: EVL, semidense/fused point, selected-depth successor, or
  learned feature bank;
- frame: target-local, support-local, root-local, and gravity convention;
- selected-view provenance: selected action id, timestamp/step, pose, depth
  source, and occlusion/visibility eligibility;
- per-candidate `u_vis`, `u_info`, `u_dir`, support count, target support bin,
  candidate family, and invalidity reason;
- paired `S^2` rotation test: rotate memory directions and candidate direction
  together and keep scalar novelty stable;
- source dropout: support-only, direction-only, Fisher-style diminishing
  returns, face/incidence, and SH ablations;
- branch-overlap report for stochastic rollouts and oracle-lookahead recovery;
- SH report: `lmax`, normalization, basis frame, roll assumption, and runtime.

### Recommendation

The thesis should make directional memory a small, inspectable architecture
section:

> We represent selected-view history not only as a pose sequence but also as a
> target-local directional support memory. The first implementation uses
> actor-visible target/support cells with second-moment `S^2` direction
> statistics and scalar novelty/support features. Fisher-style diminishing
> returns are used for rollout branch diversity diagnostics. Hestia-style
> face/incidence bins and e3nn spherical harmonics are ablations, not default
> objectives. All variants are evaluated against target-RRI and endpoint target
> reconstruction quality.

This preserves the geometric insight from coverage/information papers while
keeping ARIA-NBV's scientific claim centered on target-specific reconstruction
improvement.

## Iteration 29: Pose Descriptor And CW90 Gauge Contract

The current shared equation draft asks whether candidate pose features should be
"R6D + translation" or a QCNet-like descriptor. That should not be an either/or
decision. They play different roles:

```text
R6D + LFF = stable per-row pose descriptor.
QCNet-style RPE = query-local relation descriptor for candidate interaction.
```

The first path should keep the implemented VIN v3 contract: store canonical
poses, derive the candidate pose in the reference rig frame, encode translation
and a continuous rotation representation, then feed the pose vector through
learnable Fourier features. The interaction path can then add query/candidate
local relative descriptors for candidate-candidate, target-candidate, history,
and support relations. This resolves the TODO without replacing a calibrated
pose baseline by an attention-only relation model.

### Descriptor Ownership

| Descriptor | Owner | Use | Escalation risk |
| --- | --- | --- | --- |
| canonical pose `T_w_cq` | rollout/offline store and candidate generator | replay truth, rendering, Rerun, derived descriptor source | storing only derived features loses auditability |
| root-relative pose `T_r_cq` | model reader / derived cache | one-step scorer and `Q_H` per-row pose descriptor | raw world pose shortcut or root/frame drift |
| R6D + translation LFF | VIN v3 baseline pose encoder | continuous rotation-friendly per-row candidate embedding | hides query-specific relations if used alone |
| shell SH pose descriptor | experimental shell-profile encoder | ablate angular basis for shell candidate centers/forward directions | no roll information; not accumulated visibility memory |
| QCNet-style query-local RPE | set/attention model | candidate-candidate, target-candidate, history, and support relation bias | importing trajectory decoder/anchor losses or road-scene assumptions |
| Lie/log relative pose | optional exact geometric relation feature | ablate SE(3) relation encoding against simpler RPE | branch cuts, scaling, and convention debt |
| CW90/display twist | UI / display / rig-basis correction boundary | visualization and explicit correction paths only | silent model/camera mismatch if applied twice or skipped |

This should be the thesis wording:

> We store poses as rigid transforms and derive model descriptors at read time.
> The baseline pose token uses root-relative translation plus the 6D rotation
> representation passed through learnable Fourier features. Candidate-set
> interaction adds query-local relative position and orientation descriptors as
> attention biases. Shell spherical-harmonic encoders and Lie/log-map features
> are ablations with explicit roll, frame, and runtime tests.

### Why R6D Remains The Baseline

Zhou et al.'s rotation-representation result and PyTorch3D's transform API are
already reflected in code: `R6dLffPoseEncoder` imports
`matrix_to_rotation_6d`, forms `[t, r6d]`, and validates the LFF input dimension
as 9. VIN v3 documents the model flow as
`T_r_cq = (T_w_r)^-1 @ T_w_cq -> (t, R6D) -> LFF -> pose_enc`.

That contract is thesis-safe because:

1. it keeps the canonical pose as a transform rather than as a learned-only
   embedding;
2. it avoids Euler-angle discontinuities as the default rotation feature;
3. it is already integrated with semidense projection, voxel context, and
   CORAL one-step scoring;
4. it gives a clean control for query-local RPE ablations.

The baseline should not be replaced by shell SH. The existing SH encoder is
explicitly a shell descriptor over center direction, forward direction, radius,
and view alignment, and it does not encode roll about the forward axis. That is
useful for shell-sampling ablations, not a general pose representation for all
candidate families.

The pose-generation stack also makes roll a controlled variable rather than a
hidden default. View-direction jitter derives yaw/pitch from the sampled forward
direction and builds a roll-free rotation; optional roll jitter is isolated as a
separate local `+Z` roll. That means roll-sensitive claims need an explicit
roll-jitter experiment and should not be inferred from the default candidate
sampler. The trajectory encoder mirrors the same R6D+LFF representation, so the
history-pose control and candidate-pose control can share descriptor tests.

### QCNet Transfer Boundary

QCNet/QCNeXt contributes one main idea: build local coordinate systems for
query elements and express relationships through relative positional embeddings
before attention. ARIA should transfer that as:

```text
candidate i queries candidate j / target e / history k / support token a
through descriptors expressed in candidate i's local frame.
```

The shared equation draft already sketches this:

```text
delta_p(j,i) = R_i^T (p_j - c_i)
delta_R(j,i) = R_i^T R_j
eta_target(e,i) = concat(R_i^T(t_e - c_i), alpha_i^e)
eta_hist(k,i) = concat(R_i^T(c_k - c_i), t-k, r_k^e)
```

The part not to import is the trajectory-prediction decoder: adaptive trajectory
anchors, future-agent interaction losses, road topology, and autonomous-driving
metrics are not ARIA-NBV's thesis object. The portable piece is the
query-local relation encoding, evaluated as an ablation after the independent
R6D/LFF scorer and DeepSets/Set Transformer controls.

### CW90 / Frame Isolation

CW90 must be treated as a display and rig-basis convention boundary, not a
learned pose feature. The helper named `rotate_yaw_cw90` is actually a local
`+Z` roll/twist that swaps local axes. VIN v3 already has the right guard:
when `apply_cw90_correction=True`, poses are undone for model descriptors and
the PyTorch3D cameras must be pre-corrected and tagged `cw90_corrected=True`.
The model raises if the tag is missing.

Therefore:

- canonical rollout poses should remain stored once in a documented frame;
- display-only frustum/Rerun corrections should not mutate model inputs;
- any correction path must update both PoseTW and PyTorch3D camera extrinsics;
- the model should fail closed on untagged corrected-camera paths;
- orthonormality, determinant, and row/column-vector convention checks remain
  part of frame verification.

The implementation already has the right separation points. Candidate
generation applies the local `+Z` convention fix to the reference pose before
sampling. Candidate plotting defaults `display_rotate=False` for reference axes
and frusta because applying the same correction again would double-rotate the
display, especially once roll jitter is enabled. The model ingestion path then
requires an explicit `cw90_corrected` tag when it undoes CW90 for PoseTW inputs.

The PyTorch3D depth/backprojection tests show why this matters: PoseTW uses the
column-vector convention, while PyTorch3D transforms use row vectors, so
rotations must be transposed in the renderer path and tested against PoseTW
inverse transforms.

### Descriptor Ladder

| Rung | Descriptor set | Hypothesis | Required tests |
| --- | --- | --- | --- |
| P0 canonical pose audit | `T_w_cq`, `T_w_r`, camera intrinsics/extrinsics, orthonormality/determinant stats | stored poses are trustworthy replay/rendering truth | frame report, det/orthonormality, PyTorch3D/PoseTW convention tests |
| P1 R6D/LFF row token | root-relative `[t_r_cq, R6D(R_r_cq)]` | stable one-step pose baseline | rotation continuity, scale sensitivity, root/global gauge tests |
| P2 candidate-target scalars | distance, bearing/elevation, target-facing angle, frustum/support overlap | simple target-local geometry explains most gains | support/RRI stratification and shortcut ablation |
| P3 query-local RPE | candidate-local target/candidate/history/support relations as attention bias | interaction needs local relative geometry | row permutation, global yaw/translation, invalid-row firewall |
| P4 shell SH pose ablation | center/forward direction, radius, alignment via low-order SH | shell angular basis improves over R6D/LFF for shell profiles | roll-sensitivity, profile split, `lmax`/normalization/runtime |
| P5 Lie/log or EGNN relation ablation | exact `SE(3)` relation or graph update | exact geometry relation helps after P1-P3 | branch-cut/scaling tests and equivariance error |
| P6 learned relation/refinement | bounded recurrence or relation refinement | relation reasoning, not descriptor choice, is bottleneck | K-step stability, no future/GT leakage, matched-budget gain |

This ladder keeps the pose story scientific: first prove the pose/camera frames
are correct, then compare increasingly structured descriptors under fixed data,
labels, masks, and candidate tables.

### Tests

| Test | Mutation | Required signal |
| --- | --- | --- |
| R6D round-trip / continuity | convert rotations to R6D and back under small perturbations | no discontinuity-like jumps in pose features |
| global translation gauge | shift world positions and target/support coordinates consistently | root/query-local scalar predictions stable |
| gravity-preserving yaw gauge | rotate world frame around gravity consistently | R6D baseline and RPE scores stable when physical relation is unchanged |
| reference-root audit | compare descriptors from the same physical candidate under documented root changes | differences are explained by root-state semantics, not frame bugs |
| CW90 fail-closed | enable correction without camera tag | RuntimeError, as current v3 test expects |
| CW90 semantic parity | compare corrected PoseTW+camera path against uncorrected semantic path | model descriptors/projections agree within tolerance |
| row-vector convention | compare PyTorch3D world-to-view transform with PoseTW inverse | matches renderer/backprojection tests |
| shell no-roll test | add roll jitter around forward axis | shell SH pose descriptors cannot claim roll-sensitive behavior |
| RPE row equivariance | permute candidate rows and relation edges consistently | row scores and attention biases permute exactly |
| descriptor dropout | remove R6D, target scalars, RPE, SH, or strategy fields | gains can be attributed to a relation source |

### Failure Interpretation

| Symptom | Interpretation |
| --- | --- |
| QCNet-style RPE helps before P0/P1 frame tests pass | likely frame/candidate bug is being absorbed by attention. |
| shell SH beats R6D only under no-roll shell profiles | useful pose-profile ablation, not a general pose-encoding result. |
| CW90 toggle changes scores without semantic scene change | display convention leaked into model descriptors or cameras. |
| RPE gains vanish under row permutation or invalid-row firewall | candidate order/mask leakage, not geometric reasoning. |
| Lie/log features are unstable near branch cuts | use R6D/RPE controls until exact relation encoding is justified. |
| raw world pose outperforms local descriptors | suspect split/location shortcut; evaluate on world-frame shifts and held-out scenes. |

### Recommendation

Keep R6D+LFF as the default per-candidate pose token and add QCNet-style
query-local RPE only as the first relation-aware set-model ablation. Shell SH is
a pose-profile ablation; `S^2` visibility memory is a separate selected-history
feature; CW90 is a correction boundary that must never be a silent learned
signal. This resolves the shared-equation TODO while preserving a clear
evaluation path.

## Iteration 30: Invalidity, Masks, And Support-Gated Value Learning

The current architecture should treat invalidity as a typed constraint system,
not as a scalar reward value to be learned away. Local theory, rollout code, and
offline-RL literature all point to the same conclusion: `Q_H` may learn over
actor-selectable finite candidates, but invalid candidates, invalid targets,
missing oracle labels, and out-of-support transitions must remain explicit masks
or strata.

### Local Evidence

- `docs/contents/theory/rl_planning.qmd` owns the finite-candidate `Q_H`
  formulation, root-normalized target-gain reward, symbolic gamma, masked
  Double-DQN backup, and IQL as a later support ablation.
- `docs/contents/theory/candidate_sampling_target_selection.qmd` separates hard
  target/candidate eligibility from target-to-GT matching audit fields, keeps
  invalid candidate rows in the full shell, and requires invalid reasons and
  valid-count reporting.
- `docs/contents/theory/candidate_view_dependence.qmd` makes masks part of
  attention, argmax, softmax, loss, and bootstrap semantics; it also forbids
  smoothing over invalidity/support boundaries.
- `aria_nbv/aria_nbv/rollouts/zarr_store.py` stores actor action masks, oracle
  label masks, `q_train_mask`, invalid reason bitsets, target support, target
  root gain, TD fields, and a derived `q_h/` view. Invalid candidates receive
  false masks and NaN labels.
- `aria_nbv/aria_nbv/pose_generation/types.py` keeps compact valid views tied to
  the full candidate shell through `candidate_shell_indices`, so training can
  prove that compact rows did not silently lose invalidity context.
- `aria_nbv/aria_nbv/rl/counterfactual_env.py` has an online invalid-action
  penalty/termination path. That is useful for RQ5 online discrete experiments,
  but it is not the offline `Q_H` truth contract.
- DQN and Double DQN support replay-based finite-action value learning; Double
  DQN is the right first overestimation control. CQL, IQL, and BCQ warn that
  offline value estimates can become unreliable for unsupported actions, so
  they belong as support diagnostics or ablations after the masked baseline is
  stable.

### Typed Mask Contract

| Mask / stratum | Owner | Use | Not for |
| --- | --- | --- | --- |
| `actor_action_mask` | candidate generator and rollout writer | feasible actor-selectable actions, action selection, attention/argmax masking | encoding low value or weak support |
| `oracle_label_mask` | oracle renderer/evaluator | whether a candidate has a valid oracle label for supervised scoring | hiding actor-visible invalidity |
| `target_valid_mask` | target protocol and GT-EVAL matcher | target eligibility, unmatched/ambiguous/unsupported target filtering | treating invalid targets as low-RRI examples |
| `q_train_mask` | rollout store / training reader | rows eligible for `Q_H` supervised or TD losses | replacing feasibility, labelability, or target validity |
| support strata | target/candidate support diagnostics | stratified headroom, reliability, and failure interpretation | hard-masking setup actions unless oracle/evaluation sample is impossible |
| behavior-support strata | rollout policy provenance | offline support and OOD/extrapolation diagnostics | silently changing the feasible action set |
| bootstrap mask | TD target builder | valid successor action set for masked Double-DQN backups | maxing over padded, invalid, or all-invalid successor rows |

The practical rule is:

```text
invalidity is a hard mask;
support is a reported stratum first;
offline support mismatch is a value-learning diagnostic;
online invalid-action penalties are RQ5 bridge ablations.
```

### Backup Rule

For selected-transition rows, the store already exposes `td_reward`,
`td_next_step`, `td_terminal`, and `td_discount`. The training rule should
compute the masked Double-DQN target over a deliberately chosen successor mask:

```text
y = r_root + gamma * 1[not terminal] *
    Q_target(s', argmax_{j in M_next} Q_online(s', j))
```

`M_next` must be declared in the experiment. Use `actor_action_mask` when the
question is action feasibility; use `q_train_mask` only when the experiment
requires labelable successor rows. If the successor has no valid rows, the
transition should become terminal/blocked diagnostic evidence, not a max over
invalid filler values.

### Architecture Recommendations

1. Keep hard masks in attention, argmax, softmax, losses, and TD bootstraps.
2. Split target support from candidate infeasibility. Low target support can
   invalidate a target label; low candidate support is usually a diagnostic
   stratum unless no meaningful oracle/evaluation sample exists.
3. Log support strata before adding learned penalties: per-target support bins,
   per-candidate support, valid count, `position_id`, behavior policy support,
   target-match status, and rollout policy id.
4. Use masked Double-Q as the first `Q_H` path. CQL/IQL/BCQ are later ablations
   for support/extrapolation behavior; they do not replace invalid masks.
5. Keep `counterfactual_env.invalid_action_penalty` scoped to online discrete
   `Q_H` experiments, not offline replay truth.
6. Make reason-bit fidelity a preflight gate: total-order primary reason,
   path-collision mapping, writer/reader/inspector/trainer parity, and roundtrip
   tests.

### Failure Interpretation

| Symptom | Interpretation |
| --- | --- |
| invalid-row feature changes alter valid-row predictions | mask leak in attention, normalization, padding, or aggregation |
| all-invalid successor produces finite bootstrapped Q | bootstrap leak; blocked successor should be terminal/diagnostic |
| low-support setup actions are hard-removed | myopia by mask design; support should be stratified unless labels are impossible |
| high Q appears only in low behavior-support candidate families | offline extrapolation risk; compare CQL/IQL/BCQ-style controls |
| `q_train_mask` is true while target validity or oracle labelability is false | label leak or store corruption |
| `Q_H` gains occur only in high-support bins | support-limited result, not general architecture success |
| oracle headroom is flat when valid counts are low | generator/support bottleneck, not value-head failure |

### Tests And Evidence Requirements

The next implementation pass should add or preserve:

- invalid-row firewall tests with extreme invalid features;
- padded/all-invalid successor tests for terminal or blocked backup handling;
- `q_train_mask <= actor_action_mask` plus target-valid/oracle-label parity;
- invalid reason-code roundtrips across writer, reader, inspector, and trainer;
- support-stratified headroom and `Q_H` metrics;
- behavior-support splits by rollout policy, `position_id`, candidate family,
  sampler probability, and root policy;
- Double-Q overestimation diagnostics against oracle-rescored returns;
- online invalid-action penalty ablations only after the offline masked
  baseline is stable.

### Recommendation

The thesis should state the invalidity contract as a method invariant:

> ARIA-NBV does not learn invalidity as a low reward. Candidate feasibility,
> target validity, oracle labelability, training eligibility, and offline
> behavior support are separate typed masks or strata. The default offline
> planner trains a masked finite-candidate Double-Q value head over valid
> actor-selectable replay rows; support-limited or invalid cases are reported as
> diagnostic subsets and only become penalty-shaped rewards in later online
> bridge experiments.

This keeps target-RRI value learning interpretable and prevents the most common
offline-RL failure mode: a model that appears to plan only because invalid or
unsupported rows leaked into its loss, normalization, or bootstrap path.

## Iteration 31: Target Matching, Eligibility, And Labelability Contract

The target protocol is no longer just a prose desideratum. The live selector and
rollout store already implement most of the V1 boundary: GT OBBs are refused as
actor-visible V1 sources, observed/predicted OBB rows carry score factors and
invalid reasons, selected rows are matched to GT only after selection, target
metadata is persisted into `rollouts.zarr`, and `q_train` is blocked when the
target is not actor-valid plus GT-label-valid.

The remaining architecture risk is vocabulary drift. Some thesis text still
says observed targets are matched to GT labels by compatible class, OBB IoU,
visibility/support, projected area, and point support. The current
implementation deliberately uses support, projection, and confidence for
actor-visible eligibility and interest, then uses semantic compatibility plus
3D IoU/top-1 gap for GT association. That split is preferable. It prevents weak
actor evidence from becoming a fuzzy GT-object ranker and keeps GT-EVAL
auditability simple.

### Evidence

- `docs/contents/thesis/questions.qmd` makes OBS-SEL / PRED-Q / GT-EVAL
  mandatory, but its matching-rule wording still blends support/projection with
  GT association.
- `docs/contents/theory/candidate_sampling_target_selection.qmd` is cleaner:
  it separates hard eligibility, target interest, and post-selection GT match
  audit, and says support/visibility are eligibility and audit fields, not
  competing GT-object ranking fields.
- `aria_nbv/aria_nbv/data_handling/_target_selection.py` implements the V1
  contract: V1 prefers detected OBBs, then EVL-predicted OBBs, refuses GT-only
  sources, computes confidence/projection/support/deficit score factors, and
  accepts GT labels only after semantic-compatible IoU matching with ambiguity
  checks.
- The selector's GT match score is geometry-only by design. The docstring says
  support and projected visibility decide whether a row is labelable and
  interesting; GT association stays class-compatible 3D IoU.
- Target invalidity has stable codes for missing actor source, disallowed GT
  source, padded/nonfinite/invalid OBBs, confidence, projection, support,
  unmatched GT, and ambiguous GT.
- `target_gt_obb_world` refuses to build a target crop unless the row is
  GT-label-valid. The target scorer raises `TargetRriInvalidError` for missing
  GT matches, empty mesh crops, sparse current target support, and related crop
  invalidity.
- The rollout store persists target source, score factors, invalidity bitsets,
  matched GT ids, `gt_match_iou`, `gt_match_score`, match status, target crop
  policy, target-valid mask, and GT-label-valid mask; the validator rejects
  `q_train` for invalid target state.
- EFM3D's own OBB persistence paper path uses class, 2D/3D box distances, 2D/3D
  IoU, thresholds, running-average updates, and duplicate suppression for OBB
  tracking. SceneScript likewise uses Hungarian-style geometric matching for
  entity evaluation. These are useful audit precedents, but not a reason to
  leak GT assignment into actor-visible target selection.

### Recommended Protocol Vocabulary

Use four distinct terms in thesis and code reviews:

| Stage | Owner | Operation | Failure status |
| --- | --- | --- | --- |
| OBS-SOURCE | data-handling / EVL | choose actor-visible detected or predicted OBB source | no actor-visible source |
| OBS-ELIG | target selector | hard feasibility/labelability gate over confidence, finite OBB, projection policy, and support | target-invalid before selection |
| OBS-RANK | target selector | rank/sample eligible target rows by actor-visible interest score | low interest, not low RRI |
| GT-EVAL-MATCH | oracle/evaluation | associate selected row to a GT OBB by compatible class, IoU, and ambiguity gap | unmatched or ambiguous target-invalid |
| GT-CROP-LABEL | target scorer | crop current/candidate points and GT mesh, then compute target RRI/root gain | crop-invalid or support-invalid label failure |

This naming keeps the architecture honest: `PRED-Q` consumes the selected
actor-visible descriptor; it does not consume GT match fields, GT crops, or
target oracle labels.

### Critique

1. **Do not fold support into GT association by default.** Support and projected
   area should remain eligibility/reporting fields. If they enter GT matching,
   the thesis must explain a concrete M3 failure mode that pure class+IoU cannot
   resolve.
2. **Ambiguity should block main-claim labels before it is resolved by clever
   assignment.** Mark duplicate predicted-to-GT and top-1/top-2 ambiguous cases
   target-invalid for V1 claims; use Hungarian/global assignment only as an
   audit or repair ablation after measuring ambiguity rates.
3. **Persist crop invalidity as a first-class target reason.** The scorer already
   raises `TargetRriInvalidError` for empty mesh crops and sparse current support,
   but the architecture should expose these as stable target-label invalidity
   statuses before scale generation.
4. **Report thresholds as experimental conditions.** `min_confidence`,
   `min_support_points`, projection policy, `min_gt_iou`, match score, and
   ambiguity margin are not thesis constants until selected-target coverage,
   unmatched/ambiguous rates, support histograms, and crop-validity rates are
   reported.
5. **Keep V0 useful but quarantined.** V0 GT OBB input is a sanity/upper-bound
   target-RRI check. It should share the crop/evaluation code path with V1, but
   never share actor-visible performance tables.

### Evaluation And Audit Requirements

Before scaling target-conditioned rollouts, the target protocol report should
include:

- selected target counts by scene, snippet, class, source mode, and source
  surface (`detected_obbs`, `backbone.obb_pred_viz`, V0 GT sanity);
- OBS-ELIG failure histograms: confidence, projection, support, nonfinite/extent
  failures, no source, and disallowed GT source;
- OBS-RANK factor histograms for confidence, projected area, semidense support,
  EVL support, deficit score, and final selection score;
- GT-EVAL-MATCH histograms for IoU, match score, top-1/top-2 gap, unmatched,
  ambiguous GT, and duplicate predicted-to-GT cases;
- GT-CROP-LABEL counts for empty mesh crop, too few current target points,
  candidate target-support distribution, finite root gain, and finite diagnostic
  target RRI;
- paired V0/V1 audits on a small trusted subset to show that V1 failures are
  actor-evidence or matching failures rather than target-RRI implementation
  failures;
- visual audit artifacts showing actor-visible OBB, matched GT OBB, current
  target points, candidate target points, cropped mesh, target RRI, and scene RRI
  side by side.

### Recommendation

The thesis architecture should promote target selection to its own method
subsection with this rule:

> Target selection, target-to-GT matching, and target-RRI labeling are distinct
> operations. V1 selects an actor-visible observed/predicted target, ranks it by
> actor evidence, then uses GT OBBs only after selection to decide whether a
> label/evaluation crop is valid. Unsupported, unmatched, ambiguous, or
> crop-invalid targets are target-invalid protocol cases, not low-RRI samples.

This is stricter than a generic object-centric NBV formulation and matches the
repo's scientific boundary: ARIA-NBV can use object-centric view-selection ideas
from Instance-NBV and 3DGS work, but its main claim lives or dies on
leakage-safe target-RRI labels over observed/predicted target records.

## Iteration 32: TD Backup, Successor Candidate Masks, And All-Invalid Successors

The next `Q_H` risk is not model architecture; it is backup semantics. The live
`rollouts.zarr` writer already materializes a derived `q_h/` view with
`valid_action_mask`, `q_train_mask`, selected-action ids, `td_reward`,
`td_next_step_row_id`, `td_terminal_mask`, and `td_discount`. Tests confirm that
`q_train_mask <= valid_action_mask`, invalid candidates get NaN one-step labels,
terminal rows have zero discount, and `td_reward` uses
`target_root_gain` rather than diagnostic target RRI.

No trainer exists yet. That is the right moment to lock the semantic boundary:
the store owns factual selected transitions and masks; the trainer owns computed
DQN/Double-DQN targets. Persisting a numeric TD target as repo truth before it
is tied to a named training config/checkpoint would blur data provenance and make
future gamma, horizon, and mask experiments hard to audit.

### Evidence

- Canonical memory says `Q_H` is mandatory, candidate-query, finite-candidate,
  and predicts bounded cumulative root-normalized target gain from ASE oracle
  rollout traces; fitted Double-Q is the first value-learning target family and
  IQL is only a later ablation.
- `docs/contents/theory/rl_planning.qmd` defines the masked DQN and Double-DQN
  target over successor candidates, and explicitly says invalid candidates are
  masked before argmax, softmax, loss target, or selected action.
- The local Double-DQN TeX source gives the standard reason for decoupling
  action selection from evaluation: the single-network max overestimates values.
  The ARIA analogue is sharper because invalid or unsupported successor
  candidates can create overestimated values even before ordinary value noise.
- The IQL source warns that offline TD objectives can overestimate
  out-of-distribution actions; ARIA's finite candidate table makes this testable
  through behavior support, `q_train_mask`, and successor valid-count reports.
- The rollout writer currently sets `q_train` from actor validity, finite
  root-gain oracle label, and target-label validity. The derived `q_h/` view then
  copies masks and selected-transition fields but does not compute bootstrap
  values.
- Work-review notes keep the pass/fail bar stronger than a training loss:
  learned `Q_H` selected actions must be oracle-evaluated under equal acquisition
  and candidate budgets, beat one-step scorer/greedy references when headroom
  exists, and report recovered headroom fraction.

### Backup Contract

Use this ownership split:

| Surface | Owns | Must not own |
| --- | --- | --- |
| `rollouts.zarr` factual tables | selected action, reward metric, next step id, terminal/horizon flag, actor-valid mask, `q_train` mask, invalid reason codes, target-label validity, support strata, behavior policy provenance | trainer-specific scalar TD target, network-selected bootstrap action, checkpoint-dependent predictions |
| `q_h/` derived view | dense candidate rows, selected-transition replay fields, per-run gamma/return metadata, NaN firewall for invalid labels | claims that non-selected root candidates have factual successor states |
| trainer dataset | explicit `bootstrap_mask_kind`, successor valid counts, blocked/terminal status, horizon countdown, chosen target family | silent max over padded/invalid rows |
| trained checkpoint/report | Double-DQN selector/evaluator details, target-network cadence, calibration, oracle-rescored policy value, support-stratified metrics | replacing the immutable replay contract |

The default bootstrap mask should be the successor actor-valid action mask
because policy value asks what the actor could choose next. A stricter
`q_train_mask` bootstrap is a supervised-label-completeness ablation, not the
default policy target, because it can turn actor-valid but unlabeled successor
actions into invisible actions. Both masks should be reportable.

### All-Invalid And Blocked Successors

The trainer must distinguish at least three cases:

| Case | Backup action |
| --- | --- |
| horizon terminal or no next step | bootstrap term is zero; `td_terminal_mask=true` |
| successor table exists but actor-valid mask is empty | bootstrap term is zero; row is `blocked_successor` / all-invalid diagnostic, not a normal terminal |
| actor-valid successors exist but `q_train_mask` is empty | default policy backup can use actor-valid mask; supervised-label backup is blocked and must be reported separately |

Do not implement all-invalid handling as `max(-inf)` followed by a finite
sentinel. It should be an explicit blocked row with zero bootstrap contribution,
valid-count diagnostics, and a reason code. Otherwise an invalid-row firewall
test can pass at the candidate table while the trainer still leaks invalid filler
values through the target.

### Critique And Architecture Implications

1. **Selected-transition replay is not all-candidate transition replay.** The
   current store records the successor state for the selected action. Non-selected
   root candidates may have one-step oracle labels, but they do not have factual
   next-state candidate tables unless the rollout expanded those branches.
   `Q_H` training should not pretend otherwise.
2. **Gamma remains an experiment parameter, not a thesis constant.** Store
   `td_discount`/`discount_gamma` per view or run, but keep exact gamma/clipping
   in open decisions until evaluation gates choose it.
3. **Direct finite-horizon returns and bootstrapped targets are different
   evidence.** If materialized rollout traces contain `G_t^(H)`, they can support
   supervised finite-horizon return fitting. Double-DQN bootstrapping is the
   first value-learning target family, not a substitute for oracle lookahead
   evidence.
4. **The upper bound must optimize the same return family or be labeled as a
   separate diagnostic.** If `Q_H` trains on cumulative root-normalized return,
   bounded oracle lookahead should select by that return when used as the upper
   reference; endpoint gain can still be the policy-evaluation metric.
5. **IQL/CQL belong behind mask/support reports.** Offline-RL sophistication is
   only meaningful after all-invalid successor handling, behavior-support
   strata, and Double-Q overestimation diagnostics are visible.

### Tests And Fields To Add Before A Trainer Claim

- all-invalid successor actor-valid mask: zero bootstrap, blocked status, no
  finite invalid filler value;
- successor `q_train_mask` empty but actor-valid non-empty: default versus
  supervised-label bootstrap paths diverge explicitly;
- terminal horizon versus blocked successor status are separate fields;
- selected-action lineage maps current step to the exact successor step/candidate
  table;
- `td_reward` continues to use `target_root_gain`; diagnostic target RRI never
  becomes the default reward through a fallback;
- padded invalid rows with extreme features/logits cannot alter valid-row
  targets;
- reports include successor valid count, successor trainable count,
  `bootstrap_mask_kind`, blocked reason, horizon remaining, rollout policy, and
  target-valid status.

### Recommendation

Promote this sentence into the thesis method before implementing the trainer:

> `Q_H` is trained from selected-action finite-candidate replay. The immutable
> rollout store records factual selected transitions and masks; Double-DQN or
> supervised return targets are trainer-derived views over those facts. The
> bootstrap max ranges only over an explicitly declared successor mask, and
> all-invalid or label-empty successors are blocked diagnostic rows with zero
> bootstrap contribution, not low-reward actions.

## Iteration 33: Sequence-Model Planners Versus Rollout-Diversity Knobs

Decision Transformer and Trajectory Transformer are tempting because they turn
offline RL into trajectory modeling. For ARIA-NBV, they should remain bridge
ideas, not the first planner. The current thesis contract is more constrained:
finite candidate tables, hard masks, actor-visible state, oracle-selected
training labels, selected-transition replay, and equal-budget oracle
re-evaluation. A return-conditioned or autoregressive trajectory model would
replace several of those contracts at once, making it harder to interpret
whether gains come from non-myopic target-RRI reasoning or from behavior cloning,
model likelihood, discretization, and beam-search heuristics.

Gumbel-Top-k is different. It can improve rollout support without changing the
`Q_H` value-head contract: sample diverse valid candidate branches without
replacement, persist the sampling distribution, then train/evaluate the same
finite-candidate planner. That makes it a better near-term extension than a full
sequence-model policy.

### Evidence

- Canonical memory locks random-valid, oracle-greedy/lookahead, and
  oracle-scored temperature-softmax traces before the first `Q_H` run;
  Gumbel-Top-k is preferred later diversity evidence, not a blocker.
- `docs/contents/thesis/questions.qmd` and `roadmap.qmd` put Decision
  Transformer, CQL/BCQ/IQL, and Gumbel-Top-k behind deterministic rollout trust.
  The current exit checks evaluate random-valid, one-step oracle greedy, learned
  one-step scorer, bounded oracle lookahead, temperature-softmax, and `Q_H`
  under equal budget.
- The local implementation exposes `random`, `random_valid`, `oracle_greedy`,
  and `temperature_softmax` policies. It also supports `branch_factor`,
  `beam_width`, branch-factor schedules, stochastic branch-factor schedules,
  robust temperature logits, and diversity guards.
- Temperature-softmax currently uses masked probabilities and
  `torch.multinomial(..., replacement=False)` within one expansion step, with
  tests for invalid masking, reproducibility, distinct candidates, and affine
  score-scale invariance. That is useful, but it is not the top-down
  sequence-level Gumbel-Top-k stochastic beam algorithm.
- Decision Transformer models trajectories autoregressively as
  return-to-go/state/action token sequences and generates actions by conditioning
  on desired future return. Its transfer to ARIA would be a policy/modeling
  ablation after return and replay rows are stable.
- Trajectory Transformer models states/actions/rewards as discrete trajectory
  tokens, uses beam search as a planner, and warns that reward-to-go estimates
  are functions of the behavior policy. It is relevant as a sequence-planning
  bridge, especially for Q-guided search, but it introduces discretization,
  likelihood-model, beam-width, and model-exploitation risks.
- Gumbel-Top-k/Stochastic Beam Search gives samples without replacement from a
  sequence distribution and avoids duplicate low-entropy beams with linear cost
  in sample size and sequence length. ARIA can adopt the no-replacement branch
  sampling idea without adopting a full trajectory language model.

### Architecture Ladder

| Stage | Role | Promote only if |
| --- | --- | --- |
| deterministic greedy/lookahead | trusted headroom estimate | target protocol, masks, lineage, and oracle scoring pass |
| temperature-softmax rollout data | support/diversity data source | deterministic rollouts replay exactly and score normalization is reported |
| Gumbel-Top-k branch selection | principled no-replacement stochastic branch diversity | branch provenance, Gumbel seeds, log-probs, temperature, inclusion/threshold metadata, and diversity metrics are persisted |
| `Q_H` candidate-query value model | primary learned non-myopic result | oracle lookahead exposes headroom and selected actions are oracle-re-evaluated |
| Decision/Trajectory Transformer | later sequence-policy or sequence-planner bridge | `Q_H` baseline and replay schema are stable, and the sequence model is compared under identical target/candidate/mask/evaluation contracts |

### Critique

1. **Do not use sequence modeling to dodge the finite-candidate proof burden.**
   A trajectory model can generate plausible actions, but the thesis still needs
   evidence that selected actions improve target endpoint gain or cumulative
   root-normalized target gain under the same candidate budget.
2. **Return conditioning is not value learning.** Decision Transformer-style
   return-to-go conditioning may imitate high-return trajectories; it does not
   by itself provide per-candidate counterfactual values, overestimation
   diagnostics, or invalid-successor handling.
3. **Beam search is not free lookahead evidence.** Trajectory Transformer-style
   beam search introduces a learned transition/likelihood model. For ARIA, the
   first lookahead evidence should remain ASE mesh/oracle rollouts, because that
   isolates whether the target-RRI objective has non-myopic headroom at all.
4. **No-replacement sampling is the actionable transfer.** Temperature-softmax
   already samples distinct candidates per expansion step; Gumbel-Top-k would
   make the stochastic branch support more principled and auditable, especially
   when valid candidate distributions are low entropy.
5. **Record sequence-policy bridges as separate baselines.** If a future
   Decision/Trajectory Transformer branch is attempted, report it as
   `sequence_policy`/`sequence_planner`, not as a replacement implementation of
   `Q_H`.

### Required Fields For A Gumbel-Top-k Extension

If Gumbel-Top-k branch selection is implemented, persist:

- policy id, score source, temperature, RNG seed, branch schedule id, and
  candidate mask version;
- per-candidate logits, Gumbel perturbations or reproducible seed material,
  log-probabilities, selected order, and no-replacement rank;
- threshold or inclusion-probability metadata if used for estimators;
- sibling diversity metrics and guard rejections;
- branch lineage linking every selected child to parent state, target id,
  candidate row id, and successor step id;
- support reports comparing random-valid, temperature-softmax, Gumbel-Top-k,
  oracle-greedy, and oracle-lookahead traces.

### Recommendation

The thesis architecture should say:

> Sequence-model RL papers motivate later trajectory-policy and trajectory-model
> bridges. The thesis-core route is narrower: first establish deterministic
> oracle-lookahead headroom and a masked finite-candidate `Q_H` baseline. Use
> Gumbel-Top-k as a rollout-diversity upgrade only after deterministic and
> temperature-softmax traces replay correctly; do not replace the typed `Q_H`
> contract with a trajectory model before the replay, mask, and oracle-evaluation
> evidence is trusted.

## `.agents/work` Leads

These notes are low-authority research/work leads under `.configs/litkg.toml`,
but they are useful for thesis risk control:

- Target selector must avoid projected-area and sparse/ambiguous matching traps.
- Invalid targets are protocol-invalid rows, not low-RRI samples.
- Candidate sampler realism, `position_id` persistence, and selected-transition
  lineage are core replay trust checks.
- Dense/semi-dense RRI stream mismatch must remain explicit: actor-visible
  semi-dense support is not the oracle evaluation stream.
- Failure interpretation should report validated subsets or negative planning
  results rather than hiding sparse headroom behind model complexity.

## Verification Evidence

- `cargo check -p litkg-core -p litkg-cli -p litkg-neo4j` passed.
- `cargo test -p litkg-core --lib` passed: 59 tests.
- `python3` manifest validator confirmed 43 rows with rank/category/adoption ideas.
- `./scripts/kg/ingest_papers.sh sync && parse && materialize && export-neo4j` passed.
- Generated registry has 38 rows with `relevance_rank`; Neo4j export has 38 nodes
  with non-empty `adoptable_ideas`.
- `make kg-show-paper KG_PAPER='EFM3D-straub2024' KG_FORMAT=json` exposes the new
  EFM3D relevance metadata.
- `make kg-show-paper KG_PAPER='e3nn-SphericalHarmonics-2025' KG_FORMAT=json`
  proves URL-only sources remain metadata-only with correct title and relevance.
- `cd docs && typst compile typst/thesis/main.typ --root . /tmp/thesis-main-litreview.pdf` passed.
- Continuation scan for the geometry section passed:
  `rg -n "Geometric Invariance|QCNet|Deja View|permutation equivariance|S\\^2" .omx/specs/autoresearch-thesis-lit-review/report.md`.
- Continuation artifact metadata parses:
  `python3 -m json.tool .omx/specs/autoresearch-thesis-lit-review/result.json`.
- Continuation KG claim check for the geometry recommendation returned
  `unverifiable` because current literature `paper:*` nodes lack source paths;
  fallback `make kg-search KG_QUERY='candidate permutation equivariance target local frame relative pose Set Transformer QCNet geometric invariance'`
  returned `docs/contents/theory/candidate_view_dependence.qmd`,
  `arXiv-SE3-Transformer`, Point Transformer, and PyTorch3D transform evidence.
- `make check-agent-memory` passed after the continuation debrief.
- `git diff --check` passed.
- Iteration 2 local archive scan covered QCNet/QCNeXt, Deep Sets,
  Set Transformer, Deja View, Point Transformer, PTv3, and KPConv TeX sources;
  the report now separates candidate-set value modeling from geometry-feature
  backbone choices and lists referenced-paper follow-up leads.
- Iteration 3 external primary-source scan covered HiVT, Perceiver, Wayformer,
  Universal Transformer, RAFT, Raptor/block-recurrent ViT evidence, DUSt3R, and
  VGGT. The report now turns those referenced papers into bounded design
  transfers for latent support memory, fusion ablations, recurrence rules, and
  geometry-representation boundaries.
- Iteration 4 local archive scan covered DQN, Double DQN, CQL, IQL, Decision
  Transformer, Trajectory Transformer, and Gumbel-Top-k. The report now frames
  `Q_H` as an offline finite-action value estimator with replay-row, support,
  overestimation, headroom, and stochastic-branch controls before architecture
  escalation.
- Iteration 5 local archive scan covered VIN-NBV, Instance-NBV, PB-NBV, SCONE,
  MACARONS, FisherRF, Next Best Sense, Hestia, and related theory/work notes.
  The report now separates target-RRI reward ownership from coverage,
  uncertainty, support, object-mask, and hierarchy signals.
- Iteration 6 local archive and theory scans covered Geometric Deep Learning,
  EGNN, SE(3)-Transformer, e3nn spherical harmonics metadata, Point
  Transformer, PTv3, KPConv, MinkowskiEngine, `rri_theory.qmd`,
  `candidate_view_dependence.qmd`, `candidate_sampling_target_selection.qmd`,
  `rl_planning.qmd`, and `.agents/work` rollout/target-selection audits. The
  report now states an explicit symmetry contract and exact-equivariance
  escalation rule.
- Iteration 7 local theory/work scans covered `rollouts.zarr`, Zarr chunking,
  preflight, invalidity, candidate provenance, `position_id`, support coverage,
  and model-evaluation metrics. The report now couples each architecture stage
  to required rollout fields, pass/fail evidence, and production preflight
  gates.
- Iteration 8 local theory/work scans covered candidate-family profiles,
  `position_id` provenance, target-selection sensitivity, Hestia, GenNBV,
  PB-NBV, and Instance-NBV. The report now makes candidate distribution an
  explicit experimental variable and separates realistic V1 motion support from
  free-shell upper-bound headroom.
- Iteration 9 local theory/work, KG-route, and literature scans covered
  OBS-SEL/PRED-Q/GT-EVAL, current target-selection implementation risks, EFM3D
  OBB reliability, Instance-NBV target-object conditioning, Project Aria
  egocentric object context, and SceneScript semantic-structure caveats. The
  report now treats target-descriptor reliability as a separate audit layer
  before target-conditioned `Q_H` claims.
- Iteration 10 local theory, KG-route, and literature scans covered
  `s_cf0`/`s_cf+`/`s_oracle` state boundaries, EFM3D/EVL feature surfaces,
  semidense/DINO point-token hypotheses, Deja View recurrent refinement, Point
  Transformer/KPConv/PTv3/Minkowski support encoders, and architecture work
  notes. The report now orders state representation from compact actor-visible
  query pools to heavier recurrence or geometry backbones.
- Iteration 11 local theory/work, KG-route, and RL literature scans covered
  DQN replay diagnostics, Double DQN overestimation control, CQL/IQL offline
  support warnings, Gumbel-Top-k stochastic beams, rollout preflight, and active
  stochastic-branch backlog. The report now treats behavior-policy support and
  replayable stochastic provenance as prerequisites for interpreting `Q_H`.
- Iteration 12 local thesis, KG-route, and simulator/NBV literature scans
  covered GenNBV, Hestia, Habitat, ProcTHOR/AI2-THOR, active 3DGS bridge
  signals, and canonical RQ5/RQ6 state. The report now defines a gated bridge
  ladder from offline `Q_H` to online discrete `Q_H`, learned transitions,
  target-then-pose continuous control, and external simulators.
- Iteration 13 local theory, KG-route, and geometry-literature scans covered
  candidate-view dependence, candidate sampling frames, PoseTW/CameraTW frame
  contracts, QCNet/QCNeXt query-centric encodings, Geometric Deep Learning,
  SE(3)-Transformer, EGNN, Point Transformer, KPConv, PTv3, and MinkowskiEngine.
  The report now defines a frame-aware invariance contract and acceptance tests
  for candidate-query `Q_H`.
- Iteration 14 local rollout-contract, implementation, KG-route, SCONE/FisherRF,
  Deja View, RAFT, and Universal Transformer scans covered selected-view
  history, `selected_depth/` provenance, pose-history observations,
  directional memory, bounded recurrent refinement, and beyond-trained-range
  recurrence failure modes. The report now gates recurrence behind selected-only
  actor-visible history and leakage/provenance tests.
- Iteration 15 local theory, KG-route, QCNet/QCNeXt, Set Transformer, Deep Sets,
  and arXiv primary-record scans covered feature-fusion ordering, query-centric
  RPE, typed/masked set attention, Perceiver/Wayformer/Scene Transformer/
  VectorNet/HiVT leads, and residual-dueling value heads. The report now makes
  one-step calibration, invalidity, and finite-horizon advantage separate
  architecture contracts.
- Iteration 16 local EFM3D, scene-embedding, KG-route, scene-encoding work-note,
  Point Transformer, KPConv, PTv3, and MinkowskiEngine scans covered EVL local
  extent limits, semidense/fused point state, compressed DINO point tokens,
  candidate-query pooling, point/sparse backbone contracts, and scene-token
  provenance. The report now treats scene encoding as a typed actor-visible
  support bank queried by target/candidate geometry.
- Iteration 17 subagent and local archive scans covered QCNet/QCNeXt,
  `docs/typst/thesis/sections/03-method.typ`, `docs/contents/ideas.qmd`, and
  the referenced Perceiver, HiVT, Scene Transformer, Wayformer, and VectorNet
  leads. The report now separates transferable query-centric local-frame/RPE
  encoder ideas from trajectory-decoder and scene-score anti-patterns for
  candidate-query `Q_H`.
- Iteration 18 added VectorNet, Perceiver, Wayformer, HiVT, and Scene
  Transformer as metadata-only `docs/literature/sources.jsonl` entries with
  relevance fields, then propagated them through litkg sync/materialize/export
  and verified representative records with `kg-show-paper`.
- Iteration 19 local thesis, KG-route, and literature scans covered VIN-NBV,
  CORAL, Double DQN, CQL, IQL, SCONE, FisherRF, and support/rollout reviews. The
  report now separates calibration, uncertainty, support, invalidity, and
  finite-horizon value targets into distinct heads and tests.
- Iteration 20 local thesis, KG-route, and literature scans covered Project
  Aria, EFM3D/EVL, Instance-NBV, SceneScript, target-selection theory, and
  target-selection work reviews. The report now defines a semantic
  target-descriptor ladder and leakage tests for actor-visible V1 target inputs.
- Iteration 21 local thesis, KG-route, and literature scans covered one-step
  greedy, bounded oracle lookahead, root-normalized target return, target
  endpoint gain, SCONE/MACARONS acquisition curves, Hestia greedy controls,
  VIN-NBV quality scoring, and submodular NBV lineage. The report now defines
  target-RRI acquisition curves and greedy/headroom baselines while rejecting
  formal submodularity guarantees unless separately proven for the ARIA
  objective.
- Iteration 22 local rollout implementation, README, work-note, and preflight
  scans covered `rollouts.zarr` schema ownership, the derived `q_h/` view,
  `selected_depth/`, `target_eval_crops/`, retention profiles,
  `feature_lift_v1.zarr`, current `nbv-rollouts-info` capabilities, and
  production preflight gaps. The report now separates replay facts, training
  caches, audit-heavy payloads, and future feature-bank ownership.
- Iteration 23 local theory, KG-route, work-note, and literature scans covered
  candidate-row permutation equivariance, local-frame/gauge consistency,
  gravity/up caveats, CW90 isolation, `S^2` directional memory, EGNN/SE(3)
  ablation boundaries, and row-shuffle/mask tests. The report now turns the
  geometric-invariance section into an explicit transformation and acceptance
  test matrix.
- Iteration 24 local QCNet/QCNeXt, VIN pose encoder, thesis method, KG-route,
  RPE/S2, and advisor-deck scans covered query-centric local-frame relative
  encodings, R6D/LFF pose controls, actor-visible target descriptors, RPE versus
  directional-memory separation, and anti-shortcut tests. The report now defines
  a concrete descriptor schema and ablation ladder for the planned
  candidate-query encoder.
- Iteration 25 local Deja View, ARIA selected-history, KG-route, and prior
  recurrence scans covered looped transformer refinement, variable-`K` training,
  beyond-range collapse, selected-only history provenance, and recurrence
  diagnostics. The report now separates recurrence step budget `K` from
  acquisition horizon `H`, candidate width `N_q`, and rollout branch width `B`.
- Iteration 26 local Point Transformer, PTv3, KPConv, MinkowskiEngine,
  EFM3D scene-embedding, scene-encoding work-note, KG-route, and subagent scans
  covered feature-bank ownership, compact query pools, point/sparse backbone
  systems contracts, and representation-bottleneck tests. The report now gates
  point backbones behind measured pool failures, provenance, invariance, and
  storage/runtime evidence.
- Iteration 27 local GDL, Deep Sets, EGNN, SE(3)-Transformer, MACARONS,
  KG-route, and ARIA VIN pose-encoder scans covered output-type-specific
  invariance/equivariance, gauge caveats, candidate permutation contracts,
  gravity-aware partial symmetry, and directional-memory tests. The report now
  maps scalar values, row-wise candidate scores, set summaries, pose/vector
  fields, directional memory, selected history, and actor/oracle evidence to
  distinct symmetry contracts.
- Iteration 28 local SCONE, MACARONS, Hestia, FisherRF, e3nn/SH, theory-page,
  KG-route, and implementation scans covered target-local directional memory.
  The report now defines a D0-D6 ladder from current support diagnostics to
  second-moment `S^2` memory, scalar novelty, Fisher-style branch diversity,
  face/incidence bins, SH/e3nn angular channels, and learned visibility-module
  ablations.
- Iteration 29 local Zhou 6D/PyTorch3D/QCNet references, VIN pose-encoder code,
  pose-generation orientation/CW90 code, theory equations, KG-route, and
  subagent scans covered pose descriptor ownership. The report now resolves the
  R6D-versus-QCNet TODO as a ladder: canonical poses, R6D/LFF row tokens,
  candidate-target scalars, query-local RPE, shell SH pose ablation, Lie/log or
  EGNN relation ablation, and bounded relation refinement.
- Iteration 30 local theory, KG, implementation, RL-literature, and subagent
  scans covered invalidity, typed masks, support-gated `Q_H`, offline support,
  and invalid-action penalty boundaries. The report now defines a typed mask
  contract that separates actor feasibility, oracle labelability, target
  validity, `q_train` eligibility, support strata, behavior support, successor
  bootstrap masks, and online invalid-action penalties.
- Iteration 31 local docs, KG, implementation, tests, and OBB/entity-matching
  literature scans covered target selection, target-to-GT matching, and
  target-label validity. The report now distinguishes OBS-SOURCE, OBS-ELIG,
  OBS-RANK, GT-EVAL-MATCH, and GT-CROP-LABEL so support/projection remain
  actor-visible eligibility/reporting fields instead of hidden GT association
  signals.
- Iteration 32 local theory, KG, implementation, tests, Double-DQN/IQL sources,
  and proposal-review scans covered `Q_H` TD-backup ownership. The report now
  separates immutable selected-transition replay from trainer-derived
  Double-DQN targets, defines successor mask choices, and makes all-invalid or
  label-empty successors explicit blocked diagnostics.
- Iteration 33 local Decision Transformer, Trajectory Transformer, Gumbel-Top-k,
  KG, thesis, memory, rollout-policy implementation, and tests covered sequence
  model planning versus rollout-diversity knobs. The report now keeps
  Decision/Trajectory Transformer as later sequence-policy/planner bridges while
  treating Gumbel-Top-k as the near-term no-replacement branch-diversity
  extension after deterministic and temperature-softmax replay are trusted.

## Remaining Open Work

- The generated TeX parser still produces imperfect titles for some parsed
  papers with macro-heavy titles. That is separate from manifest relevance
  ownership and did not block registry-level relevance integration.
- The thesis text still needs a fuller literature-review prose rewrite using the
  new manifest categories; this pass prepared the source metadata and corrected
  concrete wrong claims.
- Iteration 2 follow-up should inspect the referenced HiVT/Perceiver/Wayformer/
  Scene Transformer and Universal Transformer/RAFT/RAPTOR papers before any
  recurrence or latent-bottleneck recommendation is promoted into thesis text.
- Iteration 3 follow-up should decide whether Perceiver, HiVT, Wayformer,
  Universal Transformer, RAFT, Raptor, DUSt3R, and VGGT should become explicit
  `docs/literature/sources.jsonl` entries or remain referenced-paper leads.
- Iteration 4 follow-up should compare the planned `rollouts.zarr` schema
  against the `Q_H` training contract above and identify missing fields before
  any learned value-head implementation begins.
- Iteration 5 follow-up should propagate the support-vs-invalidity distinction
  and NBV support-channel table into the thesis method/evaluation chapters and
  into the target-selection/candidate-sampling theory pages.
- Iteration 6 follow-up should convert the symmetry contract into a thesis
  method subsection plus evaluation tests for row shuffle, duplicate rows, mask
  isolation, valid-count stress, candidate-family shifts, and frame-consistency
  checks.
- Iteration 7 follow-up should compare the current Zarr writer/reader against
  the minimum learning contract above, especially `position_id`,
  selected-transition lineage, successor candidate-table references,
  invalid-reason bitsets, scene split hashes, and production preflight JSON.
- Iteration 8 follow-up should turn the profile comparison into thesis method
  and evaluation tables, then check the current candidate generator and rollout
  writer for `position_id`, non-forward target-aware valid counts, invalid
  reasons by family, and profile-specific headroom reports.
- Iteration 9 follow-up should add the OBS-SEL/PRED-Q/GT-EVAL data-product
  table, descriptor ladder, and target-selector coverage report to the thesis
  method/evaluation chapters, then resolve the doc/code wording drift around
  support/projection as eligibility versus GT association score.
- Iteration 10 follow-up should add the representation ladder and
  target/frustum/intersection query-pool contract to the thesis method, then
  audit current rollout/model fields for the minimum R0/R1 feature set before
  planning compressed DINO caches, EVL-internal reads, recurrence, or point
  backbone ablations.
- Iteration 11 follow-up should add replay-support diagnostics, stochastic
  provenance fields, and backup-ladder evidence to the thesis evaluation plan,
  then compare current rollout writer/Zarr fields against the behavior-policy
  mixture and selected-transition requirements above.
- Iteration 12 follow-up should add the bridge ladder and simulator escalation
  gate to the thesis method/discussion, then decide whether the RQ5 online
  discrete `Q_H` scope is bridge design, smoke experiment, or quantitative
  comparator after the offline `Q_H` evidence exists.
- Iteration 13 follow-up should turn the frame-aware invariance contract into
  a thesis method subsection and implementation tests for row shuffle, duplicate
  rows, mask isolation, translation/yaw consistency, CW90 isolation, and depth
  convention provenance.
- Iteration 14 follow-up should add the memory ladder to the thesis method,
  align rollout/Zarr metadata around `selected_successor_state_history`, and
  implement leakage tests that prove `Q_H` cannot consume unselected candidate
  renderings before any recurrent history encoder is trained.
- Iteration 15 follow-up should turn the fusion ladder and residual-dueling
  `Q_H` decomposition into thesis method prose, then add implementation tests
  for absolute-head contamination, valid-mean subtraction, invalid-row firewall,
  token-source ablations, and early/late fusion comparisons.
- Iteration 16 follow-up should turn the scene/support encoding ladder into a
  thesis method subsection and decide whether a `feature_lift_v1.zarr` or
  equivalent point-feature cache is the right first artifact for compressed
  DINO@point and candidate-query pooling experiments.
- Iteration 17/18 follow-up should decide whether VectorNet, Perceiver,
  Wayformer, HiVT, and Scene Transformer need local TeX/PDF downloads and parse
  bodies, or whether metadata-only indexing plus primary-source links is enough
  for the thesis literature-review scope.
- Iteration 19 follow-up should turn the calibration/support test table into
  thesis evaluation prose and implementation checks for one-step reliability,
  Double-Q overestimation, support-stratified value metrics, invalid firewalls,
  and uncertainty/reward disagreement.
- Iteration 20 follow-up should turn the semantic target-descriptor ladder into
  thesis method/evaluation prose, then audit rollout/model feature fields for
  target source mode, selector rank, actor-visible crop provenance, class/source
  stratification, GT-match status separation, and V0/V1 leakage guards.
- Iteration 21 follow-up should add acquisition-curve and AUC reporting to the
  thesis evaluation plan, then ensure rollout/evaluation outputs persist
  per-step target error, endpoint gain, cumulative root-normalized return,
  policy id, candidate profile, seed, horizon, valid counts, invalidity reasons,
  selected candidate lineage, and proxy-mismatch diagnostics.
- Iteration 22 follow-up should reconcile the draft rollout contract against
  live code and the data-handling README, add or document a production
  `nbv-rollouts-info --preflight --profile production --json` gate, decide
  `feature_lift_v1.zarr` ownership, add collection-level shard manifests and
  scene-split validation, and make invalidity reason parity visible across
  writer, validator, inspector, preflight, and training masks.
- Iteration 23 follow-up should add the geometric-invariance test matrix to the
  thesis method/evaluation chapters and eventually implement candidate-set model
  tests for row shuffle, padded invalid rows, duplicate rows, translation/yaw
  gauge changes, CW90 isolation, `S^2` memory rotation consistency, and
  declared exact-equivariance ablations.
- Iteration 24 follow-up should turn the query-centric descriptor schema into
  thesis method prose and later code fixtures: canonical pose storage, derived
  descriptor caches with frame tags/source hashes, R6D/LFF controls,
  target/query-local RPE fields, with/without strategy provenance, RPE-vs-S2
  ablations, and actor-feature schema checks excluding GT fields.
- Iteration 25 follow-up should add recurrence budget wording to the thesis
  method/discussion and, only if recurrence is implemented, log state norm,
  relative update norm, cosine-to-final-state, value/logit deltas, rank
  stability, calibration, oracle-rescored endpoint gain, and runtime by `K`.
- Iteration 26 follow-up should turn the feature-bank escalation gate into
  thesis method/evaluation prose, decide the exact `feature_lift_v1.zarr`
  schema owner, and later add tests for point-order shuffle, source dropout,
  feature schema hashes, kNN/radius or serialization sweeps, voxel-origin audits,
  and storage/runtime reports before any point/sparse backbone is promoted.
- Iteration 27 follow-up should turn the symmetry output contract into a thesis
  method subsection and tests for row permutation, global translation/yaw gauge,
  paired S2 rotation, selected-history ordering, exact-equivariance ablation
  error, and CW90/display isolation.
- Iteration 28 follow-up should add the directional-memory ladder to thesis
  method/evaluation text, then decide the first artifact schema for actor-visible
  target/support cells, `M_dir`, `u_vis`, `u_info`, `u_dir`, candidate-family
  support bins, branch-overlap reports, paired `S^2` rotation tests, and SH
  `lmax`/normalization/runtime reports.
- Iteration 29 follow-up should update shared equations and thesis method text
  so R6D/LFF is the default per-row pose token, QCNet-style query-local RPE is
  the relation-aware set-model ablation, shell SH is a shell-profile pose
  ablation, and CW90/display correction tests are explicit.
- Iteration 30 follow-up should turn the typed mask/support contract into
  thesis method/evaluation text and later implementation checks for invalid
  firewall behavior, all-invalid successor terminal handling,
  `q_train`/target-valid/oracle-label parity, reason-code roundtrips,
  support-stratified `Q_H` metrics, behavior-support splits, Double-Q
  overestimation diagnostics, and online invalid-action penalty ablation
  boundaries.
- Iteration 31 follow-up should update thesis method text and `questions.qmd`
  wording so support/projection are OBS-ELIG/OBS-RANK fields, not default
  GT-EVAL-MATCH rank terms; add target-protocol reports for target counts,
  invalid reasons, score factors, IoU/gap ambiguity, crop validity, paired V0/V1
  audits, and visual actor-visible-versus-GT overlays; and consider stable
  target-label invalidity codes for empty mesh crops and sparse current target
  support before large-scale rollout generation.
- Iteration 32 follow-up should update thesis method text and the eventual `Q_H`
  trainer contract so replay facts, trainer targets, and checkpoint predictions
  stay separate; add all-invalid successor tests, successor valid/trainable-count
  fields, `bootstrap_mask_kind`, blocked successor reasons, terminal-versus-blocked
  status, horizon countdown, selected-action lineage checks, and support-stratified
  Double-Q overestimation diagnostics.
- Iteration 33 follow-up should update rollout-support text and any future
  branch-selector issue so Gumbel-Top-k is a no-replacement rollout-diversity
  upgrade with persisted score source, temperature, seed, perturbation/rank
  metadata, inclusion/threshold metadata if used, sibling-diversity reports, and
  branch lineage; keep Decision/Trajectory Transformer baselines separate from
  the primary finite-candidate `Q_H` result.
