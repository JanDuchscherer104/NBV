// Learned tokens and assembled rows consumed by the candidate value model.
#let model = (
  // Learned selected-target token from root-relative pose and metric extents.
  target_token: $bold(h)_e^"tgt"$,
  // Candidate-local physical token shared by feasibility and conditional value.
  candidate_physical_token: $bold(h)_(t,i)^"phys"$,
  // Candidate-local conditional-value query consumed by A0/A1 fusion.
  candidate_row: $bold(x)_(t,i)$,
  // Selected pose j encoded from the current camera at decision state t.
  history_pose_feature: $bold(p)_(t,j)^"hist"$,
  // Relative age of selected pose j at decision state t.
  history_relative_age: $a_(t,j)^"hist"$,
  // Fixed-width causal selected-pose history token.
  history_token: $bold(h)_t^"hist"$,
)
