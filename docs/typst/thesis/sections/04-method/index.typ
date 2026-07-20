#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb

= Method <sec:thesis-method>

ARIA-NBV is formulated as target-conditioned selection from a finite candidate table. The implemented substrate generates and evaluates masked multi-step pose rollouts, records selected transitions, and exposes a dense training view for a planned finite-horizon value model. The current learned control is a myopic VIN scorer. Consequently, this chapter separates implemented data and replay contracts from the planned target-conditioned candidate-to-state Transformer; it does not report an untrained #symb.rl.qh model as a completed method.

The chapter first identifies the actor-visible state and the coverage limitation of local EFM3D evidence. It then specifies the persisted and planned descriptors, the finite-action and replay semantics, geometric acceptance tests, a ranked representation and architecture design space, and the canonical bounded #symb.rl.qh model. Descriptive status blocks distinguish implementation maturity from evidence maturity throughout.

#include "04-01-scene-representation-requirements.typ"

#include "04-02-descriptor-and-encoding-plan.typ"

#include "04-03-candidate-and-replay-contract.typ"

#include "04-04-architecture-contract.typ"

#include "04-05-finite-candidate-value-model.typ"
