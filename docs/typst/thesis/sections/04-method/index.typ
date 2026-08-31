#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/tables.typ": publication-table

= Method <sec:thesis-method>

Chapter 3 fixed the experimental world: a target-specific task, a
@finite-candidate-action-set:short, a causal @counterfactual-transition:short,
and a root-normalized reconstruction-gain outcome. This chapter fixes the
learner that operates inside that world. Three classifications are kept
independent throughout:

- *scientific role* asks whether an element is the selected realization, a
  matched control, a requirement of the scientific target, a contingent
  alternative, or an exploratory idea;
- *implementation maturity* asks whether its data path and computation are
  implemented, partial, planned, or only conceptual; and
- *evidence maturity* asks whether the corresponding scientific claim is
  validated, pending, conflicted, or inapplicable.

These axes prevent two recurrent category errors. Implemented does not mean
selected or empirically supported, and scientific target does not mean one
particular architecture. The target specifies the actor-visible information
and evidence needed to answer the research questions; candidate realizations
may then compete to satisfy it.

#figure(
  publication-table(
    text-size: 8.1pt,
    columns: (0.83fr, 1.05fr, 1.45fr, 1.05fr),
    header: ([*Scientific role*], [*Example*], [*Meaning in this chapter*], [*Present maturity*]),
    rows: (
      [Selected realization], [#symb.rl.s_pose, H0, A1, direct regression], [Executable reference method against which one-factor changes are interpreted.], [implemented; scientific evidence pending],
      [Matched controls], [A0; #symb.rl.s_surface; H1; CORAL], [Executable contrasts that preserve a named comparison but are not part of the selected method.], [implemented; comparisons pending],
      [Scientific target], [actor-visible target source and causal observation-updated state], [Information and evidence contract required for the core claim; architecture-neutral.], [partly implemented; not validated],
      [Contingent alternatives], [#symb.rl.s_ray; candidate-set interaction; separate horizon heads], [Promoted only after a measured failure identifies the missing distinction.], [planned or executable; unselected],
      [Exploratory ideas], [3DGS memory; SceneScript context; quantile value], [Conceptually relevant extensions whose estimand, comparison, or implementation is not yet frozen.], [ideas only],
    ),
  ),
  caption: [Interpretive status for Method. Scientific role, implementation maturity, and evidence maturity are orthogonal; no row is an empirical ranking.],
) <tab:method-status-semantics>

All admitted state realizations share a scalar-horizon, target-conditioned candidate-value
interface. The scorer reads admitted scene and target evidence, relative
candidate geometry, causal history, and remaining budget; it predicts a
conditional value for every materialized candidate before the authoritative
hard mask is applied. What differs is whether the admitted actor state retains
the target-specific information on which future return can depend.

The selected executable configuration uses the
@pose-only-counterfactual-state:short (#symb.rl.s_pose), H0 mean-pooled
#symb.rl.selected_pose_prefix, A1 candidate-to-state cross-attention, and direct
continuous Huber regression. A0 is the matched interaction control. The
privileged selected-surface state #symb.rl.s_surface, ordered H1 history, and
CORAL decoder are also executable controls, but none has a frozen comparative
result. The planned ray-aware state #symb.rl.s_ray is a candidate realization
of the actor-state target, not a claim that rays are already known to be the
best carrier. Candidate-set interaction and distributional value prediction
remain contingent hypotheses rather than silently discarded possibilities.

The value query distinguishes factual remaining budget $b_t$ from requested
residual horizon $h$. Current supervision supports dense one-step queries and
recursive queries on the factual budget diagonal; wider executable inputs do
not establish wider learned support. Exact horizon two is therefore the first
epistemic test of learned lookahead: it can compare learned recursion with an
exact finite-support endpoint without trusting a learned longer-horizon
continuation. Passing that test is necessary but not sufficient for a policy
claim, which additionally requires positive oracle headroom and held-out
endpoint recovery.

The chapter proceeds from the state design space and selected encoding, through
finite action and replay semantics, to interaction alternatives, acceptance
properties, and the finite-horizon objective. This order keeps failures
interpretable: lost state information, malformed action or replay semantics,
insufficient relational structure, and value-learning error remain distinct
explanations rather than an undifferentiated model defect.

#include "04-01-scene-representation-requirements.typ"

#include "04-02-descriptor-and-encoding-plan.typ"

#include "04-03-candidate-and-replay-contract.typ"

#include "04-04-architecture-contract.typ"

#include "04-05-finite-candidate-value-model.typ"
