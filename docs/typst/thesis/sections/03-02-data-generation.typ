#import "../../shared/macros.typ": *
#import "../../shared/symbols.typ": symb
#import "../../shared/equations.typ": eqs
#import "../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

== Data Generation and Target-Specific @relative-reconstruction-improvement:short Labels

Target selection is part of the oracle data-generation pipeline. It samples supervised target tasks for target-conditioned @next-best-view:short, rather than making a deployable claim that the learned actor discovers the target of interest on its own. The learned model receives a target descriptor and is evaluated by whether its selected views improve the matched target under oracle re-evaluation.

The target descriptor records the task and the cheap evidence available for diagnostics or later descriptor ablations:

$
  #eqs.entity.target_descriptor
$

In this descriptor, $hat(bold(B))_e$ is observed, predicted, or otherwise proposed OBB geometry for the target task; $hat(bold(y))_e$ is class probabilities or class embedding; $hat(p)_e$ is confidence; $A_e^"proj"$ is projected area; $n_e^"semi"$ and $n_e^"EVL"$ are semidense and @egocentric-voxel-lifting:short support counts; and $bold(T)_e^"rel"$ is relative target pose. These fields are not all target-task gates in the first implementation. Class, confidence, current projection, semidense support, @egocentric-voxel-lifting:short support, distance, and target bearing are retained as descriptor and audit fields so that later subsets can ask whether the target-conditioned model depends on semantic correctness or observation quality.

=== Seminar Oracle Substrate and Thesis Delta

The seminar paper is implemented evidence for the one-step scene-level oracle substrate, not the current thesis objective. Its labeler constructs a candidate table for an @aria-synthetic-environments:short snippet, renders candidate depth from the @ground-truth:short mesh with the PyTorch3D camera path, backprojects and fuses candidate points with the current semi-dense reconstruction, and computes point-mesh accuracy/completeness as @relative-reconstruction-improvement:short labels @VIN-NBV-frahm2025 @PyTorch3D-Cameras-2025. ARIA-NBV reuses that substrate for label provenance, but changes the task unit: the thesis sampler first creates target tasks, target crops define the error surface, and selected counterfactual transitions are written to a standalone rollout store for finite-horizon #symb.rl.qh.

#figure(
  table(
    columns: (0.86fr, 1.24fr, 1.16fr),
    toprule(),
    table.header([*Seminar material*], [*Thesis adaptation*], [*Placement*]),
    midrule(),
    [GT-mesh depth rendering and point-mesh RRI],
    [Reused as label provenance; target crops replace whole-scene error as the primary objective.],

    [Main data-generation method plus appendix camera-convention details.],
    [Legacy shell candidate sampling],
    [Kept as a historical/free-shell ablation; current target-conditioned mixtures own the main candidate distribution.],

    [Candidate/replay method and appendix, not a default-policy claim.],
    [CORAL ordinal scorer and bin diagnostics],
    [Reused for myopic target-scorer calibration and expected-RRI controls before residual #symb.rl.qh.],

    [Value-model method and evaluation evidence gates.],
    [Immutable one-step VIN offline store],
    [Kept separate from selected-transition `rollouts.zarr`; all-candidate labels train the scorer, selected transitions train bootstrapped #symb.rl.qh.],

    [Data-flow appendix and replay evidence matrix.],
    [Run-specific W&B and cache-size notes],
    [Historical diagnostics only until regenerated from current manifests and configs.],

    [Appendix/open-work TODO, not final experiment evidence.], bottomrule(),
  ),
  caption: [How seminar-paper implementation evidence is adapted without drifting into thesis claims.],
) <tab:seminar-substrate-placement>

#conflict_todo(
  [Do not copy seminar scene-level RRI, legacy shell sampler, one-step VIN store, or run-specific CORAL/W&B results as current target-conditioned finite-horizon evidence. They are implementation substrate or historical diagnostics unless regenerated under the target-task and rollout-store protocol.],
  source: [docs/typst/seminar_paper/main.typ; docs/typst/seminar_paper/sections/05-oracle-rri.typ; docs/typst/seminar_paper/sections/07-training-objective.typ; docs/typst/seminar_paper/sections/12h-appendix-offline-cache.typ],
  gate: [final data-generation appendix and experiment-manifest refresh],
)

=== Target Selection

Automatic target selection constitutes the first procedural layer in target-centric oracle data generation. Given a historic snippet and its egocentric encodings, the sampler chooses target tasks for which supervised target-conditioned @next-best-view:short is meaningful. A useful target task must be identifiable, evaluable, and potentially action-sensitive: the oracle must know which @ground-truth:short object the task refers to, target-specific error must be computable, and at least some feasible candidate views should expose non-marginal target-specific @relative-reconstruction-improvement:short after oracle evaluation. Near-solved targets are therefore not discarded before storage, but their low headroom must be measured and preserved as evidence.

