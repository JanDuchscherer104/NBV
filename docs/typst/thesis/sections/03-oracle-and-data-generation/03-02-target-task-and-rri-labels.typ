#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs

== Data Generation and Target-Specific @relative-reconstruction-improvement:short Labels

An oracle target task fixes the entity identity and @ground-truth:short evaluation crop. A deployable target descriptor would instead be predicted from actor-visible observations. The current rollout generator has only the first contract: it projects a selected @ground-truth:short box into a compact instruction for candidate generation. Consequently, the present target descriptor denotes the requested object and its geometry; it does not establish actor-visible target discovery.

The general descriptor notation remains

$
  #eqs.entity.target_descriptor
$

#parbreak()
The implemented oracle sampler populates only @ground-truth:short identity, class, confidence, pose, extent, and reference-relative geometry. Projected area, semidense support, @egocentric-voxel-lifting:short support, and proposal-match scores are not measured by this path and must not be interpreted from their schema placeholders.

The finite action interface consists of a candidate table $cal(Q)_t$, hard validity mask $bold(m)_t$, and invalid-reason vector $bold(rho)_t$. The admissible set is $cal(A)_t = {i : m_(t,i)=1}$. Invalid rows remain logged for coverage and failure analysis but lie outside policy argmax, sampling, loss targets, and bootstrap maximization. Low RRI is a valid low-utility outcome; it is never an encoding for infeasibility.

For target $e$, the oracle computes a target-cropped point--mesh error $Delta_t^e$. Candidate selection and #symb.rl.qh supervision use root-normalized target gain; state-relative @relative-reconstruction-improvement:short is retained as a diagnostic. Fixed-budget endpoint gain is the intended policy estimand, but the current replay store records cumulative selected-chain gains rather than an independent post-horizon endpoint reconstruction for every policy. Confirmatory policy comparisons must therefore add matched oracle endpoint re-evaluation or an explicitly persisted endpoint record.

=== Oracle Label Provenance

The one-step scene-level oracle from the seminar work supplies the rendering and point--mesh substrate @VIN-NBV-frahm2025 @PyTorch3D-Cameras-2025. The target-specific pipeline renders valid candidates from the @ground-truth:short mesh, backprojects their depth, fuses candidate points with the privileged current evaluation cloud, crops both points and mesh to the selected target box, and evaluates the resulting point--mesh error. In the current protocol the root evaluation cloud is reconstructed from ASE @ground-truth:short depth, so both the crop and the root metric are oracle-only.

#figure(
  align(center, image(
    "../../figures/camera_frame_ray_contract.pdf",
    width: 100%,
  )),
  caption: [Camera-frame and ray contract behind oracle labels. Panel A fixes the candidate camera as a calibrated left-up-forward camera and renders depth from the @ground-truth:short mesh. Panel B shows the induced unprojection: a depth pixel becomes a camera-frame ray sample, is transformed into the world frame, enters the selected candidate point set, and is cropped against the selected target surface before target-specific error is scored @ProjectAria-ASE-2025 @PyTorch3D-Cameras-2025.],
) <fig:camera-frame-ray-contract>

=== Target Selection

The implemented sampler does not match actor proposals to @ground-truth:short objects. It enumerates the non-padding @ground-truth:short OBB rows in a snippet, accepts rows with finite positive geometry, and applies seeded uniform sampling without replacement up to the configured per-snippet cap. Thus the stored `matched` status currently means geometry-valid @ground-truth:short task row, not successful proposal-to-identity association. IoU, ambiguity-gap, visibility, and support thresholds are absent from this admission rule.

#figure(
  align(center, image(
    "../../figures/target_task_sampler_contract.pdf",
    width: 100%,
  )),
  caption: [Implemented oracle target-task sampler. Geometry-valid @ground-truth:short OBB rows form the task pool, and seeded uniform sampling without replacement applies the manifest-defined cap. Rollout scoring later decides whether the selected crop is evaluable. No actor proposal, IoU match, visibility gate, or support gate is used.],
) <fig:oracle-target-task-sampler-contract>

