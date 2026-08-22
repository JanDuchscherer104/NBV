#import "../symbols.typ": symb

#let rl = (
  mdp: $
    cal(M) = (cal(S), cal(A), P, #symb.rl.r, gamma)
  $,
  nbv_mdp: $
    #symb.rl.mdp_nbv = (cal(S), cal(A), T, r_e, #symb.rl.gamma, #symb.rl.H)
  $,
  nbv_process_tuple: $
    cal(M)_"NBV"
    =
    (
      cal(S)^"hist",
      cal(S)^"cf0",
      cal(S)^"oracle",
      {cal(A)_t},
      T,
      r_t^e,
      gamma,
      H
    )
  $,
  evidence_chain: $
    cal(U)_"cov/unc" -> hat(r)_t^e (i) -> #symb.entity.target_reward -> #symb.entity.return_h -> #symb.rl.qh_theta
  $,
  candidate_row_equivariance: $
    f_theta (Pi bold(X)_t, Pi bold(m)_t)
    =
    Pi f_theta (bold(X)_t, bold(m)_t)
  $,
  candidate_mask_isolation: $
    op("Mask") (bold(X)_t, bold(m)_t)
    =
    op("Mask") (bold(X)'_t, bold(m)_t)
    quad arrow.r.double quad
    op("Mask") (f_theta (bold(X)_t, bold(m)_t), bold(m)_t)
    =
    op("Mask") (f_theta (bold(X)'_t, bold(m)_t), bold(m)_t)
  $,
  masked_candidate_selection: $
    cal(A)_t
    =
    {i in {1, dots, #symb.shape.Nq} : m_(t,i)=1},
    quad
    a_t^theta
    =
    op("argmax", limits: #true)_(i in cal(A)_t) f_(theta,i)(bold(X)_t, bold(m)_t)
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
    in
    cal(S)^"hist"
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
    in cal(S)^"cf0"
  $,
  s_pose: $
    #symb.rl.s_pose
    =
    (
      cal(S)_"root"^"VIN",
      #(symb.vin.field_v)^"root",
      (bold(T)_(r,e), bold(l)_e),
      #symb.oracle.candidates_t,
      #symb.rl.validity_mask,
      bold(H)_t^"pose",
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
  s_cf_gt_carrier: $
    #symb.rl.s_cf_gt_carrier
    =
    (
      #symb.rl.s_pose,
      (#symb.obs.depth, #symb.obs.vis, cal(K), bold(T)_"root<-cam")_(1:t)^"sel"
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
    in cal(S)^"oracle"
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
  replay_transition: $
    (x_(t+1), bold(H)_(t+1), b_(t+1), cal(Q)_(t+1))
    =
    op("Step")(
      x_t,
      bold(H)_t,
      b_t,
      q_(t,a_t),
      xi_t
    )
  $,
  counterfactual_transition: $
    #(symb.oracle.points) _(t+1) = #(symb.oracle.points) _t union #(symb.oracle.points) _(q_t)
  $,
  marginal_target_rri: $
    #symb.entity.target_rri_marginal
    =
    (#symb.entity.target_error - Delta_(t|i)^e)
    /
    max(#symb.entity.target_error, epsilon)
  $,
  cumulative_target_rri: $
    #symb.entity.target_rri_cumulative
    =
    sum_(k=0)^(t-1) op("RRI")_(k,a_k)^e
  $,
  target_root_gain_reward: $
    #symb.entity.target_reward
    =
    (#symb.entity.target_error - #symb.entity.target_error_next)
    /
    max(#symb.entity.target_error_0, epsilon)
  $,
  cumulative_target_root_gain: $
    #symb.entity.target_root_gain_cumulative
    =
    sum_(k=0)^(t-1) r_k^e
    =
    (#symb.entity.target_error_0 - #symb.entity.target_error)
    /
    max(#symb.entity.target_error_0, epsilon)
  $,
  finite_horizon_return: $
    G_(t,e)^((h))
    =
    sum_(k=0)^(min(h, b_t) - 1) #symb.rl.gamma^k r_(t+k)^e
  $,
  q_h: $
    Q_(h,e) (s_t, i)
    =
    bb(E)[G_(t,e)^((h)) | s_t, a_t=i],
    quad
    i in cal(A)_t,
    quad
    1 <= h <= b_t,
    quad
    Q_(0,e) (s, i) = 0
  $,
  qh_residual_decomposition: $
    b_(psi,i)
    =
    f_psi^"1-step" (s_t^"cf0", #symb.entity.target_desc, q_(t,i)),
    quad
    delta_(theta,t,e,i)^h
    =
    g_theta (cal(I)_(t,e), q_(t,i), h),
    quad
    Q_(h,theta,e,i)
    =
    b_(psi,i)
    +
    delta_(theta,t,e,i)^h
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
  qh_uncentered_residual: $
    Q_(h,theta,e,i)
    =
    hat(r)_psi^e (#symb.rl.s_cf0, #symb.entity.target_desc, #symb.rl.candidate_qti)
    +
    delta_(theta,t,e,i)^h (cal(I)_(t,e), q_(t,i)),
    quad
    cal(L)_delta
    =
    lambda_delta
    (1) / (abs(#symb.rl.action_set_t))
    sum_(j in #symb.rl.action_set_t) (delta_(theta,t,e,j)^h)^2
  $,
  qh_candidate_token: $
    #symb.rl.candidate_token
    =
    op("Enc")_theta (cal(I)_(t,e), q_(t,i))
  $,
  qh_candidate_value: $
    Q_(h,theta,e) (s_t, i)
    =
    #symb.rl.q_weight^top #symb.rl.candidate_token
  $,
  qh_masked_argmax: $
    #symb.rl.selected_action_theta
    =
    op("argmax", limits: #true)_(i : m_(t,i) = 1)
    Q_(h,theta,e) (s_t, i)
  $,
  qh_doubleq_index: $
    B_t^((h,e))
    =
    cases(
      Q_(h-1,theta^-,e) (
        s_(t+1),
        op("argmax", limits: #true)_(i : m_(t+1,i) = 1)
        Q_(h-1,theta,e) (s_(t+1), i)
      ) & "if " h > 1, d_t = 0, sum_i m_(t+1,i) > 0,
      0 & "otherwise"
    )
  $,
  qh_doubleq_target: $
    y_t^((h,e))
    =
    #symb.entity.target_reward
    +
    gamma
    B_t^((h,e))
  $,
  qh_loss: $
    #symb.rl.q_loss
    =
    (
      sum_((s_t,e,h,a_t,r_t^e,s_(t+1),bold(m)_(t+1),d_t) in cal(D))
      m_(t,a_t)^"train"
      (
        Q_(h,theta,e) (s_t, a_t)
        -
        y_t^((h,e))
      )^2
    )
    /
    (
      sum_((s_t,e,h,a_t,r_t^e,s_(t+1),bold(m)_(t+1),d_t) in cal(D)) m_(t,a_t)^"train"
      + epsilon
    )
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
    pi_"cont" (bold(x)_t, bold(ell)_t | s_t, #symb.entity.target_desc)
    =
    pi_"pose" (bold(x)_t | bold(ell)_t, s_t, #symb.entity.target_desc)
    pi_"look" (bold(ell)_t | s_t, #symb.entity.target_desc)
  $,
)
