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
    mu_"IoU" (hat(e), e)
    =
    op("IoU")_"3D" (hat(bold(B))_(hat(e)), bold(B)_e)
  $,
  target_identity_threshold: $
    tau_"IoU" = 0.20
  $,
  target_identity_qualified_count: $
    n_"qual" (hat(e))
    =
    op("card") ( {
      e in #symb.entity.E :
      kappa(hat(y)_(hat(e)), y_e) = 1
      and mu_"IoU" (hat(e), e) > tau_"IoU"
    } )
  $,
  target_identity_acceptance: $
    a_"id" (hat(e)) = 1
    op("iff")
    n_"qual" (hat(e)) = 1
  $,
  target_match_selection: $
    e^star = e
    op("iff")
    n_"qual" (hat(e)) = 1
    and kappa(hat(y)_(hat(e)), y_e) = 1
    and mu_"IoU" (hat(e), e) > tau_"IoU"
  $,
  target_match_acceptance: $
    a_"match" (hat(e)) = 1
    op("iff")
    n_"qual" (hat(e)) = 1
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
  state_relative_rri: $
    r_(t,"state")^e
    =
    (#symb.entity.target_error - #symb.entity.target_error_next)
    /
    (#symb.entity.target_error + epsilon)
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
