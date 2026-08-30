#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../../shared/tables.typ": publication-table
#import "../../draft_markers.typ": validation_todo

== Task and Action Construction

#validation_todo(
  [Validate repeatability, failure handling, construct interpretation, root normalization, and the endpoint estimand before describing RRI as a reliable study objective.],
  source: [docs/literature/tex-src/arXiv-VIN-NBV; metric-validation artifacts],
  gate: [frozen metric protocol, repeatability table, and claim-level source locators],
)

An oracle target task fixes entity identity, evaluation support, and the target
instruction used to construct target-bearing actions. An actor-visible task
would instead obtain its descriptor from observations. The present descriptor
therefore defines a controlled requested object and its geometry; it does not
establish actor-visible target discovery.

The general descriptor notation remains

$
  #eqs.entity.target_descriptor
$

The finite action interface consists of a candidate table $cal(Q)_t$, hard validity mask $bold(m)_t$, and invalid-reason vector $bold(rho)_t$. The admissible set is $cal(A)_t = {i : m_(t,i)=1}$. Invalid rows remain logged for coverage and failure analysis but lie outside policy argmax, sampling, loss targets, and bootstrap maximization. Low RRI is a valid low-utility outcome; it is never an encoding for infeasibility.

For target $e$, the oracle computes the target-cropped point--mesh error defined by the frozen outcome protocol. Candidate selection and #symb.rl.qh supervision use root-normalized target gain; state-relative @relative-reconstruction-improvement:short is retained as a diagnostic. Fixed-budget endpoint gain is the intended policy estimand, but the current replay store records cumulative selected-chain gains rather than an independent post-horizon endpoint reconstruction for every policy. Confirmatory policy comparisons must therefore add matched oracle endpoint re-evaluation or an explicitly persisted endpoint record.

=== Target Selection

The implemented sampler never starts from actor proposals. From a multi-slice @ground-truth:short OBB block, it selects the latest slice containing at least one non-padding row; if no such slice exists, the final all-padding slice yields no task rows. Within the selected slice, it removes padding and constructs `rows` from every remaining OBB, preserving source indices and audit fields, including confidence and geometry status. It then forms the geometry-eligible target-row set $cal(R)_s^"geom"$, whose full OBB payloads and extents are finite and whose extents are strictly positive, and applies seeded uniform sampling without replacement up to the configured per-snippet cap. Thus the stored `matched` status currently means geometry-valid @ground-truth:short task row, not successful proposal-to-identity association. Confidence, IoU, ambiguity-gap, visibility, support, headroom, and utility do not gate this sampling step.

#figure(
  align(center, image(
    "../../figures/target_task_sampler_contract.pdf",
    width: 100%,
  )),
  alt: "A left-to-right population flow begins after selecting the latest ground-truth OBB slice that contains a non-padding row; an all-padding block produces no task rows. Padding is removed before the complete rows table is constructed. The rows table retains illustrative finite positive-geometry and invalid-geometry examples with source indices and audit fields. A finite positive-extent predicate derives the geometry-eligible target-row set; one eligible example remains unsampled. Seeded uniform sampling without replacement, capped by the smaller of K and the eligible-row count, produces selected rows. Actor proposals and utility evidence do not gate sampler admission; later scorer-evidence checks remain outside the depicted sampler.",
  caption: [Oracle target-task sampler. After selecting the latest nonempty @ground-truth:short OBB slice, the audit table retains its invalid and eligible non-padding rows; an all-padding block yields no task rows. The seeded cap acts only on $cal(R)_s^"geom"$. This privileged population construction neither matches actor observations nor evaluates task utility; scorer-evidence checks occur downstream.],
) <fig:oracle-target-task-sampler-contract>

Downstream scoring may invalidate a selected task when its mesh crop, current support, or rendered evidence is unusable. Near-solved and negative-gain tasks otherwise remain scientifically informative because sampler membership encodes neither headroom nor utility. A later actor-visible protocol must introduce proposal identity and observation-quality diagnostics rather than reinterpret these oracle fields as measurements.

=== Observed-Target Admission

