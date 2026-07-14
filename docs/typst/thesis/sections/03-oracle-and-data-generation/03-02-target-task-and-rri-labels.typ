#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

== Data Generation and Target-Specific @relative-reconstruction-improvement:short Labels

This chapter fixes the implementation-invariant chain from task definition to evaluation. The logged actor-visible state $s_t^"hist"$ contains observations available at the recorded root. The counterfactual actor state $s_t^"cf0"$ augments that evidence only with acquired or simulated observations that the actor contract permits. The privileged oracle state $s_t^"oracle"$ additionally contains ground-truth geometry, matched target crops, all-candidate renders, and oracle labels. The three states are distinct objects even when they share identifiers or poses.

Target selection is part of the oracle data-generation pipeline. An *oracle target task* fixes the supervised entity identity and ground-truth evaluation crop. An *actor-visible target descriptor* is the observation-derived or predicted representation supplied to a learned policy. The former defines what is evaluated; the latter defines what the actor may condition on. A target task is not a claim that the actor autonomously discovers the target of interest.

The target descriptor records the task and the cheap evidence available for diagnostics or later descriptor ablations:

$
  #eqs.entity.target_descriptor
$

In this descriptor, $hat(bold(B))_e$ is observed, predicted, or otherwise proposed OBB geometry for the target task; $hat(bold(y))_e$ is class probabilities or class embedding; $hat(pi)_e$ is confidence; $A_e^"proj"$ is projected area; $n_e^"semi"$ and $n_e^"EVL"$ are semidense and @egocentric-voxel-lifting:short support counts; $omega_e^"EVL"$ records local @egocentric-voxel-lifting:short coverage; $ell_e^"src"$ records the actor-visible source mode; and $bold(T)_(r_t,e)$ / $bold(T)_(c_t,e)$ record reference- and current-frame target geometry. These fields are not all target-task gates in the first implementation. Class, confidence, current projection, semidense support, @egocentric-voxel-lifting:short support, distance, and target bearing are retained as descriptor and audit fields so that later subsets can ask whether the target-conditioned model depends on semantic correctness or observation quality.

The finite action interface consists of a candidate table $cal(Q)_t$, hard validity mask $bold(m)_t$, and invalid-reason vector $bold(rho)_t$. The admissible set is $cal(A)_t = {i : m_(t,i)=1}$. Invalid rows remain logged for coverage and failure analysis but lie outside policy argmax, sampling, loss targets, and bootstrap maximization. Low RRI is a valid low-utility outcome; it is never an encoding for infeasibility.

For target $e$, reconstruction quality is defined by target-cropped point--mesh error $Delta_t^e$. The immediate reward is the reduction $Delta_t^e-Delta_(t+1)^e$ normalized by the root error $Delta_0^e$, the finite-horizon return accumulates those root-normalized gains, and endpoint gain compares $Delta_0^e$ with $Delta_H^e$ after a fixed acquisition budget. This shared root denominator makes cumulative gain and endpoint gain comparable; endpoint gain remains the primary policy estimand.

Oracle-lookahead headroom is the paired endpoint-gain difference between bounded oracle lookahead and one-step oracle-greedy selection. The recovered-headroom fraction compares a learned finite-horizon policy with the learned one-step control relative to that bounded oracle reference. The fraction is reported only when measured headroom exceeds a prespecified threshold derived from the oracle metric's repeatability or noise floor. Neither reference is a universal upper bound: both are conditional on the candidate generator, target pool, hard validity regime, horizon, branch factor, and acquisition budget.

#validation_todo(
  [Establish sampling-density and mesh-tessellation sensitivity before treating target-cropped point--mesh error as stable. Invariance is a required metric-validity property, not an established result.],
  source: [RQ1 metric-validity contract; peer review],
  gate: [oracle and metric validity results],
)

=== Oracle Label Provenance

The seminar paper is implemented evidence for the one-step scene-level oracle substrate, not the current thesis objective. Its labeler constructs a candidate table for an @aria-synthetic-environments:short snippet, renders candidate depth from the @ground-truth:short mesh under a calibrated camera/rasterization convention, backprojects and fuses candidate points with the current semi-dense reconstruction, and computes point-mesh accuracy/completeness as @relative-reconstruction-improvement:short labels @VIN-NBV-frahm2025 @PyTorch3D-Cameras-2025. ARIA-NBV reuses that substrate for label provenance, but changes the task unit: the thesis sampler first creates target tasks, target crops define the error surface, and selected counterfactual transitions are written to a standalone rollout store for finite-horizon #symb.rl.qh.

