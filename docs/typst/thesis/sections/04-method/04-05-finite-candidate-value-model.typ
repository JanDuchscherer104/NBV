#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status
#import "../../../shared/tables.typ": publication-table

== Target-Conditioned Finite-Horizon Value

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@FittedQIteration-ernst2005 @FixedHorizonTD-deAsis2020 @DoubleDQN-vanHasselt2015 @UVFA-schaul2015 @CORAL-cao2019 @ReinforcementLearning-sutton2018],
  source: "aria_nbv/aria_nbv/vin/models/target_finite_horizon.py; aria_nbv/aria_nbv/lightning/qh_module.py; aria_nbv/aria_nbv/lightning/qh_q2_certification.py; aria_nbv/aria_nbv/oracle/pipelines/online_qh.py; aria_nbv/tests/lightning/test_qh_q2_certification.py",
  gate: [populate a frozen held-out exact-Q2 receipt; establish oracle headroom; evaluate endpoint recovery on untouched scenes],
)[The selected executable baseline is A1--H0--#symb.rl.s_pose with a scalar requested horizon, direct continuous Huber regression, fitted-Q training, and runtime selection under the configured hard action-support mask. Current experiments use oracle-derived support. The implementation path is tested, but learned exact-Q2 accuracy and policy evidence remain absent.]

=== Conditional scorer

The actor input contains root semidense and supported EFM3D summaries, target
geometry admitted by the declared source protocol, relative candidate geometry,
the factual selected-pose prefix, remaining budget, and materialization support.
Oracle gains, target crops, meshes, associations, and audit lineage are
excluded. The current `root_moments_v1` scene summary and H0 pose history make
this the executable @pose-only-counterfactual-state:short, denoted
#symb.rl.s_pose, not a task-sufficient reconstruction
state.

Before the hard action mask is applied, the scorer emits

#eqs.rl.qh_scorer_interface

for every materialized row. `conditional_q` alone carries return units and
enters regression, Bellman backup, and online ranking. Feasibility logits are a
separate auxiliary prediction; multiplying them by value would mix meanings.
The training adapter owns hard-valid label and bootstrap admission, while
online inference owns the final masked selection.

The selected A1 interaction lets each #symb.oracle.candidate_qti query shared scene, target,
history, budget, and horizon tokens. A0 supplies the matched independent-row
control. Both use the same geometric query and value decoder. Their comparison
therefore asks whether query-dependent state reading helps under a fixed state
and objective; it does not isolate attention independently of parameter count
or runtime.

=== Ideal value and learned representation

The value estimand is meaningful only relative to one frozen decision protocol,

$
  #eqs.rl.decision_protocol
$

where $g$ fixes the candidate-generator family and resolved configuration;
$tau$ fixes target-source admission; $sigma$ fixes state construction;
$nu_"mask"$ fixes action-support provenance and semantics; $rho$ fixes reward,
execution, and terminal conventions; and #symb.rl.gamma and #symb.rl.H_max fix
discounting and the largest residual horizon. Altering one component changes the
decision problem or its support and is therefore a protocol-transfer study, not
an ordinary train--test comparison.

Let #symb.rl.history denote the actor-visible observation and action history
available before decision step $t$. For target $e$, the return over exactly the
requested residual horizon $h$ is

$
  #eqs.rl.finite_horizon_return
$

The corresponding ideal value is

$
  #eqs.rl.q_h
$

Here #symb.oracle.candidate_qti is the physical candidate pose being
conditioned on; $i$ is only its table-local handle in the protocol-defined
admissible set $cal(A)_t$. The policy $pi$ ranges over admitted continuation policies, and the
expectation includes the transition and observation randomness fixed by
#symb.rl.decision_protocol. This is a history-conditioned object: it does not
assume that the selected finite-dimensional model input is Markov-sufficient.

The executable scorer instead receives the representation

$
  #eqs.rl.qh_representation_map
$

where #symb.rl.representation_map denotes the state-construction protocol and
#symb.rl.representation is its output. Under the sufficient condition stated
below, the pointwise training target can be written as

$
  #eqs.rl.qh_learned_predictor
$

from the frozen replay distribution. The hat distinguishes this learned
predictor from the ideal value; the superscripts retain the representation and
decision-protocol identities that determine what was fitted. Exact Bellman
closure on the compressed representation is justified only under the empirical
task-sufficiency condition

$
  #eqs.rl.qh_sufficiency_factorization
$

Decision-context sufficiency means that histories mapped to the same
#symb.rl.representation induce the same joint conditional law of reward,
successor representation, residual budget, regenerated candidate table,
hard action-support mask, and termination for every physical candidate pose.
This condition guarantees the displayed factorization and Bellman closure;
successor-representation equality alone is insufficient because continuation
support can change across splits.
Fitted-Q training then yields a representation- and replay-conditioned
projection that may still be useful for ranking candidates, but it is not
silently reinterpreted as the Bellman-optimal value of a Markov state. This is
the admitted status of #symb.rl.s_pose. Causal observation-updated state
ablations test the sufficiency hypothesis rather than merely enlarging a token.

=== Scalar requested horizon

One model call follows the frozen interface

#eqs.model.qh_frozen_interface

The notation #symb.rl.qh names the bounded
predictor family rather than a collection of separately configured models. Remaining
budget #symb.rl.budget describes the factual state;
#symb.rl.requested_horizon selects one return from the triangular domain
${(b_t,h): 1 <= h <= b_t <= H_"max"}$. Omitting
#symb.rl.requested_horizon requests the full factual
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

=== Decoder and estimator design space

Direct regression is selected because the Bellman target, endpoint gain, and
reported calibration share continuous return units. That choice does not make
the other formulations conceptually irrelevant. Each changes a distinct part
of the inference problem and therefore remains visible with an explicit role:

#figure(
  publication-table(
    text-size: 7.8pt,
    columns: (0.9fr, 0.82fr, 1.35fr, 1.35fr),
    header: ([*Alternative*], [*Scientific role*], [*Quantity estimated*], [*Condition for a meaningful comparison*]),
    rows: (
      [Direct Huber regression], [selected], [continuous finite-horizon return in root-gain units], [frozen per-horizon support, calibration, ranking, and endpoint evaluation],
      [CORAL decoder], [implemented matched decoder control], [the same scalar fitted-Q target after ordinal discretization and fixed representative decoding], [training-only support provenance and saturation diagnostics; hard-invalid rows remain excluded],
      [Separate or fixed-horizon heads], [contingent parameter-sharing control], [the same horizon-indexed values without the shared scalar-horizon interface], [compare only after each horizon has sufficient matched support],
      [Double-Q backup], [implemented selected estimator], [greedy finite-support continuation with separated selection and delayed evaluation], [report support and max-bias diagnostics; it cannot repair state aliasing],
      [Behavior-return regression], [distinct-estimand control], [return under the chain-generating behavior policy], [must not be called greedy value unless behavior and target continuation coincide],
      [One-step base + residual], [contingent decomposition], [immediate gain plus learned continuation residual], [use additive units and no candidate-table mean centering],
      [Quantile value], [exploratory idea], [a return distribution rather than one scalar expectation], [justify with measured stochasticity or aliasing and freeze projection, decoding, and calibration],
    ),
  ),
  caption: [Value-model alternatives by scientific role and estimand. Executability, selection, and evidence are distinct; alternatives are retained without presenting them as co-equal validated methods.],
) <tab:thesis-value-design-space>

