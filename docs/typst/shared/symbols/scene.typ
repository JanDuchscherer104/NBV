// Composite scene memories and candidate-conditioned scene-query descriptors.
#let scene = (
  // Canonical composite scene memory; `vin.scene_memory_t` is an unused compatibility alias.
  scene_memory_t: $bold(Phi)_t^"scene"$,
  // Canonical ray memory at step t; `obs.ray_memory_t` and VIN aliases are unused duplicates.
  ray_memory_t: $bold(M)_t^"ray"$,
  // Canonical next ray memory; `obs.ray_memory_next` is an unused duplicate.
  ray_memory_next: $bold(M)_(t+1)^"ray"$,
  // Canonical root-local EVL field; `vin.evl_local` is an unused compatibility alias.
  evl_local: $bold(E)_0^"EVL-local"$,
  // Canonical EVL support fraction; VIN retains an unused compatibility alias.
  evl_support_frac: $omega_(t,i)^"EVL"$,
  // Canonical EVL support token; VIN retains an unused compatibility alias.
  evl_support_token: $bold(g)_(t,i)^"EVL"$,
  // Canonical target support pool; `vin.target_pool` is an unused compatibility alias.
  target_support_pool: $bold(g)_e^"tgt"$,
  // Canonical frustum support pool; VIN retains an unused compatibility alias.
  frustum_support_pool: $bold(g)_(t,i)^"fr"$,
  // Canonical target-frustum pool; VIN retains an unused compatibility alias.
  target_frustum_pool: $bold(g)_(t,e,i)^"cap"$,
  // Canonical candidate ray query; VIN retains an unused compatibility alias.
  ray_query_ti: $bold(g)_(t,i)^"ray"$,
  // Canonical render-query operator; VIN retains an unused compatibility alias.
  render_query: $op("RenderQuery")$,
)
