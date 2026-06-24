#let vin = (
    // Loss symbol.
    loss: $cal(L)$,
    // Pose embedding.
    pose_emb: $bold(E)_q$,
    // Token / feature vector.
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
    // SE(3) transform.
    T: $bold(T)$,
    // Weight matrix.
    W: $bold(W)$,
    // FiLM scale.
    gamma: $bold(gamma)$,
    // FiLM shift.
    beta: $bold(beta)$,
    // Semi-dense observation count (track length).
    n_obs: $n_"obs"$,
    // Max observation count used for normalization.
    n_obs_max: $n_"obs"^"max"$,
    // Inverse-distance std (sigma_rho) from semi-dense tracks.
    inv_dist_std: $sigma_(rho)$,
    // Min / p95 of inverse-distance std for normalization.
    inv_dist_std_min: $sigma_(rho,"min")$,
    inv_dist_std_p95: $sigma_(rho,"p95")$,
    // Distance std (sigma_d) for completeness.
    dist_std: $sigma_d$,
    // Continuous oracle RRI (per candidate).
    rri: $r$,
    // Predicted RRI proxy (expected CORAL value).
    rri_hat: $hat(r)$,
    // Coverage / visibility fraction (generic).
    cov_frac: $c$,
    // Coverage-based weight.
    cov_weight: $w$,
    // Coverage-weight blend strength.
    cov_strength: $lambda$,
    // Auxiliary regression weight.
    aux_weight: $lambda_"reg"$,
    // Voxel coverage proxy (candidate-level).
    voxel_valid: $v$,
    // Semi-dense visibility proxy (candidate-level).
    sem_valid: $v^("sem")$,
    // Semi-dense projection statistics (per candidate).
    sem_proj: $bold(s)_"proj"$,
    // Semi-dense grid CNN features (per candidate).
    sem_grid: $bold(s)_"grid"$,
    // Trajectory pooled feature (optional).
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
    // Centerness after NMS (used in VINv3 field bundle).
    cent_pr_nms: $bold(V)_"cent"^"pr,nms"$,
    // Observed mask (counts > 0).
    observed: $bold(V)_"obs"$,
    // Unknown mask (1 - counts_norm).
    unknown: $bold(V)_"unk"$,
    // New-surface prior (unknown ⊙ occ_pr).
    new_surface_prior: $bold(V)_"new"$,
    // VIN scene field after lightweight 3D projection/assembly (multi-channel).
    field_v: $bold(F)_v$,
    // Time-indexed EVL/EFM evidence field used by proposal rollouts.
    field_evl_t: $bold(F)_t^"EVL"$,
    field_evl_0: $bold(F)_0^"EVL"$,
    // Compatibility aliases. New thesis prose should use symb.scene.*.
    scene_memory_t: $bold(Phi)_t^"scene"$,
    evl_local: $bold(E)_0^"EVL-local"$,
    evl_support_frac: $omega_(t,i)^"EVL"$,
    evl_support_token: $bold(g)_(t,i)^"EVL"$,
    target_pool: $bold(g)_e^"tgt"$,
    frustum_pool: $bold(g)_(t,i)^"fr"$,
    target_frustum_pool: $bold(g)_(t,e,i)^"cap"$,
    ray_query_ti: $bold(g)_(t,i)^"ray"$,
    render_query: $op("RenderQuery")$,
    // Per-candidate voxel features sampled/pooled from the scene field.
    field_q: $bold(F)_q^("vox")$,
    // Candidate pose/orientation and directional-observation features.
    pose_6d: $bold(R)^"6D"$,
    dir_unit: $bold(d)$,
    dir_memory: $bold(h)_"dir"$,
    dir_moment: $bold(M)_"dir"$,
    sh_basis: $bold(Y)_L$,
    candidate_pose_feat: $bold(h)_(t,i)^"pose"$,
    candidate_dir_feat: $bold(h)_(t,i)^"dir"$,
  )
