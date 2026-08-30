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
)[Scene-paired aggregation and reporting that preserves missingness are implemented; the confirmatory policy population is absent.]

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
learned-policy outcomes are inspected. The confirmatory analysis records the
three per-policy endpoint estimates and intervals before deriving either
contrast, and binds their scene count, cohort identity, aggregation, interval
method, and provenance to both the headroom and recovery facts. Ratios and their
decisions are reported only when this contract is complete and their headroom
denominator passes the meaningful-effect gate. The derived headroom effect and
recovery point estimate must also reproduce the endpoint means within a fixed
numeric serialization tolerance.

#figure(
  publication-table(
    text-size: 7.3pt,
    columns: (0.62fr, 0.9fr, 1.08fr, 1.6fr),
    header: ([*Prerequisite*], [*If evidence is unavailable*], [*If its decision does not pass*], [*Boundary and next discriminating evidence*]),
    rows: (
      [measurement], [metric validity is unresolved], [the oracle outcome is not stable enough for comparison], [Neither state implies planning, learning, or support behavior; complete or repair and repeat the frozen metric protocol.],
      [population / action support], [the study and action population is unresolved], [the requested estimand lacks adequate population support], [Neither state implies zero utility or policy failure; report exclusions, family survival, horizon coverage, and resource failures.],
      [oracle headroom], [non-myopic headroom is unresolved], [no meaningful non-myopic structure was detected in the frozen setup], [Neither state implies universal myopia or model inadequacy; complete the paired estimate, or change support or horizon only in a separately declared study.],
      [actor-visible $Q_1$], [immediate-value recovery is unresolved], [the available actor information does not recover immediate target value], [Neither state establishes a specifically long-horizon failure; complete or audit target matching, leakage, calibration, and state support.],
      [learned / exact $Q_2$], [recursive agreement is unresolved], [the first learned recursion is unsupported or inaccurate], [Neither state establishes endpoint planning value or a need for more architecture; separate coverage, $Q_1$ error, linkage, and bootstrap error.],
      [endpoint recovery], [endpoint recovery is unresolved], [the admitted learned policy does not recover prespecified headroom], [Neither state identifies the failed mechanism; complete or stratify by support, observability, replay coverage, and state aliasing.],
    ),
  ),
  caption: [Failure-attribution matrix. Unavailable evidence and an observed non-pass both block dependent claims, but only the latter supports a negative gate result. Measurements on an independent lane remain diagnostics rather than counterevidence.],
) <tab:thesis-failure-attribution>

#validation_todo(
  [Populate all six gate decisions and their dependency paths. Missing evidence blocks dependent claims rather than becoming a zero result or suppressing measurements from an independent lane.],
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
