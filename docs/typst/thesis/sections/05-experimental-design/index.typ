#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

= Experimental Design <sec:thesis-experimental-design>

The experiment design evaluates whether the oracle/data-generation pipeline from @sec:thesis-oracle-data-generation and the learned method from @sec:thesis-method produce leakage-safe target-aware view choices under matched acquisition budgets. It treats data support, target identity, validity masks, replay integrity, and oracle-lookahead headroom as preconditions for interpreting value-model performance.

#include "05-01-objectives-and-hypotheses.typ"

#include "05-02-learning-objective-and-replay-evidence.typ"

#include "05-03-policy-comparison-and-failure-interpretation.typ"