The observed-target audit (implementation anchor `V1`) keeps the oracle task
sampler separate from actor-visible target selection. For each observed or
predicted target record $hat(e)$, it compares only same-class GT OBB rows using
oriented 3D IoU:

$
  #eqs.entity.target_identity_iou
$

$
  #eqs.entity.target_identity_threshold
$

A GT row qualifies only when its IoU is strictly greater than $0.20$. The
matcher admits the observed target iff exactly one GT row qualifies:

$
  #eqs.entity.target_identity_qualified_count
$

$
  #eqs.entity.target_identity_acceptance
$

Equality at $0.20$ is rejected, as are zero or multiple qualifying rows. The
matching rule has no runner-up-gap or composite score. The current rollout
sampler remains a distinct oracle-task path: geometry-valid GT-row admission is
not evidence of actor-visible matching.

=== Candidate View Generation

Candidate generation turns one oracle instruction into a finite action table. Every quantitative choice---source population, target cap, shell size, family weights, motion limits, pruning thresholds, rollout recipes, renderer settings, and retention policy---belongs to the resolved run manifest and report bundle. This chapter defines semantics only; it does not designate one mutable configuration profile as canonical.

At rollout step $t$, candidate generation constructs a full shell. Here
$cal(K)_t$ is the resolved set of mixture components and $n_k$ is the row count
allocated to component $k$:

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

The sampler draws a capped direction in the reference rig frame and reinterprets it as egocentric forward motion, target-bearing motion, lateral bypass, local refinement, or backtracking according to component provenance. Position and view provenance remain distinct: a component first constructs a base camera frame, then applies bounded local yaw and pitch jitter. In the core mixture, forward-local rows use the reference-rig base frame, whereas target-bearing and lateral-bypass rows use a target-look-at base frame. The supplied point is privileged in this chapter; calling the generator target-conditioned does not make it actor-visible.

The next figure separates two questions that become illegible when overlaid:
where the decision is grounded in the 3D scene, and what support the complete
finite table retains.

#let candidate-scene-provenance = json(
  "../../figures/data/candidate_scene_81286_000035.json",
).at("provenance")
#let candidate-family-display = candidate-scene-provenance.at("family_display")
#let candidate-pose-display = candidate-scene-provenance.at("candidate_pose_display")

#figure(
  align(center, image(
    "../../figures/candidate_generation_geometry.pdf",
    width: 100%,
    alt: "A dominant oblique 3D view shows a neutral processed ground-truth room mesh, an orange selected task bounding box, a solid purple physical RGB trajectory with two teal dashed calibrated historical frusta, a separate sampling-root anchor, and the black-and-gold selected candidate frustum. A narrow bird's-eye audit shows all sixty candidate centers and validity decisions. " + candidate-pose-display + " " + candidate-family-display,
  )),
  caption: [Scene grounding and support audit for one pinned ASE decision state. Panel A separates physical RGB history, the canonical sampling root, the selected oracle-task GT OBB, and the selected candidate view. #candidate-pose-display Panel B retains all 60 stored centers and validity decisions: 25 admissible, 35 hard-rejected, and shell 47 selected. #candidate-family-display Frusta approximate the calibrated Fisheye624 valid domain; the example fixes support and validity, not policy performance.],
) <fig:candidate-generation-geometry>

The three core position families then reinterpret this capped direction. The
shared normalization operator is

$
  #eqs.action.unit_vector
$

Let $bold(f)=bold(e)_z$ be the rig-forward unit vector, $bold(b)_e$ the supplied
target bearing in the reference frame, $bold(l)_e = op("normalize")(bold(e)_y times
bold(b)_e)$ the horizontal lateral direction, and $bold(e)_y$ the world-up
direction expressed in the sampling frame. The family directions are:

$
  #eqs.action.family_directions
$

Finally, the sampler draws a component-resolved radius and transforms the reference-frame offset into world coordinates:

$
  #eqs.action.candidate_center_world
$

The forward-local family uses the reference-rig rotation as its base frame. Target-looking families instead construct a base frame from the supplied target center $bold(p)_e$:

$
  #eqs.action.target_lookat_frame
$

