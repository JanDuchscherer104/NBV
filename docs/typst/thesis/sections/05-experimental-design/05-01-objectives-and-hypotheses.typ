#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "@preview/booktabs:0.0.4": *

== Study Population and Evidence Gates

The study population is split by scene into train, validation, and held-out test manifests. The implemented generator samples oracle target tasks from geometry-valid GT rows; this establishes oracle-task coverage, not observed-target matching or deployable target support. GT target geometry, candidate renders, and target-RRI labels remain oracle assets.

=== Current generator evidence

// evidence:
// - aria_nbv/aria_nbv/oracle/target_selection.py:321-397 -> GT-OBB sampler configuration, geometry-valid task-pool construction, and seeded capped selection.
// - aria_nbv/aria_nbv/oracle/pipelines/rollout_dataset.py:420-492,789-848 -> writer configuration and generator consumption of selected oracle tasks.
// - aria_nbv/tests/oracle/test_target_selection.py:142-170 -> selection controls, uniform cap, deterministic seed, and GT-task identities.

The current data generator constructs its task pool from non-padded GT OBB rows, retains only finite positive geometry for first-pass eligibility, and applies a seeded uniform cap (three tasks per snippet by default). The writer consumes the selected oracle rows for rollout labeling. This behavior measures oracle-task coverage; it does not provide observed-target matching or deployable target support. The separate source-audit path can match actor-visible descriptors to GT rows, but that audit does not change the generator's oracle-task source.

The primary evaluation direction is a fixed acquisition budget and bounded finite candidate support. First, an actor-visible myopic control must be admitted and calibrated on the same candidate table. Then bounded oracle lookahead establishes whether the candidate setup contains non-myopic headroom:

$
  #eqs.entity.lookahead_headroom
$

Only after meaningful preregistered headroom is present is the planned finite-H scorer evaluated for recovery:

$
  #eqs.entity.q_recovery
$

Success is a matched held-out endpoint oracle evaluation, not a training loss or predicted value. The endpoint metric is:

$
  #eqs.entity.endpoint_gain
$

Its denominator is the root target error plus $epsilon$. The primary estimand is the equal-weight per-scene mean of paired endpoint differences, with the within-scene denominator equal to the number of paired, valid endpoint tasks in that scene and the scene-level denominator equal to the number of scenes with at least one such pair. The additive replay metric is the target-root gain, whose transition denominator is the maximum of the root target error and $epsilon$:

$
  #eqs.rl.target_root_gain_reward
$

These are distinct metrics. The endpoint gain is an endpoint comparison with $(Delta_0^e + epsilon)$, whereas additive target-root gain uses $max(Delta_0^e, epsilon)$; no shared-denominator or exact-equivalence claim is made. Its cumulative form is the additive trajectory diagnostic:

$
  #eqs.rl.cumulative_target_root_gain
$

State-relative RRI recomputes a state-specific denominator and remains a non-additive diagnostic. Secondary cumulative gain, state-relative RRI diagnostics, invalid-action rate, runtime, path length, and support coverage explain mechanism and feasibility.

No-root-action tasks, early-terminated trajectories, and no-supported-successor cases have no fixed-budget endpoint and are excluded from that endpoint denominator, never imputed as zero; each remains in the prespecified failure/support strata, while any realized cumulative diagnostic is reported only through its last valid state. An oracle-evaluation failure likewise contributes no endpoint or label and is counted separately. These are missing endpoint observations and support evidence, not confirmatory policy results.

No confirmatory policy result is currently established. A missing target selector, unsupported endpoint artifact, insufficient candidate support, or mismatched source/profile contract blocks the downstream policy claim rather than becoming a zero result.

#figure(
  table(
    columns: (0.85fr, 1.25fr, 1.35fr),
    toprule(),
    table.header([*Gate*], [*Evidence*], [*Interpretation*]),
    midrule(),
    [Population], [scene-split manifest and immutable counts], [held-out inference population],
    [Oracle task], [GT task pool, sampled tasks, and failures], [coverage evidence, not observed-target support],
    [Myopic control], [actor-visible ranking, calibration, and oracle re-evaluation], [required control before planning],
    [Planning headroom], [bounded oracle lookahead versus one-step oracle greedy], [finite-support opportunity gate],
    [Finite-H policy], [matched endpoint oracle artifact], [planned recovery claim only after completion],
    bottomrule(),
  ),
  caption: [Objective-to-evidence gates.]
) <tab:thesis-objective-evidence>
