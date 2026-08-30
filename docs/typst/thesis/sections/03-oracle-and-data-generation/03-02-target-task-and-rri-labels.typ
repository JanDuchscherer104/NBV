#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../../shared/tables.typ": publication-table
#import "../../draft_markers.typ": validation_todo

== Task and Action Construction

An action has value only relative to a target and to the alternatives available
in the same state. Data generation therefore begins by constructing a *target
task* and a finite *candidate shell*. The target task fixes the requested entity
$e$, its evaluation support #symb.ase.mesh_target, and the instruction used by
target-bearing proposal families. Its reusable descriptor is

$
  #eqs.entity.target_descriptor
$

where geometry, class evidence, observation support, source role, and
target-relative transforms stay explicit. In the present oracle protocol these fields originate from a
selected @ground-truth:short OBB. The descriptor therefore defines a controlled
target-conditioned task. Actor-visible target discovery is evaluated through
the separate proposal-association path below.

At decision step $t$, the proposal mechanism produces
#symb.rl.candidate_table. Each row #symb.oracle.candidate_qti represents one possible
camera pose together with its proposal provenance. The hard mask
#symb.rl.action_mask then induces the feasible action set

$
  #eqs.rl.finite_action_set
$

Candidate generation and feasibility are deliberately separate operations. The
proposal distribution determines which parts of the local action space are
represented; the mask determines which proposed rows may be selected. Invalid
rows are retained for action-space coverage and failure analysis. Selection,
stochastic normalization, loss targets, and bootstrap maximization use the
feasible subset. A feasible row with poor target gain is a valid low-utility
example.

=== Target Selection

The oracle task sampler enumerates non-padding @ground-truth:short OBBs with
finite positive geometry and samples them uniformly without replacement up to
the manifest-defined per-snippet cap. This choice makes task selection
independent of candidate reward: near-solved, difficult, and negative-gain
targets are eligible. The stored `matched` status records a geometry-valid
oracle task. Successful actor proposal-to-identity matching is a separate
observed-target event.

#figure(
  align(center, image(
    "../../figures/target_task_sampler_contract.pdf",
    width: 100%,
  )),
  caption: [Oracle target-task construction. Geometry-valid
  @ground-truth:short OBB rows form the task population; seeded uniform sampling
  without replacement applies the manifest-defined cap. Candidate scoring later
  determines whether the selected target crop is evaluable.],
) <fig:oracle-target-task-sampler-contract>

This sampler controls computational cost and keeps the task population
independent of oracle headroom. Actor-visible target selection uses
observation-derived proposals and association as a distinct stage. Oracle task
admission supplies the controlled reference population for that evaluation.

=== Observed-Target Admission

The observed-target matcher implements that distinct stage. Given an observed or
predicted proposal $hat(e)$, it compares only same-class reference OBBs using
oriented three-dimensional IoU,

$
  #eqs.entity.target_identity_iou
$

$
  #eqs.entity.target_identity_threshold
$

A reference row qualifies only when its IoU is strictly greater than $0.20$.
The proposal is admitted exactly when one reference row qualifies:

$
  #eqs.entity.target_identity_qualified_count
$

$
  #eqs.entity.target_identity_acceptance
$

Equality at the threshold, no qualifying row, and multiple qualifying rows leave
the proposal unresolved. The rule is intentionally simple: it turns an observation
proposal into an unambiguous evaluation identity. Association confidence is a
separate diagnostic, and the current oracle task sampler operates directly on
@ground-truth:short rows.

=== Candidate View Generation

Candidate generation is a proposal distribution over a bounded local camera
motion space. It determines the alternatives over which the NBV scorer ranks
actions. At step $t$, it constructs the shell

$
  #eqs.action.candidate_shell
$

and records a family label $k(i)$ for every row. The frozen
`realistic_core_60` profile allocates 24 forward-local, 24
target-bearing-local, and 12 lateral-target-bypass rows. The three families
encode complementary geometric hypotheses:

