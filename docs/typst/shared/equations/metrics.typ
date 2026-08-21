#import "../symbols.typ": symb

#let metrics = (
    pearson: $
      r_(x,y)
      =
      (sum_i (x_i - bar(x)) (y_i - bar(y)))
      /
      sqrt(sum_i (x_i - bar(x))^2 sum_i (y_i - bar(y))^2)
    $,
    categorical_entropy: $
      H(bold(p)) = - sum_(i : m_i = 1) p_i log(p_i)
    $,
    selection_rate_given_available: $
      "SelRate"_f = N_("selected",f) / N_("actor-valid",f)
    $,
    q_train_mask: $
      m_(t,i)^"train" = m_(t,i)^"actor" dot m_(t,i)^"oracle"
    $,
    selected_oracle_regret: $
      "Regret"_t = max_(i : m_(t,i) = 1) g_(t,i) - g_(t,a_t)
    $,
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
