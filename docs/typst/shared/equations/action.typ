#import "../symbols.typ": symb

#let action = (
    space: $ cal(A)^"cont" subset bb(R)^3 times op("SO")(2) $,
    candidate_shell: $
      #symb.rl.candidate_table = {q_(t,i)}_(i=1)^(#symb.shape.Nq),
      quad
      #symb.shape.Nq = 60
    $,
    power_spherical_forward: $
      bold(u)_i ~ "PS"(bold(e)_z, kappa),
      quad
      p(bold(u)) = c_kappa (1 + bold(e)_z^T bold(u))^kappa,
      quad
      kappa = 8
    $,
    angle_cap_transform: $
      psi' = psi Delta_psi / (2 pi),
      quad
      y' = sin theta_"min" + (u_y + 1) / 2 dot (sin theta_"max" - sin theta_"min")
    $,
    capped_direction: $
      bold(d)_i^0 =
      (sqrt(1 - y'^2) sin psi', y', sqrt(1 - y'^2) cos psi'),
      quad
      norm(bold(d)_i^0)_2 = 1
    $,
    family_directions: $
      bold(g)_i^"forward"
      =
      bold(f) + alpha_f (bold(d)_i^0 - (bold(d)_i^0 dot bold(f)) bold(f)),
      quad
      bold(d)_i^"forward"
      = bold(g)_i^"forward" / norm(bold(g)_i^"forward")_2,
      quad
      alpha_f = 0.45
      \
      bold(g)_i^"target"
      =
      bold(b)_e + alpha_t (bold(d)_i^0 - (bold(d)_i^0 dot bold(b)_e) bold(b)_e),
      quad
      bold(d)_i^"target"
      = bold(g)_i^"target" / norm(bold(g)_i^"target")_2,
      quad
      alpha_t = 0.4
      \
      bold(g)_i^"bypass"
      =
      0.55 bold(b)_e
      + 0.85 op("sign")(d_(i,x)^0) bold(l)_e
      + op("clip")(d_(i,y)^0, -0.35, 0.35) bold(e)_y,
      quad
      bold(d)_i^"bypass"
      = bold(g)_i^"bypass" / norm(bold(g)_i^"bypass")_2
    $,
    candidate_center_world: $
      r_i ~ cal(U)(r_"min"^(k(i)), r_"max"^(k(i))),
      quad
      bold(c)_i^w = bold(T)_r^w (r_i bold(d)_i^(k(i)))
    $,
    target_lookat_frame: $
      bold(z)_i^w =
      (bold(p)_e - bold(c)_i^w) / norm(bold(p)_e - bold(c)_i^w)_2,
      quad
      bold(g)_i^"up" = bold(e)_y - (bold(e)_y^T bold(z)_i^w) bold(z)_i^w,
      quad
      bold(y)_i^w =
      bold(g)_i^"up" / norm(bold(g)_i^"up")_2,
      quad
      bold(x)_i^w = bold(y)_i^w times bold(z)_i^w
    $,
    motion_pruning_limits: $
      ||bold(o)_i||_2 <= 1.0 "m",
      quad
      |Delta h_i| <= 0.25 "m",
      quad
      op("max")(0, -o_(i,z)) <= 0.25 "m",
      quad
      Delta psi_i <= 70 "deg"
    $,
    valid_support_threshold: $
      N_"valid" >= op("max")(12, op("ceil")(0.25 #symb.shape.Nq))
    $,
    robust_temperature_softmax: $
      ell_i =
      (s_i - op("median")(s)) / (op("IQR")(s) tau),
      quad
      P(i | m_i = 1) =
      exp(ell_i) / sum_(j:m_j=1) exp(ell_j)
    $,
  )
