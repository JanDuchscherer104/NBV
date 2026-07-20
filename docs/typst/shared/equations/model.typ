#import "../symbols.typ": symb

#let model = (
  qh_input_contract: $
    cal(I)_(t,e)
    =
    (
      #symb.model.target_token,
      #symb.scene.scene_memory_t,
      bold(H)_t,
      bold(b)_t,
      t,
      #symb.rl.H,
      {#symb.model.candidate_row, #symb.spatial.relation_rpe, m_(t,i), bold(rho)_(t,i)}_(i=1)^(#symb.shape.Nq)
    )
  $,
  qh_target_token: $
    #symb.model.target_token
    =
    op("MLP")_"tgt" (
      op("concat") (
        #symb.entity.target_desc,
        #symb.scene.target_support_pool
      )
    )
  $,
  candidate_pose_context: $
    bold(h)_(t,i)^"pose+rel"
    =
    op("concat") (
      #symb.spatial.candidate_pose_feat (q_(t,i); r_t),
      #symb.spatial.candidate_target_rel_feat (q_(t,i), e)
    )
  $,
  candidate_geometry_context: $
    #symb.model.candidate_geometry_token
    =
    op("concat") (
      #symb.scene.frustum_support_pool,
      #symb.scene.target_frustum_pool,
      #symb.scene.ray_query_ti,
      #symb.scene.evl_support_token,
      bold(phi)_(t,i)^"dir"
    )
  $,
  candidate_row_features: $
    #symb.model.candidate_row
    =
    op("concat") (
      bold(h)_(t,i)^"pose+rel",
      #symb.model.candidate_geometry_token,
      #symb.model.candidate_validity_token,
      #symb.model.candidate_provenance_token,
      bold(H)_t,
      op("Emb") (t),
      op("Emb") (#symb.rl.H),
      bold(b)_t
    )
  $,
  qh_set_encoder: $
    {bold(u)_(t,i)}_(i=1)^(#symb.shape.Nq)
    =
    E_"set" (
      {
        op("concat") (#symb.model.candidate_row, #symb.model.target_token, bold(H)_t)
      }_(i=1)^(#symb.shape.Nq),
      bold(m)_t
    )
  $,
  qh_candidate_state_cross_attention: $
    bold(u)_(t,i)
    =
    op("CrossAttn")_theta (
      #symb.model.candidate_row,
      {
        #symb.model.target_token,
        #symb.scene.scene_memory_t,
        bold(H)_t,
        op("Emb") (t),
        op("Emb") (#symb.rl.H),
        bold(b)_t
      }
    )
  $,
)
