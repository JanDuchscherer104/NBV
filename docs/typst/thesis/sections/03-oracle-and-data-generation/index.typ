#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

= Oracle and Data Generation <sec:thesis-oracle-data-generation>

This chapter defines the non-deployable machinery that turns logged ASE snippets into supervised target-conditioned NBV tasks. It owns the actor/oracle state boundary, target-task selection, candidate generation, hard validity masks, target-specific RRI labels, and rollout/replay evidence. The learned method in @sec:thesis-method consumes actor-visible products from this pipeline; GT meshes, GT target crops, dense candidate renders, and oracle lookahead remain label, teacher, upper-bound, or evaluation assets.

#include "03-01-state-and-visibility.typ"

#include "03-02-target-task-and-rri-labels.typ"
