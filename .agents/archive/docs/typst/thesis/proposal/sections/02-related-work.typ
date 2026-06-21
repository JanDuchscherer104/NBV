#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "_style.typ": *

= Related Work and Positioning

The literature is used here to assign roles, not to broaden the thesis claim.
Older active perception motivates action-conditioned sensing; VIN-NBV supplies
the quality-driven candidate-ranking precedent; Project Aria, #gls("aria-synthetic-environments"), and EFM3D
motivate the logged egocentric state; and offline value learning supplies
replay and overestimation controls for the finite candidate table.

#figure(
  table(
    columns: (1.05fr, 1.32fr, 1.48fr),
    table.header([*Role*], [*Relevant signal*], [*Adopt / defer*]),
    [Quality-driven #gls("next-best-view") @VIN-NBV-frahm2025],
    [Oracle #gls("relative-reconstruction-improvement") and ordinal one-step candidate ranking are the closest implemented precedent.],
    [Adopt point-mesh #RRI labels and a learned one-step target scorer; test whether one-step ranking is enough.],
    [Egocentric substrate @projectaria-engel2023 @ProjectAria-ASE-2025 @EFM3D-straub2024],
    [Logged streams and trajectory, semi-dense support, frozen EVL/EFM evidence, and observed/predicted OBBs form the actor-visible state.],
    [Use observed/predicted target descriptors as actor input; keep GT geometry and crops for labels and evaluation.],
    [Greedy sensing and finite candidates @KrauseSensorPlacement2008 @AdaptiveSubmodularity-golovin2011],
    [When utility has diminishing returns, greedy selection can be strong; deeper search must earn its cost empirically.],
    [Measure oracle-lookahead headroom before claiming a learnable non-myopic advantage.],
    [Continuous and radiance-field #gls("next-best-view", first: false) @Hestia-lu2026 @ObjectCentricNBV-jeong2026],
    [Continuous policies, target-then-pose hierarchies, and uncertainty/semantic utility channels are useful comparisons.],
    [Use as follow-up design pressure; do not replace target #RRI with coverage or uncertainty rewards.],
    [Finite-action value learning #cite(label("DBLP:journals/corr/MnihKSGAWR13")) @DoubleDQN-vanHasselt2015 @Transformer-vaswani2017],
    [Replay, masked Bellman targets, overestimation control, and candidate-token modeling shape #symb.rl.qh.],
    [Train masked fitted Double-Q first; keep IQL, sequence decoding, and continuous actor-critic variants as later ablations.],
  ),
  caption: [Source-backed literature roles for the proposal scope.],
) <tab:proposal-source-positioning>

The resulting lineage is deliberately narrow:

$ cal(U)_"cov/unc" -> hat(r)_t^e (i) -> #symb.entity.target_reward -> #symb.entity.return_h -> #symb.rl.qh_theta. $

Coverage and uncertainty remain diagnostics, not the thesis utility. GT meshes
and GT target boxes remain oracle assets, not V1 actor inputs. Offline and
continuous RL references become meaningful only after candidate support, masks,
and oracle re-evaluation are trustworthy.

#figure(
  align(center, image(
    "../../figures/proposal_system_flow.png",
    width: 96%,
  )),
  caption: [Evidence chain from actor-visible state and target descriptor to masked candidates, target #RRI, lookahead headroom, and the #symb.rl.qh model. Dashed paths are follow-up work.],
) <fig:proposal-system-flow>