#figure(
  publication-table(
    columns: (0.9fr, 1.5fr, 1fr),
    header: ([*Family*], [*Geometric role*], [*Profile support*]),
    rows: (
      (
        [Forward-local],
        [Preserve egocentric motion continuity while perturbing the current forward direction.],
        [24 rows; radius $[0.25, 1.1]$ m],
      ),
      (
        [Target-bearing-local],
        [Move approximately along the current target bearing and orient the camera towards the target.],
        [24 rows; radius $[0.4, 1.1]$ m],
      ),
      (
        [Lateral-target-bypass],
        [Introduce side-step parallax while retaining a component towards the target.],
        [12 rows; radius $[0.25, 1.1]$ m],
      ),
    ),
  ),
  caption: [Geometric roles of the three families in the frozen
  `realistic_core_60` intervention. Counts and radii are specific to this
  profile.],
) <tab:candidate-family-roles>

Optional refinement, revisit, and target-orbit families activate only in
challenger profiles. Because a profile changes the
represented action support, its family counts, radii, angular caps, and pruning
parameters belong to the resolved run manifest. A comparison fixes that
manifest across methods.

#figure(
  align(center, image(
    "../../figures/candidate_generation_geometry.pdf",
    width: 100%,
  )),
  caption: [One stored candidate shell from ASE scene 81286 and sample
  `ASE_81286_Atek_000035`. The perspective panel relates the shell to the logged
  camera history, target OBB, and selected prefix. The bird's-eye panel retains
  all 60 candidate centres: 25 are feasible, 35 fail clearance, and
  oracle-greedy selects row 47. The example's evidential role is proposal support
  and hard feasibility.],
) <fig:candidate-generation-geometry>

Each row begins with a random unit direction in the reference rig frame. The
frozen profile uses a forward-biased Power Spherical distribution with
$kappa=8$ @PowerSpherical-deCao2020:

$
  #eqs.action.power_spherical_forward
$

The sampled direction is then mapped into the configured azimuth and elevation
caps. With $psi = op("atan2")(u_x, u_z)$ and $u_y = sin theta$, the transform is

$
  #eqs.action.angle_cap_transform
$

$
  #eqs.action.capped_direction
$

The cap controls angular extent without changing the row count. Family-specific
maps then reinterpret the same bounded random variable relative to rig forward,
the target bearing, or the lateral direction. This factorization separates
*diversity within a family* from *the geometric meaning of the family*.

Let $bold(f)=bold(e)_z$ denote rig forward, $bold(b)_e$ the supplied target
bearing, $bold(l)_e$ its normalized horizontal lateral direction, and
$bold(e)_y$ world up in the sampling frame. The three core maps are

$
  #eqs.action.family_directions
$

A family-conditioned radius turns direction into translation; the reference
pose then maps that offset into world coordinates:

$
  #eqs.action.candidate_center_world
$

Forward-local rows retain the reference orientation. Target-looking rows use the
supplied target centre $bold(p)_e$ to construct an orthonormal look-at frame:

$
  #eqs.action.target_lookat_frame
$

The target centre in these equations is privileged under the present oracle
protocol. A deployable candidate generator must replace it with an
observation-derived target estimate. These equations specify the sampling prior;
oracle opportunity and downstream policy evidence evaluate the utility of the
actions that survive feasibility pruning.

The optional `target_orbit` challenger makes this distinction explicit. It
proposes paired signed angular offsets at the current horizontal target
standoff, thereby testing bilateral partial-orbit coverage. Pruning can remove
one side, so proposal symmetry and feasible symmetry are measured separately.
The family serves as a geometric ablation and contains no learned human-motion
model.

Pruning evaluates each proposal independently of its oracle reward. A row is
feasible only if it lies in the snippet support, stays clear of the
@ground-truth:short mesh, admits a collision-free straight path, and satisfies
the local motion bounds

$
  #eqs.action.motion_pruning_limits
$

The full shell retains proposal probability, family, rule masks, diagnostics,
and invalid-reason bitsets. The hard mask then produces #symb.rl.action_set
while retaining rejected rows for analysis. A separate root-support gate
rejects a task if pruning leaves too few alternatives:

$
  #eqs.action.valid_support_threshold
$

This gate protects the statistical support of the decision problem: one or two
surviving actions provide insufficient variation for a candidate-ranking test.
Oracle opportunity measures the utility available among the surviving
candidates. Rejected roots and family-specific failure reasons enter the dataset
population report.

=== Candidate-Support and Geometric-Coverage Diagnostics

