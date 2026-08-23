#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "@preview/booktabs:0.0.4": *

== Policy Comparison and Statistical Protocol

The experimental unit is the scene. Comparisons are paired by scene, target task, root state, candidate-generation distribution, hard-validity regime, and fixed acquisition budget. Repeated snippets and seeds are aggregated within scene so densely sampled scenes do not dominate the endpoint estimand.

The primary comparison is the paired per-scene difference in fixed-budget endpoint target-root gain. The endpoint metric uses the canonical definition:

$
  #eqs.entity.endpoint_gain
$

Its denominator is $(Delta_0^e + epsilon)$. The additive target-root-gain trajectory metric instead uses the canonical root-normalized reward and cumulative references, whose denominator is $max(Delta_0^e, epsilon)$. These metrics are distinct estimands; this protocol makes no shared-denominator or exact-equivalence claim. The analysis manifest must freeze the equal-weight scene aggregation: first average paired differences over complete endpoint pairs within each scene, then average those scene means over scenes with at least one pair. It must also freeze uncertainty, interval level, comparison family, exclusions, and minimum meaningful effect before confirmatory inspection. State-relative RRI is a per-transition diagnostic with a state-varying denominator; cumulative state-relative RRI is therefore not additive and is not the primary endpoint. Invalid-action rate, runtime, path length, and support coverage are also secondary diagnostics; none replaces the endpoint metric.

$
  #eqs.rl.target_root_gain_reward
$

$
  #eqs.rl.cumulative_target_root_gain
$

The policy table keeps information boundaries explicit:

#figure(
  table(
    columns: (0.85fr, 1.2fr, 0.65fr, 1.35fr),
    toprule(),
    table.header([*Policy*], [*Information*], [*Budget*], [*Role*]),
    midrule(),
    [$pi_"rand"$], [actor-visible], [$H$], [valid-action reference],
    [$pi_"myopic"$], [actor-visible], [$H$], [planned/calibrated one-step control],
    [$pi_"oracle-1"$], [oracle immediate reward], [$H$], [one-step oracle comparator],
    [$pi_"oracle-look"$], [bounded oracle lookahead], [$H$], [conditional finite-support upper reference],
    [$pi_Q$], [actor-visible], [$H$], [planned fixed-H recovery],
    bottomrule(),
  ),
  caption: [Matched policy comparison with explicit information boundaries.]
) <tab:thesis-policy-comparison>

Oracle lookahead and one-step oracle greedy use one target mesh/crop, depth source, renderer/backprojection, fusion, point cap, and point-mesh metric contract. Repeated evaluation tests deterministic execution under that contract, not representation or metric independence. Learned policies use the same endpoint oracle and budget, but the learned comparison remains prospective until an actor-visible target-conditioned scorer and checkpoint exist.

Failure strata are retained: missing target task, oracle-evaluation failure, no valid root action, early termination, no supported successor, and completed paired trajectory. No valid root action means no fixed-budget endpoint is available; early termination and no supported successor likewise stop the trajectory at its last valid state and contribute no later gain. An oracle-evaluation failure invalidates the affected label or endpoint rather than creating a zero. These cases are excluded from the complete-pair endpoint denominator but remain in the declared support/failure population and are reported as such. A policy that cannot continue is not silently dropped, and incomplete artifacts do not establish headroom or superiority.

The interpretation is conditional on the frozen candidate support, actor/profile protocol, metric, and endpoint artifact. A failed recovery result can indicate target observability, action support, replay coverage, reward construction, state aliasing, or model capacity; these explanations must be separated by prespecified diagnostics rather than inferred from training loss.
