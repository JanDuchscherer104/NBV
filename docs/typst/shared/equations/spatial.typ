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
  target_frame_obb_scale: $
    #symb.spatial.target_obb_scale
    = (a_x a_y a_z)^(1/3)
  $,
  target_frame_motion_direction: $
    #symb.spatial.target_frame_motion_direction
    = op("normalize") (
      (bold(R)_W^e)^top
      (bold(c)_(j,t)^W - bold(c)_(j,t-1)^W)
      /
      #symb.spatial.target_obb_scale
    )
  $,
  target_frame_view_direction: $
    #symb.spatial.target_frame_view_direction
    = op("normalize") (
      (bold(R)_W^e)^top bold(R)_(j,t)^W bold(e)_z
    )
  $,
  target_frame_frustum_geometry: $
    bold(x)^e (bold(d))
    = #symb.spatial.target_obb_scale bold(d),
    quad
    bold(x)^c (bold(d))
    = (bold(R)_e^c)^top
      (bold(x)^e (bold(d)) - bold(c)_(j,t)^e)
  $,
  target_frame_frustum_projection: $
    u (bold(d)) = c_x - f_x x_x^c / x_z^c,
    quad
    v (bold(d)) = c_y - f_y x_y^c / x_z^c
  $,
  target_frame_frustum_membership: $
    #symb.spatial.target_frame_frustum
    = {bold(d) in cal(S)^2 :
      cases(
        bold(d)^top (bold(c)_(j,t)^e - bold(x)^e (bold(d))) > 0 & "front-facing",
        x_z^c > 0 & "in front",
        -1/2 <= u (bold(d)) <= W - 1/2 & "horizontal image support",
        -1/2 <= v (bold(d)) <= H - 1/2 & "vertical image support"
      )}
  $,
  target_frame_frustum_coverage: $
    #symb.spatial.target_frame_frustum_fraction
    = op("area")_(cal(S)^2) (#symb.spatial.target_frame_frustum) / (4 pi)
  $,
  spherical_triangle_solid_angle: $
    Omega_triangle (bold(a), bold(b), bold(c))
    = 2 op("atan2") (
      abs(bold(a)^top (bold(b) times bold(c))),
      1 + bold(a)^top bold(b) + bold(b)^top bold(c) + bold(c)^top bold(a)
    )
  $,
  pinhole_frustum_solid_angle: $
    #symb.spatial.frustum_solid_angle
    = Omega_triangle (bold(q)_0, bold(q)_1, bold(q)_2)
      + Omega_triangle (bold(q)_0, bold(q)_2, bold(q)_3)
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
  candidate_proposal_support_normalization: $
    d_(t,e)^"current"
    =
    norm(#symb.entity.center - #(symb.oracle.center)_(r_t)^w)_2,
    quad
    tilde(bold(c))_(t,i)^"support"
    =
    (bold(B)_(r,t)^"Z-up")^top
    (#(symb.oracle.center)_(t,i)^w - #(symb.oracle.center)_(r_t)^w)
    /
    d_(t,e)^"current",
    quad
    tilde(bold(p))_(t,e)^"support"
    =
    (bold(B)_(r,t)^"Z-up")^top
    (#symb.entity.center - #(symb.oracle.center)_(r_t)^w)
    /
    d_(t,e)^"current",
    quad
    norm(tilde(bold(p))_(t,e)^"support")_2 = 1
  $,
  rollout_trajectory_normalization: $
    d_(0,e)^"initial"
    =
    norm(#symb.entity.center - #(symb.oracle.center)_(r_0)^w)_2,
    quad
    tilde(bold(x))_(r,t)^"trajectory"
    =
    (bold(B)_(r,0)^"target-Z-up")^top
    (bold(x)_(r,t)^w - #(symb.oracle.center)_(r_0)^w)
    /
    d_(0,e)^"initial"
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
