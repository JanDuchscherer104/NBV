// Reinforcement-learning state, action, value, and rollout notation.
#let rl = (
  // Generic reinforcement-learning state.
  s: $s$,
  // Generic observation emitted by the environment.
  o: $o$,
  // Generic action selected by a policy.
  a: $a$,
  // Generic immediate reward.
  r: $r$,
  // Generic cumulative return.
  G: $G$,
  // Generic state-action value function.
  Q: $Q$,
  // Generic state-value function.
  V: $V$,
  // Policy over available actions.
  pi: $pi$,
  // Generic advantage function.
  A: $A$,
  // Finite rollout or planning horizon.
  H: $H$,
  // Temporal discount factor.
  gamma: $gamma$,
  // Markov decision process specialized to NBV selection.
  mdp_nbv: $cal(M)_"NBV"$,
  // State-dependent feasible action set.
  action_set: $cal(A)(s_t)$,
  // Feasible action set at rollout step t.
  action_set_t: $cal(A)_t$,
  // Environment transition operator.
  transition: $T$,
  // History-only state available at rollout step t.
  s_hist: $s_t^"hist"$,
  // Offline-data state available at rollout step t.
  s_off: $s_t^"off"$,
  // Actor-visible observation state at rollout step t.
  s_obs: $s_t^"obs"$,
  // Zero-cost counterfactual state at rollout step t.
  s_cf0: $s_t^"cf0"$,
  // Zero-cost counterfactual state after the selected action.
  s_cf0_next: $s_(t+1)^"cf0"$,
  // Counterfactual state augmented with rendered geometry.
  s_cf_geom: $s_t^"cf+"$,
  // Privileged oracle state used only for labels or analysis.
  s_oracle: $s_t^"oracle"$,
  // Learned embedding of the rollout state at step t.
  state_emb: $bold(h)_t$,
  // Target-specific immediate reward at step t.
  reward_target: $r_t^e$,
  // Finite-horizon return starting at step t.
  return_h: $G_t^((H))$,
  // Horizon-conditioned action-value function.
  qh: $Q_H$,
  // Learned horizon-conditioned Q function with parameters theta.
  qh_theta: $Q_(H,theta)$,
  // Frozen or lagged target-network Q function.
  qh_target: $Q_(H,theta^-)$,
  // Scalar validity mask for candidate i at step t.
  validity_mask: $m_(t,i)$,
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
  // Optional entity-memory component of a factored rollout state.
  e: $bold(e)$,
  // Remaining-budget component of a factored rollout state.
  b: $b$,
  // Acquisition cost assigned to trajectory tau.
  acquisition_cost: $C(tau)$,
  // Finite unordered table of candidate poses at step t.
  candidate_table: $cal(Q)_t$,
  // Compatibility name for the finite candidate set at step t.
  candidate_set: $cal(Q)_t$,
  // Learned token for candidate i at rollout step t.
  candidate_token: $bold(u)_(t,i)$,
  // Candidate pose i at rollout step t.
  candidate_qti: $q_(t,i)$,
  // Vector of candidate-validity indicators at step t.
  candidate_mask: $bold(m)_t$,
  // Vector of candidate invalidity-reason codes at step t.
  invalid_reasons: $bold(rho)_t$,
  // Model input tensor containing candidate features at step t.
  candidate_features: $bold(X)_t^"cand"$,
  // Weight vector for the Q-learning objective.
  q_weight: $bold(w)_Q$,
  // Selected target/entity identifier at step t.
  target: $e_t$,
  // Remaining acquisition budget at step t.
  budget: $b_t$,
  // Action selected by the theta-parameterized policy.
  selected_action_theta: $a_t^theta$,
  // Temporal-difference regression target at step t.
  td_target: $y_t$,
  // Q-function training loss for parameters theta.
  q_loss: $cal(L)_Q (theta)$,
)
