// Composite scene memories and candidate-conditioned scene-query descriptors.
#let scene = (
  // Composite actor-visible scene memory queried by the value model.
  scene_memory_t: $bold(Phi)_t^"scene"$,
  // Sparse ray-aware occupied / free / unknown scene memory at step t.
  ray_memory_t: $bold(M)_t^"ray"$,
  // Ray-aware scene memory after incorporating the next observation.
  ray_memory_next: $bold(M)_(t+1)^"ray"$,
  // Root-local EVL evidence field used for candidate-conditioned reads.
  evl_local: $bold(E)_0^"EVL-local"$,
  // Fraction of EVL support available to candidate i at step t.
  evl_support_frac: $omega_(t,i)^"EVL"$,
  // Candidate-conditioned token pooled from EVL support.
  evl_support_token: $bold(g)_(t,i)^"EVL"$,
  // Pooled support descriptors over target, frustum, and their intersection.
  target_support_pool: $bold(g)_e^"tgt"$,
  // Support descriptor pooled over candidate i's viewing frustum.
  frustum_support_pool: $bold(g)_(t,i)^"fr"$,
  // Support descriptor pooled over the target-frustum intersection.
  target_frustum_pool: $bold(g)_(t,e,i)^"cap"$,
  // Candidate-conditioned ray-query feature vector.
  ray_query_ti: $bold(g)_(t,i)^"ray"$,
  // Named operator for querying render-derived candidate evidence.
  render_query: $op("RenderQuery")$,
)
