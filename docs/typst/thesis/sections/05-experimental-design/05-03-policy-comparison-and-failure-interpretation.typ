#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

== Policy Comparison

All selected actions are oracle-evaluated under the same acquisition and candidate budgets. Equal budget means equal selected-view horizon $H$, candidate count $N_q$, candidate-generation distribution, and validity constraints; path length, runtime, and oracle evaluation count are reported separately. Coverage is reported against the planned full scale bar of 100 @ground-truth:short mesh @aria-synthetic-environments:short scenes and 4,608 snippet windows from the current thesis contract, or against an explicit scene-level held-out subset if scale is blocked @ProjectAria-ASE-2025. Final splits are scene-level; sample-level splitting across snippets from the same scene is not valid for final claims.

#validation_todo(
  [Replace planned scale bars with generated manifest statistics for the current one-step store and rollout store; historical seminar subset counts are not current thesis evidence unless regenerated.],
  source: [docs/typst/seminar_paper/sections/04-dataset.typ; docs/typst/seminar_paper/sections/09a-evaluation.typ; current dataset manifests],
  gate: [final experiment tables],
)

#figure(
  table(
    columns: (0.72fr, 0.58fr, 0.58fr, 0.52fr, 1.3fr),
    toprule(),
    table.header([*Policy*], [*Actor input*], [*@ground-truth:short decision*], [*H*], [*Role*]),
    midrule(), [$pi_"rand"$], [yes], [no], [1],
    [lower reference over valid candidates],
    [$pi_"learned-1"$], [yes], [no], [1], [myopic learned target scorer],
    [$pi_"oracle-1"$], [no], [yes], [1], [one-step oracle upper bound],
    [$pi_"oracle-look"$], [no], [yes], [$H$], [cumulative-@relative-reconstruction-improvement:short headroom estimate],
    [$pi_Q$], [yes], [no], [$H$], [learned recovery over myopic scoring when headroom is positive],
    bottomrule(),
  ),
  caption: [Leakage-aware policy comparison. Report #symb.entity.endpoint_gain, #symb.entity.return_h, scene @relative-reconstruction-improvement:short, cost, invalidity, runtime, and coverage for each row.],
) <tab:thesis-policy-comparison>

#conflict_todo(
  [Separate acquisition horizon from planner/lookahead depth. The table currently gives random, learned-one-step, and oracle-greedy policies $H=1$ while the comparison prose requires equal selected-view horizon $H$; all policies need the same acquisition budget even when their decision rule is myopic.],
  source: [thesis questions and roadmap; literature cross-check],
  gate: [policy-comparison protocol freeze],
)

#conflict_todo(
  [Do not call the one-step oracle policy an unrestricted upper bound. It is an immediate-reward oracle-greedy comparator over the current valid candidate set; bounded oracle lookahead is a separate finite-horizon reference, and neither bounds policies outside the evaluated candidate/support regime.],
  source: [policy table; independent peer-review critic],
  gate: [policy-role terminology freeze],
)

Policy comparisons are paired by root snippet, target, candidate seed, candidate budget, and horizon. Report mean, median, bootstrap confidence intervals, and per-scene win rates for #symb.entity.endpoint_gain, #symb.entity.return_h, and invalidity; scene-level failures are reported separately from global averages.

#validation_todo(
  [Freeze the statistical protocol: resampling unit and bootstrap interval/level, scene and target clustering, seed policy, repeated snippets/targets within scenes, invalid or missing outcomes, confirmatory versus exploratory comparisons, multiplicity handling, and reported effect sizes.],
  source: [scientific peer review; independent critic],
  gate: [analysis plan before final experiment aggregation],
)

== Failure Interpretation

The failure interpretation is part of the research contract. If geometry or oracle labels fail, the contribution becomes a validation and one-step-scoring study. If target matching is sparse or ambiguous, target-specific @relative-reconstruction-improvement:short is reported only on validated subsets with unmatched counts and acceptance filters. If #symb.entity.lookahead_headroom is near zero, the thesis reports no measurable non-myopic headroom for the evaluated split, target set, horizon, branch factor, and candidate distribution. The next diagnosis is target matching, candidate support, and supervision scale; added model complexity is justified only after those evidence gaps are ruled out. Scaling and online-discrete tests remain interpretable only if they preserve target-specific @relative-reconstruction-improvement:short supervision.

#validation_todo(
  [Replace planned evidence gates with actual result tables, figures, and failure cases after M1-M5 runs are complete.],
  source: [proposal objectives/evaluation; advisor handout],
  gate: [final experiments],
)
