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
  edge_conditioned_attention: $
    bold(k)_(j,i), bold(v)_(j,i) & =
                                   f_(K,V) (op("concat") (bold(x)_(t,j), bold(r)_(j,i))) \
                     alpha_(i,j) & =
                                   op("softmax")_(j in #symb.rl.action_set)
                                   (
                                     ((bold(W)_Q bold(x)_(t,i))^top bold(k)_(j,i)) / sqrt(d)
                                   ) \
                   bold(u)_(t,i) & =
                                   sum_(j in #symb.rl.action_set)
                                   alpha_(i,j)
                                   bold(v)_(j,i)
  $,
)
