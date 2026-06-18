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
    [Appendix/open-work TODO, not final experiment evidence.],
    bottomrule(),
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

=== Target-Specific @relative-reconstruction-improvement:short

Let $C_e (#symb.obs.points_t)$ denote the oracle-only crop of accumulated points to the matched target region. The target error is the target-cropped version of the VIN-NBV @relative-reconstruction-improvement:short objective @VIN-NBV-frahm2025: point-to-mesh accuracy plus mesh-to-point completeness on the crop.

$
  #eqs.entity.target_error
$

Area weighting or uniformly sampled target-surface points prevent target-specific @relative-reconstruction-improvement:short from reflecting mesh tessellation density. For reproducibility, the current implementation computes the point-mesh distances through `OracleRRI.score` and `chamfer_point_mesh_batched`, while `aria_nbv.pose_generation.target_counterfactuals` owns the target crop. Empty or unsupported target crops are invalid label cases, not low-@relative-reconstruction-improvement:short samples. Rollout ranking and #symb.rl.qh training use root-normalized target gain; scene-level @relative-reconstruction-improvement:short is a diagnostic bridge to the older seminar oracle pipeline, not the optimized reward.

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
