// Actor-visible observations and their set- or tensor-valued encodings.
#let obs = (
    // Logged RGB image stream.
    img_rgb: $bold(I)^"rgb"$,
    // Optional grayscale image stream (used by Hestia-style formulations).
    img_gray: $bold(I)^"gray"$,
    // Depth image / rendered depth observation.
    depth: $bold(D)$,
    // Pose stream along the trajectory.
    pose: $bold(X)$,
    // Pose / camera metadata bundle.
    meta: $bold(M)$,
    // Semidense point-cloud observation stream as an abstract set.
    points_semi: $cal(P)^"semi"$,
    // Time-indexed semi-dense evidence used in proposal state notation.
    points_semi_t: $cal(P)_t^"semi"$,
    // Actor-visible point set accumulated through rollout step t.
    points_t: $cal(P)_t$,
    // Accumulated point set after incorporating the next observation.
    points_next: $cal(P)_(t+1)$,
    // Counterfactual point set associated with candidate i at step t.
    points_cand_ti: $cal(P)_(t,i)^"cand"$,
    // Sparse ray-aware occupied / free / unknown scene memory at step t.
    ray_memory_t: $bold(M)_t^"ray"$,
    // Ray-aware scene memory after incorporating the next observation.
    ray_memory_next: $bold(M)_(t+1)^"ray"$,
    // Selected candidate rays used to query or update scene memory.
    selected_rays_ti: $cal(R)_(t,i)^"sel"$,
    // Tensor encoding of accumulated geometry at step t.
    points_tensor_t: $bold(P)_t$,
    // Tensor encoding of candidate-conditioned geometry at step t.
    points_tensor_cand_ti: $bold(P)_(t,i)^"cand"$,
    // Point-attached logged visual descriptor bank.
    dino_point_bank_t: $bold(F)_t^"DINO@pt"$,
    // Learned point tokens derived from accumulated evidence at step t.
    point_tokens_t: $bold(X)_t^"pt"$,
    // Counterfactual / rendered geometry point-cloud stream.
    points_cf: $cal(P)^"cf"$,
    // Geometry / voxel-grid observation bundle.
    grid: $bold(G)$,
    // Generic visibility / directional-observability cue.
    vis: $bold(V)$,
    // Target / look-at latent.
    lookat: $bold(L)$,
    // Cumulative face visibility tensor (Hestia-style).
    face_vis: $bold(F)$,
    // Instantaneous face visibility tensor (Hestia-style).
    face_vis_step: $bold(f)$,
    // Voxel center position.
    voxel_center: $bold(p)_v$,
    // Face normal vector.
    face_normal: $bold(n)$,
  )
