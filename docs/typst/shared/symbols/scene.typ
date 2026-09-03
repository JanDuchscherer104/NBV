// Composite scene memories and candidate-conditioned scene-query descriptors.
#let scene = (
  // Canonical composite scene memory.
  scene_memory_t: $bold(Phi)_t^"scene"$,
  // Canonical ray memory at step t.
  ray_memory_t: $bold(M)_t^"ray"$,
  // Canonical next ray memory.
  ray_memory_next: $bold(M)_(t+1)^"ray"$,
  // Canonical root-local EVL field.
  evl_local: $bold(E)_0^"EVL-local"$,
  // Canonical EVL support fraction.
  evl_support_frac: $omega_(t,i)^"EVL"$,
  // Canonical EVL support token.
  evl_support_token: $bold(g)_(t,i)^"EVL"$,
  // Canonical target support pool.
  target_support_pool: $bold(g)_e^"tgt"$,
  // Canonical frustum support pool.
  frustum_support_pool: $bold(g)_(t,i)^"fr"$,
  // Canonical target-frustum pool.
  target_frustum_pool: $bold(g)_(t,e,i)^"cap"$,
  // Canonical candidate ray query.
  ray_query_ti: $bold(g)_(t,i)^"ray"$,
  // Canonical render-query operator.
  render_query: $op("RenderQuery")$,
)
