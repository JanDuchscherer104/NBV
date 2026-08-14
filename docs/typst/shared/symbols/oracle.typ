// Candidate-generation and privileged reconstruction-label notation.
#let oracle = (
    // Generic abstract reconstruction point set before time or candidate indexing.
    points: $cal(P)$,
    // Actor-visible point set accumulated through rollout step t.
    points_t: $cal(P)_t$,
    // Candidate point set.
    points_q: $cal(P)_q$,
    // Tensor encoding of a point set.
    points_tensor: $bold(P)$,
    // Candidate pose set.
    candidates: $cal(Q)$,
    // Candidate pose set at rollout step t.
    candidates_t: $cal(Q)_t$,
    // Candidate i at rollout step t.
    candidate_qti: $q_(t,i)$,
    // Tensor encoding of candidate rows/features.
    candidate_tensor: $bold(X)^"cand"$,
    // Candidate depth maps.
    depth_q: $bold(D)_q$,
    // Pixel-wise valid mask for candidate depth maps / projections.
    // (Used e.g. for rendered depth validity and projection validity.)
    mask_q: $bold(M)_q$,
    // Candidate camera intrinsics/extrinsics (non-PyTorch3D).
    cameras_q: $cal(C)_q$,
    // Direction vector (sampling).
    dir: $bold(d)$,
    // Center / translation vector.
    center: $bold(c)$,
    // Offset vector.
    offset: $bold(o)$,
    // Directional point-mesh error terms. `acc` / `comp` are compatibility aliases.
    dist_pm: $D_(P -> M)$,
    // Mesh-to-point directional reconstruction error.
    dist_mp: $D_(M -> P)$,
    // Compatibility alias for point-to-mesh reconstruction error.
    acc: $D_(P -> M)$,
    // Compatibility alias for mesh-to-point reconstruction error.
    comp: $D_(M -> P)$,
    // Symmetric point-mesh error aggregate.
    err: $D$,
    // Relative Reconstruction Improvement scalar.
    rri: $op("RRI")$,
  )
