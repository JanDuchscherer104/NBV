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
  // Actor-visible observation and action history available before decision step t.
  history: $cal(H)_t$,
  // Frozen decision protocol: generator, target source, state map, action support, reward, discount, and horizon.
  decision_protocol: $Xi$,
  // Representation produced from the admitted actor-visible history by state map sigma.
  representation: $z_t^sigma$,
  // State-construction map from actor-visible history to the scorer representation.
  representation_map: $phi_sigma$,
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
  // Architecture-neutral actor-visible counterfactual state target at rollout step t.
  s_cf0: $s_t^"cf0"$,
  // Implemented pose-history actor state used by the qh_cf0_v1 profile.
  s_pose: $s_t^"S0-pose"$,
  // Implemented privileged selected-surface control state.
  s_surface: $s_t^"S1-surface"$,
  // Planned actor-visible ray-aware state; a candidate realization of the scientific state target.
  s_ray: $s_t^"S2-ray"$,
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
  // Strictly causal prefix of previously selected poses at decision step t.
  selected_pose_prefix: $bold(H)_t^"pose"$,
  // Strictly causal prefix after the selected transition.
  selected_pose_prefix_next: $bold(H)_(t+1)^"pose"$,
  // Unused duplicate of canonical `entity.target_reward`; prefer the entity owner.
  reward_target: $r_t^e$,
  // Unused duplicate of canonical `entity.return_h`; prefer the entity owner.
  return_h: $G_t^((H))$,
  // Bounded family of horizon-conditioned action-value functions.
  qh: $Q_H$,
  // Action-mask-independent conditional candidate value emitted by the scorer.
  conditional_q: $Q_(h,theta,e,i)^"cond"$,
  // Learned representation- and protocol-conditioned value predictor.
  learned_q: $hat(Q)_(theta,h)^(sigma,Xi)$,
  // Support-conditioned ranking score reserved for candidate-set interaction models.
  support_score: $U_(theta,h)^Xi$,
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
  // Scalar validity mask for candidate i at step t.
  validity_mask: $m_(t,i)$,
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
  // Actor/oracle source-provenance role for candidate evidence.
  source_role: $ell_(t,i)^"src"$,
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
  // Exact two-step target using factual dense successor one-step rewards.
  exact_q2_target: $y_t^((2,"exact"))$,
  // Learned-recursion target error against the exact two-step control.
  q2_recursion_error: $epsilon_t^((2))$,
  // Q-function training loss for parameters theta.
  q_loss: $cal(L)_Q (theta)$,
)
