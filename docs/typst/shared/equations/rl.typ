#import "../symbols.typ": symb

#let rl = (
  mdp: $
    cal(M) = (cal(S), cal(A), P, #symb.rl.r, gamma)
  $,
  nbv_mdp: $
    #symb.rl.mdp_nbv = (cal(S), cal(A), T, r_e, #symb.rl.gamma, #symb.rl.H)
  $,
  s_hist: $
    #symb.rl.s_hist
    =
    (
      #symb.obs.img_rgb,
      #symb.obs.pose,
      #symb.obs.points_semi,
      #symb.vin.field_v,
      #symb.rl.target,
      #symb.rl.budget
    )
  $,
  s_off: $
    #symb.rl.s_off
    =
    (
      #(symb.obs.points_semi) _t,
      #symb.ase.traj,
      #symb.oracle.candidates_t,
      #symb.rl.validity_mask,
      #symb.vin.field_v
    )
  $,
  s_cf0: $
    #symb.rl.s_cf0
    =
    (
      #(symb.vin.field_v)^"root",
      #(symb.oracle.points) _t,
      #symb.oracle.candidates_t,
      #symb.rl.validity_mask,
      #symb.rl.invalid_reason,
      #symb.rl.target,
      #symb.rl.budget
    )
  $,
  s_cf_geom: $
    #symb.rl.s_cf_geom
    =
    (
      #symb.rl.s_cf0,
      (#symb.obs.depth, #symb.obs.vis, #symb.obs.points_cf, #symb.obs.face_normal)_(1:t)
    )
  $,
  s_oracle: $
    #symb.rl.s_oracle
    =
    (
      #symb.rl.s_cf_geom,
      #symb.ase.mesh,
      #symb.ase.mesh_target,
      #symb.oracle.depth_q,
      #symb.oracle.points_q,
      #symb.oracle.rri
    )
  $,
  obs_render: $
    #(symb.rl.o) _(t+1)
    =
    cal(G)(#symb.ase.mesh, #(symb.rl.x) _(t+1))
  $,
  memory_update: $
    #(symb.rl.m) _(t+1)
    =
    cal(U)(
      #(symb.rl.m) _t,
      #(symb.rl.o) _(t+1),
      #(symb.rl.x) _(t+1)
    )
  $,
  finite_action_set: $
    #symb.rl.candidate_table = {q_(t,i)}_(i=1)^(#symb.shape.Nq),
    quad
    #symb.rl.action_set_t = {i in {1, dots, #symb.shape.Nq} : m_(t,i) = 1}
  $,
  counterfactual_transition: $
    #(symb.oracle.points) _(t+1) = #(symb.oracle.points) _t union #(symb.oracle.points) _(q_t)
  $,
  target_rri_reward: $
    #symb.rl.reward_target = op("RRI")_e (q_t | #(symb.oracle.points) _t, #symb.ase.mesh_target)
  $,
  finite_horizon_return: $
    #symb.rl.return_h = sum_(k=0)^(#symb.rl.H - 1) #symb.rl.gamma^k r_(t+k)^e
  $,
  q_h: $
    #symb.rl.qh (#symb.rl.s_cf0, #(symb.rl.a) _t)
    =
    bb(E)[G_t^((H)) | s_t = #symb.rl.s_cf0, a_t = #(symb.rl.a) _t]
  $,
  qh_residual: $
    #symb.rl.qh_theta (#symb.rl.s_cf0, #symb.entity.target_desc, #symb.rl.candidate_qti)
    =
    hat(r)_psi^e (#symb.rl.s_cf0, #symb.entity.target_desc, #symb.rl.candidate_qti)
    +
    A_theta^H (#symb.rl.s_cf0, #symb.entity.target_desc, #symb.rl.candidate_table, bold(h)_t, i)
  $,
  qh_coral_interface: $
    p_(t,i,k)^"CORAL"
    &=
    sigma(o_(t,i,k)^"CORAL"),
    quad k=0,dots,K-2 \
    pi_(t,i,k)^"CORAL"
    &=
    p_(t,i,k-1)^"CORAL" - p_(t,i,k)^"CORAL",
    quad p_(t,i,-1)^"CORAL"=1,
    quad p_(t,i,K-1)^"CORAL"=0 \
    hat(r)_psi^e (#symb.rl.s_cf0, #symb.entity.target_desc, #symb.rl.candidate_qti)
    &=
    sum_(k=0)^(K - 1) pi_(t,i,k)^"CORAL" u_k
  $,
  qh_dueling_residual: $
    #symb.rl.qh_theta (#symb.rl.s_cf0, #symb.entity.target_desc, #symb.rl.candidate_qti)
    =
    hat(r)_psi^e (#symb.rl.s_cf0, #symb.entity.target_desc, #symb.rl.candidate_qti)
    +
    V_theta (#symb.rl.s_cf0, #symb.entity.target_desc, bold(H)_t)
    +
    A_(theta,i)^H
    -
    (1) / (abs(#symb.rl.action_set_t))
    sum_(j in #symb.rl.action_set_t) A_(theta,j)^H
  $,
  qh_candidate_token: $
    #symb.rl.candidate_token
    =
    (op("Transformer")_theta (#symb.rl.candidate_features))_i
  $,
  qh_candidate_value: $
    #symb.rl.qh_theta (#symb.rl.s_cf0, #symb.entity.target_desc, #symb.rl.candidate_qti)
    =
    #symb.rl.q_weight^top #symb.rl.candidate_token
  $,
  qh_masked_argmax: $
    #symb.rl.selected_action_theta
    =
    op("argmax", limits: #true)_(i : m_(t,i) = 1)
    #symb.rl.qh_theta (#symb.rl.s_cf0, #symb.entity.target_desc, #symb.rl.candidate_qti)
  $,
  qh_doubleq_index: $
    i^star
    =
    op("argmax", limits: #true)_(i : m_(t+1,i) = 1)
    #symb.rl.qh_theta (#symb.rl.s_cf0_next, #symb.entity.target_desc, q_(t+1,i))
  $,
  qh_doubleq_target: $
    #symb.rl.td_target
    =
    #symb.entity.target_reward
    +
    gamma
    (1 - d_t)
    #symb.rl.qh_target (#symb.rl.s_cf0_next, #symb.entity.target_desc, q_(t+1,i^star))
  $,
  qh_loss: $
    #symb.rl.q_loss
    =
    (1) / (abs(cal(D)))
    sum_((s,a,r,s') in cal(D))
    m_(t,a)
    (
      #symb.rl.qh_theta (#symb.rl.s_cf0, #symb.entity.target_desc, q_(t,a))
      -
      #symb.rl.td_target
    )^2
  $,
  reward_log: $
    #(symb.rl.r) _t
    =
    log(#symb.oracle.err (#(symb.oracle.points) _t, #symb.ase.mesh) + epsilon)
    -
    log(#symb.oracle.err (#(symb.oracle.points) _(t+1), #symb.ase.mesh) + epsilon)
  $,
  reward_geom: $
    #(symb.rl.r) _t^"geom"
    =
    log(#symb.oracle.err (#(symb.oracle.points) _t, #symb.ase.mesh) + epsilon)
    -
    log(#symb.oracle.err (#(symb.oracle.points) _(t+1), #symb.ase.mesh) + epsilon)
    -
    alpha bb(1)["collision"(#(symb.rl.a) _t)]
    -
    beta c(#(symb.rl.a) _t)
  $,
  planner: $
    #(symb.rl.a) _t^star
    =
    op("argmax", limits: #true)_(#(symb.rl.a) _(t:t+H-1))
    sum_(k=0)^(H-1) gamma^k #(symb.rl.r) _(t+k)
  $,
  q_backup: $
    y_t^Q
    =
    #(symb.rl.r) _t
    +
    gamma #(symb.rl.V) ( #(symb.rl.s) _(t+1) )
  $,
  iql_q_loss: $
    cal(L)_(#(symb.rl.Q))^"IQL"
    =
    ( #(symb.rl.Q) ( #(symb.rl.s) _t, #(symb.rl.a) _t ) - y_t^Q )^2
  $,
  cql_loss: $
    cal(L)_(#(symb.rl.Q))^"CQL"
    =
    (1)/(2) ( #(symb.rl.Q) ( #(symb.rl.s) _t, #(symb.rl.a) _t ) - y_t^Q )^2
    +
    alpha (
      op("logsumexp")_(a in cal(A)) #(symb.rl.Q) ( #(symb.rl.s) _t, a )
      -
      #(symb.rl.Q) ( #(symb.rl.s) _t, #(symb.rl.a) _t )
    )
  $,
  return_lambda: $
    #(symb.rl.G) _t^lambda
    =
    (1-lambda) sum_n lambda^(n-1) G_t^(n)
  $,
  leq_loss: $
    cal(L)_(#(symb.rl.V))^"LEQ"
    =
    rho_(tau) (
      #(symb.rl.V) ( #(symb.rl.s) _t ) - #(symb.rl.G) _t^lambda
    )
  $,
  gae: $
    #(symb.rl.A) _t^"GAE"
    =
    sum_(l=0)^(L-1) (gamma lambda)^l #(symb.rl.delta) _(t+l)
  $,
  ppo_clip: $
    cal(L)_(#(symb.rl.pi))^"PPO"
    =
    bb(E)[
      op("min")(
        #(symb.rl.rho) _t #(symb.rl.A) _t,
        op("clip") (#(symb.rl.rho) _t, 1-epsilon, 1+epsilon) #(symb.rl.A) _t
      )
    ]
  $,
  hier_policy: $
    #(symb.rl.z) _t ~ #(symb.rl.pi) _("hi") (z ; #(symb.rl.s) _t),
    quad
    #(symb.rl.a) _t ~ #(symb.rl.pi) _("lo") (a ; #(symb.rl.s) _t, #(symb.rl.z) _t)
  $,
  target_pose_factorization: $
    pi_"cont" (bold(x)_t, bold(ell)_t | s_t, z_e)
    =
    pi_"pose" (bold(x)_t | bold(ell)_t, s_t, z_e)
    pi_"look" (bold(ell)_t | s_t, z_e)
  $,
)
