#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../draft_markers.typ": thesis_status, validation_todo, decision_todo
#import "../../../shared/tables.typ": publication-table

== Matched Policies and Failure Attribution

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  source: "aria_nbv/aria_nbv/rollouts/reporting.py; docs/typst/thesis/experiment_data.typ",
  gate: [frozen held-out manifest, completed paired endpoints, and validated confirmatory report bundle],
)[Scene-paired aggregation and artifact-driven reporting are implemented; the confirmatory policy population is absent.]

The scene is the independent experimental unit. Comparisons are paired by
scene, target task, root state, candidate distribution, hard-validity regime,
and acquisition horizon. Repeated snippets, targets, and seeds are aggregated
within scene before inference so dense sampling cannot masquerade as independent
evidence. Policies receive the same number of acquisitions even when their
planner depth differs.

#figure(
  publication-table(
    columns: (0.75fr, 0.78fr, 0.62fr, 1.45fr),
    header: ([*Policy*], [*Decision information*], [*Budget*], [*Scientific role*]),
    rows: (
      [$pi_"rand"$], [actor-visible], [$H$], [valid-action lower reference],
      [$pi_"learned-1"$], [actor-visible], [$H$], [learned myopic control],
      [$pi_"oracle-1"$], [oracle immediate gain], [$H$], [one-step oracle-greedy comparator],
      [$pi_"oracle-look"$], [bounded oracle lookahead], [$H$], [privileged bounded-lookahead reference],
      [$pi_Q$], [actor-visible], [$H$], [finite-horizon recovery policy],
    ),
  ),
  caption: [Matched policy roles. Oracle access defines a privileged reference, not a deployable upper bound; every row retains the same acquisition budget.],
) <tab:thesis-policy-comparison>

The primary estimand is the paired per-scene difference in fixed-budget endpoint
target-quality gain. Crop, mesh, rendering, backprojection, fusion, point cap,
and point--mesh metric identity are shared across policies. The analysis
manifest freezes exclusions, within-scene aggregation, interval procedure,
comparison family, meaningful headroom, and recovered-headroom threshold before
learned-policy outcomes are inspected. Ratios are reported only when their
headroom denominator passes the meaningful-effect gate.

#figure(
  publication-table(
    text-size: 7.7pt,
    columns: (0.72fr, 1.08fr, 1.32fr, 1.28fr),
    header: ([*First failed gate*], [*Admitted interpretation*], [*Not implied*], [*Next discriminating evidence*]),
    rows: (
      [measurement], [the oracle outcome is not stable enough for comparison], [anything about planning, learning, or support], [repair and repeat the frozen metric protocol],
      [population / action support], [the requested estimand lacks an adequate study or action population], [zero utility or policy failure], [report exclusions, family survival, horizon coverage, and resource failures],
      [oracle headroom], [no meaningful non-myopic structure was detected in the frozen setup], [universal myopia or model inadequacy], [change support or horizon only in a separately declared study],
      [actor-visible $Q_1$], [the available actor information does not recover immediate target value], [a specifically long-horizon failure], [audit target matching, leakage, calibration, and state support],
      [exact $Q_2$], [the first learned recursion is unsupported or inaccurate], [endpoint planning value or a need for more architecture], [separate coverage, $Q_1$ error, successor linkage, and bootstrap error],
      [endpoint recovery], [the admitted learned policy does not recover prespecified headroom], [which mechanism failed], [stratify by support, target observability, replay coverage, and state aliasing],
    ),
  ),
  caption: [Failure-attribution matrix. Interpretation stops at the first failed gate; downstream architecture stories remain hypotheses.],
) <tab:thesis-failure-attribution>

#validation_todo(
  [Populate the six gates in order. Missing upstream evidence blocks downstream quantities rather than becoming a zero result.],
  source: [confirmatory report bundle and exact-Q2 receipt],
  gate: [artifact-backed Results chapter],
)

#decision_todo(
  [Freeze aggregation, interval level, comparison family, meaningful headroom, and recovery threshold in the resolved analysis manifest.],
  source: [confirmatory analysis plan],
  gate: [analysis freeze before outcome inspection],
)

Train-only pilots and failed generation attempts remain feasibility evidence.
Renderer out-of-memory events can motivate batching and resource measurement,
but they cannot support or refute candidate utility, oracle headroom, or policy
quality. Likewise, a policy that cannot continue remains in the paired analysis
with no further gain rather than disappearing from the denominator.

