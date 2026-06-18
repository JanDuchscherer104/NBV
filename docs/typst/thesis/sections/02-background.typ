#import "../../shared/macros.typ": *
#import "../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

= Background

The project combines @aria-synthetic-environments scene assets, @egocentric-foundation-model-3d features, oracle @relative-reconstruction-improvement labels, and VIN-style candidate scoring. @aria-synthetic-environments:short supplies Aria-like synthetic sensor trajectories, aligned semi-dense maps, and @ground-truth:short annotations at indoor-scene scale @ProjectAria-ASE-2025. @egocentric-voxel-lifting:short supplies frozen local voxel evidence, lifted DINO-derived features, and object-support signals for target-task descriptors and diagnostics @EFM3D-straub2024 @EVL-Doc-2025. In the current thesis scope, @egocentric-voxel-lifting:short is local target/support evidence rather than a full long-horizon scene memory; broad scene context comes from semi-dense and fused geometry, with point-attached feature banks treated as planned representation ablations until a persisted cache and training reader exist.

#include "02-01-related-work.typ"

#include "02-02-geometric-learning.typ"

The literature is used here to assign roles, not to broaden the thesis claim. Older active perception motivates action-conditioned sensing; VIN-NBV supplies the quality-driven candidate-ranking precedent; Project Aria, @aria-synthetic-environments, and @egocentric-foundation-model-3d:short motivate the logged egocentric state; and offline value learning supplies replay and overestimation controls for the finite candidate table.

#figure(
  table(
    columns: (1.05fr, 1.32fr, 1.48fr),
    toprule(),
    table.header([*Role*], [*Relevant signal*], [*Adopt / defer*]),
    midrule(),
    [Quality-driven @next-best-view @VIN-NBV-frahm2025],
    [Oracle @relative-reconstruction-improvement and ordinal one-step candidate ranking are the closest implemented precedent.],
    [Adopt point-mesh @relative-reconstruction-improvement:short labels and a learned one-step target scorer; test whether one-step ranking is enough.],
    [Egocentric substrate @projectaria-engel2023 @ProjectAria-ASE-2025 @EFM3D-straub2024],
    [Logged streams and trajectory, semi-dense support, frozen @egocentric-voxel-lifting:short/@egocentric-foundation-model-3d:short evidence, and observed/predicted OBBs form the actor-visible state.],
    [Use observed/predicted target descriptors as actor input; keep @ground-truth:short geometry and crops for labels and evaluation.],
    [Greedy sensing and finite candidates @KrauseSensorPlacement2008 @AdaptiveSubmodularity-golovin2011],
    [Diminishing-returns intuition; oracle-lookahead headroom as a required test.],
    [Measure oracle-lookahead headroom before claiming a learnable non-myopic advantage.],
    [CORAL, set models, QCNet, Double-Q @CORAL-cao2019 @SetTransformer-lee2019 @zhou2023query @DoubleDQN-vanHasselt2015],
    [Ordinal target scorer, MLP/DeepSets/Set Transformer candidate controls, query-centric relative-encoding ablation, masked fitted backups.],
    [QCNet trajectory decoding, motion-forecasting losses, online streaming claims, IQL/CQL/BCQ, and distributional heads remain outside the initial value result.],
    [Continuous and radiance-field @next-best-view:short @Hestia-lu2026 @ObjectCentricNBV-jeong2026],
    [Continuous policies, target-then-pose hierarchies, target/object-focused utility, and uncertainty/semantic utility channels are useful comparisons.],
    [Use as follow-up design pressure; do not replace target @relative-reconstruction-improvement:short with coverage, uncertainty, or semantic proxy rewards.],
    bottomrule(),
  ),
  caption: [Source-backed literature roles for the thesis scope.],
) <tab:thesis-source-positioning>

The resulting lineage is deliberately narrow:

$ cal(U)_"cov/unc" -> hat(r)_t^e (i) -> #symb.entity.target_reward -> #symb.entity.return_h -> #symb.rl.qh_theta. $

Coverage and uncertainty remain diagnostics, not the thesis utility. @ground-truth:short meshes and @ground-truth:short target boxes remain oracle assets for target-task sampling, labels, and evaluation; they are not learned actor inputs unless a named privileged ablation says so. Offline and continuous RL references become meaningful only after candidate support, masks, and oracle re-evaluation are trustworthy.

#figure(
  align(center, image(
    "../figures/proposal_system_flow.png",
    width: 96%,
  )),
  caption: [Evidence chain from actor-visible state and target descriptor to masked candidates, target @relative-reconstruction-improvement:short, lookahead headroom, and the #symb.rl.qh model. Dashed paths are follow-up work.],
) <fig:thesis-system-flow>

Hestia informs a deferred hierarchy in which a target or look-at point is proposed before choosing a feasible pose conditioned on it @Hestia-lu2026. In ARIA-NBV this factorization keeps target-specific @relative-reconstruction-improvement:short as supervision/evaluation and treats feasibility projection or masks as constraints:

$
  #eqs.rl.target_pose_factorization
$

#research_todo(
  [Decide which bridge literature belongs in the final thesis background versus the discussion/future-work chapter.],
  source: [proposal related work; advisor handout],
  gate: [final literature pass],
)
