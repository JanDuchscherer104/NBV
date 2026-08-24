#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../draft_markers.typ": prune_todo

= Method <sec:thesis-method>

#prune_todo(
  [Rewrite this chapter around one frozen, implemented, and evaluated method. Move rejected objectives, alternative carriers, architecture ladders, and unresolved scorer interfaces to development-only notes or a compact limitations/future-work account.],
  source: [this chapter and its source-owner decision gates],
  gate: [production scorer, frozen objective, matched controls, and end-to-end acceptance evidence],
)

ARIA-NBV is formulated as target-conditioned selection from a finite candidate table. The implemented substrate generates and evaluates masked multi-step pose rollouts, records selected transitions, exposes a dense training view, and trains an actor-only #symb.rl.qh scorer through fitted Double-Q optimization. The modular `A0/A1--S0-pose--root-moments` controls expose identical scene, target, causal-history, budget, and horizon inputs to an independent-row MLP or candidate-to-state attention, respectively; A1 remains the default. They are executable architecture controls, not yet a policy result or evidence that the compact state is task-sufficient.

The frozen interface distinguishes remaining budget $b_t$, scalar requested residual horizon $h$, and configured support bound $H_"max"$. The mathematical value family permits $1 <= h <= b_t <= H_"max"$, but implemented `V1` is deliberately restricted to the trained remaining-budget diagonal $h=b_t$; padding uses zero and every off-diagonal query fails closed. The scorer returns action-mask-independent conditional values and feasibility logits, while Lightning and online inference retain hard-mask ownership. Direct continuous Huber regression is the canonical value objective. A modular CORAL decoder over the same continuous fitted-Q targets is implemented as an ordinal ablation with fixed manifest-bound edges and continuous representatives; exact horizon-two targets, recursive lower-horizon backups, Double-Q selection/evaluation, and behavior-policy returns remain separately named controls or ablations.

The chapter first fixes the actor-visible state and the coverage limitation of local EFM3D evidence. It then separates the implemented compact scorer from richer scene carriers, interaction ablations, and bounded #symb.rl.qh learning targets. Descriptive status blocks distinguish executable maturity from scientific evidence throughout.

#include "04-01-scene-representation-requirements.typ"

#include "04-02-descriptor-and-encoding-plan.typ"

#include "04-03-candidate-and-replay-contract.typ"

#include "04-04-architecture-contract.typ"

#include "04-05-finite-candidate-value-model.typ"
