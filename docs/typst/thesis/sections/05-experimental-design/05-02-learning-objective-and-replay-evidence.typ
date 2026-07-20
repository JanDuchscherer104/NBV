#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status
#import "@preview/booktabs:0.0.4": *

== Replay Eligibility and Learning Gate

The factual rollout tables determine which records may supervise each learning problem. `valid_action_mask` defines actor-selectable actions. The stricter `q_train_mask` additionally requires a valid target/GT label state and finite target-root-gain and diagnostic target-RRI labels. Masked rows remain available for support and failure analysis but cannot enter action selection, supervised loss, or bootstrap maximization.

All eligible candidate rows can support one-step supervision. Finite-horizon temporal-difference supervision is narrower: the factual selected action must have a stored reward, successor step identifier, terminal flag, and discount, and the successor must expose a reproducible candidate table and hard mask. The derived `q_h/` arrays align these fields on a padded state--candidate view; they do not create labels for unobserved transitions. The replay pipeline in @fig:qh-rollout-replay-doubleq visualizes this distinction.

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
    [`q_train_mask`], [admit one-step labels],
    [actor-selectable rows with valid target state and finite target labels],
    [selected transitions], [admit TD linkage],
    [reward, successor id, terminal flag, discount, and successor mask],
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
    [Oracle data], [target labels, masks, lineage, and replay validation],
    [held-out coverage and matched endpoint evaluation],
    [Myopic control], [scene-level VIN substrate],
    [actor-visible target-conditioned scorer and frozen checkpoint],
    [#symb.rl.qh], [selected-transition tensors and TD linkage],
    [implemented learner, frozen checkpoint, and oracle-rescored policy],
    [Policy claim], [train-only feasibility pilots],
    [completed held-out paired comparison under equal budget], bottomrule(),
  ),
  caption: [Learning-readiness gates. Data-contract evidence does not substitute for an implemented and evaluated policy.],
) <tab:thesis-learning-readiness>

#thesis_status(
  implementation: "planned",
  evidence: "pending",
  citation: [@DoubleDQN-vanHasselt2015],
  source: "aria_nbv/aria_nbv/rollouts/zarr_store.py; aria_nbv/aria_nbv/vin/models/target_finite_horizon.py",
  gate: [finite-horizon reader, learner, checkpoint, and held-out oracle re-evaluation],
)[The replay tensors required for a masked Double-Q learner exist; the learner and policy evidence do not.]

The intended finite-candidate value model decodes actions only over valid candidate tokens:

$
  #eqs.rl.qh_candidate_token
$

$
  #eqs.rl.qh_masked_argmax
$

The planned first backup is fitted masked Double-Q @DoubleDQN-vanHasselt2015. Here $d_t=1$ at horizon termination, budget termination, or when no valid successor action exists. The boundary value $Q_(0,e)=0$ makes a one-step target non-bootstrapping by definition:

$
  #eqs.rl.qh_doubleq_index
$

$
  #eqs.rl.qh_doubleq_target
$

For an implemented learner, the replay dataset $cal(D)$ contains selected-action transition rows with state, action, immediate target reward, successor state, validity masks, and terminal flags:

$
  #eqs.rl.qh_loss
$

#figure(
  image(
    "../../figures/qh_learning_evidence_loop.pdf",
    width: 100%,
  ),
  caption: [Selected-transition replay contract for #symb.rl.qh. All valid candidates can receive one-step oracle target labels, but bootstrapped finite-horizon targets require materialized selected actions, successor counterfactual state, regenerated successor candidate tables, masks, terminal flags, and masked Double-Q targets.],
) <fig:qh-rollout-replay-doubleq>

The repository currently implements the replay and mask contract but not the finite-horizon learner. Consequently, rollout audits may establish data readiness and oracle headroom, whereas #symb.rl.qh policy performance remains outside the supported evidence until a learner and matched held-out evaluation exist.
