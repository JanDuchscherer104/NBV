#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status
#import "@preview/booktabs:0.0.4": *

== Replay Eligibility and Variable-Horizon Learning Gate

The factual rollout tables determine which records may supervise each learning problem. `valid_action_mask` defines actions selectable under the admitted V0 geometry contract. The stricter `q_train_mask` additionally requires a valid target/GT label state and finite target-root-gain and diagnostic target-RRI labels. Padding, actor validity, one-step training eligibility, transition eligibility, modality presence, source role, and horizon availability remain separate masks. Masked rows remain available for support and failure analysis but cannot enter action selection, supervised loss, or bootstrap maximization.

All eligible candidate rows can support dense one-step supervision. Exact H=2 supervision is narrower: the factual first action must have a stored reward and a valid successor step whose candidate table exposes at least one finite one-step root-gain label. General horizon-recursive supervision is narrower again: it requires a factual selected action, reward, terminal flag, discount, requested residual horizon, and—when nonterminal—a reproducible successor state and hard mask. The derived `q_h/` arrays align these fields on a padded state--candidate view; they do not create labels for unobserved transitions, make selected GT depth actor-visible, or turn sparse long-horizon action support into dense support.

#figure(
  table(
    columns: (0.78fr, 1.10fr, 1.42fr),
    toprule(),
    table.header([*Learning surface*], [*Purpose*], [*Minimum factual evidence*]),
    midrule(),
    [dense $h=1$], [immediate candidate value],
    [actor-selectable row with finite one-step root-gain label],
    [exact $h=2$], [base-case finite-support value],
    [selected reward plus successor table with at least one finite one-step root-gain label],
    [recursive $h>1$], [variable-horizon fitted value],
    [selected transition, successor actor state and mask, lower-horizon target support, terminal and discount],
    [behavior return], [policy-conditioned Monte-Carlo control],
    [complete retained reward prefix and behavior-policy identity],
    bottomrule(),
  ),
  caption: [Required replay evidence by learning target. Dense immediate labels, exact H=2 targets, recursive optimal-continuation targets, and behavior-policy returns are distinct supervision surfaces.],
) <tab:thesis-support-coverage>

#figure(
  table(
    columns: (0.72fr, 1.18fr, 1.25fr),
    toprule(),
    table.header([*Gate*], [*Available evidence*], [*Required before inference*]),
    midrule(),
    [Oracle data], [target labels, masks, lineage, replay validation, and selected-depth persistence],
    [held-out coverage, source-role audit, and matched endpoint evaluation],
    [Myopic control], [scene-level VIN substrate],
    [actor-visible target-conditioned $Q_1$ scorer and frozen checkpoint],
    [H=2 tracer], [V0 `S0-pose` scorer and selected-transition training seam],
    [exact-Q2 control, state-protocol freeze, compatible checkpoint, and oracle-rescored policy],
    [Variable-horizon $Q$], [selected transitions and explicit horizon-query contract],
    [dense Q1, certified Q2 recursion, supported horizons through $H$, horizon-balanced training, and per-horizon validation],
    [Dynamic #symb.rl.qh], [selected-observation persistence and planned state update],
    [typed dynamic-state reader, deterministic fusion, source masks, and held-out policy evaluation],
    [Policy claim], [train-only feasibility pilots],
    [completed held-out paired comparison under equal budget], bottomrule(),
  ),
  caption: [Learning-readiness gates. A runnable H=2 tracer does not establish a task-sufficient state or a variable-horizon policy.],
) <tab:thesis-learning-readiness>

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@FittedQIteration-ernst2005 @FixedHorizonTD-deAsis2020 @DoubleDQN-vanHasselt2015 @CQL-kumar2020 @BCQ-fujimoto2019],
  source: "aria_nbv/aria_nbv/data_handling/qh.py; aria_nbv/aria_nbv/vin/models/target_finite_horizon.py; aria_nbv/aria_nbv/lightning/qh_module.py; aria_nbv/aria_nbv/rollouts/qh_reader.py",
  gate: [explicit horizon-query reader, dense Q1, exact Q2 certification, supported H>2 targets, compatible checkpoint, frozen state protocol, and held-out oracle re-evaluation],
)[A masked selected-transition Double-Q learner and H=2 V0 pose-history scorer are implemented in development. One shared scorer optimized for variable residual horizons, a task-sufficient dynamic state, and policy evidence remain unimplemented.]

The finite-candidate value model decodes actions only over valid candidate rows:

$
  #eqs.rl.qh_candidate_token
$

$
  #eqs.rl.qh_masked_argmax
$

The masked argmax is already the discrete decision rule. A separate actor network and online data collection are not required to train or execute this finite-candidate policy. Batch fitted Q iteration explicitly learns a greedy Q function from a fixed collection of transitions by repeatedly solving supervised regression problems @FittedQIteration-ernst2005.

=== Primary variable-horizon target

The primary model is one conditional scorer $Q_theta(s_t,e,i,h)$ for every requested residual horizon $h$ admitted by $1 <= h <= b_t <= H$. The boundary target is

$
  y_t^((1,e)) = r_t^e
$

and the recursive target is

