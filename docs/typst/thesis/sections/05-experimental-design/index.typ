= Experimental Design <sec:thesis-experimental-design>

The experiments test the thesis claims in the order established by the
conceptual spine. They first determine whether the target-specific outcome is
repeatable and whether the scene, target, candidate, and replay population
contains the required support. They then test whether bounded oracle lookahead
improves fixed-budget endpoint reconstruction over immediate oracle-greedy
selection. Only after such headroom is established does the learned comparison
ask how much of the actor-visible myopic-to-lookahead gap is recovered. Scene
and target representations, temporal encoders, and candidate interactions are
secondary comparisons within that admitted planning problem.

The scene is the independent experimental unit. Confirmatory policy comparisons
therefore use scene-disjoint data, matched target and candidate conditions,
equal acquisition budgets, and independent endpoint oracle evaluation.
Generation throughput, invalidity, support, and resource use remain necessary
feasibility evidence, but they cannot substitute for paired policy outcomes.
This separation prevents architecture capacity or systems readiness from being
mistaken for evidence that non-myopic target reconstruction is useful.

#include "05-01-objectives-and-hypotheses.typ"

#include "05-02-learning-objective-and-replay-evidence.typ"

#include "05-03-policy-comparison-and-failure-interpretation.typ"
