#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb

= Oracle and Data Generation <sec:thesis-oracle-data-generation>

This chapter defines the experimental objects from which ARIA-NBV constructs
training and evaluation data. A logged snippet first induces an actor-side
information state #symb.rl.s_hist. A target task then turns that state into a
finite candidate table #symb.rl.candidate_table; the hard action mask
#symb.rl.action_mask selects its feasible subset. Privileged rendering assigns
target-specific reconstruction outcomes, while a selected action creates the
only factual successor that may extend the causal history. Replay storage
preserves these relations. Final padded tensors are model-specific projections.

State determines what may be conditioned on. The target and proposal mechanism
determine which actions can be compared. The oracle defines their supervision,
and lineage determines which multi-step returns can be reconstructed from
factual transitions. These dependencies connect the chapter's information,
action, measurement, and storage contracts to the learned scorer in the Method
chapter.

#include "03-01-state-and-visibility.typ"

#include "03-02-target-task-and-rri-labels.typ"

#include "03-03-replay-stores-and-diagnostics.typ"