$
  y_t^((h,e))
  =
  cases(
    r_t^e & "if " h=1 " or " d_t=1,
    r_t^e + gamma op("max", limits: #true)_(j : m_(t+1,j)=1)
      Q_(bar(theta))(s_(t+1),e,j,h-1) & "if " h>1 " and " d_t=0
  )
$

The lower-horizon prediction is treated as a fixed regression target by stop-gradient, a frozen stage checkpoint, or a delayed target copy. The defining recursion is $Q_h leftarrow Q_(h-1)$ rather than $Q_h leftarrow Q_h$. Fixed-horizon TD was introduced precisely for predictions over a bounded number of future rewards and avoids same-horizon self-bootstrapping; its horizon functions may use shared parameters and parallel updates @FixedHorizonTD-deAsis2020.

For the first implementation, the clearest schedule is staged backward induction with one shared horizon-conditioned network:

1. fit $Q_1$ from dense one-step labels for every candidate admitted by `q_train_mask`;
2. freeze or snapshot the lower-horizon target path;
3. fit $Q_2$ from selected transitions and validate it against the exact dense-successor target;
4. continue through $Q_H$, always requesting $h-1$ from the successor target path;
5. optionally fine-tune all horizons jointly after the staged model passes per-horizon regression and ranking gates.

This schedule preserves one inference interface and shared encoders while making the target lineage explicit. Separate per-horizon networks or heads are retained as a control for interference, not as the thesis-core architecture.

For remaining horizon two, the store supplies an exact target whenever the successor table has dense one-step labels:

$
  y_t^((2,e), "exact")
  =
  r_t^e
  +
  gamma
  op("max", limits: #true)_(j : m_(t+1,j)^"train"=1)
  r_(t+1,j)^e
$

This target uses no learned successor value or target network. Agreement between fitted $Q_2$ and this exact control is a required base-case test before interpreting longer-horizon results. It is not the endpoint of the method because the minimal thesis goal is one scorer spanning all supported horizons.

=== Double-Q and behavior-return controls

Double Q changes how a noisy learned successor maximum is estimated; it does not change the definition of the horizon-conditioned scorer. The online path selects

$
  j^star
  =
  op("argmax", limits: #true)_(j : m_(t+1,j)=1)
  Q_theta(s_(t+1),e,j,h-1)
$

and the delayed path evaluates $Q_(bar(theta))(s_(t+1),e,j^star,h-1)$. This selector/evaluator split can reduce overestimation caused by maximizing noisy action values @DoubleDQN-vanHasselt2015. It remains an ablation against the simpler frozen lower-horizon maximum. It is relevant in an offline setting only because a learned maximum is present, not because online learning is planned.

A retained chain also yields the truncated Monte-Carlo target

$
  G_(t,e)^((h),mu)
  =
  sum_(k=0)^(h-1) gamma^k r_(t+k)^e
$

for its behavior policy $mu$. Regression to this fixed target is a useful policy-conditioned control, but it estimates $Q^mu$, not the greedy finite-support value $Q^star$, unless $mu$ is explicitly the target continuation policy. Behavior returns from random-valid, greedy, softmax, and oracle-lookahead chains must therefore remain identified rather than pooled as if they represented one optimal value function.

Double Q addresses one maximization bias. It does not create missing successor transitions, make unsupported actions reliable, or repair state aliasing. CQL and BCQ motivate explicit offline-support diagnostics because a greedy learned policy can select actions whose multi-step consequences are weakly represented in the behavior data @CQL-kumar2020 @BCQ-fujimoto2019. Conservative regularization is introduced only if those diagnostics reveal systematic unsupported-action overestimation.

=== Horizon-balanced replay and evaluation

Dense $h=1$ rows vastly outnumber selected-action targets for $h>1$. An unweighted row mean would therefore optimize the myopic task while reporting a nominal variable-horizon loss. The training manifest must freeze either:

- a horizon-stratified sampler;
- per-horizon loss weights $w_h$;
- or a fixed number of admitted targets per horizon and scene.

Every run reports, separately for each $h$:

- admitted states, selected actions, behavior policies, candidate families, scenes, and targets;
- value loss and signed target error;
- candidate ranking and top-action regret where oracle comparison is available;
- bootstrap, terminal, and no-valid-successor fractions;
- online/target disagreement for Double-Q runs;
- endpoint performance of the masked policy requested at the remaining budget.

A single scalar validation loss is insufficient for model selection unless its horizon aggregation is frozen in advance. Cross-stage corpus admission must also require the same maximum horizon, reward and return semantics, discount, state/source protocol, candidate/reason vocabulary, and horizon-weighting rule.

The optimality claim remains bounded. $Q_theta(s,e,i,h)$ can approximate the best continuation only within the sampled finite candidate generator, hard-validity regime, represented actor state, and offline transition support. The same checkpoint cannot silently mix an `S0-pose` state with `CF-GT`, sensor-like, or V1 dynamic states. Longer requested horizons increase—not decrease—the need for selected-observation geometry and a sufficiently Markov scene state.

The development H=2 tracer may establish optimization and systems readiness only. Confirmatory interpretation requires a canonical V0 corpus, dense-Q1 and exact-Q2 controls, supported targets for every claimed horizon, cross-stage learning-contract equality, checkpoint compatibility, a frozen actor-state protocol, horizon-specific support diagnostics, and matched held-out endpoint oracle re-evaluation. A dynamic-state claim additionally requires selected-observation fusion and no-future-observation leakage tests.
