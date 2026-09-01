// VIN scorer inputs, learned features, losses, and compatibility aliases.
#let vin = (
    // Loss symbol.
    loss: $cal(L)$,
    // Pose embedding.
    pose_emb: $bold(E)_q$,
    // Reserved generic token; no direct authored use and it shares `rl.x`'s rendered form.
    token: $bold(x)$,
    // Pooled voxel token feature (used in pose-conditioned global attention).
    vox_tok: $bold(t)$,
    // Positional encoding.
    pos: $bold(p)$,
    // Global context vector.
    global: $bold(g)$,
    // Attention query.
    query: $bold(Q)_q$,
    // Attention key.
    key: $bold(K)$,
    // Attention value.
    value: $bold(V)$,
    // SE(3) transform; bold T distinguishes it from `rl.transition` and `shape.Tlen`.
    T: $bold(T)$,
    // Weight matrix.
    W: $bold(W)$,
    // FiLM scale.
    gamma: $bold(gamma)$,
    // FiLM shift.
    beta: $bold(beta)$,
    // Semi-dense observation count (track length).
    n_obs: $n_"obs"$,
    // Reserved normalization maximum; no direct authored use in the 2026-08-14 audit.
    n_obs_max: $n_"obs"^"max"$,
    // Inverse-distance std (sigma_rho) from semi-dense tracks.
    inv_dist_std: $sigma_(rho)$,
    // Reserved inverse-distance minimum; no direct authored use in the 2026-08-14 audit.
    inv_dist_std_min: $sigma_(rho,"min")$,
    // Reserved inverse-distance p95; no direct authored use in the 2026-08-14 audit.
    inv_dist_std_p95: $sigma_(rho,"p95")$,
    // Reserved distance standard deviation; no direct authored use in the 2026-08-14 audit.
    dist_std: $sigma_d$,
    // Continuous candidate RRI; plain r also denotes RL reward and the rig-frame label.
    rri: $r$,
    // Predicted RRI proxy (expected CORAL value).
    rri_hat: $hat(r)$,
    // Reserved unused coverage fraction; plain c also denotes the camera-frame label.
    cov_frac: $c$,
    // Coverage weight; plain w also denotes the world-frame label.
    cov_weight: $w$,
    // Coverage-weight blend strength.
    cov_strength: $lambda$,
    // Auxiliary regression weight.
    aux_weight: $lambda_"reg"$,
    // Candidate voxel-validity proxy; plain v also denotes the voxel-frame label.
    voxel_valid: $v$,
    // Semi-dense visibility proxy (candidate-level).
    sem_valid: $v^("sem")$,
    // Semi-dense projection statistics (per candidate).
    sem_proj: $bold(s)_"proj"$,
    // Semi-dense grid CNN features (per candidate).
    sem_grid: $bold(s)_"grid"$,
    // Reserved trajectory feature; no direct authored use in the 2026-08-14 audit.
    traj_feat: $bold(f)_"traj"$,
    // Trajectory context per candidate (optional attention).
    traj_ctx: $bold(c)_"traj"$,
    // Candidate validity mask.
    cand_valid: $m$,
    // -----------------------------------------------------------------------
    // EVL voxel-field features (as used by VINv3)
    //
    // Notes:
    // - The voxel grid lives in the voxel frame #symb.frame.v and is anchored
    //   at the final rig pose #symb.ase.traj_final (gravity-aligned).
    // - We keep notation head-centric: occupancy / evidence / counts, matching
    //   `aria_nbv/aria_nbv/vin/model_v3.py`.
    // -----------------------------------------------------------------------
    // Occupancy prediction (sigmoid) on the voxel grid.
    occ_pr: $bold(V)_"occ"^"pr"$,
    // Occupied evidence (voxelized surface evidence from inputs).
    occ_in: $bold(V)_"surf"^"in"$,
    // Free-space evidence (optional; if provided by EVL).
    free_in: $bold(V)_"free"^"in"$,
    // Observation counts / coverage proxy per voxel.
    counts: $bold(V)_"count"^"in"$,
    // Normalized counts (log1p normalized).
    counts_norm: $bold(V)_"count"^"norm"$,
    // Centerness prediction (geometric prior).
    cent_pr: $bold(V)_"cent"^"pr"$,
    // Reserved post-NMS centerness; no direct authored use in the 2026-08-14 audit.
    cent_pr_nms: $bold(V)_"cent"^"pr,nms"$,
    // Observed mask (counts > 0).
    observed: $bold(V)_"obs"$,
    // Unknown mask (1 - counts_norm).
    unknown: $bold(V)_"unk"$,
    // New-surface prior (unknown ⊙ occ_pr).
    new_surface_prior: $bold(V)_"new"$,
    // VIN scene field after lightweight 3D projection/assembly (multi-channel).
    field_v: $bold(F)_v$,
    // Reserved time-indexed EVL field; no direct authored use in the 2026-08-14 audit.
    field_evl_t: $bold(F)_t^"EVL"$,
    // Initial EVL/EFM evidence field at the rollout root.
    field_evl_0: $bold(F)_0^"EVL"$,
    // Reserved candidate voxel-field feature; no direct authored use in the 2026-08-14 audit.
    field_q: $bold(F)_q^("vox")$,
    // Reserved candidate-direction feature; no direct authored use in the 2026-08-14 audit.
    candidate_dir_feat: $bold(h)_(t,i)^"dir"$,
  )
