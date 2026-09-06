#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status
#import "../../../shared/tables.typ": publication-table

== Replay Eligibility and Finite-Horizon Learning Gate

The factual rollout tables determine which records may supervise each learning problem. The action-validity mask defines actions selectable under the admitted oracle geometry contract. The stricter Q-training eligibility additionally requires a valid target/ground-truth label state and a finite target-root-gain label. Diagnostic target RRI has its own finite-value audit predicate and does not silently remove an otherwise valid root-gain target from `q_train_mask`. Padding, actor validity, one-step training eligibility, RRI audit availability, transition eligibility, modality presence, source role, and horizon availability remain separate masks. The evidence report attributes every excluded row to its exact failed predicate, so auxiliary-metric missingness cannot redefine the learned population. Masked rows remain available for support and failure analysis but cannot enter action selection, supervised loss, or bootstrap maximization.

All eligible candidate rows can support dense one-step supervision. Exact H=2 supervision is narrower: the factual first action must have a stored reward and either an explicit terminal outcome, whose continuation is exactly zero, or a valid successor step with finite one-step root-gain labels for every hard-valid successor candidate. This completeness condition makes the masked successor maximum exact over the stored action set; one finite label is insufficient because an unlabeled hard-valid action could have the true maximum. General recursive supervision is narrower again: it requires a factual selected action, reward, terminal flag, discount, a defined training horizon, and—when nonterminal—a reproducible successor state, hard mask, and lower-horizon factual support. The derived `q_h/` arrays align these fields on a padded state--candidate view; they do not create labels for unobserved transitions, make selected GT depth actor-visible, or turn sparse long-horizon action support into dense support.

#figure(
  publication-table(
    columns: (0.78fr, 1.10fr, 1.42fr),
    header: ([*Learning surface*], [*Purpose*], [*Minimum factual evidence*]),
    rows: (
      [dense $h=1$], [immediate candidate value],
      [actor-selectable row with finite one-step root-gain label],
      [exact $h=2$], [base-case finite-support value],
      [selected reward plus either terminal outcome or complete finite one-step labels over the hard-valid successor action set],
      [recursive $h>1$], [variable-horizon fitted value],
      [selected transition, terminal and discount; nonterminal rows also require successor actor state, hard mask, and lower-horizon target support],
      [behavior return], [policy-conditioned Monte-Carlo control],
      [complete retained reward prefix and behavior-policy identity],
    ),
  ),
  caption: [Required replay evidence by learning target. Dense immediate labels, exact H=2 targets, recursive optimal-continuation targets, and behavior-policy returns are distinct supervision surfaces.],
) <tab:thesis-support-coverage>

#figure(
  publication-table(
    columns: (0.72fr, 1.18fr, 1.25fr),
    header: ([*Gate*], [*Available evidence*], [*Required before inference*]),
    rows: (
      [Oracle data], [target labels, masks, lineage, replay validation, and selected-depth persistence],
      [held-out coverage, source-role audit, and matched endpoint evaluation],
      [Myopic control], [scene-level VIN substrate],
      [actor-visible target-conditioned $Q_1$ scorer and frozen checkpoint],
      [Finite-horizon scorer], [feature-matched A0/A1--S0-pose/root-moments scalar-horizon controls and fitted-Q seam],
      [exact-Q2 certification, parameter/runtime report, compatible checkpoint, frozen state protocol, and oracle-rescored policy],
      [Requested horizons], [fail-closed scalar query and exact $h arrow.l h-1$ recursion tests],
      [supported targets through $H_"max"$, positive headroom, and per-horizon validation],
      [Dynamic #symb.rl.qh], [selected-observation persistence and planned state update],
      [typed dynamic-state reader, deterministic fusion, source masks, and held-out policy evaluation],
      [Policy claim], [train-only feasibility pilots],
      [completed held-out paired comparison under equal budget],
    ),
  ),
  caption: [Learning-readiness gates. A runnable scorer establishes executable readiness, not a scientific policy result.],
) <tab:thesis-learning-readiness>

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@FittedQIteration-ernst2005 @FixedHorizonTD-deAsis2020 @DoubleDQN-vanHasselt2015 @CQL-kumar2020 @BCQ-fujimoto2019],
  source: "aria_nbv/aria_nbv/data_handling/qh_data/batching.py; aria_nbv/aria_nbv/lightning/qh_datamodule.py; aria_nbv/aria_nbv/lightning/qh_module.py; aria_nbv/aria_nbv/lightning/qh_q2_certification.py; aria_nbv/aria_nbv/rollouts/qh_reader.py",
  gate: [populated held-out exact-Q2 receipt, supported H>2 targets, compatible checkpoint, frozen state protocol, and independent held-out oracle re-evaluation],
)[The scalar requested-horizon A0/A1 controls, dense-Q1 plus selected-recursion Double-Q learner, feasibility auxiliary, manifest-bound trained-horizon support, and bounded stratified exact-Q2 certification surface are implemented. A1 remains the default; a qualifying population receipt, task-sufficient dynamic state, and comparative policy evidence remain unavailable.]

