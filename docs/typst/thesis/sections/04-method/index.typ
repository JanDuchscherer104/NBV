#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb

= Method <sec:thesis-method>

Chapter 3 fixed the experimental world: a target-specific task, a finite and
hard-masked action set, a causal replay transition, and a root-normalized
reconstruction-gain outcome. This chapter fixes the learner that operates
inside that world. The selected method is a scalar-horizon, target-conditioned
candidate-value model. It reads root evidence, relative candidate and target
geometry, the factual selected-pose prefix, and remaining budget; it predicts a
conditional value for every materialized candidate before the authoritative
hard mask is applied.

The selected executable configuration uses the `S0-pose` state, H0 mean-pooled pose
history, A1 candidate-to-state cross-attention, and direct continuous Huber
regression. A0, an independent-row MLP with the same inputs and decoder, is the
matched interaction control. Both execute the same value task; their held-out
comparison remains pending. Richer selected-depth state, ordered history,
ordinal decoding, and candidate-set interaction remain alternatives because
none has yet passed a frozen comparative evaluation.

The value query distinguishes factual remaining budget $b_t$ from requested
residual horizon $h$. The executable scorer admits the joint triangular domain
$1 <= h <= b_t$, but the present recursive and exact-$Q_2$ evidence occupies
the factual diagonal $h=b_t$; it does not establish off-diagonal training
support. Dense one-step labels anchor $Q_1$; factual selected
transitions provide the only admissible recursive path to $Q_h$ for $h>1$.
Exact horizon two is consequently the first epistemic test of learned
lookahead: it checks whether recursion recovers a target that can be computed
without trusting a learned longer-horizon continuation. Passing that test is
necessary but not sufficient for a policy claim, which additionally requires
positive oracle headroom and held-out endpoint recovery.

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
