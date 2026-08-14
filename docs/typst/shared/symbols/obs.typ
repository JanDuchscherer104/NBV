// Actor-visible observations and their set- or tensor-valued encodings.
#let obs = (
    // Logged RGB image stream.
    img_rgb: $bold(I)^"rgb"$,
    // Reserved Hestia-style grayscale stream; no direct authored use in the 2026-08-14 audit.
    img_gray: $bold(I)^"gray"$,
    // Depth image / rendered depth observation.
    depth: $bold(D)$,
    // Pose stream along the trajectory.
    pose: $bold(X)$,
    // Reserved pose/camera metadata bundle; no direct authored use in the 2026-08-14 audit.
    meta: $bold(M)$,
    // Semidense point-cloud observation stream as an abstract set.
    points_semi: $cal(P)^"semi"$,
    // Reserved time-indexed semi-dense set; duplicates the used `ase.points_semi` form.
    points_semi_t: $cal(P)_t^"semi"$,
    // Canonical actor-visible accumulated set; `oracle.points_t` is an unused duplicate.
    points_t: $cal(P)_t$,
    // Reserved next-step accumulated set; no direct authored use in the 2026-08-14 audit.
    points_next: $cal(P)_(t+1)$,
    // Reserved candidate-conditioned set; no direct authored use in the 2026-08-14 audit.
    points_cand_ti: $cal(P)_(t,i)^"cand"$,
    // Unused duplicate of canonical `scene.ray_memory_t`; migrate or prune with its pair.
    ray_memory_t: $bold(M)_t^"ray"$,
    // Unused duplicate of canonical `scene.ray_memory_next`; migrate or prune with its pair.
    ray_memory_next: $bold(M)_(t+1)^"ray"$,
    // Reserved candidate-ray set; no direct authored use in the 2026-08-14 audit.
    selected_rays_ti: $cal(R)_(t,i)^"sel"$,
    // Reserved accumulated-geometry tensor; no direct authored use in the 2026-08-14 audit.
    points_tensor_t: $bold(P)_t$,
    // Reserved candidate-geometry tensor; no direct authored use in the 2026-08-14 audit.
    points_tensor_cand_ti: $bold(P)_(t,i)^"cand"$,
    // Point-attached logged visual descriptor bank.
    dino_point_bank_t: $bold(F)_t^"DINO@pt"$,
    // Learned point tokens derived from accumulated evidence at step t.
    point_tokens_t: $bold(X)_t^"pt"$,
    // Counterfactual / rendered geometry point-cloud stream.
    points_cf: $cal(P)^"cf"$,
    // Reserved geometry/grid bundle; no direct authored use in the 2026-08-14 audit.
    grid: $bold(G)$,
    // Generic visibility / directional-observability cue.
    vis: $bold(V)$,
    // Reserved look-at latent; no direct authored use in the 2026-08-14 audit.
    lookat: $bold(L)$,
    // Reserved cumulative Hestia visibility; no direct authored use in the 2026-08-14 audit.
    face_vis: $bold(F)$,
    // Reserved instantaneous Hestia visibility; no direct authored use in the 2026-08-14 audit.
    face_vis_step: $bold(f)$,
    // Reserved voxel-center vector; no direct authored use in the 2026-08-14 audit.
    voxel_center: $bold(p)_v$,
    // Face normal vector.
    face_normal: $bold(n)$,
  )
