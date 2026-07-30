#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb

= Method <sec:thesis-method>

ARIA-NBV is formulated as target-conditioned selection from a finite candidate table. The implemented substrate generates and evaluates masked multi-step pose rollouts, records selected transitions, exposes a dense training view, and provides scorer-independent fitted Double-Q optimization for an injected candidate-value model. It does not yet provide a production #symb.rl.qh scorer, checkpoint, or policy result. The existing myopic VIN scorer remains the historical one-step control, while the target-conditioned scene-memory scorer described in this chapter remains planned.

The current canonical direction is a bounded fixed-horizon candidate scorer whose actor state includes remaining budget. An explicit requested-horizon query $Q_theta(s_t,e,i,h)$ is a design candidate to compare before the scorer PR, not an implemented or frozen interface. Dense one-step values, exact horizon-two targets, recursive fitted values, Double-Q backups, and behavior-policy returns remain distinct potential objectives or controls; the first scorer design and objective sequence must be fixed by the source-owner decision gate.

The chapter first fixes the actor-visible state and the coverage limitation of local EFM3D evidence. It then separates implemented replay/training infrastructure from proposed scorer DTOs, finite-action semantics, geometric acceptance tests, scene-carrier alternatives, interaction architectures, and bounded #symb.rl.qh learning targets. Descriptive status blocks distinguish implementation maturity from evidence maturity throughout.

#include "04-01-scene-representation-requirements.typ"

#include "04-02-descriptor-and-encoding-plan.typ"

#include "04-03-candidate-and-replay-contract.typ"

#include "04-04-architecture-contract.typ"

#include "04-05-finite-candidate-value-model.typ"
