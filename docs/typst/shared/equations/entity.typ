#import "../symbols.typ": symb

#let entity = (
  objective: $
    op("RRI")_"total" (q)
    =
    sum_(e in #symb.entity.E)
    #(symb.entity.w) _e dot #(symb.oracle.rri) _e
    +
    #symb.entity.lambda_scene dot #symb.oracle.rri
  $,
  target_descriptor: $
    #symb.entity.target_desc
    =
    op("Enc")_"tgt" (
      hat(bold(B))_e,
      hat(bold(y))_e,
      hat(pi)_e,
      A_e^"proj",
      n_e^"semi",
      n_e^"EVL",
      omega_e^"EVL",
      ell_e^"src",
      bold(T)_(r_t,e),
      bold(T)_(c_t,e)
    )
  $,
  target_identity_iou: $
    mu_"id" (hat(e), e)
    =
    op("IoU")_"3D" (hat(bold(B))_(hat(e)), bold(B)_e)
  $,
  target_identity_acceptance: $
    a_"id" (hat(e)) = 1
    op("iff")
    cases(
      mu_1 >= tau_"IoU",
      mu_1 - mu_2 >= tau_"gap",
    )
  $,
  target_match_score: $
    mu(hat(e), e)
    =
    kappa(hat(y)_(hat(e)), y_e)
    dot op("IoU")_"3D" (hat(bold(B))_(hat(e)), bold(B)_e)
    dot sigma(A_(hat(e))^"proj", n_(hat(e))^"semi", n_(hat(e))^"EVL")
  $,
  target_match_selection: $
    (e^star, mu_1, mu_2, g_mu)
    =
    (
      op("argmax", limits: #true)_(e in cal(E)) mu(hat(e), e),
      mu(hat(e), e^star),
      op("max", limits: #true)_(e in cal(E), e != e^star) mu(hat(e), e),
      mu_1 - mu_2
    )
  $,
  target_match_acceptance: $
    a_"match" (hat(e)) = 1
    op("iff")
    cases(
      kappa(hat(y)_(hat(e)), y_(e^star)) = 1,
      mu_1 >= tau_mu,
      g_mu >= tau_"gap",
      n_(hat(e))^"semi" + n_(hat(e))^"EVL" >= tau_"support",
    )
  $,
  target_error: $
    #symb.entity.target_error
    =
    d(C_e (#symb.obs.points_t), #symb.ase.mesh_target)
    =
    #symb.entity.target_error_pm
    +
    #symb.entity.target_error_mp
  $,
  target_rri_reward: $
    #symb.entity.target_reward
    =
    (#symb.entity.target_error - #symb.entity.target_error_next)
    /
    (#symb.entity.target_error_0 + epsilon)
  $,
  state_relative_rri: $
    r_(t,"state")^e
    =
    (#symb.entity.target_error - #symb.entity.target_error_next)
    /
    (#symb.entity.target_error + epsilon)
  $,
  finite_horizon_return: $
    #symb.entity.return_h
    =
    sum_(k=0)^(H - 1) gamma^k r_(t+k)^e
  $,
  endpoint_gain: $
    #symb.entity.endpoint_gain
    =
    (#symb.entity.target_error_0 - #symb.entity.target_error_H)
    /
    (#symb.entity.target_error_0 + epsilon)
  $,
  log_gain: $
    #symb.entity.log_gain
    =
    log(#symb.entity.target_error_0 + epsilon)
    -
    log(#symb.entity.target_error_H + epsilon)
  $,
  lookahead_headroom: $
    #symb.entity.lookahead_headroom
    =
    J_e^((H)) (pi_"oracle-look")
    -
    J_e^((H)) (pi_"oracle-1")
  $,
  q_recovery: $
    #symb.entity.q_recovery
    =
    (
    J_e^((H)) (pi_Q)
    -
    J_e^((H)) (pi_"learned-1")
    )
    /
    (
    J_e^((H)) (pi_"oracle-look")
    -
    J_e^((H)) (pi_"learned-1")
    +
    epsilon
    )
  $,
)
