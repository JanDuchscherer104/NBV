#import "../../../shared/macros.typ": *

= Oracle and Data Generation <sec:thesis-oracle-data-generation>

This chapter defines the non-deployable pipeline that turns logged ASE snippets into supervised target-conditioned @next-best-view:short tasks. It separates actor state from privileged data-generation state, specifies target-task and candidate construction, defines hard invalidity and target-specific @relative-reconstruction-improvement:short, and records the resulting selected counterfactual chains. The learned method in @sec:thesis-method may consume only the actor-side projection of these artifacts; @ground-truth:short geometry, counterfactual renders, labels, and oracle search remain instruction, supervision, or evaluation assets.

#include "03-01-state-and-visibility.typ"

#include "03-02-target-task-and-rri-labels.typ"

#include "03-03-replay-stores-and-diagnostics.typ"
