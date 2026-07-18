#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb

= Method <sec:thesis-method>

ARIA-NBV is formulated as target-conditioned selection from a finite candidate table. The implemented substrate generates and evaluates masked multi-step pose rollouts, records their selected transitions, and exposes a dense training view for a future finite-horizon value model. The current learned component remains the seminar-era myopic VIN scorer. Consequently, this chapter separates implemented data and replay contracts from the finite-horizon learning interface that they are intended to support; it does not report an untrained #symb.rl.qh model as a completed method.

The chapter first identifies the actor-visible state that current scorers and candidate generators actually consume. It then specifies the descriptors that are persisted or can be derived without privileged labels, the finite-action and replay semantics, and the tested symmetry and mask invariants. The final section defines the bounded #symb.rl.qh training problem and states the remaining implementation gap.

#include "04-01-scene-representation-requirements.typ"

#include "04-02-descriptor-and-encoding-plan.typ"

#include "04-03-candidate-and-replay-contract.typ"

#include "04-04-architecture-contract.typ"

#include "04-05-finite-candidate-value-model.typ"