#figure(
  align(center, image(
    "../../figures/camera_frame_ray_contract.pdf",
    width: 100%,
  )),
  caption: [Camera-frame and ray contract behind oracle labels. Panel A fixes the candidate camera as a calibrated left-up-forward camera and renders depth from the @ground-truth:short mesh. Panel B shows the induced unprojection: a depth pixel becomes a camera-frame ray sample, is transformed into the world frame, enters the selected candidate point set, and is cropped against the matched target surface before target-specific error is scored @ProjectAria-ASE-2025 @PyTorch3D-Cameras-2025.],
) <fig:camera-frame-ray-contract>

=== Target Selection

Automatic target selection constitutes the first procedural layer in target-centric oracle data generation. Given a historic snippet and its egocentric encodings, the sampler chooses target tasks for which supervised target-conditioned @next-best-view:short is meaningful. A useful target task must be identifiable, evaluable, and potentially action-sensitive: the oracle must know which @ground-truth:short object the task refers to, target-specific error must be computable, and at least some feasible candidate views should expose non-marginal target-specific @relative-reconstruction-improvement:short after oracle evaluation. Near-solved targets are therefore not discarded before storage, but their low headroom must be measured and preserved as evidence.

#conflict_todo(
  [Resolve the admission rule. The canonical protocol admits identity-valid, evaluable targets before headroom measurement and preserves near-zero-headroom cases; non-marginal candidate gain therefore cannot also be a target-admission requirement.],
  source: [same section target-selection protocol; roadmap; candidate-sampling theory],
  gate: [target-task eligibility freeze],
)

#figure(
  align(center, image(
    "../../figures/target_task_sampler_contract.pdf",
    width: 100%,
  )),
  caption: [Oracle target-task sampling contract. @ground-truth:short OBBs and meshes define identity-valid supervised target tasks through an IoU and ambiguity-gap gate, a deterministic capped sampler writes target-task rows with descriptor and audit fields, and rollout generation later measures target @relative-reconstruction-improvement:short and headroom. The actor-visible target selector remains a separate diagnostic or later deployment contract, not the source of thesis labels.],
) <fig:oracle-target-task-sampler-contract>

The cheap admission gate is identity matching. A proposed target OBB is identity-valid when it matches exactly one @ground-truth:short target OBB by configured 3D IoU and ambiguity margin:

$
  #eqs.entity.target_identity_iou
$

$
  #eqs.entity.target_identity_acceptance
$

Here $mu_1$ and $mu_2$ are the best and second-best target-to-@ground-truth:short IoU scores for the proposal. The threshold values are protocol parameters, not theory constants. The implementation should use a moderate default and report a threshold sweep so that coverage can be inspected under looser and stricter identity definitions.

Class prediction and confidence do not decide target-task eligibility in the first pass. They are recorded because semantic correctness may matter for target descriptors and failure analysis, but the oracle can compute target-specific @relative-reconstruction-improvement:short for a geometrically identified target even when the class head is noisy. Current RGB projection, semidense support, and @egocentric-voxel-lifting:short support are likewise audit fields rather than hard gates unless a later subset explicitly asks for projected-only or support-qualified targets.

The sampler keeps rollout cost bounded by selecting a capped number of identity-valid targets per source snippet. Within that cap, it samples uniformly with a deterministic seed rather than always taking the largest or highest-IoU object. The audit surface must still report how many identity-valid targets existed before the cap, how many were selected, and how their IoU, ambiguity gap, class, confidence, projected area, support, distance, and bearing were distributed.

Headroom is evaluated after target selection because it depends on oracle candidate scoring. The rollout store should persist identity-valid targets even when measured target headroom is low; training and evaluation loaders can then filter or stratify by headroom band. This preserves negative evidence: if many well-identified targets have no candidate with useful gain, the result is a candidate/support/headroom limitation rather than a target-selection failure hidden by pre-filtering.

Counterfactual trajectory naturalness is a candidate and rollout diagnostic, not an identity gate. Hard turns, target-bearing changes, and support collapse should be measured with candidate provenance and invalid-reason fields so that the thesis can distinguish target identity failures from unrealistic or unsupported view proposals.

=== Candidate View Generation

Candidate view generation is the second procedural layer: it turns one target task into a finite action table for one rollout state. The current thesis profile deliberately uses a small family mixture rather than the older unconstrained shell from the seminar paper. The checked-in data-generation profile consumes the strict offline actor-state store, uses a training split for the first real audit subset, samples one oracle target task per source sample, and writes a separate rollout/replay store. It is an audit-scale thesis default, not an LRZ path template and not final scale evidence.

