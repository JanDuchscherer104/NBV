== Research Questions <sec:thesis-research-questions>

#import "../../shared/equations.typ": eqs
#import "../../shared/tables.typ": index-cell, publication-table

=== Research aim and evaluation logic <ssec:rq-objectives>

The research questions follow the hierarchy of the thesis argument. RQ1 fixes
what is measured. RQ2 tests whether a non-myopic planning opportunity exists and
whether a learned model can recover it. RQ3 and RQ4 test whether the
actor-visible information and generated data support that comparison. RQ5 and
RQ6 are conditional extensions beyond the core offline finite-candidate claim.

=== RQ1 — Target-specific objective and endpoint contract <ssec:rq1>

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

=== RQ2 — Bounded lookahead and learned recovery <ssec:rq2>

*Does bounded oracle lookahead improve fixed-budget target reconstruction over
one-step oracle-greedy selection, and, if so, can an offline finite-horizon value
model recover a prespecified fraction of that headroom?*

The paired endpoint difference under the same scene, target, candidates,
validity rules, horizon, and budget defines oracle-lookahead headroom:

#eqs.entity.lookahead_headroom

The learned comparison proceeds only if headroom passes a predeclared
meaningful-effect and uncertainty rule. Because that rule and the required
recovery fraction are not yet frozen, RQ2 remains prospective. Absent headroom
is a negative result for the evaluated support, not a universal claim about
target-aware planning.

=== RQ3 — Actor-visible target and information state <ssec:rq3>

*Which actor-visible target and history representation supports one-step and
finite-horizon candidate scoring without privileged target geometry, oracle
labels, or unselected candidate renders at decision time?*

Ground-truth target tasks remain restricted to supervision and evaluation. The
actor-facing `V1` protocol admits an observed proposal only when exactly one
same-class ground-truth box has oriented 3D IoU strictly greater than $0.20$.
The scorer then receives the proposal-derived target descriptor, causal egocentric
evidence, remaining budget, and requested horizon, but no privileged geometry,
candidate renders, or oracle values. Evaluation covers held-out ranking and
calibration, matching failures, and actor/oracle leakage.

=== RQ4 — Candidate, replay, and population support <ssec:rq4>

*Do the candidate generator, validity rules, rollout recipes, and replay
population provide adequate and diverse support for the RQ1--RQ3 estimands?*

The candidate table combines exploration and target-bearing views, records
generator provenance, and excludes geometric infeasibility through a hard mask.
RQ4 measures candidate-family survival, invalidity, scene and target coverage,
replay and horizon support, and resource cost. Scene-disjoint splits and
scene-level aggregation prevent dense sampling from masquerading as population
coverage.

=== RQ5 — Conditional online discrete bridge <ssec:rq5>

*If offline headroom, replay support, and actor-visible scoring are established,
does online interaction over the unchanged discrete candidate contract improve
endpoint target gain or calibration over the offline policy?*

RQ5 retains the target, information, candidate, validity, and endpoint contracts
of RQ1--RQ4. It is not required for the core offline claim.

=== RQ6 — Deferred continuous or simulator-backed control <ssec:rq6>

*If the finite-candidate evidence is stable, does a continuous or hierarchical
target-then-pose policy provide measurable headroom over the best discrete
policy under the same target-specific objective and a comparable acquisition or
motion budget?*

RQ6 changes the action and feasibility contracts and therefore requires separate
support, safety, simulator-realism, and comparable-cost evidence. It remains
deferred; the current implementation implies no continuous, simulator, or
real-device result.

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
      index-cell([RQ1]), [objective], [target reconstruction endpoint gain], [frozen repeatable metric; fixed horizon and budget],
      index-cell([RQ2]), [policy comparison], [paired greedy, lookahead, and learned-policy outcomes], [meaningful headroom before recovery],
      index-cell([RQ3]), [actor support], [ranking, calibration, matching failures, and leakage audits], [actor-visible inputs only],
      index-cell([RQ4]), [population support], [candidate, replay, validity, and coverage diagnostics], [scene-disjoint aggregation],
      index-cell([RQ5]), [conditional extension], [matched online discrete-policy evaluation], [offline gates satisfied first],
      index-cell([RQ6]), [deferred extension], [continuous or simulator-backed evaluation], [separate action and cost contract],
    ),
  ),
  caption: [Research-question-to-evidence map.],
) <tab:research-evidence-map>