The sampler bounds rollout cost without pre-filtering on headroom. Candidate scoring may subsequently invalidate the task when its mesh crop, current support, or rendered evidence is unusable; otherwise near-solved and negative-gain targets remain scientifically informative. A later actor-visible protocol must introduce proposal identity and observation-quality diagnostics as a separate selection stage rather than retroactively interpreting the present oracle fields as measurements.

=== Candidate View Generation

Candidate generation turns one oracle instruction into a finite action table. Every quantitative choice---source population, target cap, shell size, family weights, motion limits, pruning thresholds, rollout recipes, renderer settings, and retention policy---belongs to the resolved run manifest and report bundle. The Methods text defines semantics only; it does not designate one mutable TOML profile as canonical.

At rollout step $t$, candidate generation constructs a full shell

$
  #eqs.action.candidate_shell
$

with a fixed provenance component $k(i)$ per row. The core mixture contains forward-local, target-bearing, and lateral-bypass motion; the diversity challenger may additionally allocate mass to local refinement and revisit/backtrack components. The resolved manifest, rather than prose, determines which components and counts apply to a run.

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

The sampler draws a capped direction in the reference rig frame and reinterprets it as egocentric forward motion, target-bearing motion, lateral bypass, local refinement, or backtracking according to component provenance. Target-looking families orient their optical axis toward the oracle instruction. In this chapter that point is privileged; calling the generator target-conditioned does not make the point actor-visible.

#figure(
  align(center, image(
    "../../figures/candidate_generation_geometry.pdf",
    width: 100%,
  )),
  caption: [Schematic geometry of the core target-conditioned candidate families. The reference-frame direction support is reinterpreted as forward, target-bearing, or lateral-bypass motion, and target-looking cameras point toward the supplied target instruction. The manifest supplies family counts and all quantitative bounds.],
) <fig:candidate-generation-geometry>

The three core position families then reinterpret this capped direction. Let $bold(f)=bold(e)_z$ be the rig-forward unit vector, $bold(b)_e$ the supplied target bearing in the reference frame, $bold(l)_e = norm(bold(e)_y times bold(b)_e)$ the horizontal lateral direction, and $bold(e)_y$ the world-up direction expressed in the sampling frame. The family directions are:

$
  #eqs.action.family_directions
$

Finally, the sampler draws a radius and transforms the reference-frame offset into world coordinates:

$
  #eqs.action.candidate_center_world
$

`forward_local` keeps the reference rig orientation. Target-looking families orient the camera toward the supplied target center $bold(p)_e$:

$
  #eqs.action.target_lookat_frame
$

These equations describe the sampler, not an optimal proposal distribution. `forward_local` preserves egocentric continuity, `target_bearing_local` moves along the target ray, and `lateral_target_bypass` introduces side-step views; the optional challenger families test smaller corrections and reversals. Candidate-profile utility must be judged after pruning. A store in which target-aware families rarely survive cannot support a target-conditioned planning claim.

Pruning converts the full shell into a compact valid-action table. A row remains valid only if it lies in the snippet occupancy support, stays clear of the @ground-truth:short mesh, avoids straight-line path collision, and satisfies local egocentric motion limits:

$
  #eqs.action.motion_pruning_limits
$

The full shell is retained with position, strategy, mixture, sampling probability, rule masks, diagnostics, and invalid-reason bitsets. Invalid candidates are hard constraints and cannot enter #symb.rl.qh selection, stochastic normalization, or loss targets. A manifest-defined root-support threshold may reject an entire rollout task when too few actions remain:

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

This threshold is a data-support guard, not a reward threshold. Preflight reporting must retain rejected-root counts and failure reasons by candidate family.

=== Rollout Branch Sampling and Dataset Impact

