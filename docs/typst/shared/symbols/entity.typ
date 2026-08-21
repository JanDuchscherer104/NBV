// Symbols for target entities, target geometry, and target-specific objectives.
#let entity = (
  // Entity set (objects of interest).
  E: $cal(E)$,
  // Reserved predicted OBB for entity e; no direct authored use in the 2026-08-14 audit.
  B_pred: $hat(bold(B))_e$,
  // Reserved ground-truth OBB for entity e; no direct authored use in the 2026-08-14 audit.
  B_gt: $bold(B)_e$,
  // Entity-weight vector; use components as `#(symb.entity.w)_e`.
  w: $bold(w)$,
  // Mixing weight for the scene-level term.
  lambda_scene: $lambda_"scene"$,
  // Reserved global/entity objective label; no direct authored use in the 2026-08-14 audit.
  rri_total: $op("RRI")_"total"$,
  // Reserved target-specific RRI label; no direct authored use in the 2026-08-14 audit.
  rri_e: $op("RRI")_e$,
  // Observed or predicted target-hypothesis bundle available to the actor.
  target_hyp_pred_t: $bold(O)_t^"pred"$,
  // Actor-visible target/entity descriptor. The encoder map is not named phi;
  // the descriptor vector is phi_e to match the thesis entity-representation convention.
  target_desc: $bold(phi)_e$,
  // World-space center of the selected target entity.
  center: $bold(p)_e^w$,
  // Target-specific reconstruction error at rollout step t.
  target_error: $Delta_t^e$,
  // Point-to-mesh component of the target reconstruction error at step t.
  target_error_pm: $D_(P -> M,t)^e$,
  // Mesh-to-point component of the target reconstruction error at step t.
  target_error_mp: $D_(M -> P,t)^e$,
  // Target reconstruction error after the next observation.
  target_error_next: $Delta_(t+1)^e$,
  // Target reconstruction error at the rollout start.
  target_error_0: $Delta_0^e$,
  // Target reconstruction error at horizon H.
  target_error_H: $Delta_H^e$,
  // Canonical target reward; `rl.reward_target` is an unused duplicate.
  target_reward: $r_t^e$,
  // Canonical target return; `rl.return_h` is an unused duplicate.
  return_h: $G_t^((H))$,
  // Endpoint target gain across horizon H.
  endpoint_gain: $J_e^((H))$,
  // Log-scaled target gain across horizon H.
  log_gain: $J_(e,"log")^((H))$,
  // Remaining target-error reduction available to the look-ahead policy.
  lookahead_headroom: $Delta_"look"$,
  // Recovery ratio attributed to the learned Q policy.
  q_recovery: $eta_Q$,
)
