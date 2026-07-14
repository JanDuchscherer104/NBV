#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

== Policy Comparison and Statistical Protocol

The experimental unit is the scene. Every policy comparison is paired on the same scene, target task, root state, candidate seed, candidate-generation distribution, hard validity constraints, and acquisition horizon. Planner depth may differ because it defines the decision rule, but every policy receives the same number of acquired views. Repeated targets, snippets, and seeds are first aggregated within scene so that dense scenes do not dominate the primary analysis.

The primary estimand is the paired per-scene difference in fixed-budget endpoint target-quality gain. Uncertainty is quantified with 10,000 paired scene-level bootstrap replicates and a 95% percentile interval. The primary report includes the mean paired difference and interval. Secondary summaries are the median paired difference, per-scene win rate, cumulative root-normalized gain, invalid-action rate, runtime, path length, and target/scene coverage. These summaries diagnose mechanism and feasibility; they do not replace the endpoint estimand.

A policy that cannot select a valid action remains in the paired analysis as a failure with no further improvement for the remaining budget. It is not silently removed. Target-ineligible scenes and oracle-invalid samples are reported separately because they delimit the population for which the estimand is defined. Confirmatory comparisons are the preregistered RQ comparisons: metric repeatability, one-step learned versus matched baselines, oracle lookahead versus one-step oracle greedy, and, conditional on meaningful headroom, finite-horizon learned versus learned one-step control. Architecture and representation ablations are exploratory and support no generalized superiority claim.

#figure(
  table(
    columns: (0.72fr, 0.72fr, 0.58fr, 1.35fr),
    toprule(),
    table.header([*Policy*], [*Decision information*], [*Acquisition budget*], [*Scientific role*]),
    midrule(),
    [$pi_"rand"$], [actor-visible], [$H$], [valid-action lower reference],
    [$pi_"learned-1"$], [actor-visible], [$H$], [learned myopic control],
    [$pi_"oracle-1"$], [oracle immediate reward], [$H$], [one-step oracle-greedy comparator],
    [$pi_"oracle-look"$], [bounded oracle lookahead], [$H$], [conditional finite-support upper reference],
    [$pi_Q$], [actor-visible], [$H$], [learned finite-horizon recovery],
    bottomrule(),
  ),
  caption: [Matched policy comparison. All rows acquire the same number of views; oracle access and planner depth define the decision rule rather than the acquisition budget.],
) <tab:thesis-policy-comparison>

Before recovered-headroom fractions are reported, repeated oracle evaluation under controlled resampling estimates the metric noise floor. The minimum meaningful headroom threshold is frozen from that repeatability analysis rather than chosen after observing policy performance. Below the threshold, absolute paired endpoint differences may be reported, but ratios with an unstable denominator are not interpreted.

== Outcome Logic

The normal case is positive, stable oracle-lookahead headroom together with learned recovery under matched oracle re-evaluation. It supports only the scoped claim that learnable non-myopic structure exists for the evaluated scenes, targets, candidate generator, validity regime, and horizon. The boundary case is negligible headroom relative to the metric noise floor. It supports a setup-specific negative result and does not imply that target-aware view planning is universally myopic. The failure case is an invalid or unstable oracle metric. It restricts the thesis to oracle and metric validation and prevents downstream planning claims, regardless of learned-policy scores.

#validation_todo(
  [Freeze the scene aggregation function, preregistered comparison list, oracle repeatability design, and minimum meaningful headroom threshold before final aggregation.],
  source: [implementation-independent analysis protocol],
  gate: [analysis preregistration],
)
