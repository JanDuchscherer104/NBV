#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs

== State and Visibility Boundary

The thesis studies a masked finite-horizon candidate-decision process through offline, mesh-supervised counterfactual replay. Logged egocentric observations and frozen @egocentric-voxel-lifting:short evidence define the actor substrate, whereas @aria-synthetic-environments:short meshes, annotations, synthetic target instructions, rendered counterfactual geometry, and labels define privileged data generation @ProjectAria-ASE-2025 @EFM3D-straub2024 @VIN-NBV-frahm2025. An oracle product may supervise a loss or define an upper bound, but it may not enter the learned #symb.rl.qh actor unless the experiment is explicitly labelled privileged.

#figure(
  align(center, image(
    "../../figures/actor_oracle_boundary.pdf",
    width: 100%,
  )),
  caption: [Actor and oracle boundary. Legal #symb.rl.qh inputs are accumulated actor geometry, frozen @egocentric-voxel-lifting:short evidence, an explicitly declared target instruction, selected-view history, remaining budget, candidates, masks, and reason codes. @ground-truth:short geometry, target crops, dense counterfactual renders, labels, and endpoint evaluation remain privileged.],
) <fig:qh-actor-oracle-contract>

The visibility boundary is protocol-relative and temporal. A dense render for an unselected candidate at the current decision step is always oracle or teacher evidence. A render from an action already selected in the retained history may enter a later actor state only under an explicitly named protocol: `CF-GT` for privileged GT-mesh depth, `CF-sensor` for a declared sensor-like simulation, or V1 for an actually actor-visible observation. The same rule applies to backprojected points, normals, and free-space rays. Persisting selected depth does not by itself make that field a legal actor input.

The target is treated as external task context, so the value is conceptually $Q(s_t,e,a)$ rather than a target-independent state value. The logged historic state contains the recorded trajectory evidence,

$
  #eqs.rl.s_hist
$

the counterfactual actor state adds only evidence acquired along the selected synthetic history,

$
  #eqs.rl.s_cf0
$

and the oracle state adds privileged geometry and labels outside the actor input graph:

$
  #eqs.rl.s_oracle
$

$
  #eqs.rl.nbv_process_tuple
$

The counterfactual actor state separates immutable root evidence from a causal dynamic state. In the notation above, the accumulated point proxy denotes geometry fused from the root observation and any selected prior observations; the selected-pose history remains an explicit state component rather than being inferred from that point set. A pose-only implementation is therefore a deliberately weaker `S0` baseline, not a complete realization of the fused counterfactual state.

This separation is necessary because the logged snippet contains modalities that cannot be regenerated after a synthetic action. The counterfactual state therefore keeps root features fixed and updates only evidence produced by selected observations, selected-view history, budget metadata, finite candidates, masks, and reason codes. In the current oracle protocol, the target descriptor supplied to candidate generation is a privileged task instruction derived from the selected @ground-truth:short box; it is not evidence that an actor-visible detector found or localized the target. A deployable experiment must replace that instruction with an observation-derived descriptor and preserve the same crop-free actor interface.

Invalidity is a constraint rather than a reward value. Geometry-invalid candidates receive a hard action mask and a persisted candidate reason code before policy selection, stochastic normalization, loss construction, and bootstrap maximization. A geometrically feasible candidate may still have low or negative target gain. Failure of the separate oracle evaluation does not create a candidate reason code: depending on the configured recipe, the affected row or table is skipped, or its `oracle_label_mask` and `q_train_mask` are cleared and the oracle failure is reported separately. Oracle-derived feasibility must be distinguished from a deployable validity estimate whenever policy claims cross from V0 to V1.