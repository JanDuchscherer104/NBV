// Candidate-relative pose, relation, and directional-history descriptors.
#let spatial = (
  // Proposed camera frame carried by candidate action row i at decision step t.
  candidate_camera_frame: $c_(t,i)^"cand"$,
  // Factual camera frame on the realised trajectory at decision step t.
  trajectory_camera_frame: $c_t^"traj"$,
  // Reserved reference pose; no direct authored use in the 2026-08-14 audit.
  ref_pose: $r_t$,
  // Relative transform from the reference pose to candidate i.
  ref_candidate_transform: $bold(T)_(r_t,i)^"rel"$,
  // Canonical 6D rotation form; `vin.pose_6d` is an unused duplicate.
  pose_6d: $bold(R)^"6D"$,
  // Canonical candidate pose descriptor; `vin.candidate_pose_feat` is an unused duplicate.
  candidate_pose_feat: $bold(h)_(t,i)^"pose"$,
  // Candidate-target relation descriptor.
  candidate_target_rel_feat: $bold(h)_(t,e|i)^"rel"$,
  // Query-local relative positional embedding for attention-style modules.
  relation_rpe: $bold(e)_(a|i)^"rel"$,
  // Candidate-local relative displacement vector.
  local_delta_pos: $bold(delta)_(a|i)^"p"$,
  // Candidate-local relative rotation descriptor.
  local_delta_rot: $bold(delta)_(a|i)^"R"$,
  // Candidate optical-axis alignment with the target direction.
  target_alignment: $cos theta_(t,e,i)^"opt"$,
  // Canonical unit direction; duplicated by unused `oracle.dir` and `vin.dir_unit`.
  dir_unit: $bold(d)$,
  // Geometric-mean proxy scale from the selected target OBB semi-axis lengths.
  target_obb_scale: $r_e$,
  // Unit selected-camera displacement expressed in target-object coordinates.
  target_frame_motion_direction: $hat(bold(delta))_(j,t)^e$,
  // Unit selected-camera optical axis expressed in target-object coordinates.
  target_frame_view_direction: $hat(bold(v))_(j,t)^e$,
  // Calibrated front-facing footprint on the target-centred proxy sphere.
  target_frame_frustum: $cal(F)_(j,t)^e$,
  // Approximate fraction of the target proxy surface supported by one frustum.
  target_frame_frustum_fraction: $kappa_(j,t)^e$,
  // Intrinsic calibrated pinhole field-of-view solid angle.
  frustum_solid_angle: $Omega_(j,t)^"FOV"$,
  // Canonical directional memory; VIN's unused alias changes this superscript to a subscript.
  dir_memory: $bold(h)^"dir"$,
  // Canonical directional moment; VIN's unused alias changes this superscript to a subscript.
  dir_moment: $bold(M)^"dir"$,
  // Canonical spherical-harmonic basis; `vin.sh_basis` is an unused duplicate.
  sh_basis: $bold(Y)_L$,
)
