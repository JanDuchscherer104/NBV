// Candidate-generation and privileged reconstruction-label notation.
#let oracle = (
    // Generic abstract reconstruction point set before time or candidate indexing.
    points: $cal(P)$,
    // Candidate point set.
    points_q: $cal(P)_q$,
    // Reserved point-set tensor; no direct authored use in the 2026-08-14 audit.
    points_tensor: $bold(P)$,
    // Candidate pose set.
    candidates: $cal(Q)$,
    // Reserved candidate-row tensor; no direct authored use in the 2026-08-14 audit.
    candidate_tensor: $bold(X)^"cand"$,
    // Candidate depth maps.
    depth_q: $bold(D)_q$,
    // Pixel-wise valid mask for candidate depth maps / projections.
    // (Used e.g. for rendered depth validity and projection validity.)
    mask_q: $bold(M)_q$,
    // Candidate camera intrinsics/extrinsics (non-PyTorch3D).
    cameras_q: $cal(C)_q$,
    // Center / translation vector.
    center: $bold(c)$,
    // Reserved sampling offset; no direct authored use in the 2026-08-14 audit.
    offset: $bold(o)$,
    // Directional point-mesh error terms. `acc` / `comp` are compatibility aliases.
    dist_pm: $D_(P -> M)$,
    // Mesh-to-point directional reconstruction error.
    dist_mp: $D_(M -> P)$,
    // Used compatibility alias; retain until consumers migrate to `dist_pm`.
    acc: $D_(P -> M)$,
    // Used compatibility alias; retain until consumers migrate to `dist_mp`.
    comp: $D_(M -> P)$,
    // Symmetric error aggregate; glyph D can collide with `shape.D` in mixed equations.
    err: $D$,
    // Relative Reconstruction Improvement scalar.
    rri: $op("RRI")$,
  )