Rollout recipes select and retain finite chains from the valid action table. The implemented families are uniform valid sampling, one-step oracle greedy selection, bounded oracle lookahead, and temperature-softmax sampling. Their horizon, branch factor, beam width, temperature, and seed are resolved parameters. These recipes generate replay diversity and bounded references; they do not constitute a learned policy.

Bounded oracle lookahead can select a different first action from one-step greedy because it ranks retained finite-horizon chains rather than immediate gain alone (@fig:oracle-lookahead-tree). The persisted artifact contains these selected or beam-retained chains and their full per-step candidate shells; it is not an exhaustive materialization of the counterfactual action tree.

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

The target source defines the supervised task, the candidate mixture defines learnable action support, validity defines admissibility, and the recipe defines which chains enter replay. Reporting must therefore cover target-task coverage, valid fanout and invalid reasons by family, selected-family diversity, gain distributions, and retention cost before attributing policy behavior to non-myopic planning. The paired train-only pilots are bandwidth and candidate-profile probes; they are non-confirmatory and provide no held-out policy-performance evidence.

=== Target-Specific @relative-reconstruction-improvement:short

Let $C_e (#symb.obs.points_t)$ denote the oracle-only crop of accumulated evaluation points to the selected target region. The target error adapts the VIN-NBV objective to this crop @VIN-NBV-frahm2025: point-to-mesh accuracy plus mesh-to-point completeness.

#figure(
  align(center, image(
    "../../figures/target_rri_point_mesh_geometry.pdf",
    width: 100%,
  )),
  caption: [Target-specific point-mesh error behind @relative-reconstruction-improvement:short labels. Blue points are the target crop of accumulated oracle evaluation geometry, green points are the selected candidate contribution, the orange curve is the selected target mesh, purple witnesses indicate point-to-mesh accuracy, and dashed red witnesses indicate mesh-to-point completeness. Adding a valid candidate view is useful only insofar as it reduces the target-cropped aggregate error used by the oracle reward.],
) <fig:target-rri-point-mesh-geometry>

$
  #eqs.entity.target_error
$

The implementation crops mesh faces when any vertex lies inside the oriented target OBB and evaluates the configured point--mesh scorer. Geometry-invalid candidates are removed by the hard action mask and retain persisted candidate reason codes. Empty mesh crops, insufficient current support, or unusable renders instead invalidate the separate oracle evaluation: the recipe either skips the affected row or table, or clears `oracle_label_mask` and `q_train_mask`, while reporting the oracle failure independently rather than assigning a candidate reason code. The current face-based metric is not yet established as invariant to mesh tessellation or root/candidate sampling density; confirmatory use therefore requires the sensitivity tests specified in @sec:thesis-experimental-design.

The immediate training reward adapts VIN-NBV's reconstruction-improvement idea to a target crop and normalizes by the root target error rather than the current error @VIN-NBV-frahm2025. This makes equal-horizon rollouts additive against a common root baseline:

$
  #eqs.rl.target_rri_reward
$

The finite-horizon return is the discounted sum of those target rewards along a selected counterfactual branch. It is a training target for #symb.rl.qh, not a claim that the deployed system has an online continuous-control policy:

$
  #eqs.rl.finite_horizon_return
$

Endpoint gain is the primary fixed-budget comparison metric because it measures the target quality after the same number of acquisitions for each policy:

$
  #eqs.entity.endpoint_gain
$

The log-gain variant is retained only as an internal scale-sensitivity ablation:

$
  #eqs.entity.log_gain
$

#symb.entity.endpoint_gain is the fixed-budget evaluation metric, #symb.entity.return_h is the learning return, and #symb.entity.log_gain is a sensitivity diagnostic. Root-normalized gains telescope to endpoint gain when the discount is unity and geometry, horizon, and acquisition budget are matched. State-relative one-step @relative-reconstruction-improvement:short remains a VIN-compatible diagnostic. The resolved manifest must freeze the discount, clipping, target cap, crop policy, and all evaluation-geometry parameters for each reported experiment.
