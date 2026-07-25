#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb

= Method <sec:thesis-method>

ARIA-NBV is formulated as target-conditioned selection from a finite candidate table. The implemented substrate generates and evaluates masked multi-step pose rollouts, records selected transitions, and exposes a dense training view. A development implementation now additionally provides a deterministic V0, horizon-two, pose-history-conditioned #symb.rl.qh tracer and fitted-Q training seam, while the existing myopic VIN scorer remains the matched one-step control. The tracer does not yet implement the task-sufficient dynamic reconstruction state defined in this chapter: it omits selected-observation fusion and rich root EVL scene tokens. This chapter therefore distinguishes the implemented tracer from the canonical target-conditioned scene-memory model and does not treat either training loss or an unvalidated checkpoint as policy evidence.

The chapter first fixes the actor-visible state and the coverage limitation of local EFM3D evidence. It then specifies persisted and model-facing DTO roles, the finite-action and replay semantics, geometric acceptance tests, orthogonal scene-carrier and interaction-architecture ladders, and the bounded #symb.rl.qh learning targets. Descriptive status blocks distinguish implementation maturity from evidence maturity throughout.

#include "04-01-scene-representation-requirements.typ"

#include "04-02-descriptor-and-encoding-plan.typ"

#include "04-03-candidate-and-replay-contract.typ"

#include "04-04-architecture-contract.typ"

#include "04-05-finite-candidate-value-model.typ"