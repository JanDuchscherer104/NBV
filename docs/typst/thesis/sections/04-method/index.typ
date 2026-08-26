#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../draft_markers.typ": prune_todo

= Method <sec:thesis-method>

#prune_todo(
  [Rewrite this chapter around one frozen, implemented, and evaluated method. Move rejected objectives, alternative carriers, architecture ladders, and unresolved scorer interfaces to development-only notes or a compact limitations/future-work account.],
  source: [this chapter and its source-owner decision gates],
  gate: [production scorer, frozen objective, matched controls, and end-to-end acceptance evidence],
)

ARIA-NBV is formulated as target-conditioned selection from a finite candidate table. The implemented substrate generates and evaluates masked multi-step pose rollouts, records selected transitions, and exposes a persisted supervision profile that proves when every hard-valid realized action has a one-step Q label. It trains an actor-only #symb.rl.qh scorer through fitted Double-Q optimization. The modular `A0/A1--S0-pose--root-moments` controls expose identical scene, target, causal-history, budget, and horizon inputs to an independent-row MLP or candidate-to-state attention, respectively; A1 remains the default. They are executable architecture controls, not yet a policy result or evidence that the compact state is task-sufficient. One-epoch CUDA contract tests cover regression and CORAL for deployable CF0 bundle reconstruction and privileged CF+ H0/S1 optimization; these bounded fixtures establish executability only, while the learned exact-Q2 gate remains closed.

The frozen interface distinguishes remaining budget $b_t$, scalar requested residual horizon $h$, and configured support bound $H_"max"$. The `bounded_scalar_v1` scorer admits exactly one query per state over $1 <= h <= b_t <= H_"max"$: omission selects the full-budget diagonal $h=b_t$, while $h<b_t$ is a shorter return from the same factual state and padding alone uses zero. This syntactic family is wider than empirical capability: dense hard-valid labels train $h=1$, factual selected transitions train supported $h>1$, and a bundle rejects any requested horizon absent from its manifest-bound training support. A conditional value fixes the represented state, target, candidate selected first, scalar horizon, and named continuation rule; it remains independent of both the action mask and feasibility. The scorer returns those action-mask-independent conditional values and feasibility logits, while Lightning and online inference retain hard-mask ownership. Direct continuous Huber regression is the canonical value objective. A modular CORAL decoder over the same continuous fitted-Q targets is an ordinal ablation with closed train-fitted or physically predeclared support provenance and continuous representatives; exact horizon-two certification, recursive lower-horizon backups, Double-Q selection/evaluation, and behavior-policy returns remain separately named controls or ablations.

A retained rollout is not one recurrent neural-network sample. The normalized replay view expands it into a padded sequence of realized decision states: the root is one state, and every factual selected-action successor is another. For each state, the scorer receives only the causal prefix available before the current action and returns one value per materialized candidate row for one scalar requested horizon. Several states from one chain may occupy the batch/state axes and be evaluated in parallel; that colocation is a compute layout, not an information path from a later state into an earlier prediction. The current scorer contains no temporal interaction across those realized states.

Accordingly, *recursion* in this chapter means Bellman target recursion across factual successors. A longer-horizon target combines the current selected reward with a detached, frozen, or delayed shorter-horizon value at the next causal state. It is neither RNN-style hidden-state recurrence nor DETR-style iterative refinement of one prediction. The current Lightning transaction privately duplicates the actor batch so one scorer call evaluates two query domains: dense $h=1$ for every realized state and the factual residual horizon $h=b_t$ for the same states. Dense one-step loss uses every hard-valid labelled candidate; recursive $h>1$ loss uses only the factual selected transition where successor support exists. Off-diagonal queries $h<b_t$ are valid members of the public value family, but the present objective does not automatically enumerate every shorter horizon from each retained chain.

The chapter first fixes the actor-visible state and the coverage limitation of local EFM3D evidence. It then separates the implemented compact scorer from richer scene carriers, interaction ablations, and bounded #symb.rl.qh learning targets. Descriptive status blocks distinguish executable maturity from scientific evidence throughout.

#include "04-01-scene-representation-requirements.typ"

#include "04-02-descriptor-and-encoding-plan.typ"

#include "04-03-candidate-and-replay-contract.typ"

#include "04-04-architecture-contract.typ"

#include "04-05-finite-candidate-value-model.typ"
