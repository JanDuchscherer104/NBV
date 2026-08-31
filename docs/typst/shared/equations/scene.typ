#import "../symbols.typ": symb

#let scene = (
  actor_state_read: $
    bold(h)_(t,e,i)
    =
    op("Read")(
      #symb.scene.scene_memory_t,
      #symb.model.target_token,
      q_(t,i),
      #symb.rl.selected_pose_prefix,
      t,
      #symb.rl.H
    )
  $,
  evl_local_support_read: $
    #symb.scene.evl_support_frac
    =
    (1) / (K) sum_(k=1)^K
    bb(1)[x_(t,i,k) in cal(V)_0^"EVL"],
    quad
    #symb.scene.evl_support_token
    =
    op("Pool")({#symb.vin.field_evl_0 (x_(t,i,k)) : x_(t,i,k) in cal(V)_0^"EVL"})
  $,
  qh_scene_memory: $
    #symb.scene.scene_memory_t
    =
    (
      #symb.scene.ray_memory_t,
      #symb.obs.point_tokens_t,
      #symb.obs.dino_point_bank_t,
      #symb.scene.evl_local,
      #symb.entity.target_hyp_pred_t,
      #symb.spatial.dir_moment
    )
  $,
  candidate_query_pools: $
                   #symb.scene.target_support_pool & =
                                                       op("Pool")_(bold(p)_j in hat(bold(B))_e) bold(x)_j^"pt" \
                 #symb.scene.frustum_support_pool & =
                                                       op("Pool")_(bold(p)_j in op("Frustum") (q_(t,i))) bold(x)_j^"pt" \
                  #symb.scene.target_frustum_pool & =
                                                       op("Pool")_(bold(p)_j in hat(bold(B))_e inter op("Frustum") (q_(t,i))) bold(x)_j^"pt"
  $,
  candidate_ray_query: $
    #symb.scene.ray_query_ti
    =
    #symb.scene.render_query (
      #symb.scene.ray_memory_t,
      q_(t,i),
      hat(bold(B))_e
    )
    =
    (
      bold(D)_(t,i)^"near",
      bold(L)_(t,i)^"free",
      bold(L)_(t,i)^"unk",
      bold(M)_(t,i)^"hit",
      bold(W)_(t,i)^"target",
      bold(C)_(t,i)^"support",
      bold(Sigma)_(t,i)^"geom",
      bold(phi)_(t,i)^"dir"
    )
  $,
  ray_memory_update: $
    #symb.scene.ray_memory_next
    =
    op("Fuse")(
      #symb.scene.ray_memory_t,
      bold(P)_(t+1)^"selected-obs" (a_t),
      cal(R)_(t+1)^"selected-obs" (a_t)
    ),
    quad
    a_t in cal(A)_t
  $,
)
