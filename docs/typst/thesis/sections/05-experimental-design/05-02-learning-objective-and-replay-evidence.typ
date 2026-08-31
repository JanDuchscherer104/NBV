#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status
#import "../../../shared/tables.typ": publication-table

== Replay Admission for the Learning Gates

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@FittedQIteration-ernst2005 @FixedHorizonTD-deAsis2020 @DoubleDQN-vanHasselt2015],
  source: "aria_nbv/aria_nbv/rollouts/qh_reader.py; aria_nbv/aria_nbv/lightning/qh_module.py; aria_nbv/aria_nbv/lightning/qh_q2_certification.py",
  gate: [held-out dense-Q1 checkpoint; qualifying exact-Q2 receipt; matched endpoint oracle evaluation],
)[Dense one-step supervision, selected-transition fitted-Q recursion, scalar horizon support, and exact-Q2 certification are executable. No qualifying held-out learning or policy evidence is currently available.]

Replay eligibility is defined by factual evidence, not padded tensor shape. The
hard action mask identifies selectable rows. The stricter one-step training mask
also requires a finite target-root-gain label. A recursive row additionally
requires the factual selected action, its reward and terminal role, and—when
nonterminal—a reproducible successor state with lower-horizon support. Modality
presence, source role, target validity, action validity, Q-label support,
transition support, and horizon support remain separate masks.

#figure(
  publication-table(
    columns: (0.7fr, 1.1fr, 1.52fr),
    header: ([*Learning gate*], [*Estimand*], [*Minimum factual evidence*]),
    rows: (
      [actor-visible $Q_1$], [immediate root-normalized target gain], [hard-valid candidate, finite one-step label, actor-visible target protocol, and held-out scene role],
      [exact $Q_2$], [first recursive finite-support target], [selected reward plus terminal outcome or a successor table with complete one-step labels over every hard-valid row],
      [recursive $Q_h$], [greedy value within represented support], [factual selected transition, terminal and discount; nonterminal rows also require successor state, hard mask, and admitted $Q_(h-1)$ support],
    ),
  ),
  caption: [Learning-target admission. Dense one-step labels, exact two-step targets, and general recursive targets are different evidence populations.],
) <tab:thesis-support-coverage>

The exact-$Q_2$ completeness rule is strict. One finite successor label is
insufficient because an unlabelled hard-valid action could hold the maximum.
The certification denominator therefore begins with every eligible held-out
chain, retains chains that terminate or lose support, and reports how many
reach a complete successor table and a factual exact row. Missing support fails
the gate; it is not zero recursion error.

One retained rollout contributes several causal decision states. State $t$
receives only the prefix observed before $a_t$, even if later states share the
same batch. Dense $Q_1$ loss uses all admitted candidate rows; $h>1$ loss uses
only factual selected transitions. Candidate losses are averaged within state,
then states within horizon, then non-empty horizon means uniformly. This keeps
large action tables and abundant one-step rows from hiding recursive failure.

The learner implements fitted-Q recursion from $Q_h$ to a detached or delayed
$Q_(h-1)$ target and uses the hard-valid successor set for every maximum
@FittedQIteration-ernst2005 @FixedHorizonTD-deAsis2020. Double-Q selection and
evaluation address max bias but do not create transition support
@DoubleDQN-vanHasselt2015. The experiment therefore reports horizon-specific
population, calibration, terminal fraction, bootstrap support, and exact-$Q_2$
coverage before any endpoint comparison.

The promotion boundary is deliberately narrow. Executable training, a valid
checkpoint bundle, or low error on a few rows cannot establish finite-horizon
value. Actor-visible $Q_1$ must first pass on held-out scenes; exact $Q_2$ must
then pass its frozen independent-unit, coverage, and tolerance rules; endpoint
recovery is interpreted only if oracle headroom is already meaningful.

The report contract preserves those populations explicitly. Pairwise accuracy
is a unit-interval fraction with a scene-clustered 95% interval; one-step
calibration MAE is a nonnegative root-normalized-return error. The frozen $Q_1$
rule requires the point ranking to reach a declared threshold above chance, the
interval lower bound to exceed chance $0.5$, and calibration MAE not to exceed
its declared maximum. This supports point-estimated threshold attainment and
evidence above chance, not the stronger claim that the population ranking
exceeds the declared threshold.

The exact-$Q_2$ receipt keeps aggregate MAE diagnostic. Promotion instead
mirrors the executable `all_units_v1` contract: selected-chain coverage reaches
its frozen minimum, every selected support stratum contains an exact factual
row, the selected independent-unit count and minimum rows per unit meet their
floors, and the maximum rowwise excess over the frozen absolute-plus-relative
tolerance is nonpositive. Each metric, threshold, count, and boolean decision
shares its declared positive population denominator and one immutable sidecar
source; a malformed value, aggregation, unit, count, provenance, rule identity,
or contradictory boolean leaves the gate unresolved rather than producing a
measured non-pass. Actor-$Q_1$, exact-$Q_2$, and learned-policy endpoint evidence
must name one content-addressed inference bundle before their claims compose;
weight-free oracle headroom remains independent.

For each exact row, the tolerance contract is

$
  #eqs.rl.qh_exact_q2_error
$

and the reported tolerance excess subtracts the right-hand allowance from the
left-hand absolute error. Thus a maximum excess at or below zero proves that
every admitted exact row satisfies the frozen absolute-plus-relative bound; it
cannot be replaced by a pooled MAE.
