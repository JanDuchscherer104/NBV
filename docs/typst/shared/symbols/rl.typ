// Reinforcement-learning state, action, value, and rollout notation.
#let rl = (
  // Generic reinforcement-learning state.
  s: $s$,
  // Generic observation emitted by the environment.
  o: $o$,
  // Generic action selected by a policy.
  a: $a$,
  // Generic reward; plain r also labels the rig frame and VIN RRI proxy.
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
  // Finite horizon; glyph H can collide with `shape.H` image height.
  H: $H$,
  // Temporal discount factor.
  gamma: $gamma$,
  // Small positive numerical stabilizer used in denominators and logarithms.
  epsilon: $epsilon$,
  // Markov decision process specialized to NBV selection.
  mdp_nbv: $cal(M)_"NBV"$,
  // State-dependent feasible action set.
  action_set: $cal(A)(s_t)$,
  // Feasible action set at rollout step t.
  action_set_t: $cal(A)_t$,
  // Reserved transition operator; glyph T also denotes `shape.Tlen` and bold transforms.
  transition: $T$,
  // History-only state available at rollout step t.
  s_hist: $s_t^"hist"$,
  // Offline-data state available at rollout step t.
  s_off: $s_t^"off"$,
  // Reserved actor-visible state; no direct authored use in the 2026-08-14 audit.
  s_obs: $s_t^"obs"$,
  // Zero-cost counterfactual state at rollout step t.
  s_cf0: $s_t^"cf0"$,
  // Reserved next counterfactual state; no direct authored use in the 2026-08-14 audit.
  s_cf0_next: $s_(t+1)^"cf0"$,
  // Counterfactual state augmented with rendered geometry.
  s_cf_geom: $s_t^"cf+"$,
  // Privileged oracle state used only for labels or analysis.
  s_oracle: $s_t^"oracle"$,
  // Reserved rollout-state embedding; no direct authored use in the 2026-08-14 audit.
  state_emb: $bold(h)_t$,
  // Unused duplicate of canonical `entity.target_reward`; prefer the entity owner.
  reward_target: $r_t^e$,
  // Unused duplicate of canonical `entity.return_h`; prefer the entity owner.
  return_h: $G_t^((H))$,
  // Horizon-conditioned action-value function.
  qh: $Q_H$,
  // Learned horizon-conditioned Q function with parameters theta.
  qh_theta: $Q_(H,theta)$,
  // Reserved lagged target-network Q; no direct authored use in the 2026-08-14 audit.
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
  // Reserved entity-memory component; no direct authored use in the 2026-08-14 audit.
  e: $bold(e)$,
  // Remaining-budget component of a factored rollout state.
  b: $b$,
  // Reserved trajectory-acquisition cost; no direct authored use in the 2026-08-14 audit.
  acquisition_cost: $C(tau)$,
  // Canonical RL candidate table; same rendered set as `oracle.candidates_t`.
  candidate_table: $cal(Q)_t$,
  // Unused compatibility alias for `candidate_table`; migrate or prune after registry review.
  candidate_set: $cal(Q)_t$,
  // Learned token for candidate i at rollout step t.
  candidate_token: $bold(u)_(t,i)$,
  // Candidate pose i at rollout step t.
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
  // Q-function training loss for parameters theta.
  q_loss: $cal(L)_Q (theta)$,
)
