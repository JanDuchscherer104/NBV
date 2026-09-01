// Reinforcement-learning state, action, value, and rollout notation.
#let rl = (
  // Generic reinforcement-learning state.
  s: $s$,
  // Generic observation emitted by the environment.
  o: $o$,
  // Generic action selected by a policy.
  a: $a$,
  // Generic reward; use `target_reward` for the thesis target-specific objective.
  r: $r$,
  // Generic cumulative return.
  G: $G$,
  // Factual rollout-chain index used to preserve trajectory heritage.
  rollout_index: $j$,
  // Generic state-action value function.
  Q: $Q$,
  // Generic state-value function.
  V: $V$,
  // Policy over available actions.
  pi: $pi$,
  // Generic advantage function.
  A: $A$,
  // Finite horizon; glyph H can collide with `shape.H` image height.
  H: $H$,
  // Requested residual horizon supplied to a finite-horizon value query.
  requested_horizon: $h$,
  // Maximum supported residual horizon in the scorer/data contract.
  H_max: $H_"max"$,
  // Temporal discount factor.
  gamma: $gamma$,
  // Markov decision process specialized to NBV selection.
  mdp_nbv: $cal(M)_"NBV"$,
  // State-dependent feasible action set.
  action_set: $cal(A)(s_t)$,
  // Selected-action transition operator.
  transition: $cal(T)$,
  // History-only state available at rollout step t.
  s_hist: $s_t^"hist"$,
  // Offline-data state available at rollout step t.
  s_off: $s_t^"off"$,
  // Reserved actor-visible state; no direct authored use in the 2026-08-14 audit.
  s_obs: $s_t^"obs"$,
  // Zero-cost counterfactual state at rollout step t.
  s_cf0: $s_t^"cf0"$,
  // Implemented pose-history actor state used by the qh_cf0_v1 profile.
  s_pose: $s_t^"S0-pose"$,
  // Reserved next counterfactual state; no direct authored use in the 2026-08-14 audit.
  s_cf0_next: $s_(t+1)^"cf0"$,
  // Counterfactual state augmented with rendered geometry.
  s_cf_geom: $s_t^"cf+"$,
  // Implemented privileged selected-depth carrier used by qh_cfplus_gt_depth_v1.
  s_cf_gt_carrier: $s_t^"CF-GT-carrier"$,
  // Privileged oracle state used only for labels or analysis.
  s_oracle: $s_t^"oracle"$,
  // Reserved rollout-state embedding; no direct authored use in the 2026-08-14 audit.
  state_emb: $bold(h)_t$,
  // Target-specific immediate reward at rollout step t.
  target_reward: $r_t^e$,
  // Target-conditioned return from step t over requested residual horizon h.
  return_h: $G_(t,e)^((h))$,
  // Horizon-conditioned candidate-value family represented by one shared scorer.
  qh: $Q_theta(.,.,.,h)$,
  // Action-mask-independent candidate value emitted by the horizon-conditioned scorer.
  conditional_q: $Q_theta(s_t,e,i,h)$,
  // Physical or observed feasibility logit emitted by the scorer's feasibility head.
  feasibility_logits: $ell_(t,i)^"feas"$,
  // Fixed boundary assigning a continuous fitted-Q target to CORAL classes.
  coral_q_edge: $e_k^Q$,
  // Fixed continuous-Q representative used to decode CORAL class mass.
  coral_q_value: $u_k^Q$,
  // Ordinal class assigned to one fitted-Q target.
  coral_q_label: $c_n^Q$,
  // Learned horizon-conditioned Q function with parameters theta.
  qh_theta: $Q_(H,theta)$,
  // Reserved lagged target-network Q; no direct authored use in the 2026-08-14 audit.
  qh_target: $Q_(H,theta^-)$,
  // Materialized candidate row versus structural padding.
  candidate_row_mask: $m_(t,i)^"cand"$,
  // Authoritative physically valid action support.
  action_mask: $m_(t,i)^"act"$,
  // Availability of a finite value label for candidate i at requested horizon h.
  q_label_mask: $m_(t,i)^(Q,h)$,
  // Availability of a trustworthy feasibility label for candidate i.
  feasibility_label_mask: $m_(t,i)^F$,
  // Availability of a factual successor backup for transition t.
  successor_mask: $m_t^"succ"$,
  // Categorical actor/oracle source-provenance role for candidate evidence.
  source_role: $zeta_(t,i)^"src"$,
  // Categorical invalidity reason for candidate i at step t.
  invalid_reason: $rho_(t,i)$,
  // Generic state or metric increment.
  delta: $delta$,
  // Generic invalidity-reason variable.
  rho: $rho$,
  // Generic learned latent variable.
  z: $z$,
  // Pose component of a factored rollout state.
  x: $bold(x)$,
  // Persistent-memory component of a factored rollout state.
  m: $bold(m)$,
  // Reserved entity-memory component; no direct authored use in the 2026-08-14 audit.
  e: $bold(e)$,
  // Remaining-budget component of a factored rollout state.
  b: $b$,
  // Reserved trajectory-acquisition cost; no direct authored use in the 2026-08-14 audit.
  acquisition_cost: $C(tau)$,
  // Canonical finite candidate-action table.
  candidate_table: $cal(Q)_t$,
  // Learned token for candidate i at rollout step t.
  candidate_token: $bold(u)_(t,i)$,
  // Candidate action row i at rollout step t; it carries one proposed endpoint pose.
  candidate_qti: $q_(t,i)$,
  // Reserved candidate-validity vector; no direct authored use in the 2026-08-14 audit.
  candidate_mask: $bold(m)_t$,
  // Reserved invalidity-reason vector; no direct authored use in the 2026-08-14 audit.
  invalid_reasons: $bold(rho)_t$,
  // Reserved candidate-feature tensor; no direct authored use in the 2026-08-14 audit.
  candidate_features: $bold(X)_t^"cand"$,
  // Weight vector for the Q-learning objective.
  q_weight: $bold(w)_Q$,
  // Selected target/entity identifier at step t.
  target: $e_t$,
  // Remaining acquisition budget at step t.
  budget: $b_t$,
  // Action selected by the theta-parameterized policy.
  selected_action_theta: $a_t^theta$,
  // Reserved temporal-difference target; no direct authored use in the 2026-08-14 audit.
  td_target: $y_t$,
  // Exact two-step target using factual dense successor one-step rewards.
  exact_q2_target: $y_t^((2,"exact"))$,
  // Learned-recursion target error against the exact two-step control.
  q2_recursion_error: $epsilon_t^((2))$,
  // Q-function training loss for parameters theta.
  q_loss: $cal(L)_Q (theta)$,
)