The finite-candidate value model decodes actions only over valid candidate rows:

$
  #eqs.rl.qh_candidate_token
$

$
  #eqs.rl.qh_masked_argmax
$

The masked argmax is already the discrete decision rule. A separate actor network and online data collection are not required to train or execute this finite-candidate policy. Batch fitted Q iteration explicitly learns a greedy Q function from a fixed collection of transitions by repeatedly solving supervised regression problems @FittedQIteration-ernst2005.

=== Training unit, causal batching, and prediction support

A retained rollout chain supplies several realized decision states rather than one monolithic recurrent sample. The root is one state; after each selected action, its factual successor is another state with an updated current pose, selected prefix, remaining budget, and candidate table. The `q_h/` reader collates these states on padded batch and state axes. At state $t$, every actor carrier is restricted to the causal prefix available before action $a_t$: a later state may be present elsewhere in the same tensor batch, but its selected poses, observations, and candidate table are not inputs to the prediction at $t$.

The scorer evaluates the realized states and their candidate rows in parallel. For one scalar horizon query per state it emits one conditional value for every materialized candidate row. This parallel tensor layout is not recurrent inference, autoregressive rollout generation, or temporal attention across the rollout. The current scorer does not advance the environment, feed one prediction back into its next state, or iteratively refine one candidate value. During policy execution it is invoked again only after the selected action has produced a genuinely new causal state and candidate table. Causal masking across the state axis would become relevant only for a future joint temporal state encoder; it is not required when each state already carries its independently materialized causal prefix.

Prediction support and loss support are therefore different. The scorer may emit finite values for every materialized candidate. Dense one-step loss uses every hard-valid candidate with a finite immediate label. For $h>1$, recursive loss is limited to the factual selected transition. Nonterminal targets additionally require a supported factual successor; terminal targets have zero continuation. The padded candidate dimension must not be read as dense multi-step supervision, and an unselected candidate receives no invented successor or return.

=== Scalar requested-horizon targets

The scorer represents $Q_theta(s_t,e,i,h)$ for each residual horizon $h$ admitted by $1 <= h <= b_t <= H_"max"$. Remaining budget $b_t$ is a factual field of the represented state; requested horizon $h$ selects how many rewards the current value is meant to summarize. Consequently, a shorter query $h<b_t$ changes the value estimand without changing the state or pretending that less acquisition budget was available. Truncating the return of an eight-step suffix to five steps is conceptually valid only when that five-step target is explicitly constructed and factually supported; changing $b_t$ itself is not ordinary data augmentation. The boundary target is

#eqs.rl.target_root_gain_reward

and the recursive target is

#eqs.rl.qh_doubleq_target

Here *recursion* means Bellman target recursion across factual successor states.
For a nonterminal $h>1$ target, the current reward is combined with a
shorter-horizon successor value queried at $h-1$; a terminal selected transition
has zero continuation and requires no successor state. This construction
combines the Bellman decomposition of action value into immediate reward and
successor value with temporal-difference bootstrapping from an estimate of that
successor @ReinforcementLearning-sutton2018[Secs. 3.5–3.6 and 6.1, pp. 58–67 and
119–124]. The lower-horizon prediction is treated as a fixed regression target
by stop-gradient, a frozen stage checkpoint, or a delayed target copy. The
defining relation is $Q_h arrow.l Q_(h-1)$ rather than $Q_h arrow.l Q_h$, and
the executable learner rejects a nonterminal successor whose factual horizon
is not exactly $h-1$. This terminology does not denote an RNN hidden-state loop,
repeated invocation of a refinement block, or backpropagation through an
unrolled future rollout. Fixed-horizon TD was introduced precisely for
predictions over a bounded number of future rewards and avoids same-horizon
self-bootstrapping; its horizon functions may use shared parameters and parallel
updates @FixedHorizonTD-deAsis2020.

