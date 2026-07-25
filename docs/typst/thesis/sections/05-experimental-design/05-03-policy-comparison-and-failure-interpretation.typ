#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../draft_markers.typ": thesis_status, validation_todo, decision_todo
#import "@preview/booktabs:0.0.4": *

== Policy Comparison and Statistical Protocol

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  source: "aria_nbv/aria_nbv/rollouts/reporting.py; docs/typst/thesis/experiment_data.typ",
  gate: [frozen held-out manifest, completed paired endpoints, and validated report bundle],
)[The aggregation and artifact-driven reporting seam exists, but confirmatory paired policy evidence does not.]

The experimental unit is the scene. Every comparison is paired by scene, target task, root state, candidate-generation distribution, hard validity regime, and acquisition horizon. Planner depth may differ because it defines the decision rule, but every policy receives the same acquisition budget. Repeated snippets, targets, and seeds are aggregated within scene before the primary comparison so that densely sampled scenes do not dominate the estimand.

The primary estimand is the paired per-scene difference in fixed-budget endpoint target-quality gain. The centralized analysis artifact freezes the scene aggregation function, uncertainty procedure, interval level, comparison set, and minimum meaningful effect before final aggregation. Secondary summaries---cumulative root-normalized gain, invalid-action rate, runtime, path length, and task/candidate coverage---diagnose mechanism and feasibility but do not replace the endpoint estimand. The current replay store alone cannot estimate this endpoint comparison because it does not persist an independent post-budget reconstruction for every policy; confirmatory analysis therefore requires matched endpoint oracle re-evaluation or an equivalent frozen endpoint record.

Support and failure strata are fixed before policy inspection. The report distinguishes source rows without an admitted target task, admitted tasks whose oracle evaluation fails, roots without a valid action, trajectories that terminate before the shared budget, and completed paired trajectories. A policy that cannot continue remains in the comparison with no further gain; it is not silently dropped. These strata delimit the analysis population and expose whether a policy difference is instead a support or systems failure.

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
    [$pi_Q$], [actor-visible], [$H$], [planned learned finite-horizon recovery],
    bottomrule(),
  ),
  caption: [Matched policy comparison. All rows acquire the same number of views; oracle access and planner depth define the decision rule rather than the acquisition budget.],
) <tab:thesis-policy-comparison>

The first inferential comparison is bounded oracle lookahead against one-step oracle greedy. Repeated oracle evaluation estimates the metric noise floor, and the analysis artifact freezes the meaningful-headroom rule before learned-policy inspection. Recovered-headroom ratios are reported only when their denominator passes that gate. The learned comparison then contrasts #symb.rl.qh with the actor-visible myopic control under the same endpoint evaluation and acquisition budget; because neither learned target-conditioned control is presently complete, this comparison remains prospective.

#validation_todo(
  [Populate the evidence chain in order: metric repeatability, candidate and target support, oracle-lookahead headroom, myopic-control calibration, finite-horizon recovery, then representation and architecture ablations. Missing upstream evidence blocks downstream claims rather than becoming a zero result.],
  source: [thesis objective-to-evidence contract; repo:.agents/todos.toml\#todo-037],
  gate: [artifact-backed Results bundle],
)

#validation_todo(
  [Run row-shuffle, mask-isolation, duplicate-row, valid-count, frame-transform, target-source-dropout, and horizon-boundary tests for every model admitted to the policy comparison.],
  source: [geometric acceptance contract; repo:.agents/todos.toml\#todo-052],
  gate: [architecture validity report],
)

#decision_todo(
  [Freeze the scene aggregation, interval procedure, interval level, comparison family, and meaningful-headroom threshold in the resolved analysis manifest rather than in thesis prose.],
  source: [artifact-driven reporting plan; repo:.agents/todos.toml\#todo-018],
  gate: [confirmatory analysis freeze],
)

== Outcome Logic

Meaningful, stable lookahead headroom establishes only that the frozen finite-candidate setup contains exploitable non-myopic structure. No meaningful headroom is a setup-specific negative result, not evidence that target-aware planning is universally myopic. An unstable oracle metric or insufficient paired support blocks downstream policy claims. Likewise, train-only bandwidth pilots and failed generation attempts, including memory-exhaustion failures, inform compute configuration and throughput planning only; incomplete artifacts cannot establish headroom or policy superiority.
