# Architect Review

Verdict: APPROVE

Confidence: high

## Architectural assessment

- The handoff stays inside the bounded cleanup budget: the mission forbids
  target descriptors, target-conditioned scoring, Q_H implementation,
  scene-memory packages, and broad `data_handling`/app rewrites, and the
  report/ralplan repeat that scope limit instead of expanding it.
- The main recommended seam is grounded in current package ownership:
  `pose_generation` still exports the counterfactual contracts, while
  `rollouts` already owns replay/store schemas and says those replay schemas
  should not be exported from `pose_generation`.
- The report does not imply new thesis functionality is already implemented;
  it explicitly fences off target-conditioned scoring and Q_H, and the ralplan
  exit criteria repeats that no package code should claim those are
  implemented.
- The "do not delete RL in the same pass" call is correct because
  `aria_nbv.rl` is still public and test-backed, so it is not a trivial dead
  leaf. The app-panel extraction is also correctly deferred because the panel
  is large and mixed.
- The VIN branch-drift handling is credible: the PR #15 worktree already uses
  `scene_myopic`, `target_myopic`, and `target_finite_horizon`, while the
  divergent worktree still uses `multi_step`; the current checkout keeps
  `VinV3ForwardDiagnostics` leaf-local and the active public scorer is still
  `VinModelV3`.

## Required changes before implementation

None.

## Strongest antithesis

The only meaningful risk is wording drift, not scope drift. The report's
"Recommended shape" mentions "target-RRI scoring," and `rollouts.zarr` uses
`Q_H` terminology for the derived replay view, which could be misread later as
a commitment to implement a target-conditioned scoring model in this cleanup.
But the same report and ralplan explicitly say not to implement target
descriptors, target-conditioned scoring, or a real Q_H model, so that ambiguity
is not blocking for the handoff.

## Synthesis

Keep Option A as the default implementation slice, use the PR #15 VIN names
only where branch churn already exists, and defer RL quarantine plus broad
app-helper reshaping to separate cleanup passes. That preserves the narrow
mergeability goal while giving the next implementation lane a clean package
seam instead of a feature expansion.

## Follow-up applied

The report wording was tightened from "target-RRI scoring" to "target-RRI
replay evidence artifacts" before critic review.
