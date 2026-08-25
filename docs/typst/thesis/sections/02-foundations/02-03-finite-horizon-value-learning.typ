#import "../../../shared/macros.typ": *
#import "../../../shared/equations.typ": eqs

== Finite-Horizon Value Learning <sec:thesis-finite-horizon-value-learning>

Bounded lookahead is represented by a family of horizon-indexed values. For
target $e$, candidate $i$, and requested horizon $h$, the admissible finite
return and optimal conditional value are
$
  #eqs.rl.finite_horizon_return
$
$
  #eqs.rl.q_h
$
Here $cal(Pi)^"act"$ contains continuation policies restricted to each step's
generated finite candidate set and hard action support. A query with $h>b_t$ is
rejected or masked, not clamped. If an episode terminates before $h$ rewards
after termination are zero, so a terminal transition has exact zero
continuation. Fixed-Horizon TD defines policy-conditioned horizon values by
bootstrapping horizon $h$ from $h-1$, with $Q_0=0$
@FixedHorizonTD-deAsis2020. The thesis fixes the greedy finite-support optimum
as its target estimand; behavior-policy Monte Carlo returns are a different
estimand. The recursion motivates the mathematical form, not empirical gain for
ARIA-NBV.

// evidence:
// - @FixedHorizonTD-deAsis2020 -> docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:164-164, docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:245-290, docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:331-339 (fixed-horizon returns, shorter-horizon bootstrap, and Q-learning target)

Three quantities must not be conflated. The requested horizon $h$ is the query
to the value model; the factual remaining budget $b_t$ limits actions that can
actually be executed; and $H_"max"$ bounds the horizon supported by the model
and evidence contract. Universal Value Function Approximators show how a
single approximator can condition on an additional task variable
@UVFA-schaul2015, while Fixed-Horizon TD shares representations across horizon
heads @FixedHorizonTD-deAsis2020. Neither source licenses extrapolation to an
untrained horizon: a result at $h=2$ is not evidence for $h>2$.

// evidence:
// - @UVFA-schaul2015 -> docs/literature/pdf/UVFA.pdf#page=1-2 (single value approximator conditioned on an additional goal variable)
// - @FixedHorizonTD-deAsis2020 -> docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:164-164, docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:245-290 (shared representations and fixed-horizon recursion)

#figure(
  image("../../figures/qh_evidence_support_lattice.pdf", width: 90%),
  caption: [Original conceptual lattice for exact finite-horizon supervision. It combines fixed-horizon successor recursion with finite-batch and hard-action support restrictions @FixedHorizonTD-deAsis2020 @BCQ-fujimoto2019 @InvalidActionMasking-huang2022. Dense one-step labels alone do not certify longer-horizon targets; the diagram reports no empirical result.],
) <fig:qh-evidence-support-lattice>

// evidence:
// - @FixedHorizonTD-deAsis2020 -> docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:245-290, docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:331-339 (horizon recursion and fixed-horizon Q target)
// - @BCQ-fujimoto2019 -> docs/literature/tex-src/arXiv-BCQ/example_paper.tex:134-163, docs/literature/tex-src/arXiv-BCQ/example_paper.tex:406-426 (batch support and unsupported-action extrapolation)
// - @InvalidActionMasking-huang2022 -> docs/literature/tex-src/arXiv-Invalid-Action-Masking/formatting-instructions-latex.tex:66-71, docs/literature/tex-src/arXiv-Invalid-Action-Masking/formatting-instructions-latex.tex:150-174 (state-dependent admissible actions and masking scope)

Offline value learning adds two independent cautions. Double DQN decouples
action selection from target evaluation to reduce maximization bias
@DoubleDQN-vanHasselt2015; BCQ and CQL address distribution shift by
constraining or conservatively regularizing unsupported actions
@BCQ-fujimoto2019 @CQL-kumar2020. These methods do not create missing factual
successors. Every multi-step target still requires an admitted action, a
resolved transition or terminal outcome, and recursively supported
successor-side value evidence. Accordingly, a learned Double-Q successor
maximum is admitted only over rows with both $m_(t+1,i)^"act"=1$ and
$m_(t+1,i)^(Q,h-1)=1$; this training-support gate is distinct from the
hard-action-only policy used at evaluation.

// evidence:
// - @DoubleDQN-vanHasselt2015 -> docs/literature/tex-src/arXiv-Double-DQN/DoubleDQN_aaai2016_total.tex:112-124 (separate action selection and value evaluation)
// - @BCQ-fujimoto2019 -> docs/literature/tex-src/arXiv-BCQ/example_paper.tex:134-163, docs/literature/tex-src/arXiv-BCQ/example_paper.tex:406-426 (fixed-batch extrapolation and action constraints)
// - @CQL-kumar2020 -> docs/literature/tex-src/arXiv-CQL/introduction.tex:3-12, docs/literature/tex-src/arXiv-CQL/method.tex:1-20 (offline distribution shift and conservative value learning)

Sequence models offer a different planning factorization. Trajectory
Transformer performs receding-horizon replanning from predicted sequences,
whereas Decision Transformer conditions action generation on a desired return
@TrajectoryTransformer-janner2021 @DecisionTransformer-chen2021. They motivate
bounded alternatives, not equivalence to exact finite-horizon Q learning; any
comparison must preserve the same actor information, candidate support, and
endpoint target-quality evaluation.

// evidence:
// - @TrajectoryTransformer-janner2021 -> docs/literature/tex-src/arXiv-Trajectory-Transformer/text/method.tex:66-80, docs/literature/tex-src/arXiv-Trajectory-Transformer/text/method.tex:98-122 (offline sequence prediction and first-action replanning)
// - @DecisionTransformer-chen2021 -> docs/literature/tex-src/arXiv-Decision-Transformer/sections/method.tex:2-29 (return-conditioned sequence modeling and action prediction)