#validation_todo(
  [Replace the current/canonical/audit-profile language and every numeric sampler, pruning, horizon, beam, and temperature setting below with the versioned final experiment configuration and manifest statistics. Reconcile the candidate-family vocabulary with the thesis roadmap.],
  source: [thesis peer review; current roadmap; final experiment manifests],
  gate: [candidate and rollout protocol freeze],
)

At rollout step $t$, candidate generation constructs a full shell

$
  #eqs.action.candidate_shell
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
  #eqs.action.power_spherical_forward
$

The draw is mapped into configured azimuth and elevation caps without rejection. With $psi = op("atan2")(u_x, u_z)$ and $u_y = sin theta$, the cap transform is

$
  #eqs.action.angle_cap_transform
$

$
  #eqs.action.capped_direction
$

The geometry behind this finite action table is easier to read as a gauge choice than as a list of Cartesian offsets. The sampler first draws a capped direction in the reference rig frame, then each family gives that direction a different semantic axis: egocentric forward motion, target-bearing motion, or lateral target bypass. The target-looking families additionally construct a camera frame whose optical axis points to the selected actor-visible target center.

#figure(
  align(center, image(
    "../../figures/candidate_generation_geometry.pdf",
    width: 100%,
  )),
  caption: [Schematic geometry of the target-conditioned three-family candidate shell. Panel A shows the root/reference-frame direction cap; panel B shows how the same shell support is reinterpreted by the forward-local, target-bearing, and lateral-bypass center families; panel C shows the target-look camera construction and the resulting target-frustum relation. Exact sampling densities, radius draws, and pruning constraints are defined by the surrounding equations, not by the schematic scale.],
) <fig:candidate-generation-geometry>

The three position families then reinterpret this capped direction. Let $bold(f)=bold(e)_z$ be the rig-forward unit vector, $bold(b)_e$ the actor-visible target bearing in the reference frame, $bold(l)_e = norm(bold(e)_y times bold(b)_e)$ the horizontal lateral direction, and $bold(e)_y$ the world-up direction expressed in the sampling frame. The family directions are:

$
  #eqs.action.family_directions
$

Finally, the sampler draws a radius and transforms the reference-frame offset into world coordinates:

$
  #eqs.action.candidate_center_world
$

`forward_local` keeps the reference rig orientation. The two target-looking families orient the camera to the selected actor-visible target center $bold(p)_e$:

$
  #eqs.action.target_lookat_frame
$

These equations are the mathematical description of the implemented sampler, not a claim that the mixture is optimal. The three-family design has a direct downstream impact: `forward_local` preserves egocentric motion continuity; `target_bearing_local` tests whether moving along the target bearing produces supervised target gain; and `lateral_target_bypass` creates side-step views that may improve occluded target surfaces without leaving the local walking envelope. If the target-aware families do not survive pruning, the resulting rollout dataset degenerates into a forward-only dataset and cannot support a target-conditioned planning claim.

Pruning converts the full shell into a compact valid-action table. A row remains valid only if it lies in the snippet occupancy support, stays clear of the @ground-truth:short mesh, avoids straight-line path collision, and satisfies local egocentric motion limits:

$
  #eqs.action.motion_pruning_limits
$

The full shell is still retained with `position_id`, `strategy_id`, `mixture_id`, `sampler_probability`, rule masks, debug diagnostics, and invalid-reason bitsets. Invalid candidates are hard-masked constraints with explicit reasons. They are never low-@relative-reconstruction-improvement:short examples, and they must not enter #symb.rl.qh argmax, softmax, or loss targets. The canonical real config requires at least 15 valid root actions for a 60-row shell, matching the first production gate:

#figure(
  align(center, image(
    "../../figures/candidate_validity_pruning_examples.pdf",
    width: 100%,
  )),
  caption: [Candidate validity and pruning examples. The support envelope, mesh-clearance constraint, and path-collision check remove infeasible rows by setting #symb.rl.validity_mask to false and recording an invalid-reason code #symb.rl.invalid_reason. A candidate with low target support or low expected gain remains valid if it satisfies the feasibility rules; it is a supervised low-utility row rather than an invalid action.],
) <fig:candidate-validity-pruning-examples>

$
  #eqs.action.valid_support_threshold
$

This threshold is a data-support guard: it prevents low-support roots from masquerading as planning evidence, while preflight still reports the blocked roots and per-family failure modes.

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

The bounded oracle-lookahead recipe differs from one-step greedy selection because it scores first actions by the best retained finite-horizon chain, not by immediate gain alone (@fig:oracle-lookahead-tree). Invalid candidates remain masked and are not expanded into oracle branches.

