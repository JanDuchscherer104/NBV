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
$1 <= h <= b_t$. Dense one-step labels support $(b_t,1)$ across realized
budgets, whereas recursive supervision for $h>1$ follows the factual diagonal
$h=b_t$; exact $Q_2$ is executable only at $(b_t,h)=(2,2)$ and its held-out
receipt remains pending. Current bundles record trained horizons rather than
budget--horizon pairs, and deployed inference requests $h=b_t$ behind a
trained-horizon gate. A pair-bound gate is therefore required before any
off-diagonal $h>1$ query can be promoted beyond the syntactic scorer
interface. Exact horizon two remains the first epistemic test of learned
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