// evidence:
// - @ReinforcementLearning-sutton2018 -> docs/literature/pdf/RLbook2020.pdf#page=80-89, docs/literature/pdf/RLbook2020.pdf#page=141-146 (Ch. 3, Secs. 3.5-3.6, printed pp. 58-67, and Ch. 6, Sec. 6.1, printed pp. 119-124; Bellman action-value relations and temporal-difference bootstrapping)
// - @FixedHorizonTD-deAsis2020 -> docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:245-290, docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:331-339 (shorter-horizon recursion and action-value targets)

The executable joint objective uses one shared horizon-conditioned network. Its public scorer interface still admits one scalar $h$ per state. Privately, Lightning duplicates the complete actor batch along the leading batch axis and concatenates two query domains into one scorer transaction:

1. query $h=1$ for every realized state and fit every finite hard-valid candidate reward;
2. query the factual residual horizon $h=b_t$ for the same realized states, retaining recursive loss only for selected transitions with $h>1$;
3. select the successor action with the online scorer at factual $h-1$ and evaluate it with the delayed target scorer;
4. average candidate losses within each Q1 state, state losses within each horizon, and non-empty horizon means uniformly;
5. persist the realized per-horizon state and candidate counts, report state-normalized loss and absolute calibration error for every supported horizon, report pairwise ranking and greedy selected-action regret only where a dense counterfactual candidate table exists, and reject online queries absent from manifest-bound training support.

This private batching avoids a second model transaction while preserving the scalar-horizon estimand. It does not add a public vectorized horizon axis and it does not enumerate every off-diagonal query $1<h<b_t$. Sampling or enumerating additional supported state--horizon pairs would be a separate, versioned learning-contract change with its own weighting and support rules. The present objective preserves one inference interface and shared encoders while making target lineage and weighting explicit. Staged backward induction, fixed-H networks, separate per-horizon heads, and broader off-diagonal horizon enumeration remain matched alternatives rather than implicit runtime behavior.

For remaining horizon two, the store supplies an exact target whenever the successor table has dense one-step labels:

#eqs.rl.qh_exact_q2_target

This target uses no learned successor value or target network. The executable
base-case evaluation has two layers: exact-table injection tests the recursion
implementation, while the frozen-bundle certification compares the learned
recursive target against the factual control using

#eqs.rl.qh_exact_q2_error

The latter is evaluated on a deterministic bounded sample from a metadata-only
census. Its versioned stratum contains scene, target row, configured horizon,
candidate-width bin, candidate- and rollout-configuration hashes, and behavior
policy. Within each stratum wave, the selector prefers previously unseen scenes
before taking another chain from an already represented scene. This rule improves
scene coverage without pretending that several rows from one scene are independent
replications.

The `qh-exact-q2-certification-receipt-v2` receipt binds the scorer and module configuration, actor-state and learning
contracts, ordered test-store manifests and paths, test provenance, selection seed
and bounds, and absolute and relative tolerances. Its scene-disjoint evidence unit is the pair
of ordered-store-manifest digest and scene identity. Thesis-core promotion requires
at least five selected scene-disjoint units as a minimum-support gate, at least one factual selected-action exact
Q2 row in every selected unit, and the same error gate to pass in every unit. Five
units do not establish statistical power or generality, and scenes from one dataset
or physical environment may remain correlated. Pooled
row-level error remains diagnostic and cannot compensate for a failing scene. The
receipt exposes a denominator ladder from eligible census chains through materialized
successors and complete hard-valid successor labels to factual selected-action exact
Q2 rows. It also reports per-stratum support and provenance-bound fixed-support CORAL saturation
separately from recursion error. Missing support is a failed gate rather than zero
error. Development-schema `qh-exact-q2-certification-receipt-v1` receipts remain
readable historical evidence but cannot promote a claim.
Agreement with the exact control remains necessary but insufficient for
interpreting longer horizons: positive oracle-lookahead headroom must come from
independent held-out endpoint evaluation. A persisted terminal-step role
contrast is retained as a diagnostic proxy and is manifest-bound, but it cannot
promote an $h>2$ claim.

=== Double-Q and behavior-return controls

Double Q changes how a noisy learned successor maximum is estimated; it does not define the scalar horizon interface. It is the implemented selected estimator. The online path selects