#figure(
  align(center, image(
    "../figures/oracle_target_task_sampler_contract.pdf",
    width: 100%,
  )),
  caption: [Oracle target-task sampling contract. @ground-truth:short OBBs and meshes define identity-valid supervised target tasks through an IoU and ambiguity-gap gate, a deterministic capped sampler writes target-task rows with descriptor and audit fields, and rollout generation later measures target @relative-reconstruction-improvement:short and headroom. The actor-visible target selector remains a separate diagnostic or later deployment contract, not the source of thesis labels.],
) <fig:oracle-target-task-sampler-contract>

The cheap admission gate is identity matching. A proposed target OBB is identity-valid when it matches exactly one @ground-truth:short target OBB by configured 3D IoU and ambiguity margin:

$
  mu_"id" (hat(e), e)
  =
  op("IoU")_"3D" (hat(bold(B))_(hat(e)), bold(B)_e)
$

$
  a_"id" (hat(e)) = 1
  op("iff")
  cases(
    mu_1 >= tau_"IoU",
    mu_1 - mu_2 >= tau_"gap",
  )
$

Here $mu_1$ and $mu_2$ are the best and second-best target-to-@ground-truth:short IoU scores for the proposal. The threshold values are protocol parameters, not theory constants. The implementation should use a moderate default and report a threshold sweep so that coverage can be inspected under looser and stricter identity definitions.

Class prediction and confidence do not decide target-task eligibility in the first pass. They are recorded because semantic correctness may matter for target descriptors and failure analysis, but the oracle can compute target-specific @relative-reconstruction-improvement:short for a geometrically identified target even when the class head is noisy. Current RGB projection, semidense support, and @egocentric-voxel-lifting:short support are likewise audit fields rather than hard gates unless a later subset explicitly asks for projected-only or support-qualified targets.

The sampler keeps rollout cost bounded by selecting a capped number of identity-valid targets per source snippet. Within that cap, it samples uniformly with a deterministic seed rather than always taking the largest or highest-IoU object. The audit surface must still report how many identity-valid targets existed before the cap, how many were selected, and how their IoU, ambiguity gap, class, confidence, projected area, support, distance, and bearing were distributed.

Headroom is evaluated after target selection because it depends on oracle candidate scoring. The rollout store should persist identity-valid targets even when measured target headroom is low; training and evaluation loaders can then filter or stratify by headroom band. This preserves negative evidence: if many well-identified targets have no candidate with useful gain, the result is a candidate/support/headroom limitation rather than a target-selection failure hidden by pre-filtering.

Counterfactual trajectory naturalness is a candidate and rollout diagnostic, not an identity gate. Hard turns, target-bearing changes, and support collapse should be measured with candidate provenance and invalid-reason fields so that the thesis can distinguish target identity failures from unrealistic or unsupported view proposals.

=== Candidate View Generation

Candidate view generation is the second procedural layer: it turns one target task into a finite action table for one rollout state. The current thesis profile deliberately uses a small family mixture rather than the older unconstrained shell from the seminar paper. The data-generation config `.configs/build_rollouts_v1_realistic.toml` consumes the strict VIN offline store from `vin_offline`, uses the `train` split for the first real audit subset, samples one oracle target task per source sample, and writes a separate `rollouts_v1_realistic.zarr` store. The checked-in profile is an audit-scale thesis default with 25 source samples, not an LRZ path template and not final scale evidence.

At rollout step $t$, candidate generation constructs a full shell

$
  cal(Q)_t = {q_(t,i)}_(i=1)^(N_q),
  quad
  N_q = 60,
$

with one fixed provenance component $k(i)$ per row. The canonical `v1_realistic_3family` mixture is

#figure(
  table(
    columns: (1.0fr, 0.42fr, 0.9fr, 0.9fr),
    toprule(),
    table.header([*Component*], [*Rows*], [*Center family*], [*View family*]),
    midrule(), [`forward_local`], [24], [`forward_local`],
    [`forward_rig`], [`target_bearing_local`], [24], [`target_bearing_local`],
    [`target_point`], [`lateral_target_bypass`], [12], [`lateral_target_bypass`],
    [`target_point`], bottomrule(),
  ),
  caption: [Canonical three-family finite candidate table for real thesis rollouts. Counts are full-shell rows; valid-action counts are measured after geometry and motion pruning.],
) <tab:realistic-three-family-mixture>

For each row, the raw direction is sampled in the reference rig frame. The realistic profile uses the forward-biased Power Spherical distribution from the current implementation @PowerSpherical-deCao2020:

