#import "../symbols.typ": symb

#let spatial = (
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
    bold(mu)_t^"dir" (bold(v))
    =
    (sum_(k < t) w_k (bold(v)) bold(d)_k (bold(v)))
    /
    (sum_(k < t) w_k (bold(v)) + epsilon),
    quad
    #symb.spatial.dir_moment (bold(v))
    =
    (sum_(k < t) w_k (bold(v))
    bold(d)_k (bold(v)) (bold(d)_k (bold(v)))^top)
    /
    (sum_(k < t) w_k (bold(v)) + epsilon)
  $,
  direction_novelty: $
    bold(phi)_(t,i)^"dir" (bold(v))
    =
    op("concat") (
      (bold(d)_(t,i) (bold(v)))^top bold(mu)_t^"dir" (bold(v)),
      (bold(d)_(t,i) (bold(v)))^top
      #symb.spatial.dir_moment (bold(v))
      bold(d)_(t,i) (bold(v))
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
  candidate_root_target_normalization: $
    d_(t,e)^"root-target"
    =
    norm(#symb.entity.center - #(symb.oracle.center)_(r_t)^w)_2,
    quad
    tilde(bold(c))_(t,i)^w
    =
    ((#(symb.oracle.center)_(t,i)^w - #(symb.oracle.center)_(r_t)^w))
    /
    d_(t,e)^"root-target",
    quad
    tilde(bold(p))_e^w
    =
    ((#symb.entity.center - #(symb.oracle.center)_(r_t)^w))
    /
    d_(t,e)^"root-target",
    quad
    norm(tilde(bold(p))_e^w)_2 = 1
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
    op("concat") (
      #symb.spatial.local_delta_pos,
      norm(#symb.spatial.local_delta_pos)_2,
      op("enc")_R (#symb.spatial.local_delta_rot)
    ),
    quad
    #symb.spatial.relation_rpe
    =
    psi_"rel" (cal(F) (bold(eta)_(a|i))),
    quad a in {j, e, k}
  $,
)
