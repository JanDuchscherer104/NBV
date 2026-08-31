#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb

= Method <sec:thesis-method>

Chapter 3 fixed the experimental world: a target-specific task, a finite and
hard-masked action set, a causal replay transition, and a root-normalized
reconstruction-gain outcome. This chapter fixes the learner that operates
inside that world. It distinguishes two levels throughout. The *current
realization* is the executable baseline used to validate interfaces and expose
representation limits. The *scientific target* states the actor-visible
information and evidence required to answer the research questions. It is a
promotion contract, not a claim about code or results already obtained.

Both levels share a scalar-horizon, target-conditioned candidate-value
interface. The scorer reads admitted scene and target evidence, relative
candidate geometry, causal history, and remaining budget; it predicts a
conditional value for every materialized candidate before the authoritative
hard mask is applied. What differs is whether the admitted actor state retains
the target-specific information on which future return can depend.

The selected executable configuration uses the `S0-pose` state, H0 mean-pooled pose
history, A1 candidate-to-state cross-attention, and direct continuous Huber
regression. A0, an independent-row MLP with the same inputs and decoder, is the
matched interaction control. Both execute the same value task; their held-out
comparison remains pending. Richer selected-depth state, ordered history,
ordinal decoding, and candidate-set interaction remain alternatives because
none has yet passed a frozen comparative evaluation.

The value query distinguishes factual remaining budget $b_t$ from requested
residual horizon $h$. Current supervision supports dense one-step queries and
recursive queries on the factual budget diagonal; wider executable inputs do
not establish wider learned support. Exact horizon two is therefore the first
epistemic test of learned lookahead: it can compare learned recursion with an
exact finite-support endpoint without trusting a learned longer-horizon
continuation. Passing that test is necessary but not sufficient for a policy
claim, which additionally requires positive oracle headroom and held-out
endpoint recovery.

The chapter proceeds from the selected state and encoding, through finite
action and replay semantics, to architectural acceptance properties and the
finite-horizon learning objective. This order keeps failures interpretable:
lost state information, malformed action or replay semantics, and value-learning
error remain distinct explanations rather than an undifferentiated model defect.

#include "04-01-scene-representation-requirements.typ"

#include "04-02-descriptor-and-encoding-plan.typ"

#include "04-03-candidate-and-replay-contract.typ"

#include "04-04-architecture-contract.typ"

#include "04-05-finite-candidate-value-model.typ"
