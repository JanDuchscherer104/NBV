#import "../../shared/macros.typ": *
#import "../../shared/symbols.typ": symb
#import "../../shared/equations.typ": eqs

== Formal State and Visibility

The initial non-myopic experiment is a #emph[masked finite-horizon candidate-decision process], not a stationary deployment MDP. It is an offline, mesh-supervised #emph[controlled counterfactual replay] process: the oracle may render selected candidates and regenerate the next candidate table as part of the experimental protocol, while the actor sees only the typed state features below.

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

The model separates logged snippet state, counterfactual actor state, and privileged oracle state because real egocentric trajectories contain modalities that are not available after synthetic view choices. The raw historic state is the state available on the logged @aria-synthetic-environments:short trajectory:

$
  #eqs.rl.s_hist
$

The planner state is the minimal counterfactual actor state. It keeps local root @egocentric-voxel-lifting:short evidence fixed while updating the fused geometry proxy, optional point-feature bank, selected-view history, remaining horizon metadata, target descriptor, candidates, masks, and reason codes:

$
  #eqs.rl.s_cf0
$

The privileged oracle state augments this with @ground-truth:short geometry, the matched target mesh, all-candidate rendered points, and oracle labels. It is used for target-task selection, label generation, upper-bound planning, and evaluation:

$
  #eqs.rl.s_oracle
$

@ground-truth:short meshes, @ground-truth:short OBBs, @ground-truth:short crops, @ground-truth:short semantic labels, and all-candidate @ground-truth:short renders are oracle assets. They may define target tasks and labels, but they are not learned actor inputs unless a named upper-bound or privileged-teacher ablation explicitly says so. Invalidity is modeled as a constraint: masks apply before argmax, temperature softmax, loss targets, and bootstrap maximization. True infeasibility or absent evaluation samples are invalid rows; low immediate target support is reported as a diagnostic unless it prevents valid oracle evaluation.