Learning can rank only the alternatives supplied by candidate generation. The
proposal profile is therefore part of the experimental design, and its support
must be characterized before reward or policy results are interpreted. Let
$cal(I)_s$ contain all attempted non-padding rows, let
$cal(V)_s subset cal(I)_s$ contain the feasible rows selected by
#symb.rl.action_mask, and let $cal(L)_s subset cal(V)_s$ contain feasible rows
with finite oracle labels. These nested populations separate three questions:
what was proposed, what could be selected, and what could supervise learning.

The actor-valid fraction

$
  #eqs.metrics.candidate_actor_valid_fraction
$

measures pruning severity, whereas

$
  #eqs.metrics.valid_support
$

counts the number of alternatives that survive pruning. The distinction matters because
two profiles can retain the same fraction while presenting very different
numbers of choices. Family collapse is measured separately by

$
  #eqs.metrics.configured_family_zero_rate
$

which is one exactly when every configured family has zero feasible rows and
zero only when every family survives. It detects a failure that a pooled valid
fraction can hide: a large forward family may dominate the row count even when
all target-conditioned families disappear.

Because many states can originate from one scene, row-level pooling would let
large scenes dominate the study. Every state statistic $q(s)$ is therefore
averaged within scene and then macro-averaged across scenes:

$
  #eqs.metrics.state_scene_macro
$

The metric-specific set $cal(S)_(c,q)$ makes undefinedness explicit. Failed
generation roots contribute zero support and complete family collapse, while a
directional statistic is undefined if no relevant direction was attempted.
Undefined states and scenes are reported separately, and paired profile
contrasts use the shared eligible-scene intersection. This preserves the
difference between absence of support and absence of a defined measurement.

Support geometry is compared in the target-relative normalized frame
$#eqs.spatial.candidate_proposal_support_normalization$. The factual expansion
pose is the origin, the target lies at unit distance, and world up fixes the
vertical axis. The normalization removes absolute standoff while preserving
whether candidates move towards, around, above, or behind the target. This
coordinate system describes candidate motion; calibrated projection and
visibility are measured in their respective image and observation domains.

For attempted target-conditioned rows, side balance

$
  #eqs.metrics.target_side_balance
$

compares positive and negative target-relative sides after excluding the neutral
band $|y_(s,i)^"target"| <= 10^(-9)$. Circular orbit span

$
  #eqs.metrics.circular_orbit_span
$

measures the smallest angular arc covering the attempted directions. These
statistics characterize proposal diversity before pruning. Family survival and
oracle opportunity quantify the later feasibility and utility stages.

For evaluated candidates, the projection fraction

$
  #eqs.metrics.target_center_projection_fraction
$

records whether the target centre falls inside the calibrated image domain. It
measures geometric framing. Visibility additionally requires object extent and
occlusion evidence. The finite-support oracle opportunity

$
  #eqs.metrics.oracle_opportunity
$

is the best target-root gain present in $cal(L)_s$. It measures whether the
finite shell contains a useful action, independent of which policy selects it.
Low opportunity identifies an action-support limitation; high opportunity with
poor policy return instead leaves room for a ranking limitation.

Finally, jitter compliance checks whether within-family perturbations obey their
declared angular caps:

$
  #eqs.metrics.jitter_compliance
$

Uncapped spherical profiles form a different support class and are reported
separately. Jitter compliance provides generator quality control; visibility
and policy quality use their own measurements.

#figure(
  publication-table(
    columns: (0.95fr, 1.15fr, 0.65fr, 1.55fr),
    header: ([*Quantity*], [*Population*], [*Unit*], [*Interpretation boundary*]),
    rows: (
      ([Actor-valid fraction], [Attempted rows per state], [fraction], [Hard feasibility before label and training filters.]),
      ([Valid support], [Actor-valid rows per state], [rows], [Report the distribution, lower tail, and failed roots.]),
      ([Configured-family zero rate], [Configured families per state], [fraction], [Retains absent and zero-support families; state values are scene-macro reduced.]),
      ([Side balance / circular span], [Non-neutral attempted target-conditioned rows], [fraction / angle], [Neutral rows and undefined states are reported separately; proposal coverage precedes pruning.]),
      ([Target-centre projection], [Evaluated candidate views per state], [fraction], [Calibrated framing; zero-evaluated states are reported as undefined.]),
      ([Oracle opportunity], [Finite actor-valid rewards per eligible state], [gain], [Available one-step headroom; undefined when no finite actor-valid label exists.]),
      ([Jitter compliance], [Bounded-jitter rows per state], [fraction], [State--scene--cohort macro; report undefined, nonzero, and uncapped support separately.]),
    ),
  ),
  caption: [Candidate-generation diagnostics and their aggregation populations. Every state-level quantity is reduced before scene and cohort aggregation.],
) <tab:candidate-support-metric-contract>

