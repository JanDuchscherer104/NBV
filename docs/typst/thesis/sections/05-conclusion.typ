#import "../../shared/macros.typ": *
#import "../draft_markers.typ": *

= Conclusion

The expected final contribution is a reproducible target-aware finite-candidate view-selection study, not a broad claim that continuous reinforcement learning has been solved for egocentric reconstruction. The thesis tests a single planning hypothesis: after oracle target-task sampling and target-specific supervision are defined, finite-candidate oracle lookahead should expose whether non-myopic target-specific @relative-reconstruction-improvement:short headroom exists, and a learned finite-horizon value model should recover part of that headroom under matched oracle re-evaluation.

The scope limit is central to the conclusion. The thesis does not claim full continuous-control @next-best-view:short, online RL, real-device deployment, or replacement of target-specific point-mesh @relative-reconstruction-improvement:short by coverage, uncertainty, or semantic proxy objectives. Online discrete interaction, continuous target-then-pose policies, simulator-backed actor-critic, SceneScript, VLM planning, sparse/point backbones, and 3DGS control are escalation studies; they enter only if they preserve the finite-candidate target-specific @relative-reconstruction-improvement:short comparison.

If #symb.entity.lookahead_headroom is positive and #symb.rl.qh recovers part of it under oracle-rescored selected trajectories, the thesis supports the claim that target-conditioned finite-candidate planning contains learnable non-myopic structure in the evaluated @aria-synthetic-environments:short/@egocentric-voxel-lifting:short regime. If headroom is near zero, the thesis instead reports a negative planning result for the evaluated candidate generator, horizon, target set, and split. If headroom exists but #symb.rl.qh does not recover it, the failure analysis separates target observability, candidate support, rollout coverage, reward definition, and model-capacity explanations.

#research_todo(
  [Rewrite the conclusion after final evidence is known. Preserve the conditional success/failure structure rather than forcing a positive planning claim.],
  source: [proposal risk control; advisor handout],
  gate: [final writing freeze],
)