#figure(
  align(center, image(
    "../../figures/candidate_family_geometry.pdf",
    width: 100%,
    alt: "Three plan-view constructions start from the same reference rig frame. A dotted raw direction is transformed into a blue circular forward-local centre, an amber diamond target-bearing-local centre, or a teal triangular lateral-target-bypass centre. The target-conditioned panels also show the supplied target point and bearing. At every centre, a dashed arrow marks the component's base gaze and a solid arrow marks one bounded jitter realization.",
  )),
  caption: [Geometric roles of the three core proposal families. Each panel applies one position transform to the same fixed raw direction; it then separates the component's base gaze from one bounded local-jitter realization. The plan view omits the bounded vertical term retained by the adjacent family equation. The construction explains proposal semantics only: radius sampling, family counts, feasibility, and selection remain separate.],
) <fig:candidate-family-geometry>

These equations describe the sampler, not an optimal proposal distribution.
@fig:candidate-family-geometry isolates the two decisions that prose otherwise
conflates: where a row proposes to move, and how its camera is oriented there.
The forward-local transform preserves egocentric continuity, the
target-bearing-local transform biases the proposed direction around the supplied
target bearing, and the
lateral-target-bypass transform introduces side-step views. Optional challenger
families test smaller corrections and reversals. Candidate-profile utility must
still be judged after pruning. A store in which target-aware families rarely
survive cannot support a target-conditioned planning claim.

The optional `target_orbit` family is a bilateral partial-orbit endpoint proposal
prior: it samples paired signed angular offsets around the supplied target while
preserving the current horizontal target standoff. Feasibility pruning may remove
either side, so bilateral attempt does not imply bilateral surviving support. This
family is not part of the production mixture and is not a learned human-motion
prior; it is an opt-in challenger for testing whether local orbit coverage improves
candidate support.

Pruning converts the full shell into a compact valid-action table. A row remains valid only if it lies in the snippet occupancy support, stays clear of the @ground-truth:short mesh, avoids straight-line path collision, and satisfies local egocentric motion limits:

$
  #eqs.action.motion_pruning_limits
$

The full shell is retained with position, strategy, mixture, sampling probability, rule masks, diagnostics, and invalid-reason bitsets. Panel B of @fig:candidate-generation-geometry makes the distinction concrete for one stored table: invalid rows remain inspectable but sit outside the admissible set. Invalid candidates cannot enter #symb.rl.qh selection, stochastic normalization, or loss targets. Conversely, a feasible row with weak target support or low expected gain remains a valid low-utility example rather than receiving an invalid-reason code. A manifest-defined root-support threshold may reject an entire rollout task when too few actions remain:

$
  #eqs.action.valid_support_threshold
$

This threshold is a data-support guard, not a reward threshold. Preflight reporting must retain rejected-root counts and failure reasons by candidate family.

=== Candidate-Support and Geometric-Coverage Diagnostics

Candidate quality is audited before reward interpretation. Let $cal(I)_s$ be all
attempted, non-padding rows in state $s$, $cal(V)_s subset cal(I)_s$ the rows
that pass actor-valid geometry and hard-action checks, $cal(L)_s subset cal(V)_s$
the rows with a finite oracle label. The horizon-specific mask
$m_(s,i)^(Q,h)$ selects rows in $cal(L)_s$ for Q-training; it does not redefine
the canonical candidate table $cal(Q)_t$. The first transition is represented by the canonical
action mask $#symb.rl.action_mask$; finite factual value-target availability is
represented separately by $#symb.rl.q_label_mask$. These are distinct
populations: a row can be actor-valid without being renderable, oracle-labelled,
or retained for training. The candidate actor-valid fraction is therefore

$
  #eqs.metrics.candidate_actor_valid_fraction
$

and hard valid support is

$
  #eqs.metrics.valid_support
$

Both quantities are computed per decision state before pooling. The configured
family zero rate retains every configured family/state pair in its denominator,
including pairs with zero valid rows:

$
  #eqs.metrics.configured_family_zero_rate
$

Every state statistic $q(s)$ is then averaged within its scene and finally
macro-averaged across scenes:

$
  #eqs.metrics.state_scene_macro
$

