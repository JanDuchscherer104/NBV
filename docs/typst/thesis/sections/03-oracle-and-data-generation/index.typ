= Oracle and Data Generation <sec:thesis-oracle-data-generation>

The preceding chapter established what a target-conditioned planning state must
preserve. This chapter constructs the controlled decision process in which those
requirements can be tested. Starting from a logged egocentric snippet and a
requested target, the system proposes candidate observations, removes
geometrically infeasible actions, and uses privileged scene geometry to measure
the hypothetical reconstruction consequence of each remaining candidate.

The central structure is asymmetric. Every evaluable candidate may receive an
immediate oracle label, but only the selected action creates a factual successor
that can extend the actor's causal history. Unselected renders remain
supervision; they do not become observations. This distinction determines both
the actor--oracle information boundary and the replay relations from which
finite-horizon targets can be constructed. The chapter therefore proceeds from
information access, through target and action construction, to measurement and
causal replay. Model-ready tensors in Chapter 4 are projections of these
scientific relations, not their definition.

#include "03-01-state-and-visibility.typ"

#include "03-02-target-task-and-rri-labels.typ"

#include "03-03-replay-stores-and-diagnostics.typ"
