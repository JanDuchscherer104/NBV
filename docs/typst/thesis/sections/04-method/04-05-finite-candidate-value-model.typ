#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status

== Target-Conditioned Finite-Horizon Value

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@FittedQIteration-ernst2005 @FixedHorizonTD-deAsis2020 @DoubleDQN-vanHasselt2015 @UVFA-schaul2015],
  source: "aria_nbv/aria_nbv/vin/models/target_finite_horizon.py; aria_nbv/aria_nbv/lightning/qh_module.py; aria_nbv/aria_nbv/lightning/qh_q2_certification.py; aria_nbv/aria_nbv/oracle/pipelines/online_qh.py; aria_nbv/tests/lightning/test_qh_q2_certification.py",
  gate: [populate a frozen held-out exact-Q2 receipt; establish oracle headroom; evaluate endpoint recovery on untouched scenes],
)[The selected method is A1--H0--S0 with a scalar requested horizon, direct continuous Huber regression, fitted-Q recursion, and hard-masked online selection. The implementation path is tested, but learned exact-Q2 accuracy and policy evidence remain absent.]

=== Conditional scorer

The actor input contains root semidense and supported EFM3D summaries, target
geometry admitted by the declared source protocol, relative candidate geometry,
the factual selected-pose prefix, remaining budget, and materialization support.
Oracle gains, target crops, meshes, associations, and audit lineage are
excluded. The current `root_moments_v1` scene summary and H0 pose history make
this an executable `S0-pose` baseline, not a task-sufficient reconstruction
state.

Before the hard action mask is applied, the scorer emits

#eqs.rl.qh_scorer_interface

for every materialized row. `conditional_q` alone carries return units and
enters regression, Bellman backup, and online ranking. Feasibility logits are a
separate auxiliary prediction; multiplying them by value would mix meanings.
The training adapter owns hard-valid label and bootstrap admission, while
online inference owns the final masked selection.

The selected A1 interaction lets each candidate query shared scene, target,
history, budget, and horizon tokens. A0 supplies the matched independent-row
control. Both use the same geometric query and value decoder. Their comparison
therefore asks whether query-dependent state reading helps under a fixed state
and objective; it does not isolate attention independently of parameter count
or runtime.

=== Scalar requested horizon

Using the finite-horizon return and conditional value defined in
@sec:thesis-sequential-decision-foundations, the return for target $e$ over
exactly the requested residual horizon $h$ is

$
  #eqs.rl.finite_horizon_return
$

and the learned value is

$
  #eqs.rl.q_h
$

One model call follows the frozen interface

#eqs.model.qh_frozen_interface

The notation $Q_H$ names the bounded family rather than a collection of
separately configured models. Remaining budget $b_t$ describes the factual
state; $h$ selects one return from the triangular domain
${(b_t,h): 1 <= h <= b_t <= H_"max"}$. Omitting $h$ requests the full factual
residual budget. The mathematical boundary $Q_0=0$ closes recursion, whereas
zero in executable tensors denotes padding and is never a learned query.

Dense labels train $h=1$ for every hard-valid candidate. For $h>1$, only the
factual selected action has a successor observation, so recursive supervision
is necessarily narrower. The current recursive construction and exact-$Q_2$
surface populate the factual diagonal $h=b_t$, with exact $Q_2$ executable at
$(b_t,h)=(2,2)$ but its held-out receipt still pending. Dense $Q_1$ additionally
supports $(b_t,1)$ across realized budgets. Current bundles record trained
horizons rather than realized pairs, while deployed online inference requests
the diagonal and applies that horizon gate. Before any off-diagonal $h>1$
query is exposed, the bundle and runtime must add pair-bound training and
evaluation evidence and reject unsupported pairs. A wide syntactic interface
is not evidence of wide learned capability.

=== Direct continuous objective

