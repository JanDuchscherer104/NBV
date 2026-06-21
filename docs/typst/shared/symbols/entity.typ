#let entity = (
  // Entity set (objects of interest).
  E: $cal(E)$,
  // Predicted target bounding box
  B_pred: $hat(bold(B))_e$,
  // GT target bounding box.
  B_gt: $bold(B)_e$,
  // Entity-weight vector; use components as `#(symb.entity.w)_e`.
  w: $bold(w)$,
  // Mixing weight for the scene-level term.
  lambda_scene: $lambda_"scene"$,
  // Weighted objective (global + entity-specific terms).
  rri_total: $op("RRI")_"total"$,
  // Target/entity-specific RRI.
  rri_e: $op("RRI")_e$,
  // Observed or predicted target-hypothesis bundle available to the actor.
  target_hyp_pred_t: $bold(O)_t^"pred"$,
  // Actor-visible target descriptor.
  target_desc: $bold(z)_e$,
  // Target-specific reconstruction error and derived rollout metrics.
  target_error: $Delta_t^e$,
  target_error_pm: $D_(P -> M,t)^e$,
  target_error_mp: $D_(M -> P,t)^e$,
  target_error_next: $Delta_(t+1)^e$,
  target_error_0: $Delta_0^e$,
  target_error_H: $Delta_H^e$,
  target_reward: $r_t^e$,
  return_h: $G_t^((H))$,
  endpoint_gain: $J_e^((H))$,
  log_gain: $J_(e,"log")^((H))$,
  lookahead_headroom: $Delta_"look"$,
  q_recovery: $eta_Q$,
)
