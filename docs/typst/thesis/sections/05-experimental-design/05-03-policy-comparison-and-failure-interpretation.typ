#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../draft_markers.typ": thesis_status, validation_todo, decision_todo
#import "../../../shared/tables.typ": publication-table

== Policy Comparison and Statistical Protocol

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  source: "aria_nbv/aria_nbv/rollouts/reporting.py; docs/typst/thesis/experiment_data.typ",
  gate: [frozen held-out manifest, completed paired endpoints, and validated report bundle],
)[The aggregation and artifact-driven reporting seam exists, but confirmatory paired policy evidence does not.]

The experimental unit is the scene. Every comparison is paired by scene, target task, root state, candidate-generation distribution, hard validity regime, and acquisition horizon. Planner depth may differ because it defines the decision rule, but every policy receives the same acquisition budget. Repeated snippets, targets, and seeds are aggregated within scene before the primary comparison so that densely sampled scenes do not dominate the estimand.

The primary estimand is the paired per-scene difference in fixed-budget endpoint target-quality gain, using #symb.entity.endpoint_gain. Its $Delta_0^e + epsilon$ denominator is distinct from the $max(Delta_0^e, epsilon)$ denominator of cumulative target-root gain, while state-relative RRI has a state-varying denominator; both remain secondary diagnostics rather than alternate names for the endpoint. The centralized analysis artifact freezes the scene aggregation function, uncertainty procedure, interval level, comparison set, and minimum meaningful effect before final aggregation. Invalid-action rate, runtime, path length, and task/candidate coverage likewise diagnose mechanism and feasibility but do not replace the endpoint estimand. The current replay store alone cannot estimate this endpoint comparison because it does not persist an independent post-budget reconstruction for every policy; confirmatory analysis therefore requires matched endpoint oracle re-evaluation or an equivalent frozen endpoint record.

Support and failure strata are fixed before policy inspection. The report distinguishes source rows without an admitted target task, admitted tasks whose oracle evaluation fails, roots without a valid action, trajectories that terminate before the shared budget, and completed paired trajectories. A policy that cannot continue remains in the comparison with no further gain; it is not silently dropped. These strata delimit the analysis population and expose whether a policy difference is instead a support or systems failure.

#figure(
  publication-table(
    columns: (0.72fr, 0.72fr, 0.58fr, 1.35fr),
    header: ([*Policy*], [*Decision input*], [*Acquisition budget*], [*Scientific role*]),
    rows: (
      [$pi_"rand"$], [actor-visible], [$H$], [valid-action lower reference],
      [$pi_"learned-1"$], [actor-visible], [$H$], [learned myopic control],
      [$pi_"oracle-1"$], [oracle immediate reward], [$H$], [one-step oracle-greedy comparator],
      [$pi_"oracle-look"$], [bounded oracle lookahead], [$H$], [conditional finite-support upper reference],
      [$pi_Q$], [actor-visible], [$H$], [planned learned finite-horizon gap closure],
    ),
  ),
  caption: [Matched policy comparison. All rows acquire the same number of views; oracle access and planner depth define the decision rule rather than the acquisition budget.],
) <tab:thesis-policy-comparison>

The first inferential comparison is bounded oracle lookahead against one-step oracle greedy. Its evaluation contract freezes one target mesh and crop, ASE-depth source, renderer and backprojection, fusion and point cap, and point--mesh metric configuration for every policy. Repeated evaluation must reproduce the same scores within the declared numerical tolerance; it verifies deterministic execution under this contract, not invariance to a different mesh, sampling process, or metric. The analysis artifact also freezes the meaningful-headroom rule before learned-policy inspection. Learned-control gap-closure ratios are reported only after oracle headroom passes that gate and only when their distinct actor-visible-myopic-to-oracle-lookahead denominator is admissible. The learned comparison then contrasts #symb.rl.qh with the actor-visible myopic control under the same endpoint evaluation and acquisition budget; because neither learned target-conditioned control is presently complete, this comparison remains prospective.

#validation_todo(
  [Populate the evidence chain in order: evaluation-contract identity and deterministic repeatability, candidate and target support, oracle-lookahead headroom, myopic-control calibration, finite-horizon gap closure, then representation and architecture ablations. Missing upstream evidence blocks downstream claims rather than becoming a zero result.],
  source: [thesis objective-to-evidence contract],
  gate: [artifact-backed Results bundle],
)

#validation_todo(
  [Run row-shuffle, mask-isolation, duplicate-row, valid-count, frame-transform, target-source-dropout, and horizon-boundary tests for every model admitted to the policy comparison.],
  source: [geometric acceptance contract],
  gate: [architecture validity report],
)

#decision_todo(
  [Freeze the scene aggregation, interval procedure, interval level, comparison family, and meaningful-headroom threshold in the resolved analysis manifest rather than in thesis prose.],
  source: [artifact-driven reporting plan],
  gate: [confirmatory analysis freeze],
)

== Outcome Logic

Meaningful, stable lookahead headroom establishes only that the frozen finite-candidate setup contains exploitable non-myopic structure. No meaningful headroom is a setup-specific negative result, not evidence that target-aware planning is universally myopic. A non-reproducible or mismatched evaluation contract, or insufficient paired support, blocks downstream policy claims. Conclusions remain conditional on the frozen metric contract and are not claims of representation independence. Likewise, train-only bandwidth pilots and failed generation attempts, including memory-exhaustion failures, inform compute configuration and throughput planning only; incomplete artifacts cannot establish headroom or policy superiority.
