= Foundations and Related Work <sec:thesis-foundations>

The Introduction located this thesis within active perception: sensing actions
change the evidence on which later inference depends @ActivePerception-bajcsy1988
@ActiveVision-aloimonos1988. Three-dimensional view planning turns that principle
into a repeated choice of where to observe next @ViewPlanningSurvey-scott2003.
The unresolved dependency is not another planner implementation but a precise
account of what a view is valuable *for*, which actions are available, and what
information a sequential score may condition on. By the end of the chapter,
the thesis question is reduced to three coupled requirements—utility alignment,
temporal dependence, and support/state adequacy—before the experimental world
is constructed.

The argument follows the dependencies of the decision problem. It first
separates the next-best-view mechanism from the objective used to rank views,
then distinguishes target-conditioned reconstruction quality from coverage and
uncertainty proxies. It next separates candidate-view support from endpoint,
transition, and human-motion feasibility before explaining why partial
observability and delayed consequences require a finite-horizon information
state. The chapter then derives the geometric properties a candidate scorer
should preserve and positions the thesis question against the resulting
literature dimensions.

#include "02-01-active-perception-and-view-utility.typ"

#include "02-02-targets-actions-and-support.typ"

#include "02-03-candidate-support-and-motion-feasibility.typ"

#include "02-04-finite-horizon-value-learning.typ"

#include "02-05-egocentric-and-geometric-representations.typ"

#include "02-06-literature-positioning.typ"