=== Rollout Branch Sampling and Dataset Impact

Rollout recipes convert feasible candidate shells into factual training chains.
Uniform sampling explores support without a utility preference; one-step oracle
greedy selects the largest immediate target gain; bounded oracle lookahead ranks
finite action sequences; and temperature-softmax samples according to oracle
score while retaining stochastic diversity. These recipes define the behavior
distribution from which replay is collected. They serve as data-generation
policies and reference strategies. Chapter 5 evaluates the learned policy on
held-out tasks.

The first action of the highest-ranked bounded-lookahead chain can differ from the action preferred by one-step greedy because lookahead ranks retained finite-horizon chains rather than immediate gain alone (@fig:oracle-lookahead-tree). The persisted artifact contains the beam-retained chains and their full per-step candidate shells; it is not an exhaustive materialization of the counterfactual action tree.

#figure(
  align(center, image(
    "../../figures/oracle_lookahead_tree.pdf",
    width: 100%,
  )),
  alt: "A short factual prefix reaches root state s t. Two complete beam-retained paths then cross time planes t, t plus 1, and t plus 2. The thinner path begins with action i1, whose immediate target-root gain exceeds that of i2. The thicker path begins with i2 and ends in a ringed highest-ranked endpoint because its two-step return exceeds the return of the i1 path; both solid paths persist. A red dotted invalid-row stub ends at a cross before t plus 1 and has no child. A gray dashed root stub ends at one bar to denote a legal row outside branch factor two that remains in the full shell; a later dashed stub ends at two bars to denote an expanded path removed by beam width two.",
  caption: [Constructed depth-two ordering reversal for target-root gain. Both solid paths are beam-retained from one factual prefix: $i_1$ has the larger immediate gain, while $tau_2$ ranks first at $h=2$ and $gamma=1$; $tau_1$ also persists. The dotted stub is invalid. The single-bar stub is a legal shell row outside branch factor $2$; the double-bar stub is an expanded path removed by beam width $2$. Inequalities encode ordering only, not measured rewards or learned-policy performance.],
) <fig:oracle-lookahead-tree>

For stochastic collection, the temperature-softmax recipe converts each finite
oracle score $s_i$ into the robust logit

$
  #eqs.action.robust_temperature_softmax
$

Median and interquartile-range normalization reduce sensitivity to the absolute
score scale, while temperature controls concentration over the feasible rows.
The resulting replay distribution is determined jointly by target sampling,
candidate support, pruning, and rollout recipe. Reporting these factors isolates
the population and behavior distribution on which learned ranking is assessed.
Train-only pilots provide generation-cost and support-diversity evidence;
held-out evaluation supplies policy evidence.

== Measurement and Outcomes

The candidate shell defines possible interventions; the measurement operator
assigns their target-specific consequences. For each feasible row, the oracle
renders depth from #symb.ase.mesh, backprojects #symb.oracle.points_q, fuses the
candidate evidence with the root evaluation cloud, crops both points and mesh to
target $e$, and computes reconstruction error @VIN-NBV-frahm2025. Applying the
same operator before and after the hypothetical acquisition yields
$#symb.entity.target_error$ and $Delta_(t|i)^e$. The candidate label depends
jointly on camera pose, current state, target crop, and update rule.

#validation_todo(
  [Validate repeatability, numerical-failure handling, construct interpretation, root normalization, and matched endpoint re-evaluation before treating target gain as a reliable study outcome.],
  source: [docs/literature/tex-src/arXiv-VIN-NBV; metric-validation artifacts],
  gate: [frozen metric protocol, repeatability table, and claim-level source locators],
)

// evidence:
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44,78-92 (candidate rendering and reconstruction-improvement scoring)
// - ARIA-NBV intervention path -> aria_nbv/aria_nbv/oracle/_scoring.py:94-163, aria_nbv/aria_nbv/oracle/evidence.py:343-381

