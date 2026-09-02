#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": validation_todo
#import "../../../shared/tables.typ": publication-table

== Study Population and Evidence Gates

#validation_todo(
  [Preregister the eligible population, exclusions, primary estimands, aggregation unit, number of independent runs, uncertainty interval, minimum meaningful effect, and multiplicity policy before inspecting confirmatory results.],
  source: [experiment manifest and analysis specification],
  gate: [immutable analysis plan plus matched held-out policy table],
)

=== Candidate-Generation Realism Analysis Contract

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

The source population comprises ASE/ATEK snippet windows from scenes for which the configured @ground-truth:short mesh and object-box table resolve. A frozen manifest assigns entire scenes to train, validation, or test before model selection; no scene may cross these boundaries through another snippet. Each reported run records the manifest hash and the exact counts of scenes, snippets, admitted target tasks, rollout chains, transitions, and retained candidate rows. A capped train-only pilot is therefore a throughput and support probe, not a sample from which held-out policy performance can be estimated.

The present selected experiment defines oracle target tasks by seeded sampling from geometry-valid @ground-truth:short OBB rows. Its task-coverage report therefore describes the available GT pool, sampled tasks, classes, scenes, and later oracle-evaluation failures. It does not measure proposal matching, IoU ambiguity, projected visibility, or actor-observation support. A separate `v1_observed` selector now constructs descriptors from detected OBBs and actor-visible trajectory geometry without an oracle payload, but its corpus, matching failures, and support distribution are not frozen or evaluated. Consequently, @ground-truth:short target geometry may still define labels and bounded oracle references but cannot be presented as actor-visible input. The privileged-supervision boundary in @fig:qh-actor-oracle-contract applies equally to render-derived evidence: dense @ground-truth:short candidate depth may produce labels, returns, or explicitly named privileged ablations, but it is not a legal actor input. A separate teacher policy, distillation path, or current-belief renderer remains a hypothesis until implemented and evaluated, so none is promoted to a main-text process figure.

The first policy gate is an actor-visible myopic scorer over the same finite candidate table intended for #symb.rl.qh. The scorer must expose one value per candidate, respect the hard action mask, and be assessed by candidate ranking, calibration, and oracle-rescored selected actions. The existing scene-level VIN scorer is historical substrate; it is not a target-conditioned control until the observed target descriptor is wired into the model and evaluated on a frozen held-out split.

The second policy gate estimates whether bounded oracle lookahead has headroom over one-step oracle greedy:

$
  #eqs.entity.lookahead_headroom
$

Only if the preregistered analysis classifies this headroom as meaningful is #symb.rl.qh evaluated for closure of the separate actor-visible learned-myopic-to-oracle-lookahead endpoint gap:

$
  #eqs.entity.q_recovery
$

Success is measured by matched endpoint oracle evaluation, not predicted values or training loss. If lookahead has no meaningful headroom, the result is scoped to the frozen split, target protocol, candidate generator, horizon, branch factor, and validity regime. If headroom exists but the learned model does not close the prescribed actor-visible-myopic-to-oracle-lookahead gap, target observability, action support, replay coverage, reward construction, and model capacity remain separate candidate explanations.

#figure(
  publication-table(
    columns: (0.82fr, 1.18fr, 1.52fr),
    header: ([*Claim*], [*Primary evidence*], [*Decision rule*]),
    rows: (
      [Population],
      [scene-split manifest and coverage bundle],
      [Inference is restricted to the frozen held-out scene population.],
      [Task protocol],
      [GT pool, sampled tasks, classes, and oracle failures],
      [Current evidence is oracle-task coverage, not observed-target matching.],
      [Myopic control],
      [ranking, calibration, and oracle-rescored selections],
      [Actor-visible target conditioning must be implemented before comparison.],
      [Planning headroom],
      [#symb.entity.lookahead_headroom and learned-control gap-closure ratio #symb.entity.q_recovery],
      [#symb.rl.qh gap closure is evaluated only after a meaningful oracle-headroom gate.],
    ),
  ),
  caption: [Objective-to-evidence matrix.],
) <tab:thesis-objective-evidence>