#eqs.rl.qh_doubleq_index

and the delayed path evaluates $Q_(bar(theta))(s_(t+1),e,j^star,h-1)$. This selector/evaluator split can reduce overestimation caused by maximizing noisy action values @DoubleDQN-vanHasselt2015. A simpler single-estimator frozen lower-horizon maximum remains a planned matched control until it has an executable configuration and receipt. Double Q is relevant in an offline setting because a learned maximum is present, not because online learning is planned.

As distinguished from the greedy value objective in
@ssec:thesis-horizon-recursive-offline-learning, a retained chain also yields
the truncated Monte-Carlo target

#eqs.rl.finite_horizon_return

for its behavior policy $mu$. Regression to this fixed target is a useful policy-conditioned control, but it estimates $Q^mu$, not the greedy finite-support value $Q^star$, unless $mu$ is explicitly the target continuation policy. Behavior returns from random-valid, greedy, softmax, and oracle-lookahead chains must therefore remain identified rather than pooled as if they represented one optimal value function.

Double Q addresses one maximization bias. It does not create missing successor transitions, make unsupported actions reliable, or repair state aliasing. CQL and BCQ motivate explicit offline-support diagnostics because a greedy learned policy can select actions whose multi-step consequences are weakly represented in the behavior data @CQL-kumar2020 @BCQ-fujimoto2019. Conservative regularization is introduced only if those diagnostics reveal systematic unsupported-action overestimation.

=== Horizon-balanced replay and evaluation

Dense one-step rows vastly outnumber selected-action targets at longer horizons. An unweighted row mean can therefore optimize the myopic task while obscuring longer-horizon failure. The implemented learning contract freezes candidate-within-state, state-within-horizon, equal-horizon aggregation as `uniform-horizon-state-balanced-dense-q1-selected-recursion-v2`. It binds this rule with the maximum horizon, replay candidate/rollout configuration identities, behavior-policy vocabulary, reward/return semantics, and discount, and rejects cross-stage mismatches. The bundle additionally records realized state and candidate counts for every trained horizon; syntactically valid horizons without positive training support fail closed at online inference. Checkpoint admission binds the actor-state identity separately. Alternative sampling or weighting schemes require new versioned learning identities. Candidate alternatives are:

- a horizon-stratified sampler;
- per-horizon loss weights $w_h$;
- or a fixed number of admitted targets per horizon and scene.

Every run reports, separately for each $h$:

- admitted states, selected actions, behavior policies, candidate families, scenes, and targets;
- value loss and signed target error;
- candidate ranking and top-action regret where oracle comparison is available;
- bootstrap, terminal, and no-valid-successor fractions;
- online/target disagreement for Double-Q runs;
- marginal selected target RRI and the selected-chain cumulative target RRI diagnostic;
- cumulative target root gain, kept distinct from cumulative RRI;
- endpoint performance of the masked policy requested at the remaining budget.

A single scalar validation loss is insufficient for model selection unless its horizon aggregation is frozen in advance. Cross-stage corpus admission enforces the same maximum horizon, reward and return semantics, discount, state/source protocol, candidate/reason vocabulary, replay-support identity, and horizon-weighting rule.

The optimality claim remains bounded under either interface. A learned finite-horizon value can approximate the best continuation only within the sampled finite candidate generator, hard-validity regime, represented actor state, and offline transition support. The same checkpoint cannot silently mix a pose-only state with privileged selected-depth, sensor-like, or actor-visible dynamic states. Longer horizons increase—not decrease—the need for selected-observation geometry and a sufficiently Markov scene state.

The current scorer-independent learner establishes infrastructure readiness only. Its horizon metrics are clustered by factual state: candidate errors are first averaged within state, pairwise ranking accuracies are first formed within state, and greedy regret contributes one value per supported state. Only dense Q1 currently has ranking/regret support; selected-transition recursion at longer horizons reports zero counterfactual support. Confirmatory interpretation requires the source-owner scorer decision, a canonical oracle-task corpus, dense-Q1 and exact-Q2 controls, supported targets for every claimed horizon, cross-stage learning-contract equality, checkpoint compatibility, a frozen actor-state protocol, horizon-specific support diagnostics, and matched held-out endpoint oracle re-evaluation. A dynamic-state claim additionally requires selected-observation fusion and no-future-observation leakage tests.
