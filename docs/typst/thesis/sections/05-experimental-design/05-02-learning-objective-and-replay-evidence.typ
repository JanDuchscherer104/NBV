#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status
#import "../../../shared/tables.typ": publication-table

== Replay Eligibility and Finite-Horizon Learning Gate

The factual rollout tables determine which records may supervise each learning problem. The action-validity mask defines actions selectable under the admitted oracle geometry contract. The stricter Q-training eligibility additionally requires a valid target/ground-truth label state and finite target-root-gain and diagnostic target-RRI labels. Padding, actor validity, one-step training eligibility, transition eligibility, modality presence, source role, and horizon availability remain separate masks. Masked rows remain available for support and failure analysis but cannot enter action selection, supervised loss, or bootstrap maximization.

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

=== Scalar requested-horizon targets

The scorer represents $Q_theta(s_t,e,i,h)$ for each residual horizon $h$ admitted by $1 <= h <= b_t <= H_"max"$. The boundary target is

#eqs.rl.target_root_gain_reward

and the recursive target is

#eqs.rl.qh_doubleq_target

The lower-horizon prediction is treated as a fixed regression target by stop-gradient, a frozen stage checkpoint, or a delayed target copy. The defining recursion is $Q_h arrow.l Q_(h-1)$ rather than $Q_h arrow.l Q_h$, and the executable learner rejects a successor whose factual horizon is not exactly $h-1$. Fixed-horizon TD was introduced precisely for predictions over a bounded number of future rewards and avoids same-horizon self-bootstrapping; its horizon functions may use shared parameters and parallel updates @FixedHorizonTD-deAsis2020.

The executable joint objective uses one shared horizon-conditioned network:

1. query $h=1$ for every realized state and fit every finite hard-valid candidate reward;
2. query the factual scalar horizon for selected transitions with $h>1$;
3. select the successor action with the online scorer at factual $h-1$ and evaluate it with the delayed target scorer;
4. average candidate losses within each Q1 state, state losses within each horizon, and non-empty horizon means uniformly;
5. persist the realized per-horizon state and candidate counts, report state-normalized loss and absolute calibration error for every supported horizon, report pairwise ranking and greedy selected-action regret only where a dense counterfactual candidate table exists, and reject online queries absent from manifest-bound training support.

This objective preserves one inference interface and shared encoders while making target lineage and weighting explicit. Staged backward induction, fixed-H networks, and separate per-horizon heads remain matched ablations, not alternate runtime contracts.

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
and bounds, and absolute and relative tolerances. Its independent unit is the pair
of ordered-store-manifest digest and scene identity. Thesis-core promotion requires
at least five selected independent units, at least one factual selected-action exact
Q2 row in every selected unit, and the same error gate to pass in every unit. Pooled
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

Double Q changes how a noisy learned successor maximum is estimated; it does not define the scalar horizon interface. The online path selects

#eqs.rl.qh_doubleq_index

and the delayed path evaluates $Q_(bar(theta))(s_(t+1),e,j^star,h-1)$. This selector/evaluator split can reduce overestimation caused by maximizing noisy action values @DoubleDQN-vanHasselt2015. It remains an ablation against the simpler frozen lower-horizon maximum. It is relevant in an offline setting only because a learned maximum is present, not because online learning is planned.

A retained chain also yields the truncated Monte-Carlo target

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