@coral-q-decoder:short is an executable decoder over the same continuous fitted targets, not a
different action-value definition. It preserves ordinal order but requires an
additional support artifact and representative-value rule to return to
continuous units @CORAL-cao2019. Behavior-return regression changes the
estimand more fundamentally: without off-policy correction it follows the
continuation policy that generated the retained chain rather than the greedy
continuation used by fitted Q
@ReinforcementLearning-sutton2018[Secs. 5.2 and 5.5, pp. 96–97 and 103–109].
The one-step residual and quantile formulations remain hypotheses because
neither the need for the decomposition nor a return distribution has yet been
demonstrated.

// Evidence map:
// - @CORAL-cao2019 -> https://arxiv.org/pdf/1901.07884#page=3-4 (Secs. 3.2.1-3.2.3: binary label extension, shared-weight ordinal logits, weighted cross-entropy, and rank consistency); aria_nbv/aria_nbv/vin/modules/qh_value_decoders.py (executable ARIA decoder semantics)
// - @ReinforcementLearning-sutton2018 -> docs/literature/pdf/RLbook2020.pdf#page=118-119 and #page=125-131 (behavior-policy Monte Carlo action values and off-policy distinction)

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
finite support under the named target-source, actor-state, generator,
action-mask, reward, discount, and horizon protocols. Unlike an immediate
per-row target, the $h>1$ continuation value changes when the successor-support
protocol changes because that protocol changes the bootstrap maximum. It is not the
Monte Carlo return of the behavior policy that produced the retained chain,
unless that behavior policy selects the same continuation; nor is it an optimum
over ungenerated continuous camera poses. This distinction fixes the meaning
of a successful fit before any policy comparison is attempted.

=== Exact horizon two as the first non-myopic falsification test

When the selected action has a successor table with dense one-step labels, its
finite-support two-step target is computable exactly:

#eqs.rl.qh_exact_q2_target

This makes horizon two the first model-level non-myopic falsification test. A unit test
can inject exact $Q_1$ values and prove that the tensor path implements the
equation. A frozen population test instead measures learned recursion error,

#eqs.rl.qh_exact_q2_error

on held-out supported rows. The latter tests the learned $Q_1$ approximation,
state encoding, masks, successor linkage, and recursive target construction
together. The target is exact for the frozen factual successor table and reward
contract; the learned #symb.rl.learned_q remains a representation-conditioned
predictor. The comparison is therefore model evidence rather than another
implementation test or a proof of Markov sufficiency.

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
supports the #symb.rl.s_pose scorer, direct objective, `oracle_action_mask_v1`
recursion, and
exact-$Q_2$ evaluation path. The scientific target additionally requires an
evaluated actor-visible `v1_observed` corpus, a causal observation-updated
state, actor-visible or calibrated action support, a frozen held-out exact-$Q_2$ receipt, positive oracle headroom, and
endpoint recovery. The `v1_observed` admission, actor-only construction, and writer--reader path are implemented, but
that route has no frozen corpus or evaluation and has not passed these evidence gates. Until they pass, this
chapter establishes an executable method and its falsification tests, not a
successful non-myopic actor. The alternatives in
@tab:thesis-value-design-space remain scientifically available, but promotion
requires a diagnosed failure and a one-factor comparison rather than a larger
uninterpretable model bundle.
