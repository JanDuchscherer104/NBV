#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status
#import "@preview/booktabs:0.0.4": *

== Replay Eligibility and Learning Gate

The factual rollout tables determine which records may supervise each learning problem. `valid_action_mask` defines actions selectable under the admitted V0 geometry contract. The stricter `q_train_mask` additionally requires a valid target/GT label state and finite target-root-gain and diagnostic target-RRI labels. Padding, actor validity, training eligibility, and any future deployable feasibility estimate remain separate masks. Masked rows remain available for support and failure analysis but cannot enter action selection, supervised loss, or bootstrap maximization.

All eligible candidate rows can support dense one-step supervision. Exact H=2 supervision is narrower: the factual first action must have a stored reward and a valid successor step whose candidate table exposes at least one finite one-step root-gain label. General temporal-difference supervision is narrower again: it requires a factual selected action, reward, terminal flag, discount, and—when nonterminal—a reproducible successor state and hard mask. The derived `q_h/` arrays align these fields on a padded state--candidate view; they do not create labels for unobserved transitions or make selected GT depth actor-visible.

#figure(
  table(
    columns: (0.82fr, 1.10fr, 1.36fr),
    toprule(),
    table.header([*Data product*], [*Purpose*], [*Minimum evidence*]),
    midrule(),
    [target tasks], [define supervised entities],
    [GT pool, sampled tasks, class/scene coverage, and oracle failures],
    [candidate shells], [define finite action support],
    [family counts, valid fraction, invalid reasons, and selected-family coverage],
    [`q_train_mask`], [admit dense one-step labels],
    [actor-selectable rows with valid target state and finite target labels],
    [exact H=2 target], [supervise selected first actions],
    [selected reward plus a successor table with at least one finite one-step root-gain label],
    [selected transitions], [admit general TD linkage],
    [reward, terminal flag, discount, and—when nonterminal—successor id, state protocol, and mask],
    bottomrule(),
  ),
  caption: [Required support evidence. Each narrower learning surface inherits the validity requirements above it.],
) <tab:thesis-support-coverage>

#figure(
  table(
    columns: (0.74fr, 1.16fr, 1.24fr),
    toprule(),
    table.header([*Gate*], [*Available evidence*], [*Required before inference*]),
    midrule(),
    [Oracle data], [target labels, masks, lineage, replay validation, and selected-depth persistence],
    [held-out coverage, source-role audit, and matched endpoint evaluation],
    [Myopic control], [scene-level VIN substrate],
    [actor-visible target-conditioned scorer and frozen checkpoint],
    [H=2 tracer], [V0 `S0-pose` scorer and selected-transition training seam],
    [exact-Q2 control, state-protocol freeze, compatible checkpoint, and oracle-rescored policy],
    [Dynamic #symb.rl.qh], [selected-observation persistence and planned state update],
    [typed dynamic-state reader, deterministic fusion, source masks, and held-out policy evaluation],
    [Policy claim], [train-only feasibility pilots],
    [completed held-out paired comparison under equal budget], bottomrule(),
  ),
  caption: [Learning-readiness gates. Data-contract evidence and a runnable tracer do not substitute for a task-sufficient state or an evaluated policy.],
) <tab:thesis-learning-readiness>

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@DoubleDQN-vanHasselt2015],
  source: "aria_nbv/aria_nbv/data_handling/qh.py; aria_nbv/aria_nbv/vin/models/target_finite_horizon.py; aria_nbv/aria_nbv/lightning/qh_module.py; aria_nbv/aria_nbv/rollouts/qh_reader.py",
  gate: [exact H=2 control, compatible checkpoint, frozen state protocol, and held-out oracle re-evaluation],
)[A masked selected-transition Double-Q learner and H=2 V0 pose-history scorer are implemented in development. The task-sufficient dynamic state and policy evidence remain unimplemented.]

The finite-candidate value model decodes actions only over valid candidate rows:

$
  #eqs.rl.qh_candidate_token
$

$
  #eqs.rl.qh_masked_argmax
$

For remaining budget one, the dense supervised target is the stored root-normalized immediate gain for every row admitted by `q_train_mask`. For remaining budget two, the primary fixed-target control is

$
  y_t^((2,e))
  =
  r_t^e
  +
  gamma
  max_(i : m_(t+1,i)^"train" = 1)
  r_(t+1,i)^e
$

because every admitted successor candidate already carries a one-step oracle label. This target is fixed, uses no target network, and directly expresses finite-support backward induction for H=2.

The generalized fitted backup is masked Double Q @DoubleDQN-vanHasselt2015. Here $d_t=1$ at horizon termination, budget termination, or when no valid successor action exists. The boundary value $Q_(0,e)=0$ makes a one-step target non-bootstrapping by definition:

$
  #eqs.rl.qh_doubleq_index
$

$
  #eqs.rl.qh_doubleq_target
$

For an implemented learner, the replay dataset $cal(D)$ contains selected-action transition rows with state, target, requested residual horizon, action, immediate target reward, successor state, validity masks, terminal flag, and an explicit state/source protocol:

$
  #eqs.rl.qh_loss
$

Double Q is a generalized H>2 or sparse-future-label learner and an H=2 ablation; it is not assumed superior to the exact H=2 target. Offline support must be reported by behavior policy, candidate family, target, scene, and step because only selected actions have materialized successors. A target network can reduce one maximization bias but cannot repair unsupported actions or information missing from the actor state.

#figure(
  image(
    "../../figures/qh_learning_evidence_loop.pdf",
    width: 100%,
  ),
  caption: [Factual replay lineage and finite-horizon learning roles. Panel A contains implemented evidence: every candidate row admitted by `q_train_mask` may carry a one-step label, exact H=2 targets additionally require a labelled successor table, and general TD admission requires factual transition linkage. Panel B's masked Double-Q computation is implemented as a development tracer but remains an ablation until compared against fixed H=2 supervision and evaluated under a frozen state protocol.],
) <fig:qh-rollout-replay-doubleq>

The H=2 development tracer may establish optimization and systems readiness only. Confirmatory interpretation requires a canonical V0 corpus, cross-stage learning-contract equality, checkpoint compatibility, a frozen actor-state protocol, candidate-support diagnostics, and matched held-out endpoint oracle re-evaluation. A dynamic-state claim additionally requires selected-observation fusion and no-future-observation leakage tests.