Here $cal(S)_(c,q)$ is the metric-specific eligible-state set and $cal(C)_q$
contains scenes with at least one eligible state. A scene with no defined state
for $q$ is absent from the descriptive scalar and counted in the accompanying
undefined-scene table. A paired profile contrast uses the intersection of the
two profiles' eligible-scene sets and reports every excluded scene. Thus the
available-case denominator is explicit rather than an implicit row-level
complete-case analysis.

The analysis manifest freezes the missing-state rule before result inspection.
For support counts and fractions, a failed generation root contributes zero
support; for the family-zero rate it contributes one. Target-relative balance
and span are not numerically imputed when no target-conditioned direction is
defined: the failed state remains in the failure table, and a paired scene is
ineligible for a geometric profile contrast. Thus no missing state disappears
through an implicit complete-case denominator.

For geometric comparison, candidate centres and target centres use the existing
proposal-support normalization $ #eqs.spatial.candidate_proposal_support_normalization $:
the origin is the factual expansion/root pose, the target has unit norm, the
vertical axis is world-up, and distances are divided by the current root-to-target
distance $d_(t,e)^"current"$. This is a target-relative support frame, not a
camera image frame and not a claim that the root or target is visible. Side
balance is computed from non-neutral attempted target-conditioned rows in the
`target_bearing_local` and `target_orbit` families, using their target-relative
azimuth signs. The neutral bin is $|y_(s,i)^"target"| <= epsilon$ with
$epsilon = 10^(-9)$ in normalized support coordinates; its count is reported
but does not enter the two-sided balance denominator,

$
  #eqs.metrics.target_side_balance
$

and orbit coverage uses the circular minimum-covering span rather than a Cartesian
maximum-minus-minimum range:

$
  #eqs.metrics.circular_orbit_span
$

The projection fraction records whether the calibrated target centre lies inside
the calibrated image domain for evaluated rows in one state,

$
  #eqs.metrics.target_center_projection_fraction
$

and is then reduced through the same state--scene--cohort macro operator. A
state with no evaluated projection rows is undefined and counted separately;
it is not assigned a zero fraction or silently removed from a paired profile
contrast. This remains an evaluation/framing diagnostic, not visibility or actor
support. The finite-support oracle opportunity is the per-state maximum
target-root gain,

$
  #eqs.metrics.oracle_opportunity
$

which is defined only when the actor-valid, finite-label set $cal(L)_s$ is
nonempty. Its undefined-state count is reported, and eligible values are reduced
through the same state--scene--cohort macro operator. The quantity measures
available candidate headroom and is not a policy score. View jitter is likewise
computed per state and macro-reduced. States without jitter rows, or without
bounded rows for the cap-compliance diagnostic, are counted as undefined. The
nonzero seminar-profile check remains separate from legacy zero-cap spherical
support:

$
  #eqs.metrics.jitter_compliance
$

The production mixture retains the seminar model's nonzero jitter invariant.
Legacy `uniform_sphere` and `forward_powerspherical` rows with a zero cap are
annotated as uncapped spherical support and are not represented by a bounded box.

#figure(
  publication-table(
    columns: (0.95fr, 1.15fr, 0.65fr, 1.55fr),
    header: ([*Quantity*], [*Population*], [*Unit*], [*Interpretation boundary*]),
    rows: (
      [Actor-valid fraction], [Attempted rows per state], [fraction], [Hard feasibility; not label or training availability.],
      [Valid support], [Actor-valid rows per state], [rows], [Report the lower tail and failed roots, not only a pooled mean.],
      [Configured-family zero rate], [Configured families per state], [fraction], [Retains absent and zero-support families; state values are scene-macro reduced.],
      [Side balance / circular span], [Non-neutral attempted target-conditioned rows], [fraction / angle], [Neutral rows and undefined states are reported separately; proposal coverage precedes pruning.],
      [Target-centre projection], [Evaluated candidate views per state], [fraction], [State--scene--cohort macro; zero-evaluated states are reported as undefined. Calibrated framing, not visibility.],
      [Oracle opportunity], [Finite actor-valid rewards per eligible state], [gain], [Undefined when no finite actor-valid label exists; available one-step headroom, not achieved policy return.],
      [Jitter compliance], [Bounded-jitter rows per state], [fraction], [State--scene--cohort macro; report undefined, nonzero, and uncapped support separately.],
    ),
  ),
  caption: [Candidate-generation diagnostics and their aggregation populations. Every state-level quantity is reduced before scene and cohort aggregation.],
) <tab:candidate-support-metric-contract>

