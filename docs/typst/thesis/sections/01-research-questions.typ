== Research Questions <sec:thesis-research-questions>

#import "../../shared/equations.typ": eqs
#import "../../shared/tables.typ": index-cell, publication-table

=== Research aim and evaluation logic <ssec:rq-objectives>

The study evaluates a sequence of linked questions. RQ1 defines the endpoint
outcome. RQ2 then asks whether bounded oracle lookahead improves that outcome
relative to one-step oracle-greedy selection and, conditionally, how much of
the separate actor-visible myopic-to-oracle-lookahead gap an offline model
closes. RQ3 defines the admissible information, and RQ4 establishes the target,
action, and replay support over which both comparisons are interpretable. RQ5
and RQ6 extend the study only if the offline finite-candidate evidence warrants
online or continuous-control claims.

=== RQ1 — Target-specific objective and endpoint outcome <ssec:rq1>

*Can target-conditioned finite-candidate NBV be evaluated through a stable,
target-specific reconstruction objective under a fixed acquisition budget?*

For a target $e$, the oracle measures reconstruction error on a frozen target
crop. The primary estimand is the quality change from the root state to the
endpoint after $H$ acquisitions:

#eqs.entity.endpoint_gain

State-relative RRI is a one-step diagnostic, root-normalized gain supplies the
training reward, and endpoint gain remains the policy outcome. A positive answer
requires a frozen, repeatable metric and equal acquisition horizons; runtime,
invalid actions, and oracle calls are reported separately.

=== RQ2 — Bounded lookahead and learned gap closure <ssec:rq2>

*Does bounded oracle lookahead improve fixed-budget endpoint target gain over
one-step oracle-greedy selection and, if so, how much of the actor-visible
myopic-to-oracle-lookahead endpoint gap does an offline finite-horizon value
model close?*

The paired endpoint difference under the same scene, target, candidates,
validity rules, horizon, and budget defines oracle-lookahead headroom:

#eqs.entity.lookahead_headroom

The learned comparison proceeds only if this headroom passes a predeclared
meaningful-effect and uncertainty rule. Its ratio uses a different baseline:

#eqs.entity.q_recovery

Here the numerator is the gain of the finite-horizon learned policy over the
actor-visible learned-myopic control, and the denominator is the full gap from
that control to oracle lookahead. The ratio is therefore conditional learned
gap closure, not a fraction of the oracle-lookahead headroom above
oracle-greedy. Because the headroom rule and required gap-closure fraction are
not yet frozen, RQ2 remains prospective. If headroom is absent, the evaluated
support does not expose a non-myopic advantage; this does not establish its
universal absence.

=== Conditions for interpretation

==== RQ3 — Actor-visible target and information state <ssec:rq3>

*Which end-to-end target, action-support, and history protocol supports
one-step and finite-horizon candidate scoring without privileged target
geometry, oracle labels, or unselected candidate renders at decision time?*

Ground-truth target tasks remain restricted to task construction, supervision,
and evaluation. The actor-facing protocol must account for how the target
instruction, candidate support, hard validity mask, selected state update, and
scorer inputs are produced. The scorer receives only the declared target
descriptor, causal egocentric evidence, remaining budget, and requested horizon;
evaluation separately audits matching failures, ranking and calibration, and
actor/oracle leakage.

==== RQ4 — Candidate, replay, and population support <ssec:rq4>

*Do the candidate generator, validity rules, rollout recipes, and replay
population provide adequate and diverse support for the RQ1--RQ3 estimands?*

The candidate table combines exploration and target-bearing views, records
generator provenance, and excludes geometric infeasibility through a hard mask.
RQ4 measures candidate-family survival, invalidity, scene and target coverage,
replay and horizon support, and resource cost. Scene-disjoint splits and
scene-level aggregation prevent dense sampling from masquerading as population
coverage.

=== Scope extensions

==== RQ5 — Online discrete bridge <ssec:rq5>

*If offline headroom, replay support, and actor-visible scoring are established,
does online interaction over the unchanged discrete candidate set and validity
rules improve endpoint target gain or calibration over the offline policy?*

RQ5 keeps the target, information, candidate, validity, and endpoint assumptions
of RQ1--RQ4 unchanged. It is not required for the offline finite-candidate
evaluation.

==== RQ6 — Continuous or simulator-backed control <ssec:rq6>

*If the finite-candidate evidence is stable, does a continuous or hierarchical
target-then-pose policy provide measurable headroom over the best discrete
policy under the same target-specific objective and a comparable acquisition or
motion budget?*

RQ6 changes the action space and feasibility assumptions and therefore requires
separate evidence for support, safety, simulator realism, and comparable cost.
It remains deferred; the current implementation implies no continuous,
simulator, or real-device result.

=== Shared evidence constraints <ssec:protocol>

Action validity, actor support, target validity, oracle-label validity, and
training eligibility remain distinct; missing evidence is not encoded as low
utility. Confirmatory comparisons are paired under the same scene, target,
candidates, validity regime, and budget. The scene is the experimental unit,
and the analysis plan freezes exclusions, aggregation, uncertainty, and decision
rules before policy outcomes are inspected.

=== Research-to-evidence map <ssec:matrix>

#figure(
  publication-table(
    columns: (0.42fr, 1.08fr, 1.32fr, 1.18fr),
    header: ([*RQ*], [*Question role*], [*Primary evidence*], [*Interpretation gate*]),
    rows: (
      index-cell([RQ1]), [outcome measurement], [target reconstruction endpoint gain], [frozen repeatable metric; fixed horizon and budget],
      index-cell([RQ2]), [lookahead and learned gap closure], [paired greedy, lookahead, myopic-control, and learned-policy outcomes], [meaningful oracle headroom before learned gap closure],
      index-cell([RQ3]), [information boundary], [matching, ranking, calibration, and leakage audits], [end-to-end actor-visible protocol],
      index-cell([RQ4]), [population and support], [candidate, replay, validity, and coverage diagnostics], [scene-disjoint aggregation],
      index-cell([RQ5]), [conditional extension], [matched online discrete-policy evaluation], [offline gates satisfied first],
      index-cell([RQ6]), [deferred extension], [continuous or simulator-backed evaluation], [separate action space and cost comparison],
    ),
  ),
  caption: [Research-question-to-evidence map.],
) <tab:research-evidence-map>
