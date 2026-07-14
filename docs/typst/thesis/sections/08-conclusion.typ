#import "../../shared/macros.typ": *
#import "../draft_markers.typ": *

= Conclusion

The expected final contribution is a reproducible target-aware finite-candidate view-selection study, not a broad claim that continuous reinforcement learning has been solved for egocentric reconstruction. The thesis tests a single planning hypothesis: after oracle target-task sampling and target-specific supervision are defined, finite-candidate oracle lookahead should expose whether non-myopic target-specific @relative-reconstruction-improvement:short headroom exists, and a learned finite-horizon value model should recover part of that headroom under matched oracle re-evaluation.

The scope limit is central to the conclusion. The thesis does not claim full continuous-control @next-best-view:short, online RL, real-device deployment, or replacement of target-specific point-mesh @relative-reconstruction-improvement:short by coverage, uncertainty, or semantic proxy objectives. Online discrete interaction, continuous target-then-pose policies, simulator-backed actor-critic, SceneScript, VLM planning, sparse/point backbones, and 3DGS control are escalation studies; they enter only if they preserve the finite-candidate target-specific @relative-reconstruction-improvement:short comparison.

The conclusion follows a fixed decision matrix. Positive and stable headroom together with learned recovery supports a scoped learnable non-myopic-planning claim for the evaluated regime. Negligible headroom supports a setup-specific negative result, not a universal myopia claim. An invalid or unstable oracle metric prevents downstream planning claims and restricts the thesis contribution to oracle validation. If valid headroom exists but #symb.rl.qh does not recover it, the result is a learned-control failure; target observability, candidate support, rollout coverage, reward definition, and model capacity remain competing explanations unless the sensitivity analysis discriminates among them.

#research_todo(
  [Rewrite the conclusion after final evidence is known. Preserve the conditional success/failure structure rather than forcing a positive planning claim.],
  source: [proposal risk control; advisor handout],
  gate: [final writing freeze],
)