=== Rollout Branch Sampling and Dataset Impact

Rollout recipes select and retain finite chains from the valid action table. The implemented families are uniform valid sampling, one-step oracle greedy selection, bounded oracle lookahead, and temperature-softmax sampling. Their horizon, branch factor, beam width, temperature, and seed are resolved parameters. These recipes generate replay diversity and bounded references; they do not constitute a learned policy.

The first action of the highest-ranked bounded-lookahead chain can differ from the action preferred by one-step greedy because lookahead ranks retained finite-horizon chains rather than immediate gain alone (@fig:oracle-lookahead-tree). The persisted artifact contains the beam-retained chains and their full per-step candidate shells; it is not an exhaustive materialization of the counterfactual action tree.

#figure(
  align(center, image(
    "../../figures/oracle_lookahead_tree.pdf",
    width: 100%,
  )),
  alt: "A short factual prefix reaches root state s t. Two complete beam-retained paths then cross time planes t, t plus 1, and t plus 2. The thinner path begins with action i1, whose immediate target-root gain exceeds that of i2. The thicker path begins with i2 and ends in a ringed highest-ranked endpoint because its two-step return exceeds the return of the i1 path; both solid paths persist. A red dotted invalid-row stub ends at a cross before t plus 1 and has no child. A gray dashed root stub ends at one bar to denote a legal row outside branch factor two that remains in the full shell; a later dashed trajectory reaches t plus 2 and ends at two bars to denote removal by beam width two after expansion.",
  caption: [Constructed depth-two ordering reversal for target-root gain. Both solid paths are beam-retained from one factual prefix: $i_1$ has the larger immediate gain, while $tau_2$ ranks first at $h=2$ and $gamma=1$; $tau_1$ also persists. The dotted stub is invalid. The single-bar stub is a legal shell row outside branch factor $2$; the double-bar stub is an expanded path removed by beam width $2$. Inequalities encode ordering only, not measured rewards or learned-policy performance.],
) <fig:oracle-lookahead-tree>

For stochastic branches, let $s_i$ be the finite oracle score of valid row $i$. The robust logit used for temperature-softmax is

$
  #eqs.action.robust_temperature_softmax
$

The target source defines the supervised task, the candidate mixture defines learnable action support, validity defines admissibility, and the recipe defines which chains enter replay. Reporting must therefore cover target-task coverage, valid fanout and invalid reasons by family, selected-family diversity, gain distributions, and retention cost before attributing policy behavior to non-myopic planning. The paired train-only pilots are bandwidth and candidate-profile probes; they are non-confirmatory and provide no held-out policy-performance evidence.

== Measurement and Outcomes

Task construction and action admission specify the intervention; measurement
specifies what consequence is compared. The oracle renders a selected
candidate from the @ground-truth:short mesh, backprojects its depth, updates the
privileged evaluation cloud through the frozen fusion rule, crops points and
mesh to the selected target, and evaluates point--mesh error
@VIN-NBV-frahm2025. The crop, rendering, fusion, and scoring path are
oracle-only.

// evidence:
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44,78-92 (candidate rendering and reconstruction-improvement scoring)
// - ARIA-NBV intervention path -> aria_nbv/aria_nbv/oracle/_scoring.py:94-163, aria_nbv/aria_nbv/oracle/evidence.py:343-381

=== Operational Reconstruction Error <sec:thesis-reconstruction-quality-metric>

// evidence:
// - aria_nbv/aria_nbv/oracle/evidence.py:93-101,343-381 -> ASE GT-depth is the thesis evaluation source; MPS semi-dense points are a legacy diagnostic source.
// - aria_nbv/aria_nbv/oracle/_scoring.py:94-163 -> candidate depth is backprojected, fused with the root cloud, and scored against the target mesh.
// - aria_nbv/aria_nbv/rri_metrics/point_mesh.py:31-141 -> the selected error uses squared point-to-face accuracy and equal-face face-to-point completeness.

