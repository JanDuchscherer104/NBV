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
    #symb.vin.dir_memory (bold(v))
    =
    sum_(k < t) w_k (bold(v))
    #symb.vin.sh_basis (bold(d)_k (bold(v)))
  $,
  direction_memory_moment: $
    #symb.vin.dir_moment (bold(v))
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
    #symb.vin.dir_moment (bold(v))
    bold(d)_(t,i) (bold(v))
    )
    /
    (op("tr") (#symb.vin.dir_moment (bold(v))) + epsilon)
  $,
  qh_scene_memory: $
    bold(Phi)_t^"scene"
    =
    (
      bold(X)_t^"pt",
      bold(F)_t^"DINO@pt",
      bold(E)_0^"EVL-local",
      bold(O)_t^"pred",
      #symb.vin.dir_moment
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
    // TODO: what is the difference between these potential candidate features? Frustum vs. projected? Pooling over the entire scene vs. just the candidate crop?
              bold(z)_e & =
                          op("Pool")_(bold(p)_j in hat(bold(B))_e) bold(x)_j^"pt" \
         bold(z)_i^"fr" & =
                          op("Pool")_(bold(p)_j in op("Frustum") (q_(t,i))) bold(x)_j^"pt" \
    bold(z)_(e,i)^"cap" & =
                          op("Pool")_(bold(p)_j in hat(bold(B))_e inter op("Frustum") (q_(t,i))) bold(x)_j^"pt"
  $,
  qh_target_token: $
    bold(T)_e
    =
    op("MLP")_phi (
      op("concat") (
        #symb.entity.target_desc,
        phi_"target" (bold(Phi)_t^"scene", hat(bold(B))_e)
      )
    )
  $,
  candidate_pose_features: $
    #symb.vin.candidate_pose_feat (q_(t,i))
    =
    op("concat") (
      // TODO: It's either R6d + bold(t)_(t,i) or the QCNet like decsriptor!
      bold(t)_(t,i),
      bold(R)_(t,i)^"6D",
      norm(bold(t)_(t,i) - bold(t)_e)_2^2,
      alpha_(t,i)^e,
      // TODO: What is l_(t, i). OBB?
      l_(t,i),
      // TODO: what is strategy?
      c_(t,i)^"strategy"
    )
  $,
  candidate_query_local_frame: $
    bold(delta)_(j,i)^"p"
    =
    bold(R)_(t,i)^top (bold(p)_j - bold(c)_(t,i)),
    quad
    bold(delta)_(j,i)^"R"
    =
    bold(R)_(t,i)^top bold(R)_j
  $,
  candidate_query_rpe: $
    bold(eta)_(j,i)^"cand"
    &=
    op("concat") (bold(delta)_(j,i)^"p", norm(bold(delta)_(j,i)^"p")_2, op("enc")_R (bold(delta)_(j,i)^"R")) \
    bold(eta)_(e,i)^"target"
    &=
    op("concat") (bold(R)_(t,i)^top (bold(t)_e - bold(c)_(t,i)), alpha_(t,i)^e) \
    bold(eta)_(k,i)^"hist"
    &=
    op("concat") (bold(R)_(t,i)^top (bold(c)_k - bold(c)_(t,i)), t - k, r_k^e) \
    bold(r)_(a,i)^"rpe"
    &=
    phi_R (cal(F) (bold(eta)_(a,i))),
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
      #symb.vin.candidate_pose_feat (q_(t,i)),
      phi_"target-rel" (q_(t,i), #symb.entity.target_desc)
    )
  $,
  candidate_geometry_context: $
    bold(g)_(t,i)
    =
    op("concat") (
      phi_"frustum" (bold(X)_t^"pt", q_(t,i)),
      phi_"target-frustum" (bold(X)_t^"pt", #symb.entity.target_desc, q_(t,i)),
      phi_"EVL-local" (bold(E)_0^"EVL-local", q_(t,i), #symb.entity.target_desc),
      phi_"dir" (#symb.vin.dir_moment, q_(t,i))
    )
  $,
  candidate_row_features: $
    bold(x)_(t,i)
    =
    op("concat") (
      bold(p)_(t,i),
      bold(g)_(t,i),
      phi_"valid" (m_(t,i), rho_(t,i)),
      bold(H)_t
    )
  $,
  qh_set_encoder: $
    {bold(u)_(t,i)}_(i=1)^(#symb.shape.Nq)
    =
    E_"set" (
      {
        op("concat") (bold(x)_(t,i), bold(T)_e, bold(H)_t)
      }_(i=1)^(#symb.shape.Nq),
      bold(m)_t
    )
  $,
)