$
  bold(u)_i ~ "PS"(bold(e)_z, kappa),
  quad
  p(bold(u)) = c_kappa (1 + bold(e)_z^T bold(u))^kappa,
  quad
  kappa = 8.
$

The draw is mapped into configured azimuth and elevation caps without rejection. With $psi = op("atan2")(u_x, u_z)$ and $u_y = sin theta$, the cap transform is

$
  psi' = psi Delta_psi / (2 pi),
  quad
  y' = sin theta_"min" + (u_y + 1) / 2 dot (sin theta_"max" - sin theta_"min"),
$

$
  bold(d)_i^0 =
  norm((sqrt(1 - y'^2) sin psi', y', sqrt(1 - y'^2) cos psi')).
$

The three position families then reinterpret this capped direction. Let $bold(f)=bold(e)_z$ be the rig-forward unit vector, $bold(b)_e$ the actor-visible target bearing in the reference frame, $bold(l)_e = norm(bold(e)_y times bold(b)_e)$ the horizontal lateral direction, and $bold(e)_y$ the world-up direction expressed in the sampling frame. The family directions are:

$
  bold(d)_i^"forward" =
  norm(bold(f) + alpha_f (bold(d)_i^0 - (bold(d)_i^0 dot bold(f)) bold(f))),
  quad
  alpha_f = 0.45,
$

$
  bold(d)_i^"target" =
  norm(bold(b)_e + alpha_t (bold(d)_i^0 - (bold(d)_i^0 dot bold(b)_e) bold(b)_e)),
  quad
  alpha_t = 0.4,
$

$
  bold(d)_i^"bypass" =
  norm(
    0.55 bold(b)_e
    + 0.85 op("sign")(d_(i,x)^0) bold(l)_e
    + op("clip")(d_(i,y)^0, -0.35, 0.35) bold(e)_y
  ).
$

Finally, the sampler draws a radius and transforms the reference-frame offset into world coordinates:

$
  r_i ~ cal(U)(0.25, 1.1),
  quad
  bold(c)_i^w = bold(T)_r^w (r_i bold(d)_i^(k(i))).
$

`forward_local` keeps the reference rig orientation. The two target-looking families orient the camera to the selected actor-visible target center $bold(p)_e$:

$
  bold(z)_i^w = norm(bold(p)_e - bold(c)_i^w),
  quad
  bold(y)_i^w =
  norm(bold(e)_y - (bold(e)_y^T bold(z)_i^w) bold(z)_i^w),
  quad
  bold(x)_i^w = bold(y)_i^w times bold(z)_i^w.
$

These equations are the mathematical description of the implemented sampler, not a claim that the mixture is optimal. The three-family design has a direct downstream impact: `forward_local` preserves egocentric motion continuity; `target_bearing_local` tests whether moving along the target bearing produces supervised target gain; and `lateral_target_bypass` creates side-step views that may improve occluded target surfaces without leaving the local walking envelope. If the target-aware families do not survive pruning, the resulting rollout dataset degenerates into a forward-only dataset and cannot support a target-conditioned planning claim.

Pruning converts the full shell into a compact valid-action table. A row remains valid only if it lies in the snippet occupancy support, stays clear of the @ground-truth:short mesh, avoids straight-line path collision, and satisfies local egocentric motion limits:

$
  ||bold(o)_i||_2 <= 1.0 "m",
  quad
  |Delta h_i| <= 0.25 "m",
  quad
  op("max")(0, -o_(i,z)) <= 0.25 "m",
  quad
  Delta psi_i <= 70 "deg".
$

The full shell is still retained with `position_id`, `strategy_id`, `mixture_id`, `sampler_probability`, rule masks, debug diagnostics, and invalid-reason bitsets. Invalid candidates are hard-masked constraints with explicit reasons. They are never low-@relative-reconstruction-improvement:short examples, and they must not enter #symb.rl.qh argmax, softmax, or loss targets. The canonical real config requires at least 15 valid root actions for a 60-row shell, matching the first production gate $op("max")(12, op("ceil")(0.25 N_q))$. This threshold is a data-support guard: it prevents low-support roots from masquerading as planning evidence, while preflight still reports the blocked roots and per-family failure modes.

=== Rollout Branch Sampling and Dataset Impact

Rollout generation samples finite branches over the valid candidate table. The canonical thesis profile materializes four recipe families:

#figure(
  table(
    columns: (1fr, 0.58fr, 0.58fr, 0.58fr, 1.12fr),
    toprule(),
    table.header([*Recipe*], [*$H$*], [*$B$*], [*Beam*], [*Selection rule*]),
    midrule(), [`random_valid`], [1], [1], [1],
    [Uniform over valid rows.], [`oracle_greedy`], [1], [1], [1],
    [Argmax of oracle target-root gain.], [`oracle_lookahead`], [2], [2], [2],
    [Bounded oracle greedy branches.], [`temperature_softmax`], [2], [2], [2],
    [Softmax over robust oracle scores with $tau=1$.], bottomrule(),
  ),
  caption: [Canonical rollout recipes for the real thesis profile. The recipes create replay diversity and oracle-lookahead references; they do not train #symb.rl.qh by themselves.],
) <tab:realistic-rollout-recipes>

For stochastic branches, let $s_i$ be the finite oracle score of valid row $i$. The robust logit used for temperature-softmax is

$
  ell_i =
  (s_i - op("median")(s)) / (op("IQR")(s) tau),
  quad
  P(i | m_i = 1) =
  exp(ell_i) / sum_(j:m_j=1) exp(ell_j).
$

The downstream effect of these choices is scientific rather than cosmetic. The target source controls what counts as a supervised task; the candidate mixture controls the support on which #symb.rl.qh can learn finite-action values; the validity rules decide which actions are admissible; and the branch sampler determines whether the replay store contains only myopic winners or also valid lower-ranked alternatives. A trustworthy thesis dataset must therefore report, per scene and target, selected target counts, valid candidates, valid candidates by `position_id`, invalid reasons by family, selected-family histograms, marginal and cumulative target-root gain, diagnostic state-relative target @relative-reconstruction-improvement:short, and storage/retention settings. Only after these diagnostics show non-degenerate target-aware support should failures or successes be attributed to planning rather than to the data-generation profile.

=== Target-Specific @relative-reconstruction-improvement:short

Let $C_e (#symb.obs.points_t)$ denote the oracle-only crop of accumulated points to the matched target region. The target error is the target-cropped version of the VIN-NBV @relative-reconstruction-improvement:short objective @VIN-NBV-frahm2025: point-to-mesh accuracy plus mesh-to-point completeness on the crop.

$
  #eqs.entity.target_error
$

Area weighting or uniformly sampled target-surface points prevent target-specific @relative-reconstruction-improvement:short from reflecting mesh tessellation density. For reproducibility, the current implementation computes the point-mesh distances through `OracleRRI.score` and `chamfer_point_mesh_batched`, while `aria_nbv.pose_generation.target_counterfactuals` owns the target crop. Empty or unsupported target crops are invalid label cases, not low-@relative-reconstruction-improvement:short samples.

The immediate training reward adapts VIN-NBV's reconstruction-improvement idea to a target crop and normalizes by the root target error rather than the current error @VIN-NBV-frahm2025. This makes equal-horizon rollouts additive against a common root baseline:

$
  #eqs.entity.target_rri_reward
$

The finite-horizon return is the discounted sum of those target rewards along a selected counterfactual branch. It is a training target for #symb.rl.qh, not a claim that the deployed system has an online continuous-control policy:

$
  #eqs.entity.finite_horizon_return
$

Endpoint gain is the primary fixed-budget comparison metric because it measures the target quality after the same number of acquisitions for each policy:

$
  #eqs.entity.endpoint_gain
$

The log-gain variant is retained as a scale-sensitivity ablation, mirroring the broader NBV literature's use of logarithmic error reduction while keeping the root-normalized endpoint gain as the default thesis metric:

$
  #eqs.entity.log_gain
$

#symb.entity.endpoint_gain is the primary fixed-horizon endpoint metric, #symb.entity.return_h is the rollout training return, and #symb.entity.log_gain is only an algebraic scale-sensitivity ablation. The default immediate rollout / #symb.rl.qh reward is root-normalized by #symb.entity.target_error_0, so with $gamma=1$ its additive return telescopes to endpoint gain up to epsilon under equal-horizon, equal-budget comparisons. The current-error denominator defines state-relative one-step @relative-reconstruction-improvement:short for diagnostics and VIN compatibility only; the final discount and clipping policy remain open protocol parameters.

#decision_todo(
  [Lock identity-IoU thresholds, ambiguity gap, per-snippet target cap, near-solved-target filtering policy for loaders, clipping, and final gamma policy.],
  source: [target-selection interview; target-selection autoresearch report],
  gate: [RQ1/RQ2 protocol freeze],
)

#validation_todo(
  [Regenerate current manifest-backed counts for one-step labels, target-task samples, rollout rows, storage footprint, render cost, invalid reasons, and target-headroom strata before presenting scale or runtime claims.],
  source: [seminar offline-cache appendix; current rollout-store contract],
  gate: [M1/M2 data-generation evidence],
)
