// Learned tokens and assembled rows consumed by the candidate value model.
#let model = (
  // Learned selected-target token consumed by the value model.
  target_token: $bold(h)_e^"tgt"$,
  // Per-candidate model row assembled from typed descriptors.
  candidate_row: $bold(x)_(t,i)$,
  // Candidate geometry/support token.
  candidate_geometry_token: $bold(h)_(t,i)^"geom"$,
  // Candidate validity/reason embedding.
  candidate_validity_token: $bold(h)_(t,i)^"valid"$,
  // Candidate source/provenance embedding kept separate from geometry.
  candidate_provenance_token: $bold(h)_(t,i)^"prov"$,
  // Selected pose j encoded from the current camera at decision state t.
  history_pose_feature: $bold(p)_(t,j)^"hist"$,
  // Relative age of selected pose j at decision state t.
  history_relative_age: $a_(t,j)^"hist"$,
  // Fixed-width causal selected-pose history token.
  history_token: $bold(h)_t^"hist"$,
)
