#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": validation_todo

== Population, Estimands, and Gate Order

#validation_todo(
  [Preregister the eligible population, exclusions, scene aggregation, independent-run structure, uncertainty interval, meaningful headroom, learned-control gap-closure fraction, and comparison family before inspecting confirmatory outcomes.],
  source: [experiment manifest and analysis specification],
  gate: [immutable analysis plan plus matched held-out policy table],
)

=== Candidate-Support Estimands and Aggregation

RQ4 treats the scene as the independent unit. Candidate-support quality-control
observations are computed per state, averaged across states within scene, and
finally macro-averaged across the scene cohort; no candidate row is treated as
an independent scene replicate. These within-profile diagnostics remain
descriptive. Any comparative claim instead uses a paired per-scene difference
over eligible scene/target/root tasks observed under both profiles, equal
candidate budgets, and the frozen candidate-generation manifest. Its report
identity is `paired_scene_mean_difference`, with the paired scene count as its
denominator and an interval computed over the paired scene differences.

Missing or failed states are retained in the audit tables. Support counts and
fractions use the preregistered failure values stated in
@tab:candidate-support-metric-contract; an undefined target-relative direction
prevents that paired scene from entering a geometric contrast rather than
creating an angle by imputation. The excluded-scene count and reason remain
reported. Thus the descriptive state--scene macro summaries and the paired
comparative estimand have distinct populations and cannot be substituted for
one another.

Minimum operational support is reported as a worst-case diagnostic; the fifth
percentile of per-state valid support is the more stable lower-tail estimand,
accompanied by actor-valid fraction, configured-family zero rate,
target-side balance, and circular target-relative orbit span. Failed roots and
zero-valid configured family/state pairs remain part of the denominator. The
projection fraction, oracle opportunity, and jitter compliance are secondary
diagnostics: projection is calibrated framing rather than visibility, oracle
opportunity is finite-support headroom rather than policy performance, and
jitter compliance must preserve the nonzero production seminar-jitter invariant.

The source population comprises ASE/ATEK snippet windows whose configured
@ground-truth:short mesh and object-box table resolve. A frozen manifest assigns
entire scenes to train, validation, or test before model selection; snippets from
one scene cannot cross those boundaries. Every report records the manifest hash,
scenes, snippets, admitted target tasks, rollout chains, realized transitions,
candidate rows, exclusions, and failure strata. A capped training pilot may test
throughput or support, but it cannot estimate held-out policy performance.

The current task generator samples geometry-valid ground-truth boxes. It can
therefore establish oracle-task coverage, not actor-visible target discovery.
Ground-truth target geometry may define task construction, labels, and bounded
oracle references, but an actor-facing claim additionally requires an
observation-derived descriptor and an audit of its matching and failure
population. The same boundary excludes unselected candidate renders and
oracle-derived labels from decision-time input.

The evidence graph in @fig:qh-learning-evidence-loop answers the research
questions through seven stages. After population and action support are
established, actor-protocol validity and oracle headroom form independently
reportable branches; they meet again only when endpoint recovery is interpreted:

1. *Measurement validity (RQ1):* freeze crop, render, fusion, and point--mesh
   metric identity; show repeatability within a declared tolerance.
2. *Population and action support (part of RQ4):* establish scene-disjoint
   target-task coverage, candidate-family survival, hard validity, and acquisition
   feasibility with exact denominators.
3. *Actor-visible protocol (RQ3):* audit target matching, the complete
   actor-input identity, and actor--oracle leakage without using policy headroom.
4. *Oracle headroom (first half of RQ2):* compare bounded lookahead with
   one-step oracle greedy under the same acquisition budget,

   $
     #eqs.entity.lookahead_headroom
   $

5. *Actor-visible $Q_1$ (RQ3 and RQ4):* under the admitted protocol, evaluate
   target-conditioned one-step ranking, scene-clustered uncertainty,
   calibration, and dense-label replay coverage.
6. *Exact $Q_2$ (RQ2 and RQ4):* measure held-out two-step error, factual-successor
   coverage, and horizon support against the finite-support target.
7. *Endpoint gap closure (second half of RQ2):* only after meaningful headroom
   and admitted learned-value prerequisites, estimate the prespecified
   learned-myopic-to-oracle-lookahead gap-closure fraction

   $
     #eqs.entity.q_recovery
   $

   from matched endpoint oracle evaluation. Its denominator is distinct from
   oracle-lookahead headroom above oracle greedy.

RQ5 and RQ6 are evaluated only if the offline finite-candidate evidence justifies
extending the action or interaction setting. This dependency graph prevents an
attractive downstream policy estimate from compensating for an unstable metric,
an unsupported action set, privileged actor input, or failed recursion.
