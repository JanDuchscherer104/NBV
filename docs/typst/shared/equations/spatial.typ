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
  candidate_pose_features: $
    #symb.spatial.candidate_pose_feat (q_(t,i); r_t)
    =
    op("concat") (
      xi_(r_t,i)^"rel",
      bold(R)_(r_t,i)^"6D",
      Delta h_(t,i),
      bold(u)_(t,i)^"up/frustum"
    )
  $,
  candidate_target_relation: $
    #symb.spatial.candidate_target_rel_feat (q_(t,i), e)
    =
    op("concat") (
      bold(R)_(t,i)^top (bold(c)_e - bold(c)_(t,i)),
      norm(bold(c)_e - bold(c)_(t,i))_2,
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
