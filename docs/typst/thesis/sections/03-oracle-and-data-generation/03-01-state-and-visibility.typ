#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs

== State and Visibility Boundary

The initial non-myopic experiment is a #emph[masked finite-horizon candidate-decision process], not a stationary deployment MDP. It is an offline, mesh-supervised #emph[controlled counterfactual replay] process over Project Aria-style @aria-synthetic-environments:short snippets: logged egocentric observations and frozen @egocentric-voxel-lifting:short evidence define the actor state, while @aria-synthetic-environments:short meshes and annotations provide target matching, rendered counterfactual geometry, labels, and evaluation @ProjectAria-ASE-2025 @EFM3D-straub2024 @VIN-NBV-frahm2025. The core scientific constraint is therefore a leakage boundary: oracle products may supervise a loss or report an upper bound, but they must not become inputs to the learned #symb.rl.qh actor unless the experiment is explicitly named as privileged.

#figure(
  align(center, image(
    "../../figures/actor_oracle_boundary.pdf",
    width: 100%,
  )),
  caption: [Actor-visible and oracle-only state boundary for the V1 thesis protocol. Solid arrows denote legal #symb.rl.qh inputs: accumulated geometry, frozen @egocentric-voxel-lifting:short evidence, target descriptors, history, budget, candidates, masks, and invalid reasons. @ground-truth:short meshes, @ground-truth:short boxes, target crops, dense candidate renders, target labels, returns, and endpoint metrics remain on the oracle side and can supervise labels, upper bounds, evaluation, or explicitly named teacher ablations only.],
) <fig:qh-actor-oracle-contract>

The three state spaces referenced by the protocol tuple are the codomains of the shared state equations. The logged historic state contains only the original trajectory evidence,

$
  #eqs.rl.s_hist
$

the counterfactual actor state is the deployable state for #symb.rl.qh decisions,

$
  #eqs.rl.s_cf0
$

and the privileged oracle state is a label/evaluation state outside the actor input graph:

$
  #eqs.rl.s_oracle
$

$
  #eqs.rl.nbv_process_tuple
$

The model separates logged snippet state, counterfactual actor state, and privileged oracle state because real egocentric trajectories contain modalities that are not available after synthetic view choices. The raw historic state is available on the logged @aria-synthetic-environments:short trajectory. The planner state keeps local root @egocentric-voxel-lifting:short evidence fixed while updating the fused geometry proxy, optional point-feature bank, selected-view history, remaining horizon metadata, target descriptor, candidates, masks, and reason codes. The privileged oracle state augments this with @ground-truth:short geometry, the matched target mesh, all-candidate rendered points, and oracle labels for target-task selection, label generation, upper-bound planning, and evaluation.

@ground-truth:short meshes, @ground-truth:short OBBs, @ground-truth:short crops, @ground-truth:short semantic labels, and all-candidate @ground-truth:short renders are oracle assets. They may define target tasks and labels, but they are not learned actor inputs unless a named upper-bound or privileged-teacher ablation explicitly says so. Invalidity is modeled as a constraint: masks apply before argmax, temperature softmax, loss targets, and bootstrap maximization. True infeasibility or absent evaluation samples are invalid rows; low immediate target support is reported as a diagnostic unless it prevents valid oracle evaluation.