Let $C_e (#symb.obs.points_t)$ denote the oracle-only crop of accumulated evaluation points to the selected target region. In the thesis protocol, its root points are reconstructed from the observed prefix of ASE @ground-truth:short depth; a candidate contributes renderer-derived depth that is backprojected and fused with the same root cloud. MPS semi-dense points remain actor-visible representation input and a legacy diagnostic source, not the current oracle evaluation cloud.

Writing $P=C_e (#symb.obs.points_t)$ and $M=cal(M)_e^"GT"$ for the target-cropped point set and mesh, the selected directional accuracy is the mean squared distance from each reconstructed point to its closest @ground-truth:short triangle,

#eqs.rri.acc

It penalizes reconstructed points that lie away from the target surface and therefore exposes extra, noisy, or misregistered geometry. The reverse term is the mean squared distance from each @ground-truth:short face to its closest reconstructed point,

#eqs.rri.comp

It penalizes target faces without nearby reconstructed evidence and therefore exposes missing support. Their sum is the bidirectional point--mesh error,

$
  #eqs.entity.target_error
$

whose directional terms and total have units of square metres. The current and candidate-augmented clouds pass through the same deterministic fusion and point-cap configuration before scoring. This fusion step makes the before/after comparison operationally reproducible; it does not turn the point set into a continuous surface measure.

#figure(
  align(center, image(
    "../../figures/target_rri_point_mesh_geometry.pdf",
    width: 100%,
  )),
  caption: [Point--mesh metric definition and controlled validity fixture. Panel A isolates the exact point-to-triangle primitive. Panel B distinguishes the point-to-face accuracy and face-to-point completeness reductions using computed closest-point witnesses. Panel C holds the planar support and point set fixed while changing only the triangle table; the measured equal-face completeness term changes from $0.03640$ to $0.02284$ $"m"^2$. These values are generated by the repository's PyTorch3D metric on a synthetic fixture and demonstrate a tessellation-sensitivity mechanism; they are not an ASE performance result.],
) <fig:target-rri-point-mesh-geometry>

The completeness reduction gives every mesh face equal weight. It is deliberately neither an area-weighted surface integral nor invariant to retessellation: subdividing part of an unchanged surface changes how much that region contributes. The controlled fixture in @fig:target-rri-point-mesh-geometry demonstrates this property. It bounds the interpretation of the operational estimand but does not invalidate comparisons that share one fixed mesh and scoring protocol.

// evidence:
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/experiments.tex:135 (sampled point-to-mesh accuracy and completeness).
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/supplemental_text.tex:154-169 (fixed surface samples and 5 cm precision/recall).
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/4_experiments.tex:63-67 (Chamfer primary metric; coverage and F1 diagnostics).

=== Reliability under the Frozen Protocol

Reliability asks whether repeated execution of the same declared intervention
produces stable errors and candidate rankings. It therefore covers rendering,
backprojection, crop construction, point fusion and capping, numerical failure
handling, and any stochastic sampling used by the metric. Deterministic code
paths and a fixed mesh make the protocol reproducible in principle, but they do
not establish repeatability across the intended study population. That evidence
remains a prerequisite for RQ1 rather than an inferred property of the formula.

#figure(
  publication-table(
    columns: (1.05fr, 1.45fr, 1.32fr),
    align: left,
    header: ([*Metric family*], [*Question answered*], [*Dependency and thesis role*]),
    rows: (
      [Equal-face bidirectional point--mesh error],
      [Are reconstructed points close to @ground-truth:short faces, and does every @ground-truth:short face have nearby point evidence?],
      [Depends on point fusion and mesh tessellation; selected operational RRI error.],
      [Point-sampled Chamfer / accuracy--completeness],
      [Are two sampled surface point sets mutually close?],
      [Depends on sampling density, randomness, norm, and squaring convention; important alternative, not the current metric.],
      [Thresholded precision, recall, and F-score],
      [What fraction of predicted and reference samples fall within tolerance $tau$, and how do the two fractions balance?],
      [Interpretable at a physical tolerance but threshold-dependent; useful diagnostic rather than the scalar RRI owner.],
      [TSDF, occupancy, coverage, or information gain],
      [How much volumetric surface, free space, or previously unknown space is reconstructed or observed?],
      [Depends on grid, truncation, and visibility definitions; answers a different question from target surface quality.],
    ),
  ),
  caption: [Reconstruction-metric alternatives and their role in this thesis. No alternative is promoted to a co-primary metric.],
) <tab:thesis-reconstruction-metric-comparison>

For comparison, a common squared point-sampled Chamfer convention draws a reference set $Q_e$ from the mesh and averages nearest-neighbour distances in both directions,

#eqs.rri.point_sampled_chamfer

Its apparent symmetry does not remove sampling-density dependence: changing the number or distribution of samples changes the finite approximation. Some benchmarks also use unsquared distances, so the norm and squaring convention are part of the metric definition rather than an interchangeable naming detail. At tolerance $tau$, precision counts reconstructed samples with a reference neighbour closer than $tau$, recall counts reference samples with a reconstructed neighbour closer than $tau$, and $F_(1,tau)=2 "Prec"_tau "Rec"_tau/("Prec"_tau+"Rec"_tau)$. These scores are physically interpretable but can change with the selected threshold and discard error magnitude on either side of it. Volumetric coverage and information gain are valuable for exploration and mapping, yet they measure discovered space or uncertainty reduction rather than the target reconstruction-quality change defined here.

=== Construct Validity

Construct validity asks what the operational error represents. In this thesis it
measures idealized target-surface evidence under ASE depth, a selected target
crop, equal-face mesh reduction, and the declared reconstruction update. It is
not a representation-independent measure of object quality, perceived quality,
or scene completeness. The rendering and fusion operator are part of the
estimand: two systems using the same point--mesh formula but different state
updates do not measure the same intervention effect.

The implementation crops mesh faces when any vertex lies inside the oriented
target @oriented-bounding-box and evaluates the selected point--mesh scorer.
Geometry-invalid candidates are removed by the hard action mask and retain
persisted candidate reason codes. Empty mesh crops, insufficient current
support, or unusable renders instead invalidate the separate oracle evaluation:
the recipe either skips the affected row or table, or clears oracle-label
validity and Q-training eligibility, while reporting the oracle failure
independently rather than assigning a candidate reason code.

Every compared policy must therefore share the same target mesh and crop,
ASE-depth source, renderer and backprojection, fusion and point cap, and metric
configuration. Replacing ASE depth with MPS semi-dense evidence would define a
different intervention and would require separate analysis of texture,
gradient, uncertainty, and sampling effects.

=== RRI, Training Reward, and Endpoint Gain

The thesis objective is not the absolute point--mesh error alone, but its normalized reduction after a fixed acquisition budget. It distinguishes state-relative RRI, the additive target-root reward, and endpoint gain: all are dimensionless reductions of the same target-cropped error, but their denominators and scientific roles differ.

The state-relative marginal target RRI remains the VIN-compatible candidate diagnostic:

$
  #eqs.rl.marginal_target_rri
$

The implementation also reports its selected-chain running sum:

$
  #eqs.rl.cumulative_target_rri
$

Because the marginal RRI denominator changes with state, this cumulative diagnostic does not telescope to endpoint improvement. The immediate training reward instead adapts the same error reduction to a target crop and normalizes by the rollout-root target error @VIN-NBV-frahm2025:

$
  #eqs.rl.target_root_gain_reward
$

With matched sequential states and unit discount, its selected-chain sum is the root-normalized endpoint difference under that same clamped root denominator:

$
  #eqs.rl.cumulative_target_root_gain
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

#symb.entity.endpoint_gain is the fixed-budget evaluation metric, #symb.entity.return_h is the learning return, and #symb.entity.log_gain is a sensitivity diagnostic. The endpoint equation uses $Delta_0^e + epsilon$, whereas the additive target-root reward uses $max(Delta_0^e, epsilon)$; the two are therefore not canonically interchangeable, even when geometry, horizon, and acquisition budget match. State-relative one-step @relative-reconstruction-improvement:short remains a VIN-compatible diagnostic. The resolved manifest must freeze the discount, clipping, target cap, crop policy, and all evaluation-geometry parameters for each reported experiment.
