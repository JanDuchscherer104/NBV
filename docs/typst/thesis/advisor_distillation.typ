#import "template/layout/proposal_template.typ": *
#import "metadata.typ": *
#import "../shared/macros.typ": *
#import "../shared/glossary.typ": *
#import "../shared/symbols.typ": symb
#import "../shared/equations.typ": eqs
#import "sections/proposal/_style.typ": *

#let proposalTitleEnglish = "ARIA-NBV: Target-Conditioned Thesis Plan"
#let proposalTitleGerman = "ARIA-NBV: Zielkonditionierter Forschungsplan"

#let advisor-style(body) = {
  set text(size: 10.2pt)
  set par(leading: 0.92em, justify: true)
  set math.equation(numbering: "(1)")
  show heading.where(level: 1): set block(above: 1.25em, below: 0.62em)
  show heading.where(level: 1): set text(size: 14.2pt, weight: 700, fill: proposal-blue)
  show heading.where(level: 2): set block(above: 0.9em, below: 0.36em)
  show heading.where(level: 2): set text(size: 11.1pt, weight: 650, fill: proposal-red)
  show figure.caption: set text(size: 8.2pt, fill: proposal-muted)
  show math.equation: set text(size: 10pt, weight: 400)
  show table.cell: it => {
    set text(size: 8.15pt)
    set par(justify: false, leading: 0.72em)
    it
  }
  show table.cell.where(y: 0): it => {
    set text(size: 8.15pt, weight: 680, fill: proposal-blue)
    set par(justify: false)
    it
  }
  set table(inset: (x: 5pt, y: 4pt))
  body
}

#let claim-box(title, body) = block(above: 0.5em, below: 0.7em, breakable: true)[
  #rect(
    width: 100%,
    radius: 3pt,
    inset: (x: 7pt, y: 6pt),
    fill: proposal-blue.lighten(95%),
    stroke: 0.45pt + proposal-blue.lighten(55%),
  )[
    #text(size: 8.1pt, weight: 700, fill: proposal-red)[#smallcaps(title)]
    #v(3pt)
    #body
  ]
]

#let rq-node(title, body, critical: false) = rect(
  width: 100%,
  radius: 3pt,
  inset: (x: 7pt, y: 5pt),
  fill: if critical { proposal-red.lighten(93%) } else { proposal-blue.lighten(96%) },
  stroke: 0.45pt + if critical { proposal-red.lighten(45%) } else { proposal-blue.lighten(58%) },
)[
  #text(size: 8pt, weight: 700, fill: if critical { proposal-red } else { proposal-blue })[#title]
  #h(4pt)
  #text(size: 8pt, fill: proposal-ink)[#body]
]

#let rq-down() = align(center)[
  #text(size: 9.5pt, fill: proposal-muted)[#sym.arrow.b]
]

#let gantt-bar(start, duration, critical: false) = {
  let total = 154
  let tail = total - start - duration
  grid(
    columns: (start * 1fr, duration * 1fr, tail * 1fr),
    column-gutter: 0pt,
    [],
    rect(
      height: 7pt,
      radius: 2pt,
      fill: if critical { proposal-red } else { proposal-blue },
    ),
    [],
  )
}

#let gantt-row(label, start, duration, critical: false) = grid(
  columns: (0.27fr, 0.73fr),
  column-gutter: 6pt,
  align: horizon,
  {
    set par(justify: false, leading: 0.78em)
    text(
      size: 8.1pt,
      weight: if critical { 700 } else { 500 },
      fill: if critical { proposal-red } else { proposal-ink },
    )[#label]
  },
  gantt-bar(start, duration, critical: critical),
)

#set document(title: proposalTitleEnglish, author: author)
#set text(font: "New Computer Modern")

#show: make-glossary.with(link: false)
#register-aria-glossary()

#show: proposal.with(
  title: proposalTitleEnglish,
  titleGerman: proposalTitleGerman,
  thesisKindEnglish: thesisKindEnglish + " Advisor Handout",
  thesisKindGerman: "Betreuer-Handout zur " + thesisKindGerman,
  academicDegree: academicDegree,
  program: program,
  specialization: specialization,
  universityEnglish: universityEnglish,
  universityGerman: universityGerman,
  facultyEnglish: facultyEnglish,
  facultyGerman: facultyGerman,
  firstExaminer: firstExaminer,
  secondExaminer: "",
  supervisors: supervisors,
  author: author,
  email: email,
  matriculationNumber: matriculationNumber,
  startDate: startDate,
  submissionDate: datetime(day: 8, month: 5, year: 2026),
  submissionDateText: "8 May 2026",
  transparency_ai_tools: [
    AI-assisted tools were used to consolidate repository documentation, check proposal consistency, and draft this advisor handout. The author remains responsible for the final research scope, technical claims, citations, and submitted document.
  ],
)

#show: proposal-style
#show: advisor-style

= Current State and Thesis Contract

The implemented ARIA-NBV substrate provides #gls("aria-synthetic-environments") snippets with poses, calibration, semidense geometry, #gls("ground-truth") meshes, #gls("egocentric-voxel-lifting") scene encodings, scene-level oracle #gls("relative-reconstruction-improvement") labels, finite candidate tables, and a VIN one-step scorer inspired by quality-driven #gls("next-best-view") ranking @projectaria-engel2023 @ProjectAria-ASE-2025 @EFM3D-straub2024 @EVL-Doc-2025 @VIN-NBV-frahm2025. #ASE supplies Aria-like synthetic sensor trajectories, aligned semi-dense maps, and GT annotations at indoor-scene scale @ProjectAria-ASE-2025. #EVL supplies frozen egocentric voxel evidence and object-support signals for actor-visible target records @EFM3D-straub2024 @EVL-Doc-2025.

