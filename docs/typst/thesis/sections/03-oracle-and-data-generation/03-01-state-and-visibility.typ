#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs

== State and Visibility Boundary

The initial non-myopic experiment is a #emph[masked finite-horizon candidate-decision process], not a stationary deployment MDP. It is an offline, mesh-supervised #emph[controlled counterfactual replay] process: the oracle may render selected candidates and regenerate the next candidate table as part of the experimental protocol, while the actor sees only the typed state features below.

#figure(
  align(center, image(
    "../../figures/qh_actor_oracle_contract.pdf",
    width: 100%,
  )),
  caption: [Actor-visible and oracle-only state boundary for the V1 thesis protocol. The learned #symb.rl.qh policy may consume accumulated geometry, frozen @egocentric-voxel-lifting:short evidence, target descriptors, history, budget, candidates, masks, and invalid reasons; @ground-truth:short meshes, boxes, dense candidate renders, target labels, and endpoint metrics supervise labels, upper bounds, evaluation, or explicitly named teacher ablations only.],
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
