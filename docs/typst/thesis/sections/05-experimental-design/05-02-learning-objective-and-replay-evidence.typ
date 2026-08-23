#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": development_only
#import "@preview/booktabs:0.0.4": *

== Replay Eligibility and Finite-Horizon Learning Gate

=== Implemented evidence surface

// evidence:
// - aria_nbv/aria_nbv/data_handling/qh_data/batching.py:62-136 -> selected-row, successor, and bootstrap masks with explicit no-label successor behavior.
// - aria_nbv/aria_nbv/rollouts/zarr_store.py:970-985,3190-3216 -> q_h mask/label validation and padded projection.
// - aria_nbv/tests/data_handling/test_qh.py:371-393 and aria_nbv/tests/rollouts/test_zarr_store.py:182-206 -> focused mask and return-contract proofs.

The factual replay tables provide dense one-step labels only where a row is actor-selectable and has finite oracle support. `valid_action_mask`, `q_train_mask`, and padding remain distinct. Invalid and padded rows cannot enter selection, loss, or bootstrap. A nonterminal successor with no label-supported action has no bootstrap support; it is not assigned a utility value.

The implemented learner can consume selected transitions for an injected scorer. It does not establish a complete H=2 scorer, a task-sufficient successor memory, or a policy result. The primary planned learning objective is the bounded fixed-H return in additive target-root-gain units:

$
  #eqs.rl.finite_horizon_return
$

For the admitted persisted Q_H primary path, the stored reward metric is `target_root_gain`; state-relative RRI is reported separately and is never substituted there. The generic `selected_target_reward` helper retains a legacy fallback through `target_root_gain`, `root_gain`, `target_rri`, or `rri` for non-admitted diagnostic rows outside Q_H evidence. That compatibility fallback is not the primary learning or evaluation path.

// evidence:
// - aria_nbv/aria_nbv/rollouts/zarr_store.py:108-112,989-1008 -> persisted Q_H reward and return contract validation.
// - aria_nbv/aria_nbv/rri_metrics/returns.py:85-88 and aria_nbv/tests/rri_metrics/test_rollout_metrics.py:23-36 -> generic legacy reward fallback and its precedence test.

#figure(
  table(
    columns: (1fr, 1.2fr, 1.55fr),
    toprule(),
    table.header([*Surface*], [*Current role*], [*Minimum evidence*]),
    midrule(),
    [dense one-step], [implemented label/read surface], [actor-valid row and finite root-gain label],
    [fixed-H scorer], [planned primary objective], [production scorer, compatible checkpoint, and supported selected transitions],
    [endpoint evaluation], [planned scientific proof], [matched held-out oracle re-evaluation],
    bottomrule(),
  ),
  caption: [Learning surfaces and evidence gates.]
) <tab:thesis-support-coverage>

The read-model evidence is bounded and factual. It aligns stored rows, preserves candidate identity, and reports padding and mask counts when explicitly requested; it does not manufacture support for unobserved transitions.

=== Development controls

#development_only(() => [
  Exact-$H=2$ supervision is a base-case certification control. Requested-horizon recursion, Monte Carlo behavior returns, Double-Q comparisons, conservative offline controls such as CQL/BCQ, horizon-balanced sampling, and residual objectives are separate estimands or ablations. Each requires its own horizon/support report and must not be pooled into the primary fixed-H method.

  Evaluation reports per-horizon admitted states, selected actions, support, terminal/no-bootstrap fractions, loss and ranking, while endpoint target-root gain remains the scientific outcome. No single aggregate loss can establish policy quality.
])
