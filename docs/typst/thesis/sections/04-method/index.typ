#import "../../draft_markers.typ": prune_todo

= Method <sec:thesis-method>

#prune_todo(
  [Rewrite this chapter around one frozen, implemented, and evaluated method. Move rejected objectives, alternative carriers, architecture ladders, and unresolved scorer interfaces to development-only notes or a compact limitations/future-work account.],
  source: [this chapter and its source-owner decision gates],
  gate: [production scorer, frozen objective, matched controls, and end-to-end acceptance evidence],
)

Chapter 3 defined the controlled decision process; this chapter specifies the
model evaluated within it. At each realized state, the model receives a causal
scene representation, a target state, a finite set of candidate views, the
selected-view history, the remaining acquisition budget, and a requested
prediction horizon. It returns one conditional value for every materialized
candidate. The hard feasibility mask remains outside the value function and
restricts which of those candidates a policy may select.

Geometry enters through relations rather than absolute world coordinates.
Candidate poses are expressed from the rollout root and current camera, the
target is expressed relative to each candidate, and candidate rows remain
exchangeable. Each candidate reads shared scene, target, history, budget, and
horizon context through the same interaction module. The scene-carrier boundary
separates immutable root evidence from information added by selected
observations; the current compact controls use pooled EVL and semi-dense
evidence, causal pose history, and an optional privileged selected-surface
update. Richer ray-aware or entity-level memories can replace that carrier
without changing the candidate-value interface.

Learning follows the factual asymmetry of the replay data. Under the dense-label
corpus, immediate oracle labels supervise every evaluable feasible candidate at
a state. Longer-horizon targets are available only for selected actions whose
factual successors are stored. The finite-horizon target therefore combines the
selected action's immediate gain with a shorter-horizon value at the next causal
state, as defined in @ssec:thesis-horizon-recursive-offline-learning. The
following sections separate scene and target representation, geometric
encoding, causal replay, architecture acceptance properties, and the fitted
value objective so that each design choice can be tested without redefining the
others.

#include "04-01-scene-representation-requirements.typ"

#include "04-02-descriptor-and-encoding-plan.typ"

#include "04-03-candidate-and-replay-contract.typ"

#include "04-04-architecture-contract.typ"

#include "04-05-finite-candidate-value-model.typ"
