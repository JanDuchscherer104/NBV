= Foundations and Related Work <sec:thesis-foundations>

The Introduction framed target-conditioned NBV as relational prediction over a
causal geometric state. This chapter supplies the concepts needed to make that
formulation precise. It asks what consequence makes a view useful, which actions
can be considered, when immediate ranking is insufficient, and what information
a finite-horizon score must preserve. The argument therefore separates utility
from proposal and feasibility before introducing partial observability,
state-dependent action support, and delayed reconstruction consequences.

The synthesis yields four design principles inherited by the later chapters:
utility must be aligned with the requested target; candidate value is relational
rather than a property of a pose alone; the scene state must preserve causal
observability; and the representation should remove arbitrary coordinates and
row order without erasing gravity, scale, orientation, occlusion, or temporal
order. @sec:thesis-oracle-data-generation turns these principles into a
controlled data-generating process, and @sec:thesis-method instantiates them in
one learned candidate scorer.

#include "02-01-active-perception-and-view-utility.typ"

#include "02-02-targets-actions-and-support.typ"

#include "02-03-candidate-support-and-motion-feasibility.typ"

#include "02-04-finite-horizon-value-learning.typ"

#include "02-05-egocentric-and-geometric-representations.typ"

#include "02-06-literature-positioning.typ"
