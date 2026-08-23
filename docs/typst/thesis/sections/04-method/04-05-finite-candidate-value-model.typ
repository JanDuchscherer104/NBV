#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": development_only

== Target-Conditioned Finite-Horizon Value Model

=== Implemented learning substrate

// evidence:
// - aria_nbv/aria_nbv/lightning/qh_module.py:74-88,399-400 -> injected actor-only scorer, selected-transition Double-Q adapter, and bootstrap reporting.
// - aria_nbv/aria_nbv/data_handling/qh_data/views.py:176-257 -> actor/supervision DTO separation and absence of oracle labels from actor tensors.
// - aria_nbv/tests/lightning/test_qh_module.py:146-210 -> profile and contract admission before scorer construction.

The implemented component is scorer-independent fitted-Q infrastructure: an injected scorer receives actor DTOs, while the Lightning adapter owns admitted-row loss, target synchronization, and selected-transition backups. This is an implemented substrate contract, not a production finite-horizon scorer, checkpoint, or policy result.

The persisted reward semantics are additive target-root gain. The canonical one-step reward is:

$
  #eqs.rl.target_root_gain_reward
$

and the finite-horizon return is:

$
  #eqs.rl.finite_horizon_return
$

Target-root gain telescopes under matched selected states and $gamma=1$:

$
  #eqs.rl.cumulative_target_root_gain
$

State-relative target RRI is a separate diagnostic for current-state improvement. It is not an alias for `target_root_gain` and is not additive.

No production scorer is evaluated here. Any future scorer would remain bounded by the generated candidate support, hard-validity regime, represented actor state, and offline transition support; the current DTO frame and profile contracts do not prove task-sufficient memory, scorer invariance, or policy optimality.

#development_only(() => [
  === Development scorer direction

  The planned scorer is a bounded fixed-horizon value model with remaining budget in state. For finite candidate support, its intended value and masked decision rule use the shared equations:

  $
    #eqs.rl.q_h
  $

  $
    #eqs.rl.qh_masked_argmax
  $

  A requested-horizon model, exact-$H=2$ target, recursive targets, Double-Q selector/evaluator variants, Monte Carlo behavior returns, CQL/BCQ support controls, residual heads, and alternative encoders are development evidence. They remain separately identified by horizon, state/source protocol, support, and estimand. CQL/BCQ are not part of the primary flow and are introduced only if unsupported-action diagnostics justify an offline-conservatism study.

  Exact-$H=2$ is a certification control, not the method definition. A behavior return estimates $Q^mu$, not the greedy finite-support value $Q^star$. No alternative enters the accepted primary path until it has an admitted scorer, compatible checkpoint, and matched oracle re-evaluation.
])
