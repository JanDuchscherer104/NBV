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
)