#figure(
  align(center, image(
    "../../figures/oracle_lookahead_tree.pdf",
    width: 100%,
  )),
  caption: [Bounded oracle-lookahead tree used as a rollout reference. Valid first-action rows may be expanded into selected-depth successor states and scored by cumulative root-normalized return #symb.rl.return_h; invalid rows are hard-masked and receive no branch. The selected first action can differ from the one-step greedy winner when a lower immediate reward opens a better second-step target view.],
) <fig:oracle-lookahead-tree>

For stochastic branches, let $s_i$ be the finite oracle score of valid row $i$. The robust logit used for temperature-softmax is

$
  #eqs.action.robust_temperature_softmax
$

The downstream effect of these choices is scientific rather than cosmetic. The target source controls what counts as a supervised task; the candidate mixture controls the support on which #symb.rl.qh can learn finite-action values; the validity rules decide which actions are admissible; and the branch sampler determines whether the replay store contains only myopic winners or also valid lower-ranked alternatives. A trustworthy thesis dataset must therefore report, per scene and target, selected target counts, valid candidates, valid candidates by `position_id`, invalid reasons by family, selected-family histograms, marginal and cumulative target-root gain, diagnostic state-relative target @relative-reconstruction-improvement:short, and storage/retention settings. Only after these diagnostics show non-degenerate target-aware support should failures or successes be attributed to planning rather than to the data-generation profile.

=== Target-Specific @relative-reconstruction-improvement:short

Let $C_e (#symb.obs.points_t)$ denote the oracle-only crop of accumulated points to the matched target region. The target error is the target-cropped version of the VIN-NBV @relative-reconstruction-improvement:short objective @VIN-NBV-frahm2025: point-to-mesh accuracy plus mesh-to-point completeness on the crop.

#figure(
  align(center, image(
    "../../figures/target_rri_point_mesh_geometry.pdf",
    width: 100%,
  )),
  caption: [Target-specific point-mesh error behind @relative-reconstruction-improvement:short labels. Blue points are the target crop of accumulated actor-visible geometry, green points are the selected candidate contribution, the orange curve is the matched target mesh, purple witnesses indicate point-to-mesh accuracy, and dashed red witnesses indicate mesh-to-point completeness. Adding a valid candidate view is useful only insofar as it reduces the target-cropped aggregate error used by the oracle reward.],
) <fig:target-rri-point-mesh-geometry>

$
  #eqs.entity.target_error
$

Area weighting or uniformly sampled target-surface points prevent target-specific @relative-reconstruction-improvement:short from reflecting mesh tessellation density. For reproducibility, the current implementation computes the point-mesh distances through `OracleRRI.score` and `chamfer_point_mesh_batched`, while `aria_nbv.rollouts.target_counterfactuals` owns the target crop. Empty or unsupported target crops are invalid label cases, not low-@relative-reconstruction-improvement:short samples.

#validation_todo(
  [Do not retain the tessellation-invariance claim until the actual metric uses documented area weighting or uniform surface sampling and passes a triangulation-density test. The current face-mean path can change weighting when a surface is subdivided.],
  source: [thesis peer review; active oracle metric implementation],
  gate: [target-RRI metric validation],
)

#validation_todo(
  [Specify and validate homogeneous root/candidate evaluation geometry before using target-RRI labels as thesis evidence: point source, render stride, fusion/downsampling, point cap, crop policy, and density-parity test must be matched or their bias quantified.],
  source: [RRI theory review; thesis peer review],
  gate: [oracle label validity study],
)

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

#research_todo(
  [Either cite a reviewed NBV source that specifically supports logarithmic error reduction or remove the literature-generalization clause. The current repo evidence supports log gain only as an internal scale-sensitivity ablation.],
  source: [thesis questions; literature cross-check],
  gate: [final metric-citation audit],
)

$
  #eqs.entity.log_gain
$

#symb.entity.endpoint_gain is the primary fixed-horizon endpoint metric, #symb.entity.return_h is the rollout training return, and #symb.entity.log_gain is only an algebraic scale-sensitivity ablation. The default immediate rollout / #symb.rl.qh reward is root-normalized by #symb.entity.target_error_0, so with $gamma=1$ its additive return telescopes to endpoint gain up to epsilon under equal-horizon, equal-budget comparisons. The current-error denominator defines state-relative one-step @relative-reconstruction-improvement:short for diagnostics and VIN compatibility only; the final discount and clipping policy remain open protocol parameters.

#decision_todo(
  [Lock identity-IoU thresholds, ambiguity gap, per-snippet target cap, near-solved-target filtering policy for loaders, clipping, and final gamma policy.],
  source: [target-selection interview; target-selection autoresearch report],
  gate: [RQ1/RQ2 protocol freeze],
)
