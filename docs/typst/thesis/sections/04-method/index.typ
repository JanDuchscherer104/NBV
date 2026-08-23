#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../draft_markers.typ": development_only

= Method <sec:thesis-method>

ARIA-NBV is a target-conditioned selection problem over a finite candidate table. The current method path records an implemented replay, read-model, DTO, profile, and return substrate. Its evidence boundary ends before a production scorer or learned policy: no checkpoint or held-out policy result is claimed here.

The method fixes the actor/oracle boundary, the finite replay contract, the three mask meanings, the frame and support limits, and the metric semantics before any policy claim. The following sections record these implemented contracts; development-mode material retains the future scorer design and its evaluation gates separately.

#development_only(() => [
  The planned scorer direction is a bounded fixed-horizon value model. Remaining budget is part of the actor state, and the candidate table is the finite support on which selection, training, and bootstrap are defined. Requested-horizon queries, exact-$H=2$ certification, recursive fitted values, Monte Carlo returns, CQL/BCQ controls, alternative encoders, and alternative policies are development evidence or future comparisons, not the accepted flow.
])

#include "04-01-scene-representation-requirements.typ"
#include "04-02-descriptor-and-encoding-plan.typ"
#include "04-03-candidate-and-replay-contract.typ"
#include "04-04-architecture-contract.typ"
#include "04-05-finite-candidate-value-model.typ"