The thesis tests a single planning hypothesis: after target-specific supervision and actor-visible target selection are defined, finite-candidate oracle lookahead should expose whether non-myopic target-specific #RRI headroom exists, and a learned finite-horizon value model should recover part of that headroom under matched oracle re-evaluation. VIN-NBV provides the one-step reconstruction-quality ranking precedent; GenNBV and Hestia motivate continuous and hierarchical #NBV extensions, but their primary objectives remain coverage-like rather than target-specific point-mesh #RRI @VIN-NBV-frahm2025 @GenNBV-chen2024 @Hestia-lu2026.

#claim-box([Thesis contract])[
  The system object is a leakage-safe finite-candidate target-specific #RRI decision process on #ASE/#EVL. Given an #ASE snippet, an actor-visible target record, a finite valid candidate set, and a fixed horizon, ARIA-NBV measures target-specific point-mesh #RRI, estimates non-myopic headroom by oracle lookahead, and learns #symb.rl.qh from actor-visible inputs to recover that headroom. The learned state-action value model induces the finite-action policy $pi_(Q)$.

  The success rule is conditional: if #symb.entity.lookahead_headroom is positive on the evaluated split, #symb.rl.qh should improve over the learned myopic target scorer under matched oracle re-evaluation. If headroom is near zero, the thesis reports a negative planning result for the evaluated candidate generator, horizon, target set, and split.

  Scope limits: the handout does not claim full continuous-control #NBV, online RL, real-device deployment, or replacement of target-specific point-mesh #RRI by coverage, uncertainty, or semantic proxy objectives.
]
The contribution is fourfold: a leakage-safe target-specific #RRI protocol, a headroom-measured finite-candidate planning test, a geometry-aware residual #symb.rl.qh value model, and support-aware rollout generation. The validation sequence follows that order: target-specific #RRI label construction, a calibrated target-conditioned one-step scorer over potential counterfactual views, oracle lookahead headroom, and residual dueling #symb.rl.qh over finite valid candidates. Online discrete interaction, continuous target-then-pose policies, and simulator-backed actor-critic are escalation studies; they enter only if they preserve this #emph[finite-candidate target-specific #RRI comparison].

= Formal Model and Research Questions

The initial non-myopic experiment is a #emph[masked finite-horizon candidate-decision process], not a stationary deployment MDP. It is an offline, mesh-supervised #emph[controlled counterfactual replay] process: the oracle may render selected candidates and regenerate the next candidate table as part of the experimental protocol, while the actor sees only the typed state features below. After fixing the root snippet, target, candidate generator, RNG seed, transition rule, and horizon, the process can be treated as MDP-like over valid candidate indices:

$
  cal(M)_"NBV"
  =
  (
    cal(S)^"hist",
    cal(S)^"cf0",
    cal(S)^"oracle",
    {cal(A)_t},
    T,
    r_t^e,
    gamma,
    H
  ).
$

== State and Visibility

The model separates #emph[logged snippet state], #emph[counterfactual actor state], and #emph[privileged oracle state] because real egocentric trajectories contain modalities that are not available after synthetic view choices. The raw historic state is the actor-visible state available on the logged #ASE trajectory:

$
  #symb.rl.s_hist
  =
  (
    #symb.obs.img_rgb,
    #symb.obs.pose,
    #symb.obs.points_semi_t,
    #symb.vin.field_evl_t,
    #symb.entity.target_hyp_pred_t
  ).
$

The symbol #symb.obs.points_t denotes the accumulated fused point-set proxy after selected logged or rendered views. It does not include the frozen EVL tensor, target descriptor, directional $bb(S)^2$ memory, candidate feature table, or learned history tokens. The minimal counterfactual actor state freezes the root EVL field and updates the fused geometry proxy, selected-view history $bold(h)_t$, remaining horizon metadata $b_t$, target descriptor, candidates, masks, and reason codes:

$
  #symb.rl.s_cf0
  =
  (
    #symb.vin.field_evl_0,
    #symb.obs.points_t,
    #symb.entity.target_desc,
    bold(h)_t,
    b_t,
    #symb.rl.candidate_table,
    #symb.rl.candidate_mask,
    #symb.rl.invalid_reasons
  ).
$

The privileged oracle state augments this counterfactual actor state with GT geometry, the matched target mesh, all-candidate rendered points, and oracle labels. It is used for label generation, upper-bound planning, and evaluation:

