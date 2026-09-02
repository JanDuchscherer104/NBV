#import "../symbols.typ": symb

#let metrics = (
  spearman: $
    rho = "corr"("rank"(#(symb.vin.rri_hat) _i), "rank"(#(symb.vin.rri) _i))
  $,
  topk_acc: $ "TopKAcc"(k) = (1) / N sum_i bb(1)[y_i in "TopK"(bold(pi)_i, k)] $,
  confusion: $ C_(a,b) = |{i : y_i = a, hat(y)_i = b}| $,
  label_hist: $ h_k = |{i : y_i = k}| $,
  candidate_validity: $
    #(symb.vin.cand_valid) _i
    =
    bb(1)["finite"]
    dot bb(1)[#(symb.vin.voxel_valid) _i > 0]
    dot bb(1)[#(symb.vin.sem_valid) _i > 0]
  $,
  rri_mean: $ bar(#symb.vin.rri) = (1)/(N) sum_i #(symb.vin.rri) _i $,
  pred_rri_mean: $ bar(#symb.vin.rri_hat) = (1)/(N) sum_i #(symb.vin.rri_hat) _i $,
  bias2: $ "bias"^2 = ((1)/(N) sum_i (#(symb.vin.rri_hat) _i - #(symb.vin.rri) _i))^2 $,
  variance: $
    "var"
    =
    (1)/(N) sum_i (#(symb.vin.rri_hat) _i - #(symb.vin.rri) _i)^2
    - ((1)/(N) sum_i (#(symb.vin.rri_hat) _i - #(symb.vin.rri) _i))^2
  $,
  mean: $ bar(x) = (1)/(N) sum_i x_i $,
  std: $ sigma_x = sqrt((1)/(N) sum_i (x_i - bar(x))^2) $,
  voxel_valid_mean: $ bar(#symb.vin.voxel_valid) = (1)/(N) sum_i #(symb.vin.voxel_valid) _i $,
  voxel_valid_std: $
    sigma_(#symb.vin.voxel_valid) = sqrt((1)/(N) sum_i (#(symb.vin.voxel_valid) _i - bar(#symb.vin.voxel_valid))^2)
  $,
  sem_valid_mean: $ bar(#symb.vin.sem_valid) = (1)/(N) sum_i #(symb.vin.sem_valid) _i $,
  sem_valid_std: $
    sigma_(#symb.vin.sem_valid) = sqrt((1)/(N) sum_i (#(symb.vin.sem_valid) _i - bar(#symb.vin.sem_valid))^2)
  $,
  candidate_valid_frac: $ (1)/(N) sum_i #(symb.vin.cand_valid) _i $,
  candidate_actor_valid_fraction: $
    f_"actor"(s) =
    (sum_(i in cal(I)_s) m_(s,i)^"act") / |cal(I)_s|
  $,
  valid_support: $
    n_"valid"(s) = |{i in cal(I)_s : m_i^"act" = 1}|
  $,
  configured_family_zero_rate: $
    z_"family"(s) =
    1 / (|cal(F)_s|) sum_(f in cal(F)_s) bb(1)[n_"valid"(s,f) = 0]
  $,
  state_scene_macro: $
    cal(S)_(c,q) = {s in cal(S)_c : q(s) " is defined"},
    quad
    bar(q)_c = 1 / (|cal(S)_(c,q)|) sum_(s in cal(S)_(c,q)) q(s),
    quad
    cal(C)_q = {c in cal(C) : |cal(S)_(c,q)| > 0},
    quad
    bar(q) = 1 / (|cal(C)_q|) sum_(c in cal(C)_q) bar(q)_c
  $,
  target_side_balance: $
        n_+ (s) & = sum_(i in cal(I)_s^"target") bb(1)[y_(s,i)^"target" > epsilon], \
        n_- (s) & = sum_(i in cal(I)_s^"target") bb(1)[y_(s,i)^"target" < -epsilon], \
         n_0(s) & = sum_(i in cal(I)_s^"target") bb(1)[|y_(s,i)^"target"| <= epsilon], \
    b_"side"(s) & = 1 - (|n_+(s) - n_-(s)|) / (n_+(s) + n_-(s)), \
                & n_+(s) + n_-(s) > 0
  $,
  circular_orbit_span: $
    alpha_(s,1) <= dots <= alpha_(s,n_s),
    quad alpha_(s,n_s+1) = alpha_(s,1) + 2 pi,
    quad s_"orbit"(s) = 2 pi - max_(1 <= j <= n_s) (alpha_(s,j+1) - alpha_(s,j))
  $,
  target_center_projection_fraction: $
    f_"proj"(s) =
    (sum_(i in cal(I)_s^"evaluated") bb(1)[i in cal(I)_s^"projected"])
    / (|cal(I)_s^"evaluated"|),
    quad |cal(I)_s^"evaluated"| > 0
  $,
  oracle_opportunity: $
    o_"oracle"(s) = max_(i in cal(L)_s) g_(s,i)^"target-root",
    quad |cal(L)_s| > 0
  $,
  jitter_compliance: $
    f_"jitter"(s) =
    (sum_(i in cal(I)_s^"jitter") bb(1)[b_i = 1] dot bb(1)[abs(Delta psi_i) <= bar(psi)_i] dot bb(1)[abs(Delta theta_i) <= bar(theta)_i]) /
    (sum_(i in cal(I)_s^"jitter") bb(1)[b_i = 1]),
    quad sum_(i in cal(I)_s^"jitter") bb(1)[b_i = 1] > 0
  $,
  cov_weight_mean: $ bar(#symb.vin.cov_weight) = (1)/(N) sum_i #(symb.vin.cov_weight) _i $,
  drop_nonfinite_logits_frac: $
    (sum_i bb(1)["finite"(#(symb.vin.rri) _i)] dot bb(1)["nonfinite"(bold(ell)_i)])
    / (sum_i bb(1)["finite"(#(symb.vin.rri) _i)])
  $,
  skip_nonfinite_logits: $
    bb(1)[sum_i bb(1)["finite"(#(symb.vin.rri) _i)] > 0 dot sum_i #(symb.vin.cand_valid) _i = 0]
  $,
  skip_no_valid: $ bb(1)[sum_i bb(1)["finite"(#(symb.vin.rri) _i)] = 0] $,
  grad_norm: $ ||nabla_theta cal(L)||_2 $,
)
