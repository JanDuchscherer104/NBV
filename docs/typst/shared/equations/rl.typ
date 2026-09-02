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
    f_theta (Pi bold(X)_t, Pi bold(m)_t^"cand")
    =
    Pi f_theta (bold(X)_t, bold(m)_t^"cand")
  $,
  candidate_mask_isolation: $
    op("Mask") (bold(X)_t, bold(m)_t^"cand")
    =
    op("Mask") (bold(X)'_t, bold(m)_t^"cand")
    quad arrow.r.double quad
    op("Mask") (f_theta (bold(X)_t, bold(m)_t^"cand"), bold(m)_t^"cand")
    =
    op("Mask") (f_theta (bold(X)'_t, bold(m)_t^"cand"), bold(m)_t^"cand")
  $,
  masked_candidate_selection: $
    cal(A)_t
    =
    {i in {1, dots, #symb.shape.Nq} : m_(t,i)^"act"=1},
    quad
    a_t^theta
    =
    op("argmax", limits: #true)_(i in cal(A)_t) Q_(h,theta,e) (s_t, i)
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
      #symb.scene.scene_memory_t,
      #symb.entity.target_desc,
      #symb.rl.candidate_table,
      #symb.rl.validity_mask,
      #symb.rl.selected_pose_prefix,
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
      #symb.rl.selected_pose_prefix,
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
    #symb.rl.action_set_t = {i in {1, dots, #symb.shape.Nq} : m_(t,i)^"act" = 1}
  $,
  replay_transition: $
    (x_(t+1), #symb.rl.selected_pose_prefix_next, b_(t+1), cal(Q)_(t+1))
    =
    op("Step")(
      x_t,
      #symb.rl.selected_pose_prefix,
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
    sum_(k=0)^(h - 1) #symb.rl.gamma^k r_(t+k)^e,
    quad 1 <= h <= b_t <= #symb.rl.H_max
  $,
  decision_protocol: $
    #symb.rl.decision_protocol
    =
    (g, tau, sigma, nu_"mask", rho, #symb.rl.gamma, #symb.rl.H_max)
  $,
  q_h: $
    Q_(h,e)^(star,#symb.rl.decision_protocol) (#symb.rl.history, q_(t,i))
    =
    op("sup", limits: #true)_(pi in cal(Pi)^"act")
    bb(E)_pi [G_(t,e)^((h)) | #symb.rl.history, a_t=q_(t,i)],
    quad
    i in cal(A)_t,
    quad
    1 <= h <= b_t <= #symb.rl.H_max,
    quad
    Q_(0,e)^(star,#symb.rl.decision_protocol) (#symb.rl.history, q_(t,i)) = 0
  $,
  qh_representation_map: $
    #symb.rl.representation
    =
    #symb.rl.representation_map (#symb.rl.history)
  $,
  qh_learned_predictor: $
    #symb.rl.learned_q (#symb.rl.representation, e, q_(t,i))
    approx
    Q_(h,e)^(star,#symb.rl.decision_protocol) (#symb.rl.history, q_(t,i)),
    quad "if" #symb.rl.representation "is decision-context sufficient"
  $,
  qh_sufficiency_factorization: $
    Q_(h,e)^(star,#symb.rl.decision_protocol) (#symb.rl.history, q_(t,i))
    =
    Q_(h,e)^(star,sigma,#symb.rl.decision_protocol) (#symb.rl.representation, q_(t,i))
    quad "if" #symb.rl.representation "is decision-context sufficient"
  $,
  support_conditioned_score: $
    #symb.rl.support_score
      (#symb.rl.representation, e, cal(C)_t^"ctx", q_(t,i))
  $,
  qh_scorer_interface: $
    (#symb.rl.conditional_q, #symb.rl.feasibility_logits)
    =
    f_theta (#symb.rl.representation, e, q_(t,i), h),
    quad
    1 <= h <= #symb.rl.budget <= #symb.rl.H_max,
    quad
    h = #symb.rl.budget "when omitted"
  $,
  qh_conditional_mask_independence: $
    (#symb.rl.conditional_q, #symb.rl.feasibility_logits)
    (s_t,e,q_(t,i),h, bold(m)_t)
    =
    (#symb.rl.conditional_q, #symb.rl.feasibility_logits)
    (s_t,e,q_(t,i),h,bold(m)'_t)
  $,
  qh_huber_loss: $
    cal(L)_Q
    =
    (1)/(N_Q)
    sum_(n in cal(D)_Q)
    rho_1 (Q_(n)^"cond" - y_n),
    quad
    rho_1(e) = cases(
      0.5 e^2 & "if" abs(e) <= 1,
      abs(e) - 0.5 & "otherwise"
    )
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
    #symb.rl.coral_q_label
    &=
    sum_(k=0)^(K - 2) bb(1)[y_n > #symb.rl.coral_q_edge],
    quad
    l_(n,k)=bb(1)[#symb.rl.coral_q_label > k] \
    cal(L)_Q^"CORAL"
    &=
    -sum_n sum_(k=0)^(K - 2)
    (l_(n,k) log p_(n,k) + (1-l_(n,k)) log(1-p_(n,k))),
    quad p_(n,k)=sigma(o_(n,k)) \
    pi_(n,k)^"raw"
    &=
    p_(n,k-1)-p_(n,k),
    quad p_(n,-1)=1,
    quad p_(n,K-1)=0 \
    tilde(pi)_(n,k)
    &=
    (max(pi_(n,k)^"raw",0)) /
    (sum_(j=0)^(K - 1) max(pi_(n,j)^"raw",0) + epsilon) \
    Q_n^"cond"
    &=
    sum_(k=0)^(K - 1) tilde(pi)_(n,k) #symb.rl.coral_q_value
  $,
  qh_uncentered_residual: $
    Q_(h,theta,e,i)
    =
    hat(r)_psi^e (#symb.rl.s_cf0, #symb.entity.target_desc, #symb.oracle.candidate_qti)
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
    op("argmax", limits: #true)_(i : m_(t,i)^"act" = 1)
    Q_(h,theta,e) (s_t, i)
  $,
  qh_supported_successor_set: $
    cal(A)_(t+1)^((Q,h-1))
    =
    {i : m_(t+1,i)^"act" = 1 and m_(t+1,i)^(Q,h-1) = 1}
  $,
  qh_doubleq_index: $
    B_t^((h,e))
    =
    cases(
      Q_(h-1,theta^-,e) (
        s_(t+1),
        op("argmax", limits: #true)_(i in cal(A)_(t+1)^((Q,h-1)))
        Q_(h-1,theta,e) (s_(t+1), i)
      ) & "if " h > 1 and d_t = 0 and cal(A)_(t+1)^((Q,h-1)) != emptyset,
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
  qh_exact_q2_target: $
    #symb.rl.exact_q2_target
    =
    r_t^e
    +
    gamma_t
    max_(j : m_(t+1,j)^"train" = 1)
    r_(t+1,j)^e
  $,
  qh_exact_q2_error: $
    #symb.rl.q2_recursion_error
    =
    abs(
      y_t^((2,"recursive"))
      -
      #symb.rl.exact_q2_target
    ),
    quad
    #symb.rl.q2_recursion_error
    <=
    tau_"abs"
    +
    tau_"rel"
    abs(#symb.rl.exact_q2_target)
  $,
  qh_loss: $
    #symb.rl.q_loss
    =
    (
    sum_((s_t,e,h,a_t,r_t^e,s_(t+1),bold(m)_(t+1)^"act",d_t) in cal(D))
    m_(t,a_t)^(Q,h)
    (
      Q_(h,theta,e) (s_t, a_t)
      -
      y_t^((h,e))
    )^2
    )
    /
    (
    sum_((s_t,e,h,a_t,r_t^e,s_(t+1),bold(m)_(t+1)^"act",d_t) in cal(D)) m_(t,a_t)^(Q,h)
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