=== Operational Reconstruction Error <sec:thesis-reconstruction-quality-metric>

// evidence:
// - aria_nbv/aria_nbv/oracle/evidence.py:93-101,343-381 -> ASE GT-depth is the thesis evaluation source; MPS semi-dense points are a legacy diagnostic source.
// - aria_nbv/aria_nbv/oracle/_scoring.py:94-163 -> candidate depth is backprojected, fused with the root cloud, and scored against the target mesh.
// - aria_nbv/aria_nbv/rri_metrics/point_mesh.py:31-141 -> the selected error uses squared point-to-face accuracy and equal-face face-to-point completeness.

Let $C_e$ crop geometry to the selected target region. The evaluation point set
$P_t^e = C_e (#symb.obs.points_t)$ is reconstructed from the observed prefix of
ASE @ground-truth:short depth. Candidate $i$ contributes renderer-derived depth,
which is backprojected and fused with the same root cloud to obtain
$P_(t|i)^e$. MPS semi-dense points serve as actor-side representation input and
as a legacy diagnostic source. ASE depth defines the current oracle evaluation
cloud.

For target mesh $M_e=#symb.ase.mesh_target$, the point-to-mesh term is the mean
squared distance from each reconstructed point to its closest reference
triangle,

#eqs.rri.acc

It measures how closely the reconstructed evidence lies on the target surface
and is therefore sensitive to extra, noisy, or misregistered points. The reverse
mesh-to-point term is

#eqs.rri.comp

and measures which target faces lack nearby reconstructed evidence. Their sum is
the target error

$
  #eqs.entity.target_error
$

with units of square metres. Root and candidate-augmented clouds pass through
the same deterministic fusion and point-cap operator, so the difference isolates
the candidate evidence under a fixed update rule. The resulting estimand is
defined on the capped point set, fixed target mesh, and declared fusion operator.

#figure(
  align(center, image(
    "../../figures/target_rri_point_mesh_geometry.pdf",
    width: 100%,
  )),
  caption: [Geometry of the operational point--mesh error. Panel A isolates the
  point-to-triangle primitive; panel B separates point-to-face accuracy from
  face-to-point completeness. Panel C keeps the surface and point set fixed but
  changes its tessellation, changing equal-face completeness from $0.03640$ to
  $0.02284$ $"m"^2$. The synthetic fixture provides evidence for metric
  sensitivity.],
) <fig:target-rri-point-mesh-geometry>

Because completeness weights faces equally, its value depends on mesh
tessellation and differs from an area-weighted surface integral. Subdividing one
region changes its contribution even when the geometric surface is unchanged
(@fig:target-rri-point-mesh-geometry). Comparisons are internally consistent
when they share one fixed target mesh and scoring protocol, but the numeric error
is specific to that mesh representation.

// evidence:
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/experiments.tex:135 (sampled point-to-mesh accuracy and completeness).
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/supplemental_text.tex:154-169 (fixed surface samples and 5 cm precision/recall).
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/4_experiments.tex:63-67 (Chamfer primary metric; coverage and F1 diagnostics).

=== Reliability under the Frozen Protocol

For fixed source state, target, candidate, and manifest, repeated oracle
evaluation should reproduce both $Delta_(t|i)^e$ and the induced candidate
ordering. This requirement covers the complete measurement operator---rendering,
backprojection, target cropping, fusion, capping, and numerical failure
handling---because instability in any component changes the label. Deterministic
code and a fixed mesh make exact replay possible, but RQ1 still requires
repeatability measurements over the intended scene and target population.

#figure(
  publication-table(
    columns: (1.05fr, 1.45fr, 1.32fr),
    align: left,
    header: ([*Metric family*], [*Question answered*], [*Dependency and thesis role*]),
    rows: (
      (
        [Equal-face bidirectional point--mesh error],
        [Are reconstructed points close to @ground-truth:short faces, and does every @ground-truth:short face have nearby point evidence?],
        [Depends on point fusion and mesh tessellation; selected operational RRI error.],
      ),
      (
        [Point-sampled Chamfer / accuracy--completeness],
        [Are two sampled surface point sets mutually close?],
        [Depends on sampling density, randomness, norm, and squaring convention; alternative operationalization.],
      ),
      (
        [Thresholded precision, recall, and F-score],
        [What fraction of predicted and reference samples fall within tolerance $tau$, and how do the two fractions balance?],
        [Interpretable at a physical tolerance but threshold-dependent; secondary diagnostic alongside scalar RRI.],
      ),
      (
        [TSDF, occupancy, coverage, or information gain],
        [How much volumetric surface, free space, or previously unknown space is reconstructed or observed?],
        [Depends on grid, truncation, and visibility definitions; answers a different question from target surface quality.],
      ),
    ),
  ),
  caption: [Reconstruction measures answer different geometric questions. The
  equal-face point--mesh error is the selected outcome; the other families are
  diagnostics or alternative operationalizations.],
) <tab:thesis-reconstruction-metric-comparison>

