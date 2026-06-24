#let scene = (
  // Composite actor-visible scene memory queried by the value model.
  scene_memory_t: $bold(Phi)_t^"scene"$,
  // Sparse ray-aware occupied / free / unknown scene memory.
  ray_memory_t: $bold(M)_t^"ray"$,
  ray_memory_next: $bold(M)_(t+1)^"ray"$,
  // Root-local EVL evidence field and candidate-conditioned local reads.
  evl_local: $bold(E)_0^"EVL-local"$,
  evl_support_frac: $omega_(t,i)^"EVL"$,
  evl_support_token: $bold(g)_(t,i)^"EVL"$,
  // Pooled support descriptors over target, frustum, and their intersection.
  target_support_pool: $bold(g)_e^"tgt"$,
  frustum_support_pool: $bold(g)_(t,i)^"fr"$,
  target_frustum_pool: $bold(g)_(t,e,i)^"cap"$,
  // Candidate-conditioned ray-query feature vector.
  ray_query_ti: $bold(g)_(t,i)^"ray"$,
  render_query: $op("RenderQuery")$,
)
