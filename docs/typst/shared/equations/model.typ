#import "../symbols.typ": symb

#let model = (
  qh_input_contract: $
    cal(I)_(t,e)
    =
    (
      #symb.scene.scene_memory_t,
      bold(T)_(r arrow.l e),
      bold(a)_e,
      {bold(T)_(r arrow.l c_i), bold(T)_(c_t arrow.l c_i),
       bold(T)_(c_i arrow.l e), #symb.rl.candidate_row_mask}_(i=1)^(#symb.shape.Nq),
      {bold(T)_(c_t arrow.l c_j)}_(j<t),
      #symb.rl.budget,
      #symb.rl.requested_horizon
    )
  $,
  qh_frozen_interface: $
    f_theta(
      #symb.rl.s_pose,
      bold(T)_(r arrow.l e),
      bold(a)_e,
      {q_(t,i)}_(i=1)^(#symb.shape.Nq),
      #symb.rl.requested_horizon
    )
    ->
    ({Q_(h,theta,e,i)^"cond"}_(i=1)^(#symb.shape.Nq),
     {ell_(t,i)^"feas"}_(i=1)^(#symb.shape.Nq))
  $,
  qh_target_token: $
    #symb.model.target_token
    =
    op("TargetProj") (
      op("concat") (
        op("PoseEnc") (bold(T)_(r arrow.l e)),
        bold(a)_e
      )
    )
  $,
  candidate_pose_context: $
    #symb.model.candidate_physical_token
    = op("PhysicalProj") (
      op("concat") (
        op("PoseEnc") (bold(T)_(r arrow.l c_i)),
        op("PoseEnc") (bold(T)_(c_t arrow.l c_i)),
        #symb.scene.scene_memory_t
      )
    )
  $,
  candidate_row_features: $
    #symb.model.candidate_row
    = op("ValueQueryProj") (
      op("concat") (
        #symb.model.candidate_physical_token,
        op("PoseEnc") (bold(T)_(c_i arrow.l e))
      )
    )
  $,
  qh_set_encoder: $
    {bold(u)_(t,i)}_(i=1)^(#symb.shape.Nq)
    =
    E_"set" (
      {
        op("concat") (#symb.model.candidate_row, #symb.model.target_token, bold(H)_t)
      }_(i=1)^(#symb.shape.Nq),
      bold(m)_t
    )
  $,
  qh_state_fusion_controls: $
    bold(Z)_t
    &=
    (
      #symb.scene.scene_memory_t,
      #symb.model.target_token,
      bold(h)_t^"hist",
      op("Emb") (#symb.rl.budget / #symb.rl.H_max),
      op("Emb") (#symb.rl.requested_horizon / #symb.rl.H_max)
    ) \
    bold(c)_(t,i)^"A0"
    &=
    op("MLP")_"A0" (
      op("concat") (#symb.model.candidate_row, op("vec")(bold(Z)_t))
    ) \
    bold(c)_(t,i)^"A1"
    &=
    op("CrossAttn")_"A1" (#symb.model.candidate_row, bold(Z)_t, bold(Z)_t) \
    #symb.rl.candidate_token^"Ak"
    &=
    op("concat") (
      #symb.model.candidate_row,
      bold(c)_(t,i)^"Ak",
      #symb.model.candidate_row dot bold(c)_(t,i)^"Ak"
    ),
    quad "Ak" in {"A0", "A1"}
  $,
  qh_history_controls: $
    #symb.model.history_pose_feature
    &=
    op("PoseEnc") (T_(c_t arrow.l c_j)),
    quad j<t \
    #symb.model.history_relative_age
    &=
    (t-1-j) / #symb.rl.H_max \
    #symb.model.history_token^"H0"
    &=
    op("HistProj") (
      1 / max(1,t) sum_(j<t) #symb.model.history_pose_feature
    ) \
    #symb.model.history_token^"H1"
    &=
    op("HistProj") (
      op("LastValid") (
        op("CausalTransformer") (
          [bold(e)_"empty",
           {#symb.model.history_pose_feature + g(#symb.model.history_relative_age)}_(j<t)]
        )
      )
    )
  $,
  qh_cfplus_h0_control: $
    op("Struct")(bold(o)_t) = op("Struct")(bold(o)'_t)
    quad arrow.r.double quad
    f_theta^"CF+-H0"(
      #symb.rl.s_pose,
      bold(o)_t,
      #symb.entity.target_desc,
      {q_(t,i)}_(i=1)^(#symb.shape.Nq),
      #symb.rl.requested_horizon
    )
    =
    f_theta^"CF+-H0"(
      #symb.rl.s_pose,
      bold(o)'_t,
      #symb.entity.target_desc,
      {q_(t,i)}_(i=1)^(#symb.shape.Nq),
      #symb.rl.requested_horizon
    )
  $,
  qh_s1_selected_surface: $
    bold(p)_(t,j,u)^(c_t)
    &=
    T_(c_t arrow.l r) T_(r arrow.l c_j)
    pi^(-1)(u, D_(j,u)^"sel"),
    quad j<t \
    bold(z)_(t,j,u)
    &=
    phi_"pt"(bold(p)_(t,j,u)^(c_t) / sigma_"xyz") \
    bold(g)_t^"S1"
    &=
    [op("Mean") bold(z), op("Max") bold(z),
      rho_t^"present", rho_t^"pixel", rho_t^"view"] \
    #symb.scene.scene_memory_t^"S1"
    &=
    #symb.scene.scene_memory_t^"root"
    + W_"pt" bold(g)_t^"S1",
    quad W_"pt"^(0) = 0
  $,
)
