#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

= Method <sec:thesis-method>

ARIA-NBV is a target-conditioned, finite-candidate @next-best-view problem in the Project Aria / @aria-synthetic-environments:short / @egocentric-foundation-model-3d:short observation regime. The learned method tests whether bounded planning over a valid finite candidate table improves target reconstruction quality beyond myopic selection. It does not claim first-order continuous control, complete scene reconstruction, or fresh counterfactual image understanding.

The chapter proceeds in dependency order. First, it states the representation requirements imposed by actor-visible target selection and counterfactual rollout. Second, it defines the descriptor protocol: the typed target, scene, history, candidate, relation, support, mask, and provenance tensors available to the actor. Third, it states the replay contract that turns valid candidate rows into selected transitions. Finally, it gives the value-model contract and the acceptance tests needed before heavier geometric attention or equivariant modules can be credited.

#include "04-01-scene-representation-requirements.typ"

#include "04-02-descriptor-and-encoding-plan.typ"

#include "04-03-candidate-and-replay-contract.typ"

#include "04-04-architecture-contract.typ"

#include "04-05-finite-candidate-value-model.typ"
