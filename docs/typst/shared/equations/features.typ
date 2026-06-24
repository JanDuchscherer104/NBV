#import "../symbols.typ": symb

#let features = (
  film: $
    #(symb.vin.global) _i^"film"
    = (1 + #(symb.vin.gamma) _i) dot.op #(symb.vin.global) _i + #(symb.vin.beta) _i
  $,
  semidense_validity: $
    m_(i,j)
    =
    bb(1)["finite"] dot bb(1)[z_(i,j) > 0] dot
    bb(1)[0 <= u_(i,j) < W_i] dot bb(1)[0 <= v_(i,j) < H_i]
  $,
  semidense_visibility: $
    v_i^("sem")
    = (sum_j w_(i,j) m_(i,j)) / (sum_j w_(i,j) f_(i,j))
  $,
  direction_unit: $
    bold(d)_k (bold(v))
    =
    (bold(c)_k - bold(v)) / (norm(bold(c)_k - bold(v))_2)
  $,
  direction_memory_sh: $
    #symb.spatial.dir_memory (bold(v))
    =
    sum_(k < t) w_k (bold(v))
    #symb.spatial.sh_basis (bold(d)_k (bold(v)))
  $,
  direction_memory_moment: $
    #symb.spatial.dir_moment (bold(v))
    =
    sum_(k < t) w_k (bold(v))
    bold(d)_k (bold(v)) (bold(d)_k (bold(v)))^top
  $,
  direction_novelty: $
    nu_(t,i)^"dir" (bold(v))
    =
    1 -
    (
    (bold(d)_(t,i) (bold(v)))^top
    #symb.spatial.dir_moment (bold(v))
    bold(d)_(t,i) (bold(v))
    )
    /
    (op("tr") (#symb.spatial.dir_moment (bold(v))) + epsilon)
  $,
  evl_local_support_read: $
    #symb.scene.evl_support_frac
    =
    (1) / (K) sum_(k=1)^K
    bb(1)[x_(t,i,k) in cal(V)_0^"EVL"],
    quad
    #symb.scene.evl_support_token
    =
    op("Pool")({#symb.vin.field_evl_0 (x_(t,i,k)) : x_(t,i,k) in cal(V)_0^"EVL"})
  $,
  logged_point_projection: $
    bold(p)_(j,c,tau)
    =
    bold(T)_(w)^(c_tau) bold(p)_j,
    quad
    (u_(j,tau), v_(j,tau), alpha_(j,tau))
    =
    pi_(kappa_tau) (bold(p)_(j,c,tau))
  $,
  logged_feature_sample: $
    bold(f)_(j,tau)
    =
    op("Sample") (
      bold(F)_tau^"2D",
      u_(j,tau),
      v_(j,tau)
    )
  $,
  logged_visibility_gate: $
    m_(j,tau)^"vis"
    =
    alpha_(j,tau)
    m_(j,tau)^"obs/depth"
    m_(j,tau)^"quality"
  $,
  logged_feature_pool: $
    w_(j,tau)
    =
    m_(j,tau)^"vis" q_j r_(j,tau),
    quad
    overline(bold(f))_j
    =
    (sum_tau w_(j,tau) bold(f)_(j,tau))
    /
    (sum_tau w_(j,tau) + epsilon)
  $,
  compressed_point_descriptor: $
    bold(f)_j^"DINO-comp"
    =
    op("Compress") (overline(bold(f))_j),
    quad
    n_j^"valid"
    =
    sum_tau m_(j,tau)^"vis"
  $,
  qh_scene_memory: $
    #symb.scene.scene_memory_t
    =
    (
      #symb.scene.ray_memory_t,
      bold(X)_t^"pt",
      bold(F)_t^"DINO@pt",
      #symb.scene.evl_local,
      bold(O)_t^"pred",
      #symb.spatial.dir_moment
    )
  $,
  point_dino_token: $
    bold(x)_j^"pt"
    =
    op("concat") (
      bold(p)_j,
      bold(f)_j^"DINO-comp",
      sigma_j^(-1),
      n_j,
      bold(a)_j^"hist"
    )
  $,
  candidate_query_pools: $
                   #symb.scene.target_support_pool & =
                          op("Pool")_(bold(p)_j in hat(bold(B))_e) bold(x)_j^"pt" \
                 #symb.scene.frustum_support_pool & =
                          op("Pool")_(bold(p)_j in op("Frustum") (q_(t,i))) bold(x)_j^"pt" \
                  #symb.scene.target_frustum_pool & =
                          op("Pool")_(bold(p)_j in hat(bold(B))_e inter op("Frustum") (q_(t,i))) bold(x)_j^"pt"
  $,
  candidate_ray_query: $
    #symb.scene.ray_query_ti
    =
    #symb.scene.render_query (
      #symb.scene.ray_memory_t,
      q_(t,i),
      hat(bold(B))_e
    )
    =
    (
      bold(D)_(t,i)^"near",
      bold(L)_(t,i)^"free",
      bold(L)_(t,i)^"unk",
      bold(M)_(t,i)^"hit",
      bold(W)_(t,i)^"target",
      bold(C)_(t,i)^"support",
      bold(Sigma)_(t,i)^"geom",
      nu_(t,i)^"dir"
    )
  $,
  qh_target_token: $
    #symb.model.target_token
    =
    op("MLP")_"tgt" (
      op("concat") (
        #symb.entity.target_desc,
        #symb.scene.target_support_pool
      )
    )
  $,
  candidate_reference_transform: $
    #symb.spatial.ref_candidate_transform
    =
    bold(T)_(w,r_t)^(-1) bold(T)_(w,c_(t,i)),
    quad
    bold(delta)_(r_t,i)^p
    =
    bold(R)_(r_t)^top (bold(c)_(t,i) - bold(c)_(r_t)),
    quad
    bold(R)_(r_t,i)
    =
    bold(R)_(r_t)^top bold(R)_(t,i)
  $,
  candidate_pose_features: $
    #symb.spatial.candidate_pose_feat (q_(t,i); r_t)
    =
    op("concat") (
      bold(delta)_(r_t,i)^p,
      op("R6D") (bold(R)_(r_t,i)),
      norm(bold(delta)_(r_t,i)^p)_2,
      op("atan2") (delta_(r_t,i)^y, delta_(r_t,i)^x),
      Delta h_(t,i),
      bold(u)_(t,i)^"up/frustum"
    )
  $,
  candidate_target_relation: $
    #symb.spatial.candidate_target_rel_feat (q_(t,i), e)
    =
    op("concat") (
      bold(delta)_(e|i)^p,
      norm(bold(delta)_(e|i)^p)_2,
      #symb.spatial.target_bearing,
      beta_(t,e,i)^"elev",
      lambda_(t,e,i)^"obb"
    )
  $,
  candidate_query_local_frame: $
    #symb.spatial.local_delta_pos
    =
    bold(R)_(t,i)^top (bold(p)_a - bold(c)_(t,i)),
    quad
    #symb.spatial.local_delta_rot
    =
    bold(R)_(t,i)^top bold(R)_a
  $,
  candidate_query_rpe: $
    bold(eta)_(a|i)
    =
    op("concat") (#symb.spatial.local_delta_pos, norm(#symb.spatial.local_delta_pos)_2, op("enc")_R (#symb.spatial.local_delta_rot)),
    quad
    #symb.spatial.relation_rpe
    =
    psi_"rel" (cal(F) (bold(eta)_(a|i))),
    quad a in {j, e, k}
  $,
  edge_conditioned_attention: $
    bold(k)_(j,i), bold(v)_(j,i) & =
                                   f_(K,V) (op("concat") (bold(x)_(t,j), bold(r)_(j,i))) \
                     alpha_(i,j) & =
                                   op("softmax")_(j in #symb.rl.action_set_t)
                                   (
                                     ((bold(W)_Q bold(x)_(t,i))^top bold(k)_(j,i)) / sqrt(d)
                                   ) \
                   bold(u)_(t,i) & =
                                   sum_(j in #symb.rl.action_set_t)
                                   alpha_(i,j)
                                   bold(v)_(j,i)
  $,
  candidate_pose_context: $
    bold(p)_(t,i)
    =
    op("concat") (
      #symb.spatial.candidate_pose_feat (q_(t,i); r_t),
      #symb.spatial.candidate_target_rel_feat (q_(t,i), e)
    )
  $,
  candidate_geometry_context: $
    bold(g)_(t,i)
    =
    op("concat") (
      #symb.scene.frustum_support_pool,
      #symb.scene.target_frustum_pool,
      #symb.scene.ray_query_ti,
      #symb.scene.evl_support_token,
      phi_"dir" (#symb.spatial.dir_moment, q_(t,i))
    )
  $,
  candidate_row_features: $
    bold(x)_(t,i)
    =
    op("concat") (
      bold(p)_(t,i),
      bold(g)_(t,i),
      #symb.model.candidate_validity_token,
      #symb.model.candidate_provenance_token,
      bold(H)_t
    )
  $,
  ray_memory_update: $
    #symb.scene.ray_memory_next
    =
    op("Fuse")(
      #symb.scene.ray_memory_t,
      #symb.obs.points_cand_ti,
      #symb.obs.selected_rays_ti
    )
  $,
  qh_set_encoder: $
    {bold(u)_(t,i)}_(i=1)^(#symb.shape.Nq)
    =
    E_"set" (
      {
        op("concat") (bold(x)_(t,i), #symb.model.target_token, bold(H)_t)
      }_(i=1)^(#symb.shape.Nq),
      bold(m)_t
    )
  $,
  qh_candidate_state_cross_attention: $
    bold(u)_(t,i)
    =
    op("CrossAttn")_theta (
      bold(x)_(t,i),
      {#symb.model.target_token, #symb.scene.ray_memory_t, bold(H)_t, bold(b)_t, #symb.scene.evl_local}
    )
  $,
)