Point-sampled Chamfer distance draws a finite reference set $Q_e$ from
the mesh and averages nearest-neighbour distances in both directions:

#eqs.rri.point_sampled_chamfer

Sampling density, randomness, norm, and squaring convention determine its finite
value despite the symmetric formula. Thresholded precision, recall, and F-score add a
physically interpretable tolerance $tau$, but discard error magnitude on either
side of that threshold. Volumetric coverage and information gain measure
observed space or uncertainty reduction. These are useful complementary
quantities. Each operationalization maps a different geometric construct.

=== Construct Validity

The operational construct is *target-surface evidence after a declared
acquisition and update*. ASE depth, the selected target crop, equal-face mesh
reduction, and the fusion operator jointly define it. Perceived object quality
and whole-scene completeness require different constructs. Two systems that
share the final point--mesh formula but apply different state updates estimate
different intervention effects.

The implementation includes a mesh face in the target crop when any vertex lies
inside the target @oriented-bounding-box. A geometry-invalid candidate is
excluded by #symb.rl.action_mask. An empty crop, insufficient root support, or
unusable render makes the oracle outcome undefined and clears
#symb.rl.q_label_mask. This preserves whether failure occurred in the action
domain or in the measurement operator.

Comparative policy evidence therefore requires the same target mesh and crop,
ASE-depth source, renderer, backprojection, fusion, point cap, and metric
configuration. Replacing ASE depth with MPS semi-dense evidence changes both the
observation process and the error population and therefore defines a separate
experimental outcome.

=== RRI, Training Reward, and Endpoint Gain

The learning and evaluation quantities are derived from the same error sequence
$Delta_0^e, Delta_1^e, dots, Delta_H^e$, but answer different questions.
State-relative RRI asks how much one action improves the *current* state;
target-root reward assigns additive credit along a chain; endpoint gain asks how
much the target improved after a fixed budget. Their denominators determine
whether they can be accumulated or compared across states.

The VIN-compatible marginal diagnostic is

$
  #eqs.rl.marginal_target_rri
$

Its selected-chain running sum is

$
  #eqs.rl.cumulative_target_rri
$

Because each term is normalized by its own $#symb.entity.target_error$, the sum
describes accumulated local relative improvements. Fixed-budget policy outcomes
use the root-to-endpoint definition below.

The training reward normalizes every step by the rollout-root target
error @VIN-NBV-frahm2025:

$
  #eqs.rl.target_root_gain_reward
$

With unit discount, summing these rewards over a factual chain telescopes:

$
  #eqs.rl.cumulative_target_root_gain
$

The horizon-conditioned return used to supervise #symb.rl.qh is

$
  #eqs.rl.finite_horizon_return
$

This return evaluates a candidate first action under the continuation rule that
generated the remaining factual chain. Its scope is offline finite-candidate
control.

The primary policy outcome is endpoint gain

$
  #eqs.entity.endpoint_gain
$

because it compares target error after the same acquisition budget $H$. The
log-gain variant

$
  #eqs.entity.log_gain
$

is retained as a scale-sensitivity diagnostic. Thus
#symb.entity.target_rri_marginal describes local candidate improvement,
#symb.entity.return_h supplies the learning target, and
#symb.entity.endpoint_gain supplies the fixed-budget evaluation outcome. The
endpoint denominator $Delta_0^e + epsilon$ differs from the clamped root
denominator $max(Delta_0^e, epsilon)$ used by the additive reward. Near zero root
error, each quantity must be interpreted under its own denominator. The resolved
manifest must therefore freeze the discount, clipping, crop, point update, and
all evaluation-geometry parameters for each reported experiment.
