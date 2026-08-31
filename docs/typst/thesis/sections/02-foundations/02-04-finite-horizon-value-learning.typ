#import "../../../shared/macros.typ": *
#import "../../../shared/equations.typ": eqs

== Sequential Decision-Making under Partial Observability <sec:thesis-sequential-decision-foundations>

An egocentric reconstruction system never observes the complete physical scene.
Its decision can depend on the sequence of earlier actions and observations, not
only on the latest frame. In a partially observable Markov decision process, a
belief state is a sufficient statistic of that action--observation history for
policy choice @POMDPRobotics-lauri2023. ARIA-NBV does not attempt general belief
inference; the relevant consequence is narrower: any finite representation used
for view selection is a hypothesis about which parts of the history are
sufficient for predicting future target improvement.

// evidence:
// - @POMDPRobotics-lauri2023 -> docs/literature/tex-src/arXiv-POMDP-Robotics-Survey/root.tex:505-505, docs/literature/tex-src/arXiv-POMDP-Robotics-Survey/root.tex:589-606 (history-dependent policies, belief-state sufficiency, and belief updates)

The preceding section defined the admissible choices as the state-dependent
row-index set $cal(A)(s_t)$ after proposal and feasibility checks. That set can
change as the target-conditioned reconstruction and current pose change, while
a hierarchical controller can also condition camera position on an earlier
look-at decision @PB-NBV-jia2025 @Hestia-lu2026. Sequential value must therefore
be conditioned on the currently available action rather than treating every
camera pose as permanently selectable.

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/method.tex:21-45, docs/literature/tex-src/arXiv-PB-NBV/jzz_2025_ral_resub.tex:55-70 (state-dependent candidate support followed by scoring and selection)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:100-118 (look-at-conditioned camera-position decision)

Sequentiality matters when the best immediate view is not the best first step
of a sequence. For target $e$, candidate $i$, and requested horizon $h$, the
finite return and corresponding conditional value are
$
  #eqs.rl.finite_horizon_return
$
$
  #eqs.rl.q_h
$
where continuation policies choose only from the admissible candidates at each
step. These equations specialize the standard discounted-return and
action-value constructions to a requested target and finite horizon
@ReinforcementLearning-sutton2018[Secs. 3.3–3.6, pp. 54–67]. Fixed-Horizon TD
defines horizon-indexed predictions with the boundary $Q_0=0$ and relates
horizon $h$ to the shorter horizon $h-1$ @FixedHorizonTD-deAsis2020. If an
episode ends before all $h$ rewards are collected, later rewards are zero. The
value thus states the consequence of taking a candidate now and then following
a named continuation rule; it is not an intrinsic property of the camera pose
alone.

// evidence:
// - @ReinforcementLearning-sutton2018 -> docs/literature/pdf/RLbook2020.pdf#page=76-89 (Ch. 3, Secs. 3.3-3.6, printed pp. 54-67; returns, action values, policies, and optimal values)
// - @FixedHorizonTD-deAsis2020 -> docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:164-164, docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:245-290, docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:331-339 (fixed-horizon returns, shorter-horizon bootstrap, and Q-learning target)

The horizon is distinct from two related bounds. The requested horizon $h$
states how many future acquisition rewards the query represents; the remaining
budget $b_t$ limits how many acquisitions are still possible; and $H_"max"$
marks the largest horizon supported by the chosen model and evidence. Universal
Value Function Approximators establish the general possibility of conditioning
one approximator on an additional task variable, while Fixed-Horizon TD shares
representations across horizon-indexed predictions @UVFA-schaul2015
@FixedHorizonTD-deAsis2020. Neither result licenses extrapolation beyond the
horizons actually supported and evaluated.

// evidence:
// - @UVFA-schaul2015 -> docs/literature/pdf/UVFA.pdf#page=1-2 (single value approximator conditioned on an additional goal variable)
// - @FixedHorizonTD-deAsis2020 -> docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:164-164, docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:245-290 (shared representations and fixed-horizon recursion)

Learning such values from a fixed data collection introduces an epistemic
constraint in addition to the mathematical horizon. Batch-constrained and
conservative offline reinforcement-learning methods are motivated by the error
that arises when a learned policy assigns high value to actions outside the
data distribution @BCQ-fujimoto2019 @CQL-kumar2020. These methods differ in how
they control that error, but they share the warning relevant here: a longer
horizon does not create evidence for transitions that the data never resolves.

// evidence:
// - @BCQ-fujimoto2019 -> docs/literature/tex-src/arXiv-BCQ/example_paper.tex:134-163, docs/literature/tex-src/arXiv-BCQ/example_paper.tex:406-426 (batch support and unsupported-action extrapolation)
// - @CQL-kumar2020 -> docs/literature/tex-src/arXiv-CQL/introduction.tex:3-12, docs/literature/tex-src/arXiv-CQL/method.tex:1-20 (offline distribution shift and conservative value learning)

Together, partial observability, state-dependent choices, and finite-horizon
return make candidate value explicitly relational @POMDPRobotics-lauri2023
@FixedHorizonTD-deAsis2020. A camera pose has no context-free value. Its value
depends on the causal information state, requested target, currently admissible
support, horizon, state-update rule, and continuation policy. The next
dependency is therefore representational. The actor state must preserve the
distinctions on which those future consequences depend.

// evidence:
// - @POMDPRobotics-lauri2023 -> docs/literature/tex-src/arXiv-POMDP-Robotics-Survey/root.tex:505-505, docs/literature/tex-src/arXiv-POMDP-Robotics-Survey/root.tex:589-606 (history and belief-state role under partial observability)
// - @FixedHorizonTD-deAsis2020 -> docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:245-290 (horizon-indexed prediction)