$
  #symb.rl.s_oracle
  =
  (
    #symb.rl.s_cf0,
    #symb.ase.mesh,
    #symb.ase.mesh_target,
    {#symb.obs.points_cand_ti}_(i=1)^(N_q),
    {r_t^e (i)}_(i=1)^(N_q)
  ).
$

A candidate row is one available candidate view at step $t$: pose, view direction, provenance, support fields, validity mask, invalid reason, and candidate features. The action is the valid row index, and $q_t=q_(t,a_t)$ is the selected candidate pose:

$
  #eqs.rl.finite_action_set
$

#emph[Invalidity is modeled as a constraint]. Masks apply before argmax, temperature softmax, loss targets, and bootstrap maximization. True infeasibility or absent evaluation samples are invalid rows; low immediate target support is reported as a diagnostic unless it prevents a valid oracle evaluation.

== Target-Specific RRI Labels

The target protocol has two named regimes. V0 uses GT OBB target input as a diagnostic upper-bound path. #emph[V1] is the main #emph[actor-visible protocol]: Observed Target Selection (OBS-SEL) chooses from observed or predicted target hypotheses; Predicted-Target Q (PRED-Q) conditions the one-step scorer or #symb.rl.qh on actor-visible target descriptors; Ground-Truth Target Evaluation (GT-EVAL) uses #emph[GT OBBs and target mesh crops only for labels, matching checks, and evaluation]. The actor-visible descriptor is

$
  #eqs.entity.target_descriptor
$

In this descriptor, $hat(bold(B))_e$ is observed or predicted OBB geometry; $hat(bold(y))_e$ is class probabilities or class embedding; $hat(p)_e$ is confidence; $A_e^"proj"$ is projected area; $n_e^"semi"$ and $n_e^"EVL"$ are semidense and EVL support counts; and $bold(T)_e^"rel"$ is relative target pose. The OBB-level descriptor is paired with an actor-visible crop ablation that pools spatial feature fields inside $hat(bold(B))_e$.

#emph[Target selection] and #emph[target-to-GT matching] are different operations. The current thesis contract separates hard actor-visible eligibility, target-interest ranking or sampling, and deterministic GT matching. For training/root diversity, OBS-SEL may sample actor-visible target hypotheses by top-$K$, temperature-softmax, or a later stratified target sampler over support/visibility/distance/class strata:

$
  P(hat(e)_j | #symb.rl.s_hist)
  =
  (exp(beta u_(t,j)^"tar"))
  /
  (sum_(l in cal(E)_t^"obs") exp(beta u_(t,l)^"tar")).
$

After a target hypothesis $hat(e)$ is selected, GT-EVAL deterministically matches it to a GT target for labels and evaluation. The scale contract keeps support and projected visibility as eligibility/audit fields; GT association itself is class-compatible 3D IoU with an ambiguity gap:

$
  mu(hat(e), e)
  =
  kappa(hat(y)_(hat(e)), y_e)
  dot
  op("IoU")_3D(hat(B)_(hat(e)), B_e^"GT")
$

Here $mu_1$ is the best match score, $mu_2$ the runner-up score, and $g_mu$ the top-1/top-2 gap. The validated target subset is defined by symbolic acceptance filters:

$
  #eqs.entity.target_match_acceptance
$

The numeric values of $tau_mu$, $tau_"gap"$, and target eligibility thresholds remain advisor-level protocol parameters. Unmatched, unsupported, or ambiguous targets are target-invalid protocol cases rather than low target-specific #RRI examples. Projected target feasibility uses clipped visible image-overlap area, not raw projected extents outside the image.

Let $C_e (#symb.obs.points_t)$ denote the oracle-only crop of accumulated points to the matched target region. The target error is the target-cropped version of the VIN-NBV #RRI objective @VIN-NBV-frahm2025: point-to-mesh accuracy plus mesh-to-point completeness on the crop. Area weighting or uniformly sampled target-surface points prevent target-specific #RRI from reflecting mesh tessellation density. For reproducibility, the current implementation computes the point-mesh distances through `OracleRRI.score` and `chamfer_point_mesh_batched`, while `aria_nbv.pose_generation.target_counterfactuals` owns the target crop. Rollout ranking and #symb.rl.qh training use root-normalized target gain; scene-level #RRI is a diagnostic bridge to the older seminar oracle pipeline, not the optimized reward.

$
  #eqs.entity.target_error
$

$
  #eqs.entity.target_rri_reward
$

$
  #eqs.entity.finite_horizon_return
$

$
  #eqs.entity.endpoint_gain
$

$
  #eqs.entity.log_gain
$

#symb.entity.endpoint_gain is the #emph[primary fixed-horizon endpoint metric], #symb.entity.return_h is the #emph[rollout training return], and #symb.entity.log_gain is only an algebraic #emph[scale-sensitivity ablation]. Since each immediate #RRI term is normalized by the current target error, the additive return is not algebraically identical to endpoint gain; the former supports value fitting and the latter supports fixed-horizon interpretation.

== Candidate Transitions

Selecting a candidate means choosing a valid index $a_t=i in cal(A)_t$ and then rendering or retrieving only $q_(t,i)$ for the transition. Oracle rendering follows the repository's PyTorch3D depth-rendering path, so camera-frame and rasterizer conventions are part of the label contract rather than model input @PyTorch3D-Cameras-2025. The rollout writer keeps all-candidate renders oracle-only for scoring and persists only materialized selected/parent depth at a canonical configured resolution as actor-history state for successor #symb.rl.qh encoders. Target-eval crop point payloads are sampled/audit retention; scalar target distances, support counts, and gains are training-core facts. Greedy selection chooses the highest current score; temperature-softmax widens rollout support over valid candidate scores; Gumbel-Top-$K$ is a deferred diversity method if temperature-softmax produces insufficient branch diversity:

$
  P(a_t = i | s_t)
  =
  (exp(beta ell_(t,i)))
  /
  (sum_(j in cal(A)_t) exp(beta ell_(t,j))).
$

After selection, the acquired geometry is added to the current geometry:


$
  #symb.obs.points_next
  =
  #symb.obs.points_t
  union
  #symb.obs.points_cand_ti.
$

The next candidate table $cal(Q)_(t+1)$ is regenerated from the updated geometry, selected-view history, and remaining horizon metadata with the same logged mixture families, while #symb.vin.field_evl_0 remains fixed. The initial mixture vocabulary contains #emph[target-point or look-at] candidates from the actor-visible target record, #emph[radial-towards/radial-away] shell candidates for local exploration, #emph[forward-rig] candidates that preserve logged trajectory direction, and #emph[bounded yaw/pitch/roll jitter] with per-row strategy provenance.

== Research Questions and Headroom

The research questions form a dependency chain: objective definition, target representation, candidate support, finite-horizon planning, scale, and optional online/continuous escalation. RQ1--RQ4 define the thesis-core tests; RQ5 and RQ6 scope scale and escalation only after the finite-candidate contract is interpretable.

#figure(
  block(width: 100%)[
    #rq-node(
      [RQ1 Objective and metrics],
      [Can target-conditioned finite-candidate #NBV improve endpoint target quality under equal budget while training on additive target #RRI returns?],
    )
    #rq-down()
    #rq-node(
      [RQ2 Target and matching],
      [Can actor-visible target descriptors and deterministic GT matching produce leakage-safe target #RRI labels at sufficient coverage?],
    )
    #rq-down()
    #rq-node(
      [RQ3 Candidate and rollout support],
      [Do mixed target-centric/exploration candidates and stochastic rollout support produce enough valid, diverse, non-myopic training data?],
    )
    #rq-down()
    #rq-node(
      [RQ4 Headroom and #symb.rl.qh],
      [Does bounded oracle lookahead expose non-myopic headroom, and can masked residual dueling #symb.rl.qh recover it over the learned myopic scorer?],
      critical: true,
    )
    #rq-down()
    #rq-node(
      [RQ5 Scaling question],
      [Which scaling path preserves mesh/oracle target #RRI supervision beyond validated subsets?],
    )
    #rq-down()
    #rq-node(
      [RQ6 Escalation question],
      [When, after finite-candidate evidence, is online discrete or continuous target-then-pose control justified?],
    )
  ],
  caption: [Research-question dependency: metric definition, target protocol, rollout support, headroom/value learning, scaling, and possible online or continuous escalation.],
) <fig:advisor-rq-dag>

Oracle lookahead selects by cumulative target-specific #RRI, while endpoint gain evaluates the resulting trajectory. Report #symb.entity.q_recovery only when the oracle-lookahead denominator is positive; otherwise report raw endpoint gains and the no-headroom condition. The headroom and recovery quantities are

$
  #eqs.entity.lookahead_headroom
$

$
  #eqs.entity.q_recovery
$

= Finite-Candidate Value Model

The value-model hypothesis is that a masked finite-candidate model can recover positive oracle-lookahead headroom from actor-visible state. #symb.rl.qh maps each valid candidate row to a finite-horizon value using actor-visible scene, target, selected-history, budget, candidate, mask, and reason-code features. Its outputs select actions, but thesis evidence comes from #emph[oracle re-scoring] of the selected trajectories.

== Design Principle: Symmetries of the Decision Problem

The model class follows the structure of the decision problem. The action space is a masked finite set of candidate views, each defined relative to a target, selected history, and partially observed geometry. Geometric deep learning supplies vocabulary for these regularities without committing the thesis to a full equivariant tensor network @GeometricDeepLearning-bronstein2021. #emph[candidate-row permutation] requires equivariant per-candidate outputs; #emph[local camera and target frames] reduce dependence on global coordinates; #emph[$bb(S)^2$ visibility memory] records where the target has already been observed; and the #emph[target record] acts as the query that determines which reconstruction errors matter.

The architectural reason to model candidates jointly is that, for a fixed state and target, immediate target-specific #RRI is a sampled utility field over feasible poses, not only an unrelated list of labels. A local view of this field is

$
  F_(s,e): op("SE")(3) -> bb(R)
$

$
  F_(s,e)(q) = op("RRI")_e(s,q)
$

Nearby candidates can be compared with $xi_(i j)=op("Log")(q_i^(-1) q_j)$, so within a stable visibility regime $F_(s,e)(q_i op("Exp")(xi)) approx F_(s,e)(q_i) + nabla_xi F_(s,e)(q_i)^top xi$. This is only a #emph[piecewise] smoothness assumption: occlusion changes, frustum boundaries, collision/validity changes, and target-support loss can create sharp discontinuities. The set model is therefore justified as a way to learn local correlation, redundancy, and regime boundaries, not as a license to smooth RRI across invalid or unsupported views. FisherRF strengthens the same intuition by treating views as overlapping information sources with diminishing returns @FisherRF-jiang2024; set models provide the permutation-equivariant machinery for the unordered candidate table @DeepSets-zaheer2017 @SetTransformer-lee2019.

#figure(
  table(
    columns: (0.78fr, 0.72fr, 1.0fr, 1.08fr),
    table.header([*Object*], [*Structure*], [*Bias*], [*Implementation role*]),
    [candidate table $cal(Q)_t$],
    [finite set],
    [permuting rows permutes per-candidate #symb.rl.qh outputs],
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
    [actor-visible target descriptor and predicted-OBB crop; GT crops remain labels/evaluation],
  ),
  caption: [Symmetry contract for the value model. Added structure is evaluated by oracle-scored endpoint target quality under the paired headroom protocol.],
) <tab:advisor-geometric-bias>

The one-step target scorer is adapted to counterfactual rollout rows rather than reusing the seminar VIN checkpoint unchanged. The inputs #symb.obs.points_t, #symb.rl.candidate_table, #symb.rl.candidate_mask, selected history, directional memory, and budget reflect the current rollout state. The scorer remains myopic and predicts immediate target-specific #RRI evidence for each candidate. #symb.rl.qh is residual around this calibrated base, with the dueling residual head as the canonical value definition.

The myopic scorer uses the CORAL ordinal-regression interface of Cao et al. and the `coral-pytorch` layer/loss implementation, adapted to ARIA-NBV's skewed oracle-RRI labels @CORAL-cao2019 @coral-pytorch-2025. The implemented seminar path first fits $K$ empirical quantile bins over oracle RRI values, converts each ordinal label to CORAL threshold targets, and decodes each threshold logit as a cumulative probability $p_k=P(y>k)$ rather than as a softmax class posterior. The scalar base $hat(r)_psi^e$ is then obtained by converting cumulative threshold probabilities into class marginals and taking an expectation over bin representatives:

$
  #eqs.rl.qh_coral_interface
$

Relative to vanilla `coral-pytorch`, the ARIA-NBV adaptation adds RRI-specific label handling and calibration: ordinal labels are converted to threshold levels internally; bin representatives $u_k$ are initialized from fitted bin means and may be learned through monotone cumulative-softplus deltas; threshold biases may be initialized from fitted class priors; balanced or focal threshold losses and monotonicity / relative-to-random diagnostics remain training controls. These additions calibrate the one-step target-RRI scorer; they do not change the thesis utility, which remains oracle-evaluated target-specific #RRI and finite-candidate #symb.rl.qh recovery under matched budgets.

Training is staged to preserve the residual interpretation: train and calibrate $hat(r)_psi^e$, then freeze or slow-finetune it while fitting the residual #symb.rl.qh, and finally ablate whether end-to-end fine-tuning improves oracle-evaluated policy performance.

The scene memory uses the frozen EVL field, accumulated actor-visible geometry, target support, and directional memory. The tensors $bold(V)(#symb.obs.points_t)$, $bold(V)_"dir" (#symb.obs.points_t)$, and $bold(V)_"target" (#symb.entity.target_desc)$ denote voxelized accumulated geometry, directional-observation channels, and target-support channels:

$
  #eqs.features.qh_scene_memory
$

The target token grounds the descriptor in actor-visible spatial evidence by reading a target-local crop from scene memory. In this equation $hat(bold(B))_e$ is the observed or predicted target OBB, not a GT crop:

$
  #eqs.features.qh_target_token
$

Candidate orientation and accumulated visibility are separate signals. The pose branch uses the continuous R6D rotation representation @zhou2019continuity. In the pose feature, $bold(t)_(t,i)$ is candidate translation, $bold(R)_(t,i)^"6D"$ is candidate orientation, $bold(t)_e$ is the target center or support centroid, $alpha_(t,i)^e$ is the target-bearing or incidence proxy, $l_(t,i)$ is acquisition/path cost, and $c_(t,i)^"strategy"$ encodes candidate-strategy provenance:

$
  #eqs.features.candidate_pose_features
$

R6D+LFF encodes each candidate token independently. The default candidate token includes relative pose to the target and selected-history summaries. Inspired by QCNet's query-centric relative encoding @zhou2023query, the interaction ablation adds target, selected-history, and other-candidate relations in candidate $i$'s local frame. Here $bold(c)_(t,i)$ and $bold(R)_(t,i)$ are the candidate camera center and orientation; $bold(p)_j$ and $bold(R)_j$ are a neighboring candidate, history, target, or scene-token representative point and orientation:

$
  #eqs.features.candidate_query_local_frame
$

The relative positional encodings are Fourier/MLP features over candidate-candidate, target-candidate, and history-candidate relations:

$
  #eqs.features.candidate_query_rpe
$

These pairwise features modulate attention keys and values rather than replacing candidate content features:

$
  #eqs.features.edge_conditioned_attention
$

Query-centric RPE and the R6D pose branch encode #emph[pose relations]. The $bb(S)^2$ memory encodes a different quantity: the #emph[accumulated distribution of viewing directions] that have already observed a target-local cell.

Accumulated visibility is an actor-visible directional memory on $bb(S)^2$. Spherical harmonics provide the higher-capacity ablation because they are functions on the sphere and expose a standard implementation path @e3nn-SphericalHarmonics-2025. Let $bold(v)$ be a voxel, point cell, or target-local cell; $bold(c)_k$ the camera center selected at step $k$; and $w_k(bold(v))$ a visibility/support weight. The baseline memory is a second moment of observed directions:

$
  #eqs.features.direction_unit
$

$
  #eqs.features.direction_memory_moment
$

Directional novelty compares a candidate viewing direction with the existing memory:

$
  #eqs.features.direction_novelty
$

Low-order spherical harmonics provide a higher-capacity directional-memory ablation @e3nn-SphericalHarmonics-2025:

$
  #eqs.features.direction_memory_sh
$

Directional-memory ablations report endpoint #symb.entity.endpoint_gain and angular diversity around the matched target crop, so representation changes are tied to observable view-selection behavior.

Each candidate row then receives pose, target-relative, frustum, belief-render, directional novelty, mask/reason, and history features. Here $bold(p)_(t,i)$ is pose/target context, $bold(g)_(t,i)$ is geometry/frustum context, $rho_(t,i)$ is the invalid-reason code, and $bold(H)_t$ is a learned selected-history token representation distinct from the horizon scalar $H$:

$
  #eqs.features.candidate_pose_context
$

$
  #eqs.features.candidate_geometry_context
$

$
  #eqs.features.candidate_row_features
$

The candidate encoder is permutation-equivariant: candidate row order may change, but the corresponding per-candidate values should permute with it. The default interaction model is a masked Set Transformer, with independent candidate MLP and pooled DeepSets controls used to test whether candidate-candidate interaction is actually needed @DeepSets-zaheer2017 @SetTransformer-lee2019:

$
  #eqs.features.qh_set_encoder
$

No-interaction candidate MLP scoring and pooled DeepSets aggregation are required baselines before attributing gains to masked Set Transformer interaction or QCNet-style RPE.

For immediate target-specific #RRI, the physical oracle label of candidate $q_i$ does not change when unrelated rows are added to $cal(Q)_t$. Candidate interaction can therefore corrupt absolute calibration if it replaces the independent scorer. The safer myopic ablation uses candidate context only as a zero-mean relative advantage correction:

$
  hat(r)_i^"set" =
    hat(r)_i^"ind"
    + lambda (
      A_i^"set"
      - (1) / (abs(cal(A)_t)) sum_(j in cal(A)_t) A_j^"set"
    )
$

This tests whether the candidate population improves ranking while preserving the independent path as the calibrated absolute RRI estimate. The case for set interaction is stronger for #symb.rl.qh because finite-horizon value genuinely depends on successor candidate tables, masks, branch support, and the candidate generator.

The value head is a dueling residual decomposition over valid actions @DuelingDQN-wang2016. $hat(r)_psi^e$ is the calibrated myopic base; $V_theta$ is shared scene-target-history value; $A_(theta,i)^H$ is candidate-specific finite-horizon advantage; and the mean advantage is subtracted only over #symb.rl.action_set_t. The decomposition fits finite candidate tables because many candidate views can be near-duplicates in value while still requiring candidate-specific corrections:

$
  #eqs.rl.qh_dueling_residual
$

== Hypothesis, Controls, and Ablations

#figure(
  table(
    columns: (0.62fr, 1.76fr),
    table.header([*Model role*], [*Content*]),
    [Hypothesis model],
    [adapted target-conditioned myopic scorer, masked Set Transformer candidate interaction, residual dueling #symb.rl.qh, hard masks/reasons, matched-budget oracle re-scoring],

    [Required controls], [independent candidate MLP and pooled DeepSets context over valid candidate rows],

    [Ablations],
    [QCNet-style candidate-local RPE, Fisher/SCONE support-overlap attention bias, $bb(S)^2$ memory variants, EGNN-style candidate graph, privileged-teacher distillation, distributional #symb.rl.qh heads],

    [Architecture ladder],
    [A0 independent scorer; A1 pooled DeepSets context; A2 masked Set Transformer; A3 Set Transformer with $op("SE")(3)$ relative bias; A4 Fisher/SCONE overlap bias; A5 residual dueling #symb.rl.qh],

    [Bridges],
    [Hestia-style target-then-pose policies, online discrete interaction, external mesh/oracle-compatible simulators, sparse/point backbones],
  ),
  caption: [Value-model hypothesis, controls, and ablations. Dense GT candidate renders may supervise later ablations, but V1 actor inputs remain actor-visible.],
) <tab:advisor-value-ladder>

= Learning Objective and Evaluation

The learned value model is interpreted only after the myopic scorer passes ranking, calibration, and oracle-selected rollout checks, and after the replay store passes support, mask, seed, and successor-table checks. These gates make the evaluation contract a scientific guardrail rather than a post-hoc reporting checklist.

The rollout store is evaluated by #emph[transition support, not only by label count]. A #symb.rl.qh dataset requires coverage of target difficulty, candidate provenance, valid and invalid near-misses, selected-chain diversity, and successor-table availability; otherwise value differences may reflect a biased candidate distribution.

#figure(
  table(
    columns: (0.72fr, 1.02fr, 1.06fr),
    table.header([*Data product*], [*Purpose*], [*Minimum evidence*]),
    [one-step all-candidate labels],
    [train and calibrate $hat(r)_psi^e$],
    [rank correlation, top-$k$ oracle hit, calibration],

    [paired greedy/lookahead roots],
    [measure #symb.entity.lookahead_headroom],
    [same root, target, seed, $N_q$, horizon, and validity masks],

    [stochastic support traces],
    [avoid fitting #symb.rl.qh only on greedy states],
    [policy entropy, unique selected chains, target visibility],

    [invalid near-misses],
    [stress hard masks and failure modes],
    [invalid-reason distribution and with/without-mask diagnostics],

    [target and candidate strata],
    [test support across target difficulty and candidate families],
    [class/support/area/occlusion bins, per-strategy #RRI histograms, successor-table availability],
  ),
  caption: [Rollout-support coverage. Target, candidate, validity, and successor-table gaps are reported before interpreting value-model differences.],
) <tab:advisor-support-coverage>

The learned one-step target scorer is the myopic control for #symb.rl.qh. Its evidence consists of held-out ranking, oracle-evaluated model-selected rollouts, calibration and stage-shift diagnostics, and Rerun examples of representative successes and failures.

#figure(
  table(
    columns: (0.62fr, 1.78fr),
    table.header([*Surface*], [*Required evidence*]),
    [One-step scorer],
    [held-out rank correlation, top-$k$ oracle hit, calibration, stage-shift diagnostics, selected-candidate oracle #RRI, target visibility, Rerun success/failure examples],

    [Candidate and replay],
    [strategy provenance, path increments, scene/target support fields, validity masks, reason codes, with/without-mask rank metrics, policy metadata, seed metadata, shuffled-candidate evaluation, duplicate-row robustness, valid-count sensitivity],

    [Scale and storage],
    [scene-level splits, paired policy comparisons, bootstrap confidence intervals, per-scene win rates, no silent coverage changes, scale axes reported separately, Zarr asset references, LRZ/Slurm/DSS/resume/storage gates],
  ),
  caption: [Evidence required before interpreting policy comparisons: scorer quality, replay integrity, and scale reporting.],
) <tab:advisor-evidence-contract>

The one-step scorer is trained on all valid candidate rows with oracle immediate target-specific #RRI labels. The bootstrapped #symb.rl.qh backup is trained only on expanded transition rows for which the selected action, successor counterfactual state, successor candidate table, successor mask, and terminal flag are materialized. If all-candidate successor expansion is unavailable, non-expanded candidates contribute myopic supervision but not bootstrapped finite-horizon targets.

The finite-candidate value model decodes actions only over valid candidate tokens:

$
  #eqs.rl.qh_candidate_token
$

$
  #eqs.rl.qh_masked_argmax
$

The initial backup is fitted masked Double-Q #cite(label("DBLP:journals/corr/MnihKSGAWR13")) @DoubleDQN-vanHasselt2015. Here $d_t=1$ at horizon termination, budget termination, or when no valid successor action exists:

$
  #eqs.rl.qh_doubleq_index
$

$
  #eqs.rl.qh_doubleq_target
$

The replay dataset $cal(D)$ contains selected-action transition rows with state, action, immediate target reward, successor state, validity masks, and terminal flags:

$
  #eqs.rl.qh_loss
$

All selected actions are re-evaluated by the oracle under identical roots, candidate budgets, and acquisition budgets. Equal budget means equal selected-view horizon $H$, candidate count $N_q$, candidate-generation distribution, and validity constraints; path length, runtime, and oracle evaluation count are reported separately. Coverage is reported against the full scale bar of 100 GT-mesh ASE scenes and 4,608 snippet windows from the current thesis contract, or against an explicit scene-level held-out subset if scale is blocked @ProjectAria-ASE-2025. Final splits are scene-level; sample-level splitting across snippets from the same scene is not valid for final claims.

Policy comparisons are paired by root snippet, target, candidate seed, candidate budget, and horizon. Report mean, median, bootstrap confidence intervals, and per-scene win rates for #symb.entity.endpoint_gain, #symb.entity.return_h, and invalidity; #emph[scene-level failures] are reported separately from global averages.

#figure(
  table(
    columns: (0.72fr, 0.58fr, 0.58fr, 0.52fr, 1.3fr),
    table.header([*Policy*], [*Actor input*], [*GT decision*], [*H*], [*Role*]),
    [$pi_"rand"$], [yes], [no], [1], [lower reference over valid candidates],
    [$pi_"learned-1"$], [yes], [no], [1], [myopic learned target scorer],
    [$pi_"oracle-1"$], [no], [yes], [1], [one-step oracle upper bound],
    [$pi_"oracle-look"$], [no], [yes], [$H$], [cumulative-#RRI headroom estimate],
    [$pi_Q$], [yes], [no], [$H$], [learned recovery over myopic scoring when headroom is positive],
  ),
  caption: [Leakage-aware policy comparison. Report #symb.entity.endpoint_gain, #symb.entity.return_h, scene #RRI, cost, invalidity, runtime, and coverage for each row.],
) <tab:advisor-policy-comparison>

= What We Adopt From Prior Work

The literature is used as an evidence ledger, not as a source of additional thesis objectives. Each source family contributes one role: objective precedent, substrate, model bias, backup rule, target-focus contrast, coverage contrast, or bridge. The table keeps object-centric 3DGS as evidence that target-focused view utility is a relevant contrast, while preserving ASE mesh-supervised target-specific #RRI as the thesis utility.

#figure(
  table(
    columns: (0.9fr, 1.72fr, 1.18fr),
    table.header([*Source family*], [*Adopt for ARIA-NBV*], [*Boundary*]),
    [VIN-NBV @VIN-NBV-frahm2025],
    [Oracle point-mesh #RRI labels, ordinal target #RRI ranking, learned myopic control.],
    [One-step ranking alone does not establish multi-step planning.],

    [Project Aria / #ASE / EFM3D @projectaria-engel2023 @ProjectAria-ASE-2025 @EFM3D-straub2024],
    [Poses, calibration, semidense points, frozen EVL/EFM evidence, OBB predictions.],
    [GT geometry and GT OBBs are labels/evaluation only.],

    [Greedy sensing @KrauseSensorPlacement2008 @AdaptiveSubmodularity-golovin2011],
    [Diminishing-returns intuition; oracle-lookahead headroom as a required test.],
    [Non-myopic learning is interpreted only after headroom is measured.],

    [CORAL, set models, QCNet, Double-Q @CORAL-cao2019 @SetTransformer-lee2019 @zhou2023query #cite(label("DBLP:journals/corr/MnihKSGAWR13")) @DoubleDQN-vanHasselt2015],
    [Ordinal target scorer, MLP/DeepSets/Set Transformer candidate controls, query-centric relative-encoding ablation, masked fitted backups.],
    [QCNet trajectory decoding, motion-forecasting losses, online streaming claims, IQL/CQL/BCQ, and distributional heads remain outside the initial value result.],

    [SCONE, MACARONS @SCONE-guedon2022 @MACARONS-guedon2023],
    [Coverage/gain prediction over partial 3D evidence and online RGB-only coverage anticipation as contrast.],
    [Surface coverage, occupancy, and RGB-only self-supervision remain contrast objectives.],

    [Object-centric 3DGS NBV @ObjectCentricNBV-jeong2026],
    [Target/object-focused view utility as evidence that object-level metrics should be reported separately.],
    [3DGS object vectors, uncertainty, and representation state do not replace EVL/predicted-OBB target inputs or target-specific point-mesh #RRI.],

    [Geometric ML and scale bridges @GeometricDeepLearning-bronstein2021 @EGNN-satorras2021 @SE3Transformer-fuchs2020 @ProcTHOR-deitke2022 @Habitat-savva2019 @IsaacSim-Sensors-2025 @MinkowskiEngine-choy2019 @point-transformer-zhao2021 @PointTransformerV3-wu2024 @KPConv-thomas2019],
    [Symmetry vocabulary, optional equivariant graph ablations, simulator substrate questions, and sparse/point-backbone scaling references.],
    [Full equivariant tensor networks, external simulators, and point backbones remain scale or ablation studies.],

    [GenNBV, Hestia, 3DGS, SceneScript @GenNBV-chen2024 @Hestia-lu2026 @FisherRF-jiang2024 @SceneScript-avetisyan2024],
    [Continuous-control pressure, directional face/visibility memory, semantic/global-memory extensions.],
    [Proxy coverage and semantics are not replacements for #emph[target-specific point-mesh #RRI].],
  ),
  caption: [Adopted literature roles. Each source family contributes a specific design transfer or contrast point.],
) <tab:advisor-adoption-ledger>

Hestia informs a deferred hierarchy in which a target or look-at point is proposed before choosing a feasible pose conditioned on it @Hestia-lu2026. In ARIA-NBV this factorization would keep target-specific #RRI as supervision/evaluation and treat feasibility projection or masks as constraints:

$
  #eqs.rl.target_pose_factorization
$

= Roadmap, Risks, and Decisions

The failure interpretation is part of the research contract. If M1 geometry or oracle labels fail, the contribution becomes a validation and one-step-scoring study. If target matching is sparse or ambiguous, target-specific #RRI is reported only on validated subsets with unmatched counts and acceptance filters. If #symb.entity.lookahead_headroom is near zero, the thesis reports no measurable non-myopic headroom for the evaluated split, target set, horizon, branch factor, and candidate distribution. The next diagnosis is target matching, candidate support, and supervision scale; added model complexity is justified only after those evidence gaps are ruled out. Scaling and online-discrete tests remain interpretable only if they preserve #emph[target-specific #RRI supervision].

#figure(
  rect(width: 100%, inset: 7pt, radius: 3pt, stroke: 0.4pt + proposal-rule)[
    #grid(
      columns: (0.27fr, 0.73fr),
      column-gutter: 6pt,
      align: horizon,
      [],
      grid(
        columns: (12fr, 19fr, 31fr, 30fr, 31fr, 31fr),
        column-gutter: 0pt,
        text(size: 7.2pt, fill: proposal-muted)[May],
        text(size: 7.2pt, fill: proposal-muted)[Jun],
        text(size: 7.2pt, fill: proposal-muted)[Jul],
        text(size: 7.2pt, fill: proposal-muted)[Aug],
        text(size: 7.2pt, fill: proposal-muted)[Sep],
        text(size: 7.2pt, fill: proposal-muted)[submit],
      ),
    )
    #v(3pt)
    #gantt-row([M0 advisor agreement], 0, 12)
    #gantt-row([M1 oracle/geometry validation], 12, 21)
    #gantt-row([M2 myopic baselines + scale], 33, 21)
    #gantt-row([M3 target-specific RRI protocol], 54, 21)
    #gantt-row([M4 actor-visible scorer], 75, 28)
    #gantt-row([M5 lookahead + #symb.rl.qh recovery], 103, 21, critical: true)
    #gantt-row([M6 scale/escalation analysis], 124, 14)
    #gantt-row([M7 final evidence + writing], 138, 14, critical: true)
    #gantt-row([M8 submission freeze], 152, 2, critical: true)
  ],
  caption: [Thesis timeline from 2026-04-29 to 2026-09-30. Red bars mark the headroom/value-learning result and submission freeze.],
) <fig:advisor-gantt>

Open advisor decisions are the final scene-level split; symbolic target-match thresholds $(tau_mu, tau_"gap", tau_"support")$; the CORAL-to-#symb.rl.qh interface; the initial actor-visible crop descriptor ablation; the final evidence scale and subset rule; and whether any external or online scaling substrate preserves comparable mesh/oracle target-specific #RRI labels. These choices affect the strength and scope of the final evidence, not the target-conditioned finite-candidate question.
