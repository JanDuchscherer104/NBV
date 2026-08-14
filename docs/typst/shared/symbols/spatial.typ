// Candidate-relative pose, relation, and directional-history descriptors.
#let spatial = (
  // Reference pose for candidate-relative descriptors.
  ref_pose: $r_t$,
  // Relative transform from the reference pose to candidate i.
  ref_candidate_transform: $bold(T)_(r_t,i)^"rel"$,
  // Continuous rotation representation used for neural pose features.
  pose_6d: $bold(R)^"6D"$,
  // Relative/local candidate pose descriptor.
  candidate_pose_feat: $bold(h)_(t,i)^"pose"$,
  // Candidate-target relation descriptor.
  candidate_target_rel_feat: $bold(h)_(t,e|i)^"rel"$,
  // Query-local relative positional embedding for attention-style modules.
  relation_rpe: $bold(e)_(a|i)^"rel"$,
  // Candidate-local relative displacement vector.
  local_delta_pos: $bold(delta)_(a|i)^"p"$,
  // Candidate-local relative rotation descriptor.
  local_delta_rot: $bold(delta)_(a|i)^"R"$,
  // Optical-axis or bearing alignment from candidate to target.
  target_bearing: $cos theta_(t,e,i)^"opt"$,
  // Directional observation history on S^2.
  dir_unit: $bold(d)$,
  // Learned summary of directional observation history.
  dir_memory: $bold(h)^"dir"$,
  // Directional moment matrix accumulated from observation history.
  dir_moment: $bold(M)^"dir"$,
  // Spherical-harmonic basis values through degree L.
  sh_basis: $bold(Y)_L$,
)