The decoder maps each candidate representation directly to the continuous,
root-normalized finite-horizon return. This regression target preserves metric
order and additive return units. The implemented Huber penalty is quadratic for
small residuals and linear beyond its fixed threshold. Losses are first
averaged within realized state and then within horizon. Consequently, a state
with more valid candidates does not receive more weight merely because it
contributes more rows, and abundant one-step states do not silently dominate a
sparser recursive horizon. Reported calibration and support remain stratified
by horizon.

At $h=1$, evaluation can use dense candidate labels to report continuous error,
within-state pairwise ranking, and greedy regret. Factual $h>1$ transitions do
not supply counterfactual values for unselected rows, so longer-horizon ranking
and regret remain undefined until exact or independently oracle-rescored
candidate tables exist. Recording zero support is more faithful than inventing
a metric from the selected transition alone.

=== Fitted-Q recursion <ssec:thesis-horizon-recursive-offline-learning>

Batch fitted Q iteration turns the fixed replay collection into successive
supervised problems @FittedQIteration-ernst2005. The immediate reward is

// Evidence map:
// - @FittedQIteration-ernst2005 -> https://www.jmlr.org/papers/volume6/ernst05a/ernst05a.pdf:504-508 (successive supervised Q-function approximations and greedy recursive targets)

#eqs.rl.target_root_gain_reward

and for $h>1$ the selected method uses the lower-horizon target

#eqs.rl.qh_doubleq_target

where the continuation value is detached, frozen, or supplied by a delayed
copy. The structural rule is $Q_h arrow.l Q_(h-1)$: a horizon never bootstraps
from itself. The successor maximum intersects the factual horizon support with
the hard action set,

#eqs.rl.qh_supported_successor_set

and Double Q separates row selection from delayed evaluation
@DoubleDQN-vanHasselt2015. This estimator may limit max bias, but it cannot
repair unsupported actions, aliased state, or missing selected observations.

The recursion estimates greedy continuation over the generated, hard-valid
finite support under the named state and target-source protocols. It is not the
Monte Carlo return of the behavior policy that produced the retained chain,
unless that behavior policy selects the same continuation; nor is it an optimum
over ungenerated continuous camera poses. This distinction fixes the meaning
of a successful fit before any policy comparison is attempted.

=== Why exact horizon two is decisive

When the selected action has a successor table with dense one-step labels, its
finite-support two-step target is computable exactly:

#eqs.rl.qh_exact_q2_target

This makes horizon two the first non-myopic falsification test. A unit test
can inject exact $Q_1$ values and prove that the tensor path implements the
equation. A frozen population test instead measures learned recursion error,

#eqs.rl.qh_exact_q2_error

on held-out supported rows. The latter tests the learned $Q_1$ approximation,
state encoding, masks, successor linkage, and recursive target construction
together. It is therefore model evidence rather than another implementation
test.

The held-out evaluation begins with the complete eligible chain population
rather than only rows on which an exact target is available. Chains that
terminate or lose support before $h=2$ remain in the denominator with zero exact
rows. Scene- and target-stratified coverage, error, uncertainty, numeric
tolerance, candidate width, generator, recipe, and behavior policy are frozen
before inspection. Low error on a small supported subset cannot justify a
longer horizon when minimum support or coverage fails.

Exact $Q_2$ is necessary but not sufficient: policy claims additionally require
positive equal-budget oracle headroom and held-out endpoint recovery.

The resulting evidence boundary is explicit. The current implementation
supports the `S0-pose` scorer, direct objective, hard-masked recursion, and
exact-$Q_2$ evaluation path. The scientific target additionally requires an
evaluated actor-visible `v1_observed` corpus, a causal observation-updated
state, a frozen held-out exact-$Q_2$ receipt, positive oracle headroom, and
endpoint recovery. The `v1_observed` admission and writer--reader path is implemented, but
that intermediate has not passed these evidence gates. Until they pass, this
chapter establishes an executable method and its falsification tests, not a
successful non-myopic actor.
